# §3 편성 스케줄링: 내 일정 달력 · 편성 표 · 그날 편성 · 통보 · 기본 편성
import os, sys, time, datetime, json
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
tag = str(int(time.time()))[-6:]
H = {'x-conti': '1'}

def fail(msg): print('FAIL:', msg); sys.exit(1)

def mk(b, name, user):
    c = b.new_context(viewport={'width': 1240, 'height': 900}); pg = c.new_page()
    pg.on('dialog', lambda d: d.accept())
    return c, pg

def run():
    with sync_playwright() as p:
        b = p.chromium.launch(); errs = []
        cL, pl = mk(b, '하은', None); pl.on('pageerror', lambda e: errs.append('L:' + str(e)))
        pl.goto(URL); pl.wait_for_selector('#lgUser', timeout=8000)
        pl.click('[data-act="lg-mode"][data-m="signup"]'); pl.wait_for_selector('#lgName')
        pl.fill('#lgName', '하은'); pl.fill('#lgUser', 'sl' + tag); pl.fill('#lgPass', 'secret1'); pl.click('[data-act="lg-submit"]')
        pl.wait_for_selector('#gtTeam', timeout=8000); pl.fill('#gtTeam', '편성팀'); pl.click('[data-act="team-create"]'); pl.wait_for_selector('.hd [data-act="team"]', timeout=8000)
        team = pl.evaluate('CONTI.S.team.id')
        pl.click('.hd [data-act="team"]'); pl.wait_for_selector('#tmLink'); link = pl.locator('#tmLink').inner_text().strip(); pl.keyboard.press('Escape')

        cM, pm = mk(b, '민수', None); pm.on('pageerror', lambda e: errs.append('M:' + str(e)))
        pm.goto(link); pm.wait_for_selector('#lgUser', timeout=8000)
        pm.click('[data-act="lg-mode"][data-m="signup"]'); pm.wait_for_selector('#lgName')
        pm.fill('#lgName', '민수'); pm.fill('#lgUser', 'sm' + tag); pm.fill('#lgPass', 'secret1'); pm.click('[data-act="lg-submit"]')
        pm.wait_for_selector('#jnName', timeout=8000); pm.click('#gtSess .q:has-text("드럼")'); pm.click('[data-act="team-join"]'); pm.wait_for_selector('.hd [data-act="team"]', timeout=8000)
        uidM = pm.evaluate('CONTI.NET.user.id')

        # ---- 겸임 세션: 민수 = 드럼 + 싱어 ----
        pm.click('.hd [data-act="settings"]'); pm.wait_for_selector('#sSess')
        pm.click('#sSess2 [data-s2="싱어"]'); pm.click('#sOk'); pm.wait_for_timeout(1200)
        ses = pm.evaluate('CONTI.S.team.me.mySessions')
        if '드럼' not in ses or '싱어' not in ses: fail('겸임 세션 저장 안 됨: %s' % ses)
        print('multi-session ok:', ses)

        # ---- 날짜 두 개 열기 ----
        d1 = (datetime.date.today() + datetime.timedelta(days=7)).isoformat()
        d2 = (datetime.date.today() + datetime.timedelta(days=14)).isoformat()
        for d, lb in ((d1, '주일 2부'), (d2, '수요예배')):
            r = cL.request.post(URL + 'api/teams/%s/dates' % team, headers=H, data={'date': d, 'label': lb, 'time': '11:00'})
            if r.status != 200: fail('날짜 열기 실패: ' + r.text()[:120])

        # ---- 멤버 달력: 탭 순환 ok → maybe → no ----
        pm.goto(URL + '#/cal'); pm.wait_for_selector('.cal-cell.on', timeout=15000)
        cell = pm.locator('[data-cal="%s"]' % d1)
        if not cell.count(): fail('열린 날짜 셀이 달력에 없음')
        cell.click(); pm.wait_for_timeout(900)
        if pm.evaluate("CONTI.SCH.availability.find(a=>a.date===%s).state" % json.dumps(d1)) != 'ok': fail('첫 탭이 ok 가 아님')
        cell.click(); pm.wait_for_timeout(900)
        if pm.evaluate("CONTI.SCH.availability.find(a=>a.date===%s).state" % json.dumps(d1)) != 'maybe': fail('두 번째 탭이 maybe 가 아님')
        srv = cM.request.get(URL + 'api/teams/%s/schedule' % team).json()
        if not [a for a in srv['availability'] if a['date'] == d1 and a['state'] == 'maybe']: fail('서버에 maybe 저장 안 됨')
        if '사역 2일 중 1일 답함' not in pm.locator('.cal-foot').inner_text(): fail('달력 하단 진행 문구 이상: ' + pm.locator('.cal-foot').inner_text())
        print('calendar cycle ok')

        # ---- 인도자 편성 표 + 그날 편성 ----
        pl.goto(URL + '#/sched'); pl.wait_for_selector('.schtab', timeout=15000)
        if '민수' not in pl.locator('.schtab').inner_text(): fail('편성 표에 멤버가 없음')
        pl.locator('.schtab .dcol').first.click(); pl.wait_for_selector('[data-lsel]', timeout=10000)
        did = pl.evaluate('CONTI.route().a')
        sel = pl.locator('[data-lsel="드럼"]').first
        opts = sel.locator('option').all_inner_texts()
        if not any('민수' in o for o in opts): fail('드럼 드롭다운에 민수 없음: %s' % opts)
        sel.select_option(label=[o for o in opts if '민수' in o][0]); pl.wait_for_timeout(1200)
        srv = cL.request.get(URL + 'api/teams/%s/schedule' % team).json()
        dd = [d for d in srv['dates'] if d['id'] == did][0]
        if not [r for r in dd['lineup'] if r['memberId'] == uidM and r['session'] == '드럼']: fail('편성 저장 안 됨: %s' % dd['lineup'])
        if '보류' not in pl.locator('.lwarn').inner_text(): fail('보류 경고가 안 뜸')
        print('lineup save + warning ok')

        # ---- 통보하기 → lineup.notify ----
        pl.click('[data-act="lnotify"]'); pl.wait_for_timeout(2500)
        ns = [n for n in cM.request.get(URL + 'api/notifications?team=' + team).json()['notifications'] if n['type'] == 'lineup.notify']
        if not ns: fail('lineup.notify 알림 없음')
        if '드럼으로 섭니다' not in ns[0]['title']: fail('통보 알림 문구 이상: %s' % ns[0]['title'])
        print('notify ok:', ns[0]['title'])
        # 멤버 홈 카드에 뜨고 확인하면 사라짐
        pm.goto(URL + '#/home'); pm.reload(); pm.wait_for_selector('.todo-card', timeout=10000)
        if '드럼으로 섭니다' not in pm.locator('.todo').inner_text(): fail('홈 카드에 편성 통보 없음')
        pm.click('.todo-card [data-act="noti-ack"]'); pm.wait_for_timeout(1200)
        print('home card ok')

        # ---- 편성된 날을 불가능으로 → avail.conflict ----
        pm.goto(URL + '#/cal'); pm.wait_for_selector('[data-cal="%s"]' % d1, timeout=15000)
        pm.locator('[data-cal="%s"]' % d1).click(); pm.wait_for_timeout(1200)   # maybe → no (확인창 자동 수락)
        st = pm.evaluate("(CONTI.SCH.availability.find(a=>a.date===%s)||{}).state" % json.dumps(d1))
        if st != 'no': fail('불가능으로 안 바뀜: %s' % st)
        cf = [n for n in cL.request.get(URL + 'api/notifications?team=' + team).json()['notifications'] if n['type'] == 'avail.conflict']
        if not cf: fail('avail.conflict 알림 없음')
        print('conflict ok:', cf[0]['title'])

        # ---- 기본 편성 + 자동 생성 시 불가능한 사람은 비움 ----
        r = cL.request.patch(URL + 'api/teams/%s/settings' % team, headers=H, data={'slots': {'드럼': 1, '싱어': 2}, 'defaultLineup': {'드럼': [uidM], '싱어': [uidM, '']}})
        if r.status != 200: fail('기본 편성 저장 실패: ' + r.text()[:120])
        wd = (datetime.date.today() + datetime.timedelta(days=5)).weekday(); wd_js = (wd + 1) % 7
        cL.request.post(URL + 'api/teams/%s/recurring' % team, headers=H, data={'weekday': wd_js, 'label': '자동예배', 'time': '11:00'})
        cL.request.get(URL + 'api/services?team=' + team)   # 인도자 조회가 자동 생성 트리거
        srv = cL.request.get(URL + 'api/teams/%s/schedule' % team).json()
        autos = [d for d in srv['dates'] if d['label'] == '자동예배' and d['lineup']]
        if not autos: fail('자동 생성 날짜에 기본 편성이 안 채워짐')
        if not [x for x in autos[0]['lineup'] if x['memberId'] == uidM]: fail('기본 편성 멤버가 없음: %s' % autos[0]['lineup'])
        print('default lineup ok:', len(autos), '개 날짜')

        # 불가능한 날은 비워지는지
        d_auto = autos[0]['date']
        cM.request.put(URL + 'api/teams/%s/availability' % team, headers=H, data={'date': d_auto, 'state': 'no'})
        cL.request.put(URL + 'api/teams/%s/dates/%s/lineup' % (team, autos[0]['id']), headers=H, data={'lineup': []})
        # 다시 채우려면 새 날짜가 필요하므로 서버 함수를 직접 검증: 되돌리기 버튼 로직과 같은 규칙
        pl.goto(URL + '#/lineup/' + autos[0]['id']); pl.wait_for_selector('[data-act="ldefault"]', timeout=10000)
        pl.evaluate("CONTI.pullSchedule(null,true)"); pl.wait_for_timeout(1200)
        pl.click('[data-act="ldefault"]'); pl.wait_for_timeout(1500)
        srv = cL.request.get(URL + 'api/teams/%s/schedule' % team).json()
        dd = [d for d in srv['dates'] if d['id'] == autos[0]['id']][0]
        if [x for x in dd['lineup'] if x['memberId'] == uidM]: fail('불가능한 사람이 기본 편성에 들어감: %s' % dd['lineup'])
        print('default skips unavailable ok')

        # ---- 카톡용 문구 ----
        t = cL.request.get(URL + 'api/teams/%s/dates/%s/text' % (team, did)).json()
        if '드럼 민수' not in t['text']: fail('카톡 문구 이상: %s' % t['text'])
        print('kakao text ok')

        print('errors:', errs)
        if errs: fail('page errors')
        b.close()
    print('LINEUP TEST OK')

if __name__ == '__main__':
    run()
