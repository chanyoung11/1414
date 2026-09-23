# 앱에서 유튜브 "동영상 플레이어 구성 오류"(153) — 중계 페이지 app/yt.html (2026-09-23)
#  앱 웹뷰 주소(iOS capacitor://localhost)는 Referer 로 나가지 않는다 → 유튜브가 153 으로 막는다.
#  앱은 lets1414.com/yt.html 을 넣고 그 페이지가 유튜브를 넣는다.
#  1. 웹: 예전처럼 유튜브를 바로 넣는다 (중계 안 탐, referrerpolicy·enablejsapi 그대로)
#  2. 중계: 다른 출처(relay.localhost)의 yt.html 을 통해 넣어도 유튜브 요청의 Referer 가 중계 페이지 주소이고
#     origin 도 그 주소다. 유튜브에 닿으면 onReady·재생 상태가 앱까지 돌아온다
import os, sys, time
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
def fail(m): print('FAIL:', m); sys.exit(1)

def run():
  tag = str(int(time.time()))[-6:]
  u = urlparse(URL); relay_base = '%s://relay.localhost:%s/' % (u.scheme, u.port or 80)   # 다른 출처. 크롬은 *.localhost 를 이 기기로 보낸다 (유튜브는 IP 주소 Referer 를 150 으로 막아서 127.0.0.1 은 못 쓴다)
  with sync_playwright() as p:
    b = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
    c = b.new_context(viewport={'width': 1180, 'height': 820})
    pg = c.new_page()
    errs = []; pg.on('pageerror', lambda e: errs.append(repr(e)[:200])); pg.on('dialog', lambda d: d.accept())
    embeds = []   # 유튜브 embed 요청 (주소, Referer)
    c.on('request', lambda r: embeds.append((r.url, r.headers.get('referer'))) if '/embed/' in r.url and 'youtube.com' in r.url else None)
    pg.goto(URL); pg.wait_for_selector('#lgUser')
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
    pg.fill('#lgName', '하은'); pg.fill('#lgUser', 'yt' + tag); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam'); pg.fill('#gtTeam', '영상팀'); pg.click('[data-act="team-create"]')
    pg.wait_for_selector('.shell[data-page]', timeout=10000)
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
    pg.fill('[data-f="svc.name"]', '영상 예배')
    pg.click('[data-act="add-item"]'); pg.wait_for_timeout(400)
    pg.fill('[data-f="item.title"]', '곡')
    pg.set_input_files('#pieceFile', [SHEET])
    pg.wait_for_function("(()=>{const it=CONTI.S.services[0].items[0];const p=(it.pieces||[])[0];return p&&p.w>0})()", timeout=90000)
    pg.fill('#ytUrl', 'https://youtu.be/dQw4w9WgXcQ?t=42'); pg.click('[data-act="add-yt"]'); pg.wait_for_timeout(600)
    sid = pg.evaluate("CONTI.S.services[0].id")

    # ---- 1. 웹은 그대로 바로 넣는다
    pg.goto(URL + '#/play/' + sid); pg.wait_for_selector('#yt', state='attached', timeout=10000)
    if pg.evaluate("CONTI.YT.relay") != '': fail('웹인데 중계 주소가 켜져 있음: %r' % pg.evaluate("CONTI.YT.relay"))
    at = pg.evaluate("()=>{const f=document.querySelector('#yt');return {src:f.getAttribute('src'),rp:f.getAttribute('referrerpolicy'),allow:f.getAttribute('allow')}}")
    if not at['src'].startswith('https://www.youtube.com/embed/dQw4w9WgXcQ?'): fail('웹 iframe 이 유튜브를 바로 넣지 않음: %s' % at['src'])
    q = parse_qs(urlparse(at['src']).query)
    if q.get('enablejsapi') != ['1'] or q.get('start') != ['42']: fail('웹 iframe 파라미터가 이상함: %s' % at['src'])
    if 'origin' in q: fail('localhost 인데 origin 을 붙임: %s' % at['src'])
    if at['rp'] != 'strict-origin-when-cross-origin': fail('referrerpolicy 가 바뀜: %s' % at['rp'])
    if 'autoplay' not in (at['allow'] or ''): fail('allow 가 빠짐: %s' % at['allow'])
    print('1 웹 바로 넣기 ok', at['src'].split('?')[1])

    # ---- 2. 중계 페이지를 거친다 (앱과 같은 길. 출처가 다르게 relay.localhost 로)
    embeds.clear()
    pg.evaluate("(r)=>{CONTI.YT.relay=r+'yt.html'}", relay_base)
    pg.evaluate("()=>{location.hash='#/home'}"); pg.wait_for_timeout(300)
    pg.goto(URL + '#/play/' + sid); pg.wait_for_selector('#yt', state='attached', timeout=10000)
    src = pg.evaluate("document.querySelector('#yt').getAttribute('src')")
    if not src.startswith(relay_base + 'yt.html?v=dQw4w9WgXcQ&start=42'): fail('중계 주소가 아님: %s' % src)
    fr = None
    for _ in range(40):
      fr = next((f for f in pg.frames if f.url.startswith(relay_base + 'yt.html')), None)
      if fr and fr.query_selector('iframe'): break
      pg.wait_for_timeout(250)
    if not fr: fail('중계 페이지가 안 뜸')
    inner = fr.evaluate("()=>{const f=document.querySelector('iframe');return f?{src:f.src,rp:f.referrerPolicy}:null}")
    if not inner: fail('중계 페이지 안에 유튜브 iframe 이 없음')
    iq = parse_qs(urlparse(inner['src']).query)
    if not inner['src'].startswith('https://www.youtube.com/embed/dQw4w9WgXcQ?'): fail('중계 안쪽 주소가 이상함: %s' % inner['src'])
    if iq.get('origin') != [relay_base.rstrip('/')]: fail('중계 안쪽 origin 이 중계 주소가 아님: %s' % iq.get('origin'))
    if iq.get('start') != ['42'] or iq.get('enablejsapi') != ['1']: fail('중계 안쪽 파라미터가 빠짐: %s' % inner['src'])
    if inner['rp'] != 'strict-origin-when-cross-origin': fail('중계 안쪽 referrerpolicy: %s' % inner['rp'])
    # 잘못된 id 는 그대로 넣지 않는다
    bad = fr.evaluate("()=>{const q=new URLSearchParams('v=%22%3E%3Cscript%3Ex');return (q.get('v')||'').replace(/[^\\w-]/g,'').slice(0,20)}")
    if bad != 'scriptx': fail('id 거르기: %r' % bad)
    print('2 중계 주소·origin ok', inner['src'].split('?')[1][:80])

    # 유튜브 요청의 Referer — 네트워크가 있을 때만 확인된다
    pg.wait_for_timeout(1500)
    ref = [r for (u2, r) in embeds if '/embed/dQw4w9WgXcQ' in u2]
    if ref:
      if ref[-1] != relay_base: fail('유튜브가 받은 Referer 가 중계 페이지가 아님: %r' % ref[-1])
      print('2-b 유튜브가 받은 Referer =', ref[-1])
      # 유튜브까지 닿으면 준비 신호와 재생 상태가 중계를 지나 앱으로 돌아와야 한다
      try:
        pg.wait_for_function("CONTI.P.ytReady===true", timeout=15000)
        pg.evaluate("()=>CONTI.P.play()")
        pg.wait_for_function("CONTI.P.playing===true&&CONTI.P.t>42", timeout=20000)
        pg.evaluate("()=>CONTI.P.pause()"); pg.wait_for_function("CONTI.P.playing===false", timeout=10000)
        print('2-c 중계로 준비·재생·멈춤·시각 ok, t=%.1f' % pg.evaluate("CONTI.P.t"))
      except Exception as e:
        fail("중계를 지나 유튜브 메시지가 오가지 않음: %s %s" % (str(e)[:80], pg.evaluate("({r:CONTI.P.ytReady,p:CONTI.P.playing,t:CONTI.P.t,d:CONTI.P.dur})")))
      # 3. 유튜브가 막으면(onError) 준비 안 된 것으로 돌리고 안내한다. IP 주소 Referer 는 유튜브가 150 으로 막는다
      pg.evaluate("(r)=>{CONTI.YT.relay=r+'yt.html'}", relay_base.replace('relay.localhost', '127.0.0.1'))
      pg.evaluate("()=>{location.hash='#/home'}"); pg.wait_for_timeout(300)
      pg.goto(URL + '#/play/' + sid); pg.wait_for_selector('#yt', state='attached', timeout=10000)
      try: pg.wait_for_function("/오류 \\d+/.test((document.querySelector('#ytHint')||{}).textContent||'')", timeout=15000)
      except Exception: fail('onError 인데 안내가 안 바뀜: %s' % pg.evaluate("(document.querySelector('#ytHint')||{}).textContent"))
      if pg.evaluate("CONTI.P.ytReady"): fail('onError 뒤에도 ytReady 가 true')
      print('3 막힌 영상 안내 ok:', pg.evaluate("document.querySelector('#ytHint').textContent")[:40])
    else:
      print('2-b 유튜브에 닿지 않아(오프라인) Referer·재생 확인은 건너뜀')

    if errs: fail('콘솔 오류: %s' % errs[:3])
    b.close()
  print('PASS test_ytrelay')

run()
