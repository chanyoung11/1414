# 제보 14~16 (2026-09-18)
# 14 코드 인식 알약이 요금제마다 다른 색 · 무제한은 금색
# 15 영상을 일부 세션에게만 달면 타임라인 메모 대상도 그 안에서만
# 16 앱 웹뷰(localhost)에서 유튜브가 "플레이어 구성 오류" 나던 origin 파라미터
import os, sys, time, json
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = 'http://localhost:8766/'
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
def fail(m): print('FAIL:', m); sys.exit(1)

def run():
  tag = str(int(time.time()))[-6:]
  with sync_playwright() as p:
    b = p.chromium.launch()
    c = b.new_context(viewport={'width': 1180, 'height': 820}, has_touch=True)
    pg = c.new_page()
    errs = []; pg.on('pageerror', lambda e: errs.append(repr(e)[:200])); pg.on('dialog', lambda d: d.accept())
    pg.goto(URL); pg.wait_for_selector('#lgUser')
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
    pg.fill('#lgName','하은'); pg.fill('#lgUser','u14'+tag); pg.fill('#lgPass','secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam'); pg.fill('#gtTeam','14팀'); pg.click('#gtSess .q:has-text("건반")'); pg.click('[data-act="team-create"]')
    pg.wait_for_selector('.shell[data-page]', timeout=10000)

    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
    pg.fill('[data-f="svc.name"]','9/20 주일')
    pg.click('[data-act="add-item"]'); pg.wait_for_timeout(400)
    pg.fill('[data-f="item.title"]','예수로 나의 구주 삼고'); pg.fill('[data-f="item.key"]','G')
    pg.set_input_files('#pieceFile', [SHEET])
    pg.wait_for_function("(()=>{const it=CONTI.S.services[0].items[0];const p=(it.pieces||[])[0];return p&&p.w>0})()", timeout=90000)
    pg.wait_for_timeout(800)
    sid = pg.evaluate("CONTI.S.services[0].id")

    # ---- 14 요금제마다 다른 알약 색
    # 요금제는 서버가 알려 준다 — 사용량 응답을 바꿔 가며 알약을 본다
    plan_now = {'v': ('free', 20)}
    def usage_route(r):
      pl, cap = plan_now['v']
      r.fulfill(status=200, content_type='application/json', body=json.dumps(
        {'plan': pl, 'ocr': {'used': 1, 'cap': cap}, 'omr': {'used': 0, 'cap': cap},
         'resetAt': '2026-10-01', 'enforced': True, 'credits': False, 'month': '2026-09', 'creditOmr': 0}))
    pg.route('**/usage*', usage_route)
    got = {}
    for plan, cap, want in [('free',20,''), ('pro',100,'p-pro'), ('plus',300,'p-plus'), ('plus',None,'p-unl')]:
      plan_now['v'] = (plan, cap)
      pg.goto(URL + '#/home'); pg.wait_for_timeout(300)
      pg.goto(URL + '#/edit/' + sid); pg.wait_for_selector('.cb-credit', timeout=8000); pg.wait_for_timeout(700)
      r = pg.evaluate("()=>{const e=document.querySelector('.cb-credit');const s=getComputedStyle(e);"
                      "return {cls:e.className,txt:e.textContent.trim(),bg:s.backgroundImage.slice(0,20),fg:s.color,plan:CONTI.PLANQ.plan+'/'+CONTI.PLANQ.ocr.cap}}")
      got[plan+'/'+str(cap)] = r['cls'] + ' ' + r['txt']
      if want and want not in r['cls']: fail('%s(%s) 알약에 %s 가 없음: %s' % (plan, cap, want, r))
      if not want and ('p-pro' in r['cls'] or 'p-plus' in r['cls'] or 'p-unl' in r['cls']): fail('무료인데 색이 붙음: %s' % r)
      if want == 'p-unl' and 'gradient' not in r['bg']: fail('무제한인데 금색이 아님: %s' % r)
    if len(set(got.values())) != 4: fail('요금제마다 같은 모양: %s' % got)
    print('14 요금제 색 ok', got)
    pg.unroute('**/usage*')

    # ---- 15 영상을 일부 세션에게만 → 메모 대상도 그 안에서만
    sess = pg.evaluate("CONTI.S.team.sessions.filter(x=>x!=='인도자')")
    if len(sess) < 2: fail('세션이 둘 미만이라 검사 불가: %s' % sess)
    pick = sess[0]
    pg.fill('#ytUrl', 'https://youtu.be/dQw4w9WgXcQ'); pg.click('[data-act="add-yt"]'); pg.wait_for_timeout(700)
    pg.evaluate("(s)=>{CONTI.S.services[0].items[0].media[0].sessions=[s];CONTI.save();CONTI.render()}", pick)
    pg.wait_for_timeout(400)

    # 인도자는 '그 세션 눈으로 보기'로 바꿔야 태그된 영상이 보인다
    pg.goto(URL + '#/play/' + sid); pg.wait_for_selector('.panel.media', timeout=10000); pg.wait_for_timeout(1200)
    pg.evaluate("(s)=>{CONTI.pl().session=s;CONTI.render()}", pick); pg.wait_for_timeout(1200)
    # ---- 16 origin 파라미터가 빠졌는가 (앱 웹뷰는 https://localhost 라 붙이면 플레이어가 안 뜬다)
    if pg.evaluate("CONTI.ytOriginParam()") != '': fail('localhost 인데 origin 파라미터를 붙임: %r' % pg.evaluate("CONTI.ytOriginParam()"))
    src = pg.evaluate("()=>{const f=document.querySelector('#yt');return f?f.getAttribute('src'):'(없음)'}")
    if src == '(없음)': fail('연습 화면에 유튜브 iframe 이 없음')
    if 'origin=' in src: fail('iframe src 에 origin 이 남아 있음: %s' % src)
    if 'enablejsapi=1' not in src: fail('enablejsapi 가 빠짐: %s' % src)
    print('16 origin 안 붙음 ok', src.split('?')[1][:60])

    pg.click('[data-act="tnote"]'); pg.wait_for_selector('#cText', timeout=5000); pg.wait_for_timeout(300)
    btns = pg.evaluate("()=>[...document.querySelectorAll('#modal [data-s]')].map(b=>[b.dataset.s,b.textContent.trim()])")
    if not btns: fail('대상 버튼이 없음 (인도자가 아닌가)')
    if btns[0][1] != '태그된 전체': fail("'태그된 전체' 라벨이 아님: %s" % btns)
    names = [x[0] for x in btns if x[0]]
    if names != [pick]: fail('태그된 세션 밖이 고를 수 있게 남음: %s (기대 %s)' % (names, [pick]))
    print('15 메모 대상 제한 ok', btns)
    pg.click('#modal [data-close]'); pg.wait_for_timeout(500)

    # 전체로 달린 영상은 제한 없음
    pg.evaluate("()=>{CONTI.S.services[0].items[0].media[0].sessions=[];CONTI.save()}")
    pg.goto(URL + '#/play/' + sid); pg.wait_for_selector('.panel.media', timeout=10000); pg.wait_for_timeout(1200)
    pg.click('[data-act="tnote"]'); pg.wait_for_selector('#cText', timeout=5000); pg.wait_for_timeout(300)
    b2 = pg.evaluate("()=>[...document.querySelectorAll('#modal [data-s]')].map(b=>[b.dataset.s,b.textContent.trim()])")
    if b2[0][1] != '전체': fail("전체 공개인데 라벨이 바뀜: %s" % b2)
    if len([x for x in b2 if x[0]]) != len(sess): fail('전체 공개인데 세션이 빠짐: %s (팀 %s)' % (b2, sess))
    print('15-b 전체 공개면 제한 없음 ok', len(b2))

    if errs: fail('콘솔 오류: %s' % errs[:3])
    b.close()
  print('OK — 제보 14~16')
run()
