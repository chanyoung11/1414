# 발행본 · 파일 · 메모 서버 동기화 (온라인 모드)
# 준비: npm run dev (8766) + DATABASE_URL/AUTH_SECRET/BLOB_READ_WRITE_TOKEN
import os, sys, time
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
tag = str(int(time.time()))[-6:]
LEADER = ('lead' + tag, 'secret1', '하은')
MEMBER = ('mem' + tag, 'secret1', '민수')

def fail(msg):
    print('FAIL:', msg); sys.exit(1)

def signup(pg, user):
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=8000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
    pg.fill('#lgName', user[2]); pg.fill('#lgUser', user[0]); pg.fill('#lgPass', user[1]); pg.click('[data-act="lg-submit"]')

def run():
    with sync_playwright() as p:
        b = p.chromium.launch(); errs = []
        # ---- 인도자: 팀 → 예배 → 곡 + 악보 → 발행 ----
        c1 = b.new_context(viewport={'width': 1180, 'height': 820}); pg = c1.new_page(); pg.on('pageerror', lambda e: errs.append('L:' + str(e)))
        signup(pg, LEADER); pg.wait_for_selector('#gtTeam', timeout=8000)
        pg.fill('#gtTeam', '동기화팀'); pg.click('[data-act="team-create"]'); pg.wait_for_selector('.hd [data-act="team"]', timeout=8000)
        pg.click('.hd [data-act="team"]'); pg.wait_for_selector('#tmLink'); link = pg.locator('#tmLink').inner_text().strip(); pg.keyboard.press('Escape')
        pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]')
        pg.fill('[data-f="svc.name"]', '동기화 예배'); pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]')
        pg.fill('[data-f="item.title"]', '우리 주 하나님'); pg.fill('[data-f="item.key"]', 'A'); pg.fill('[data-f="item.form"]', '1414 – AAB – Int(2)')
        pg.set_input_files('#pieceFile', [SHEET]); pg.wait_for_timeout(3000)
        pg.click('#sheet .slice', position={'x': 200, 'y': 160}); pg.wait_for_selector('#modal [data-l]', timeout=5000); pg.click('#modal [data-l]'); pg.wait_for_timeout(500)
        markers = pg.evaluate("CONTI.S.services[0].items[0].pieces[0].markers.length")
        if markers < 1: fail('marker not created')
        svc_id = pg.evaluate("CONTI.S.services[0].id")
        pg.click('[data-act="publish"]'); pg.wait_for_selector('#pubOnly'); kk = pg.locator('#kk').input_value()
        if '#/view/' + svc_id not in kk: fail('카톡 텍스트에 링크 없음: ' + kk)
        pg.click('#pubOnly'); pg.wait_for_timeout(6000)   # 파일 업로드 + 스냅샷
        r = c1.request.get(URL + 'api/services?team=' + pg.evaluate("CONTI.S.team.id"))
        if svc_id not in r.text(): fail('서버에 발행본 없음: ' + r.text())
        print('leader published', svc_id)

        # ---- 멤버: 초대 가입 → 홈에 자동으로 예배 → 보기에서 악보 → 연습에서 메모 ----
        c2 = b.new_context(viewport={'width': 430, 'height': 900}); pm = c2.new_page(); pm.on('pageerror', lambda e: errs.append('M:' + str(e)))
        pm.goto(link); pm.wait_for_selector('#lgUser', timeout=8000)
        pm.click('[data-act="lg-mode"][data-m="signup"]'); pm.wait_for_selector('#lgName'); pm.fill('#lgName', MEMBER[2]); pm.fill('#lgUser', MEMBER[0]); pm.fill('#lgPass', MEMBER[1]); pm.click('[data-act="lg-submit"]')
        pm.wait_for_selector('#jnName', timeout=8000); pm.click('#gtSess .q:has-text("드럼")'); pm.click('[data-act="team-join"]')
        pm.wait_for_selector('.hd [data-act="team"]', timeout=8000); pm.wait_for_selector('.svcrow', timeout=15000)
        if '동기화 예배' not in pm.locator('.svcrow').first.inner_text(): fail('멤버 홈에 발행본 없음')
        pm.goto(URL + '#/view/' + svc_id); pm.wait_for_selector('.thumb', timeout=15000)
        bg = pm.locator('.thumb').first.evaluate("el=>getComputedStyle(el).backgroundImage")
        if 'blob:' not in bg: fail('멤버 악보 썸네일이 blob이 아님: ' + bg)
        pm.goto(URL + '#/play/' + svc_id + '/0'); pm.wait_for_selector('#sheet [data-marker]', timeout=15000)
        pm.click('#sheet [data-marker]'); pm.wait_for_selector('#cText'); pm.fill('#cText', '드럼 필 주의'); pm.click('[data-sc="session"]'); pm.click('#cSave')
        saved = False
        for _ in range(16):
            pm.wait_for_timeout(500)
            if '드럼 필 주의' in c2.request.get(URL + 'api/notes?team=' + pm.evaluate("CONTI.S.team.id") + '&service=' + svc_id).text(): saved = True; break
        if not saved: fail('메모가 서버에 없음')
        # 기기 데이터를 지우고 다시 열어도 서버에서 메모가 내려온다
        pm.evaluate("indexedDB.deleteDatabase('conti-v1')"); pm.goto(URL + '#/home'); pm.reload(); pm.wait_for_selector('.svcrow', timeout=15000)
        pm.goto(URL + '#/play/' + svc_id + '/0'); pm.wait_for_selector('#sheet .m[data-note]', timeout=15000)
        if '드럼 필 주의' not in pm.locator('#sheet .m[data-note]').first.inner_text(): fail('재로그인 후 메모 없음')
        # 메모 칩 → 삭제 → 서버에서도 삭제
        pm.click('#sheet .m[data-note]'); pm.wait_for_selector('#nmDel'); pm.click('#nmDel')
        gone = False
        for _ in range(16):   # 저장 0.7초 뒤 전송 + 운영 지연 → 최대 8초 폴링
            pm.wait_for_timeout(500)
            if '드럼 필 주의' not in c2.request.get(URL + 'api/notes?team=' + pm.evaluate("CONTI.S.team.id") + '&service=' + svc_id).text(): gone = True; break
        if not gone: fail('삭제 후에도 서버에 메모가 남음')
        print('member sync ok')

        # ---- 인도자 v2 발행 → 멤버 새로고침으로 반영 ----
        pg.goto(URL + '#/edit/' + svc_id); pg.wait_for_selector('[data-f="item.title"]'); pg.fill('[data-f="item.title"]', '우리 주 하나님 (v2)'); pg.wait_for_timeout(400)
        pg.click('[data-act="publish"]'); pg.wait_for_selector('#pubOnly'); pg.click('#pubOnly'); pg.wait_for_timeout(4000)
        pm.goto(URL + '#/home'); pm.wait_for_selector('.hd'); pm.evaluate("CONTI.SYNC.pullServices().then(()=>CONTI.render())"); pm.wait_for_timeout(3000)
        if 'v2' not in pm.locator('.svcrow').first.inner_text(): fail('멤버가 v2를 못 받음: ' + pm.locator('.svcrow').first.inner_text())
        pm.goto(URL + '#/view/' + svc_id); pm.wait_for_timeout(1500)
        if '(v2)' not in pm.locator('#app').inner_text(): fail('멤버 보기에 v2 제목 없음')
        print('v2 ok; errors:', errs)
        if errs: fail('page errors')
        b.close()
    print('SYNC TEST OK')

if __name__ == '__main__':
    run()
