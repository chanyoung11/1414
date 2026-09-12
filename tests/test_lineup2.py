# 편성 화면: 날짜 머리글이 버튼처럼 보이고, 그날 편성이 떠 있는 패널로 열리며, 세션 인원을 그날만 조절한다
import os, sys, time
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
tag = str(int(time.time()))[-6:]
H = {'x-conti': '1'}
def fail(m): print('FAIL:', m); sys.exit(1)

def run():
  with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    c = b.new_context(viewport={'width': 1400, 'height': 950}); pg = c.new_page()
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=8000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
    pg.fill('#lgName', '하은'); pg.fill('#lgUser', 'ln' + tag); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam', timeout=8000); pg.fill('#gtTeam', '편성팀'); pg.click('[data-act="team-create"]')
    pg.wait_for_selector('.shell[data-page]', timeout=8000)
    team = pg.evaluate('CONTI.S.team.id')

    # 날짜 두 개
    for d, lb in [('2026-10-04', '주일 1부'), ('2026-10-11', '주일 2부')]:
        c.request.post(URL + 'api/teams/%s/dates' % team, headers=H, data={'date': d, 'label': lb, 'time': '11:00'})
    pg.goto(URL + '#/sched'); pg.wait_for_selector('.schtab', timeout=10000); pg.wait_for_timeout(800)

    # ---- 날짜 머리글이 버튼처럼 (테두리·배경) ----
    st = pg.evaluate("""(()=>{const e=document.querySelector('.dcol>span');const s=getComputedStyle(e);
      return {bw:s.borderTopWidth,br:s.borderTopLeftRadius,bg:s.backgroundColor,txt:e.innerText.replace(/\\n/g,' ')}})()""")
    if st['bw'] == '0px': fail('날짜 머리글에 테두리가 없음: %s' % st)
    if st['br'] == '0px': fail('모서리가 안 둥글다: %s' % st)
    if '주일' not in st['txt']: fail('요일·이름이 안 보임: %s' % st)
    print('date button ok:', st)

    # ---- 누르면 떠 있는 패널로 열린다 (표가 뒤에 남아 있다) ----
    pg.click('.dcol'); pg.wait_for_selector('.lnpanel', timeout=6000); pg.wait_for_timeout(500)
    if not pg.locator('.schtab').count(): fail('패널을 열었더니 뒤의 편성 표가 사라짐')
    if not pg.locator('.dcol.on').count(): fail('열린 날짜가 표시되지 않음')
    print('floating panel ok')

    # ---- 다른 날짜로 바로 옮겨 간다 ----
    pg.locator('.dcol').nth(1).click(); pg.wait_for_timeout(900)
    if '2부' not in pg.locator('.lnhd').inner_text(): fail('다른 날짜로 안 옮겨감: ' + pg.locator('.lnhd').inner_text())
    print('switch date ok')

    # ---- 그날만 세션 인원 늘리기 ----
    row = pg.locator('.lrow').first
    sess = row.locator('.lsess').inner_text().split('\n')[0].strip()
    before = pg.locator('.lrow').first.locator('select[data-lsel]').count()
    pg.locator('.lrow').first.locator('[data-act="lslots"][data-d="1"]').click(); pg.wait_for_timeout(2000)
    after = pg.locator('.lrow').first.locator('select[data-lsel]').count()
    if after != before + 1: fail('자리가 안 늘어남: %d → %d' % (before, after))
    did = pg.evaluate("CONTI.route().a")
    srv = [d for d in c.request.get(URL + 'api/teams/%s/schedule?month=2026-10' % team, headers=H).json()['dates'] if d['id'] == did][0]
    if not srv.get('slots'): fail('그날 정원이 서버에 안 저장됨: %s' % srv)
    print('per-date slots ok:', sess, before, '→', after, srv['slots'])

    # ---- 팀 기본 정원은 그대로 ----
    t = c.request.get(URL + 'api/teams/' + team, headers=H).json()
    base = (t.get('settings') or {}).get('slots') or {}
    if base.get(sess) == after: fail('팀 기본 정원까지 바뀜: %s' % base)
    print('team default untouched ok')

    # ---- 닫으면 편성 표로 돌아온다 ----
    pg.click('.lnhd [data-act="lclose"]'); pg.wait_for_timeout(800)
    if pg.locator('.lnpanel').count(): fail('패널이 안 닫힘')
    if not pg.locator('.schtab').count(): fail('닫았더니 편성 표가 없음')
    print('close ok')

    if errs: fail('페이지 오류:\n' + '\n'.join(errs[:5]))
    print('PASS test_lineup2')
    b.close()

run()
