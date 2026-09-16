# 무료 플랜의 월 AI 한도는 '곡' 단위로 센다.
# - 한 곡에 악보가 여러 장이어도 한 번만 차감된다
# - 같은 달에 같은 곡을 다시 인식해도 더 차감하지 않는다
# - 한도를 넘으면 402 ai_limit 로 막힌다
# ENFORCE_PLAN=1 일 때만 의미가 있으므로, 꺼져 있으면 건너뛴다
import os, sys, time, json
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
tag = str(int(time.time()))[-6:]
H = {'x-conti': '1'}
def fail(m): print('FAIL:', m); sys.exit(1)

def run():
  with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={'width': 1200, 'height': 900}); L = ctx.new_page()
    L.on('dialog', lambda d: d.accept())
    L.goto(URL); L.wait_for_selector('#lgUser', timeout=8000)
    L.click('[data-act="lg-mode"][data-m="signup"]'); L.wait_for_selector('#lgName')
    L.check('#lgAgree')
    L.fill('#lgName', '하은'); L.fill('#lgUser', 'aq' + tag); L.fill('#lgPass', 'secret1')
    L.click('[data-act="lg-submit"]')
    L.wait_for_selector('#gtTeam', timeout=8000); L.fill('#gtTeam', '한도팀'); L.click('[data-act="team-create"]')
    L.wait_for_selector('.shell[data-page]', timeout=8000)
    team = L.evaluate('CONTI.S.team.id')

    health = ctx.request.get(URL + 'api/health').json()
    if not health.get('enforcePlan'):
      print('SKIP — ENFORCE_PLAN 이 꺼져 있어 한도 검사를 하지 않는다'); b.close(); return

    # 인식 엔진이 실제로 붙어 있어야 의미가 있다. 그래도 한도는 엔진 호출 '전에' 검사되므로
    # 402 가 먼저 오는지로 확인할 수 있다
    def ocr(song):
      r = ctx.request.post(URL + 'api/ocr', headers={**H, 'content-type': 'application/json'},
                           data=json.dumps({'teamId': team, 'songKey': song,
                                            'images': [{'b64': 'x' * 200, 'mime': 'image/jpeg', 'w': 10, 'h': 10}]}))
      return r.status, r.text()[:160]

    # 같은 곡을 세 번 불러도 한 곡만 센다
    for i in range(3):
      st, _ = ocr('song-A')
      if st == 402: fail('첫 곡부터 한도에 걸림')
    used = int(L.evaluate("()=>0") or 0)

    # 서로 다른 곡으로 한도(10)까지 채운다
    hit = None
    for i in range(2, 14):
      st, txt = ocr('song-%d' % i)
      if st == 402:
        hit = i
        if 'ai_limit' not in txt: fail('402 인데 ai_limit 이 아님: ' + txt)
        break
    if hit is None: fail('곡을 13개 불렀는데 한도에 안 걸림')
    # song-A(1곡) + song-2..song-(hit-1) = 10곡째에서 막혀야 한다
    n_ok = 1 + (hit - 2)
    if n_ok != 10: fail('한도가 10곡이 아님: %d 곡째에서 막힘' % (n_ok + 1))
    print('OK — 곡 단위로 세고 10곡에서 막힘 (같은 곡 반복은 1회만 차감)')
    b.close()

run()
