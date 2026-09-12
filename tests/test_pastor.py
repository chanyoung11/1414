# §4.2 목회자 말씀 탭 · §4.6 목회자 링크 페이지 · 알림 설정 · 계정 삭제
import os, sys, time, datetime
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
tag = str(int(time.time()))[-6:]
H = {'x-conti': '1'}

def fail(msg): print('FAIL:', msg); sys.exit(1)

def run():
    with sync_playwright() as p:
        b = p.chromium.launch(); errs = []
        cL = b.new_context(viewport={'width': 1300, 'height': 950}); pl = cL.new_page()
        pl.on('pageerror', lambda e: errs.append('L:' + str(e))); pl.on('dialog', lambda d: d.accept())
        pl.goto(URL); pl.wait_for_selector('#lgUser', timeout=8000)
        pl.click('[data-act="lg-mode"][data-m="signup"]'); pl.wait_for_selector('#lgName')
        pl.fill('#lgName', '하은'); pl.fill('#lgUser', 'pl' + tag); pl.fill('#lgPass', 'secret1'); pl.click('[data-act="lg-submit"]')
        pl.wait_for_selector('#gtTeam', timeout=8000); pl.fill('#gtTeam', '말씀탭팀'); pl.click('[data-act="team-create"]'); pl.wait_for_selector('.shell[data-page]', timeout=8000)
        team = pl.evaluate('CONTI.S.team.id')
        link = pl.evaluate("location.origin+location.pathname+'#/join/'+CONTI.S.team.invite")

        # 예배 하나 발행 + 앞으로의 사역 날짜 하나
        pl.click('[data-act="new-svc"]'); pl.wait_for_selector('[data-f="svc.name"]'); pl.fill('[data-f="svc.name"]', '말씀탭 예배')
        soon = (datetime.date.today() + datetime.timedelta(days=5)).isoformat()
        pl.fill('[data-f="svc.date"]', soon)
        pl.click('[data-act="add-item"]'); pl.wait_for_selector('[data-f="item.title"]'); pl.fill('[data-f="item.title"]', '곡'); pl.wait_for_timeout(400)
        svc_id = pl.evaluate('CONTI.S.services[0].id')
        pl.click('[data-act="publish"]'); pl.wait_for_selector('#pubOnly'); pl.click('#pubOnly'); pl.wait_for_timeout(5000)

        # ---- 목회자 계정 ----
        cP = b.new_context(viewport={'width': 1300, 'height': 950}); pp = cP.new_page()
        pp.on('pageerror', lambda e: errs.append('P:' + str(e))); pp.on('dialog', lambda d: d.accept())
        pp.goto(link); pp.wait_for_selector('#lgUser', timeout=8000)
        pp.click('[data-act="lg-mode"][data-m="signup"]'); pp.wait_for_selector('#lgName')
        pp.fill('#lgName', '김OO 목사님'); pp.fill('#lgUser', 'pp' + tag); pp.fill('#lgPass', 'secret1'); pp.click('[data-act="lg-submit"]')
        pp.wait_for_selector('#jnName', timeout=8000); pp.click('[data-act="team-join"]'); pp.wait_for_selector('.shell[data-page]', timeout=8000)
        uidP = pp.evaluate('CONTI.NET.user.id')
        r = cL.request.patch(URL + 'api/teams/%s/members/%s' % (team, uidP), headers=H, data={'role': 'pastor'})
        if r.status != 200: fail('목회자 지정 실패: ' + r.text()[:120])

        # ---- 목회자: 말씀 탭이 보이고, 편집·편성은 안 보임 ----
        pp.goto(URL + '#/home'); pp.reload(); pp.wait_for_selector('.hd', timeout=10000); pp.wait_for_timeout(1500)
        nav = pp.locator('.side').inner_text()
        if '말씀' not in nav: fail('목회자에게 말씀 메뉴가 없음: ' + nav)
        if '편성' in nav: fail('목회자에게 편성 메뉴가 보임')
        if pp.locator('[data-act="new-svc"]').count(): fail('목회자에게 새 예배 버튼이 보임')
        pp.click('.navi[data-act="word"]'); pp.wait_for_selector('.wrow', timeout=15000)
        if '말씀탭 예배' not in pp.locator('#app').inner_text(): fail('말씀 탭에 예배가 없음')
        if '미입력' not in pp.locator('#app').inner_text(): fail('미입력 배지가 없음')
        pp.fill('#wpPassage', '시편 103:1-5'); pp.fill('#wpTitle', '잊지 말아야 할 은혜'); pp.fill('#wpLine', '받은 은혜를 세어보는 예배')
        pp.fill('#wpMemo', '설교 마지막에 인용할 계획이에요')
        pp.click('[data-act="word-save"]'); pp.wait_for_timeout(2000)
        if '입력됨' not in pp.locator('#app').inner_text(): fail('저장 후 입력됨 배지가 없음')
        print('pastor word tab ok')

        # ---- 인도자: word.received 알림 + 에디터 카드가 잠김 ----
        ns = [n for n in cL.request.get(URL + 'api/notifications?team=' + team).json()['notifications'] if n['type'] == 'word.received']
        if not ns: fail('word.received 알림 없음')
        pl.goto(URL + '#/edit/' + svc_id); pl.wait_for_selector('.wordblock', timeout=15000); pl.wait_for_timeout(500)
        if pl.locator('[data-w="passage"]').count(): fail('목회자 입력인데 인도자가 고칠 수 있음')
        if '수정 요청' not in pl.locator('#app').inner_text(): fail('수정 요청 버튼이 없음')
        if '김OO 목사님' not in pl.locator('.wordblock').inner_text(): fail('출처가 안 보임')
        print('editor locked ok:', ns[0]['title'])

        # ---- 메모 공개 여부: 멤버에게는 안 보이고 인도자에게는 보임 ----
        w = cL.request.get(URL + 'api/services/%s?team=%s' % (svc_id, team)).json()['word']
        if '설교 마지막' not in (w.get('memo') or ''): fail('인도자가 메모를 못 봄')
        cM = b.new_context(); pmr = cM.request
        pmr.post(URL + 'api/auth/signup', headers=H, data={'name': '민수', 'username': 'pm' + tag, 'password': 'secret1'})
        pmr.post(URL + 'api/invite/%s/join' % link.split('/join/')[1], headers=H, data={'name': '민수', 'session': '드럼'})
        wm = pmr.get(URL + 'api/services/%s?team=%s' % (svc_id, team)).json()['word']
        if wm.get('memo'): fail('멤버에게 비공개 메모가 노출됨: %s' % wm)
        if wm.get('passage') != '시편 103:1-5': fail('멤버에게 본문이 안 보임')
        print('memo visibility ok')

        # ---- 수정 요청 → 목회자에게 word.request ----
        rq = cL.request.post(URL + 'api/services/%s/word-request' % svc_id, headers=H, data={'teamId': team})
        if rq.status != 200: fail('수정 요청 실패: ' + rq.text()[:120])
        wr = [n for n in cP.request.get(URL + 'api/notifications?team=' + team).json()['notifications'] if n['type'] == 'word.request']
        if not wr: fail('word.request 알림 없음')
        print('word request ok')

        # ---- §4.6 링크 페이지: 로그인 없이 제출, 1회용 ----
        lr = cL.request.post(URL + 'api/services/%s/word-link' % svc_id, headers=H, data={'teamId': team}).json()
        cX = b.new_context(); px = cX.new_page(); px.on('pageerror', lambda e: errs.append('X:' + str(e)))
        px.goto(URL + '#/word-link/' + lr['token']); px.wait_for_selector('#wlSend', timeout=15000)
        if '말씀탭 예배' not in px.locator('#app').inner_text(): fail('링크 페이지에 예배 이름이 없음')
        px.click('#wlSend'); px.wait_for_timeout(600)
        if '이름을 적어' not in px.locator('#wlErr').inner_text(): fail('이름 필수 검사가 없음')
        px.fill('#wlName', '박OO 목사님'); px.fill('#wlPassage', '요한복음 15:5'); px.fill('#wlTitle', '가지')
        px.click('#wlSend'); px.wait_for_selector('text=보냈어요', timeout=15000)
        w2 = cL.request.get(URL + 'api/services/%s?team=%s' % (svc_id, team)).json()['word']
        if w2['passage'] != '요한복음 15:5' or w2['from']['type'] != 'link': fail('링크 제출이 반영 안 됨: %s' % w2)
        px.reload(); px.wait_for_timeout(2500)
        if '링크를 열 수 없어요' not in px.locator('#app').inner_text(): fail('1회용이 아님')
        print('word link ok')

        # ---- 알림 설정: 끄면 홈 카드에서 빠짐 ----
        pp.goto(URL + '#/home'); pp.wait_for_selector('.hd'); pp.goto(URL + '#/settings'); pp.wait_for_selector('.setpane', timeout=8000); pp.click('[data-act="set-tab"][data-t="noti"]'); pp.wait_for_selector('#sNoti', timeout=5000)
        if not pp.locator('[data-noti="word.request"]').count(): fail('알림 설정 목록이 없음')
        # 알림 토글은 누르는 즉시 이 기기에 저장된다 (§6.8 알림 탭에는 저장 버튼이 없다)
        pp.uncheck('[data-noti="word.request"]'); pp.wait_for_timeout(600)
        pp.goto(URL + '#/home'); pp.reload(); pp.wait_for_selector('.hd', timeout=10000); pp.wait_for_timeout(2500)
        body = pp.locator('#app').inner_text()
        if '말씀을 다시 봐' in body: fail('끈 알림이 홈 카드에 남음')
        print('notification settings ok')

        # ---- 계정 삭제: 아이디 확인 + 마지막 인도자는 막힘 ----
        bad_del = cL.request.post(URL + 'api/auth/delete', headers=H, data={'username': 'pl' + tag, 'password': 'secret1'})
        if bad_del.status != 400 or '인도자' not in bad_del.text(): fail('마지막 인도자가 그냥 삭제됨: %s %s' % (bad_del.status, bad_del.text()[:120]))
        pp.goto(URL + '#/settings'); pp.wait_for_selector('.setpane', timeout=8000); pp.click('[data-act="set-tab"][data-t="account"]'); pp.wait_for_selector('#sDel', timeout=5000); pp.click('#sDel'); pp.wait_for_selector('#daUser', timeout=5000)
        pp.fill('#daUser', 'wrong'); pp.click('#daGo'); pp.wait_for_timeout(500)
        if '아이디가 맞지' not in pp.locator('#daErr').inner_text(): fail('아이디 확인이 없음')
        pp.fill('#daUser', 'pp' + tag); pp.fill('#daPw', 'secret1'); pp.click('#daGo')
        pp.wait_for_selector('#lgUser', timeout=20000)
        if cP.request.get(URL + 'api/me').status != 401: fail('삭제 후에도 세션이 살아 있음')
        ms = cL.request.get(URL + 'api/teams/' + team).json()['members']
        if [m for m in ms if m['userId'] == uidP]: fail('삭제된 계정이 팀에 남음')
        print('account delete ok')

        print('errors:', errs)
        if errs: fail('page errors')
        b.close()
    print('PASTOR TEST OK')

if __name__ == '__main__':
    run()
