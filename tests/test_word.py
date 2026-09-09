# §4.3 에디터 말씀 카드 · §4.4 콘티 보기 말씀 줄·곡별 이유 · §4.5 예배 노트 바텀시트
import os, sys, time
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
tag = str(int(time.time()))[-6:]
L = ('wl' + tag, 'secret1', '하은')
M = ('wm' + tag, 'secret1', '민수')

def fail(msg): print('FAIL:', msg); sys.exit(1)

def run():
    with sync_playwright() as p:
        b = p.chromium.launch(); errs = []
        cL = b.new_context(viewport={'width': 1240, 'height': 900}); pl = cL.new_page()
        pl.on('pageerror', lambda e: errs.append('L:' + str(e))); pl.on('dialog', lambda d: d.accept())
        pl.goto(URL); pl.wait_for_selector('#lgUser', timeout=8000)
        pl.click('[data-act="lg-mode"][data-m="signup"]'); pl.wait_for_selector('#lgName')
        pl.fill('#lgName', L[2]); pl.fill('#lgUser', L[0]); pl.fill('#lgPass', L[1]); pl.click('[data-act="lg-submit"]')
        pl.wait_for_selector('#gtTeam', timeout=8000); pl.fill('#gtTeam', '말씀팀'); pl.click('[data-act="team-create"]'); pl.wait_for_selector('.hd [data-act="team"]', timeout=8000)
        team = pl.evaluate('CONTI.S.team.id')
        pl.click('.hd [data-act="team"]'); pl.wait_for_selector('#tmLink'); link = pl.locator('#tmLink').inner_text().strip(); pl.keyboard.press('Escape')

        cM = b.new_context(viewport={'width': 1240, 'height': 900}); pm = cM.new_page()
        pm.on('pageerror', lambda e: errs.append('M:' + str(e))); pm.on('dialog', lambda d: d.accept())
        pm.goto(link); pm.wait_for_selector('#lgUser', timeout=8000)
        pm.click('[data-act="lg-mode"][data-m="signup"]'); pm.wait_for_selector('#lgName'); pm.fill('#lgName', M[2]); pm.fill('#lgUser', M[0]); pm.fill('#lgPass', M[1]); pm.click('[data-act="lg-submit"]')
        pm.wait_for_selector('#jnName', timeout=8000); pm.click('[data-act="team-join"]'); pm.wait_for_selector('.hd [data-act="team"]', timeout=8000)

        # ---- 인도자: 말씀 입력(자동 저장) + 곡별 이유 + 인도자의 글 ----
        pl.click('[data-act="new-svc"]'); pl.wait_for_selector('[data-f="svc.name"]'); pl.fill('[data-f="svc.name"]', '말씀 예배')
        pl.wait_for_selector('[data-w="passage"]', timeout=5000)
        pl.fill('[data-w="passage"]', '시편 103:1-5')
        pl.fill('[data-w="title"]', '잊지 말아야 할 은혜')
        pl.fill('[data-w="line"]', '받은 은혜를 세어보는 예배')
        pl.fill('[data-f="svc.message"]', '이번 예배는 "돌아옴"으로 잡았어요.')
        pl.wait_for_function("document.querySelector('#wSaved') && document.querySelector('#wSaved').textContent==='저장됨'", timeout=10000)
        svc_id = pl.evaluate('CONTI.S.services[0].id')
        w = cL.request.get(URL + 'api/services/%s?team=%s&draft=1' % (svc_id, team))
        pl.click('[data-act="add-item"]'); pl.wait_for_selector('[data-f="item.title"]'); pl.fill('[data-f="item.title"]', '예수로 나의 구주 삼고')
        pl.fill('[data-f="item.reason"]', '“은혜를 세어보라”는 구절과 이어지는 곡')
        pl.wait_for_timeout(500)
        print('word saved:', pl.evaluate('JSON.stringify(CONTI.S.services[0].word)')[:120])

        pl.click('[data-act="publish"]'); pl.wait_for_selector('#pubOnly'); pl.click('#pubOnly'); pl.wait_for_timeout(5000)
        rev1 = pl.evaluate('CONTI.S.services[0].messageRev')
        if not rev1: fail('발행 시 noteRev 가 오르지 않음: %s' % rev1)

        # ---- 멤버: 콘티 열면 바텀시트 자동 + 말씀 블록 + 곡 이유 ----
        pm.goto(URL + '#/home'); pm.reload(); pm.wait_for_selector('.svcrow', timeout=15000)
        pm.goto(URL + '#/view/' + svc_id); pm.wait_for_selector('#modal .msgbody', timeout=15000)
        sheet = pm.locator('#modal').inner_text()
        for need in ['인도자의 글', '시편 103:1-5', '잊지 말아야 할 은혜', '받은 은혜를 세어보는 예배', '읽었어요', '다시 보려면']:
            if need not in sheet: fail('바텀시트에 "%s" 없음:\n%s' % (need, sheet[:400]))
        pm.click('#msgOk'); pm.wait_for_timeout(1200)
        if pm.locator('#modal .msgbody').count(): fail('읽었어요 후에도 시트가 남음')
        if pm.evaluate('CONTI.S.readRev[%r]' % svc_id) != rev1: fail('readRev 기록 안 됨')
        rr = cM.request.get(URL + 'api/services/%s?team=%s' % (svc_id, team)).json()
        if rr.get('readRev') != rev1: fail('서버에 readRev 저장 안 됨: %s' % rr.get('readRev'))
        if not rr.get('word') or rr['word']['passage'] != '시편 103:1-5': fail('멤버에게 말씀이 안 내려감: %s' % rr.get('word'))
        # 콘티 보기 본문: 말씀 줄 + 곡 이유 줄
        body = pm.locator('#app').inner_text()
        if '시편 103:1-5 · 잊지 말아야 할 은혜' not in body: fail('콘티 보기 말씀 줄 없음')
        if '은혜를 세어보라' not in body: fail('곡 카드에 이유 줄 없음')
        # 아이콘은 남고 점은 사라짐
        if not pm.locator('[data-act="msg"]').count(): fail('예배 노트 아이콘이 사라짐')
        if 'dot' in (pm.locator('[data-act="msg"]').first.get_attribute('class') or ''): fail('읽은 뒤에도 빨간 점이 남음')
        print('bottom sheet ok')

        # ---- 말씀만 바꿔 재발행 → 점 + 다시 한 번 ----
        pl.goto(URL + '#/edit/' + svc_id); pl.wait_for_selector('[data-w="line"]', timeout=10000)
        pl.fill('[data-w="line"]', '은혜를 세어보는 예배 (수정)')
        pl.wait_for_function("CONTI.S.services[0].word && CONTI.S.services[0].word.line.includes('수정')", timeout=10000)
        pl.wait_for_timeout(1500)
        pl.click('[data-act="publish"]'); pl.wait_for_selector('#pubOnly'); pl.click('#pubOnly'); pl.wait_for_timeout(5000)
        rev2 = pl.evaluate('CONTI.S.services[0].messageRev')
        if rev2 <= rev1: fail('말씀만 바뀌었는데 noteRev 가 안 오름: %s → %s' % (rev1, rev2))
        pm.goto(URL + '#/home'); pm.reload(); pm.wait_for_selector('.hd', timeout=10000); pm.wait_for_timeout(2500)
        pm.goto(URL + '#/view/' + svc_id); pm.wait_for_selector('#modal .wordblock', timeout=15000); pm.wait_for_timeout(500)
        if '수정' not in pm.locator('#modal').inner_text(): fail('재발행 후 시트가 다시 안 뜸: ' + pm.locator('#modal').inner_text()[:200])
        print('re-publish sheet ok (rev %s → %s)' % (rev1, rev2))

        # ---- 목회자 저장 → word.received 알림(인도자) ----
        me_m = pm.evaluate('CONTI.NET.user.id')
        r = cL.request.patch(URL + 'api/teams/%s/members/%s' % (team, me_m), headers={'x-conti': '1'}, data={'role': 'pastor'})
        if r.status != 200: print('WARN: pastor 역할 부여 실패(아직 미지원):', r.text()[:120])
        else:
            rw = cM.request.put(URL + 'api/services/%s/word' % svc_id, headers={'x-conti': '1'}, data={'teamId': team, 'word': {'passage': '요한복음 15:5', 'title': '가지', 'line': '붙어 있으라', 'memo': '설교 마지막에 인용', 'memoPublic': False}})
            if rw.status != 200: fail('목회자 말씀 저장 실패: ' + rw.text()[:150])
            ns = [n for n in cL.request.get(URL + 'api/notifications?team=' + team).json()['notifications'] if n['type'] == 'word.received']
            if not ns: fail('word.received 알림 없음')
            print('word.received ok:', ns[0]['title'])

        print('errors:', errs)
        if errs: fail('page errors')
        b.close()
    print('WORD TEST OK')

if __name__ == '__main__':
    run()
