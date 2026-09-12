# 라이브러리 동기화: 콘티에서 만든 곡이 곡·편곡으로 서버에 쌓이고, 다른 기기·팀원이 받는다
import os, sys, time
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
tag = str(int(time.time()))[-6:]
H = {'x-conti': '1'}
L = ('ll' + tag, 'secret1', '하은')

def fail(msg): print('FAIL:', msg); sys.exit(1)

def login(pg, u, mode='login'):
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=8000)
    if mode == 'signup':
        pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.fill('#lgName', u[2])
    pg.fill('#lgUser', u[0]); pg.fill('#lgPass', u[1]); pg.click('[data-act="lg-submit"]')

def run():
    with sync_playwright() as p:
        b = p.chromium.launch(); errs = []
        cA = b.new_context(viewport={'width': 1240, 'height': 900}); pa = cA.new_page()
        pa.on('pageerror', lambda e: errs.append('A:' + str(e))); pa.on('dialog', lambda d: d.accept())
        login(pa, L, 'signup')
        pa.wait_for_selector('#gtTeam', timeout=8000); pa.fill('#gtTeam', '라이브러리팀'); pa.click('[data-act="team-create"]'); pa.wait_for_selector('.shell[data-page]', timeout=8000)
        team = pa.evaluate('CONTI.S.team.id')
        link = pa.evaluate("location.origin+location.pathname+'#/join/'+CONTI.S.team.invite")

        # ---- 곡을 만들면 라이브러리에 쌓이고 서버로 올라감 ----
        pa.click('[data-act="new-svc"]'); pa.wait_for_selector('[data-f="svc.name"]'); pa.fill('[data-f="svc.name"]', '라이브러리 예배')
        pa.click('[data-act="add-item"]'); pa.wait_for_selector('[data-f="item.title"]')
        pa.fill('[data-f="item.title"]', '주 은혜임을'); pa.fill('[data-f="item.key"]', 'G'); pa.fill('[data-f="item.form"]', '1414 – AAB')
        pa.set_input_files('#pieceFile', [SHEET])
        pa.wait_for_function("(()=>{const p=(CONTI.S.services[0].items[0].pieces||[])[0];return p&&p.ocr&&p.ocr!=='pending'})()", timeout=60000)
        pa.wait_for_timeout(5000)   # 라이브러리 push 디바운스(3초) + 업로드
        srv = cA.request.get(URL + 'api/songs?team=' + team).json()
        if not srv['songs']: fail('서버에 곡이 없음')
        s0 = srv['songs'][0]
        if s0['title'] != '주 은혜임을': fail('제목이 다름: %s' % s0['title'])
        a0 = (s0.get('arrangements') or [{}])[0]
        if not (a0.get('pieces') or []): fail('악보 조각이 편곡에 안 올라감')
        if a0.get('form') != '1414 – AAB': fail('송폼이 편곡에 안 들어감: %r' % a0.get('form'))
        if not srv['blobs']: fail('악보 파일 URL 이 없음')
        print('push ok:', s0['title'], '· 조각', len(a0['pieces']))

        # ---- 다른 기기(같은 인도자)에서 받아짐 ----
        cB = b.new_context(viewport={'width': 1240, 'height': 900}); pb = cB.new_page()
        pb.on('pageerror', lambda e: errs.append('B:' + str(e))); pb.on('dialog', lambda d: d.accept())
        login(pb, L)
        pb.wait_for_selector('.shell[data-page]', timeout=10000); pb.wait_for_timeout(4000)
        pb.evaluate("CONTI.pullSongs(true)"); pb.wait_for_timeout(2500)
        got = pb.evaluate("CONTI.S.songs.map(s=>s.title)")
        if '주 은혜임을' not in got: fail('다른 기기에 라이브러리가 안 내려옴: %s' % got)
        # 악보 파일도 같이 (썸네일이 뜨는지)
        pb.click('.navi[data-act="nav-lib"]'); pb.wait_for_selector('.songrow', timeout=10000); pb.wait_for_timeout(1200)
        thumb = pb.evaluate("!!document.querySelector('.songrow .sthumb').style.backgroundImage")
        if not thumb: fail('목록에 악보 썸네일이 안 뜸')
        print('pull ok:', got)

        # ---- 멤버도 라이브러리를 본다(읽기) ----
        cM = b.new_context(viewport={'width': 1240, 'height': 900}); pm = cM.new_page()
        pm.on('pageerror', lambda e: errs.append('M:' + str(e))); pm.on('dialog', lambda d: d.accept())
        pm.goto(link); pm.wait_for_selector('#lgUser', timeout=8000)
        pm.click('[data-act="lg-mode"][data-m="signup"]'); pm.wait_for_selector('#lgName')
        pm.fill('#lgName', '민수'); pm.fill('#lgUser', 'lm' + tag); pm.fill('#lgPass', 'secret1'); pm.click('[data-act="lg-submit"]')
        pm.wait_for_selector('#jnName', timeout=8000); pm.click('[data-act="team-join"]'); pm.wait_for_selector('.shell[data-page]', timeout=8000)
        pm.wait_for_timeout(3500)
        pm.evaluate("CONTI.pullSongs(true)"); pm.wait_for_timeout(2000)
        mlib = pm.evaluate("CONTI.S.songs.map(s=>s.title)")
        if '주 은혜임을' not in mlib: fail('멤버가 라이브러리를 못 받음: %s' % mlib)
        # 멤버는 못 고침
        up = cM.request.post(URL + 'api/songs', headers=H, data={'teamId': team, 'title': '멤버곡'})
        if up.status != 403: fail('멤버가 곡을 만들 수 있음: %s' % up.status)
        # 멤버 화면에는 편집 버튼이 없다
        pm.goto(URL + '#/library'); pm.wait_for_selector('.songrow', timeout=10000); pm.wait_for_timeout(600)
        if pm.locator('[data-act="lib-new"]').count(): fail('멤버에게 새 곡 버튼이 보임')
        print('member read-only ok')

        # ---- B 기기에서 편곡을 고치면 A 기기로 전파 ----
        arr = pb.evaluate("CONTI.S.songs.find(x=>x.title==='주 은혜임을').arrangements[0].id")
        cB.request.patch(URL + 'api/arrangements/' + arr, headers=H, data={'teamId': team, 'songNote': '밝게'})
        pa.evaluate("CONTI.S.songsAt='';CONTI.pullSongs(true)"); pa.wait_for_timeout(2500)
        note = pa.evaluate("((CONTI.S.songs.find(x=>x.title==='주 은혜임을')||{}).arrangements||[{}])[0].songNote")
        if note != '밝게': fail('수정이 전파 안 됨: %s' % note)
        print('edit propagation ok')

        # ---- 삭제도 전파 ----
        sid = pa.evaluate("CONTI.S.songs.find(x=>x.title==='주 은혜임을').id")
        pa.goto(URL + '#/library/' + sid); pa.wait_for_selector('.acard', timeout=10000); pa.wait_for_timeout(600)
        pa.click('[data-act="song-more"]'); pa.wait_for_selector('#smDel2', timeout=5000)
        pa.click('#smDel2'); pa.wait_for_timeout(2500)
        left = cA.request.get(URL + 'api/songs?team=' + team).json()['songs']
        if [x for x in left if x['title'] == '주 은혜임을']: fail('서버에서 안 지워짐')
        pb.evaluate("CONTI.S.songsAt='';CONTI.pullSongs(true)"); pb.wait_for_timeout(2500)
        if pb.evaluate("CONTI.S.songs.filter(x=>x.title==='주 은혜임을').length"): fail('다른 기기에서 삭제가 반영 안 됨')
        print('delete propagation ok')

        print('errors:', errs)
        if errs: fail('page errors')
        b.close()
    print('LIBRARY TEST OK')

if __name__ == '__main__':
    run()
