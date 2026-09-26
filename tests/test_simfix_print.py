# 아이폰 앱 인쇄 (시뮬레이터 점검 C1 · C2 · C6 · C7) — 앱(https://localhost)을 흉내 내고 가짜 Printer 플러그인으로 넘기는 값을 본다.
#
# 사용: CONTI_URL=http://localhost:8766/ .venv/bin/python tests/test_simfix_print.py   (개발 서버가 떠 있어야 한다 · AI 는 가짜)
#   종이 확인(C2)에 pdftoppm(poppler)이 있으면 헤드리스 크로미움이 만든 PDF 를 픽셀로 본다. 없으면 그 부분만 건너뛴다.
#
# 본다
#  C6 팀을 만든 인도자(기본 세션 '인도자')가 인쇄 시트를 열면 세션 단추 하나('전체')가 켜져 있고, 미리보기 머리·바닥글도 '전체'다.
#     목록에 있는 세션(드럼)은 그대로 둔다 · 무대에서 내보낼 때처럼 PRT.session 이 '인도자'여도 '전체'로 열린다
#  C7 폰 미리보기: 쪽이 보이는 폭에 맞춰 줄어 한 장이 통째로 보인다(가로 스크롤 없음) · 돌려도 다시 맞는다 ·
#     넓은 화면에서는 실제 크기 그대로(F62: 넘치면 왼쪽부터) · 종이(nprint)에는 실제 크기(zoom 1)·여백 0
#  C1 인쇄 · PDF 가 앱에 방향·종이·쪽 크기를 넘긴다 (합주용 = A4 가로 1123×794 · 보관용 = 세로) — 앱은 이걸로 인쇄 방향과
#     쪽 한 장 = 종이 한 장을 맞춘다. 앱 쪽(PrinterPlugin.swift)은 여기서 돌릴 수 없어 코드에 그 자리가 있는지만 본다
#  C2 조판(.ppage)이 print-color-adjust: exact — '배경 그래픽' 없이 찍어도(print_background=False) 검은 송폼 띠와 노란
#     하이라이트가 종이에 남는다
import os, sys, time, shutil, subprocess, tempfile
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
SRV = urlparse(URL)
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
tag = str(int(time.time()))[-6:]
def fail(m): print('FAIL:', m); sys.exit(1)

# 가짜 Printer — 부른 순간의 값과 화면(인쇄 조판만 남았는지 · 쪽 배율 · 여백)을 적어 둔다
MOCK = r"""
(() => {
  window.__prints = [];
  window.Capacitor = {
    getPlatform: () => 'ios', isNativePlatform: () => true, isPluginAvailable: () => false,
    Plugins: {
      Printer: {
        print: async (o) => {
          const pp = document.querySelector('#printArea .ppage'), out = document.querySelector('#printArea .pvout');
          window.__prints.push({ o, nprint: document.body.classList.contains('nprint'),
            zoom: pp ? getComputedStyle(pp).zoom : null, pad: out ? getComputedStyle(out).paddingLeft : null,
            pageW: pp ? pp.offsetWidth : 0 });
          return { completed: false };
        },
        audioFocus: async () => ({}),
      },
      App: { addListener: () => Promise.resolve({ remove() {} }), getLaunchUrl: () => Promise.resolve(undefined), exitApp() {}, getInfo: () => Promise.resolve({}) },
      SplashScreen: { hide: () => Promise.resolve() },
    },
  };
})();
"""

SESS_JS = "[...document.querySelectorAll('#modal [data-po=\"session\"]')].filter(b=>b.classList.contains('on')).map(b=>b.dataset.v)"
FIT_JS = """(()=>{const o=document.querySelector('#printArea .pvout'),pp=o.querySelector('.ppage'),r=pp.getBoundingClientRect(),cs=getComputedStyle(o);
  return {scrollW:o.scrollWidth,clientW:o.clientWidth,avail:o.clientWidth-parseFloat(cs.paddingLeft)-parseFloat(cs.paddingRight),
    left:r.left,right:r.right,w:r.width,pw:CONTI.PG.pw,pages:o.querySelectorAll('.ppage').length}})()"""

def check_fit(pg, label):
    m = pg.evaluate(FIT_JS)
    if m['scrollW'] > m['clientW'] + 1: fail('%s: 미리보기가 옆으로 넘친다 (가로 스크롤): %s' % (label, m))
    if m['left'] < -0.5 or m['right'] > m['clientW'] + 0.5: fail('%s: 쪽이 화면 밖으로 나간다: %s' % (label, m))
    if m['w'] < m['avail'] * 0.97: fail('%s: 쪽이 보이는 폭에 맞지 않고 너무 작다: %s' % (label, m))
    return m

def open_sheet(pg):
    pg.click('.top [data-act="print"]'); pg.wait_for_selector('#pvGo', timeout=8000); pg.wait_for_timeout(200)

def preview(pg):
    pg.click('#pvGo'); pg.wait_for_selector('#printArea.pv .ppage', timeout=10000); pg.wait_for_timeout(500)

def close_preview(pg):
    pg.click('[data-pv="close"]'); pg.wait_for_timeout(300)
    if pg.locator('#printArea').count(): fail('미리보기 닫기가 안 먹음')

def run():
    with sync_playwright() as p:
        b = p.chromium.launch(); errs = []
        c = b.new_context(viewport={'width': 390, 'height': 844}, screen={'width': 390, 'height': 844},
                          is_mobile=True, has_touch=True, device_scale_factor=2, service_workers='block')
        def handler(route):
            u = urlparse(route.request.url)
            if u.scheme == 'https' and u.hostname in ('localhost', 'lets1414.com', 'www.lets1414.com') and u.port is None:
                try: return route.fulfill(response=route.fetch(url='%s://%s/%s' % (SRV.scheme, SRV.netloc, u.path.lstrip('/')) + ('?' + u.query if u.query else '')))
                except Exception:
                    try: return route.abort()
                    except Exception: return
            if u.hostname == SRV.hostname and u.port == SRV.port: return route.continue_()
            return route.abort()   # 바깥(글꼴 CDN 등)은 막는다
        c.route('**/*', handler)
        c.add_init_script(MOCK)
        pg = c.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
        pg.goto('https://localhost/')
        if not pg.evaluate('location.hostname==="localhost"&&!location.port&&location.protocol==="https:"'): fail('앱 흉내가 안 됨 (NATIVE 아님)')

        # ---- 인도자: 팀을 만들면 세션이 '인도자' ----
        pg.wait_for_selector('#lgUser', timeout=15000)
        pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
        pg.fill('#lgName', '인도'); pg.fill('#lgUser', 'sfp' + tag); pg.fill('#lgPass', 'secret12'); pg.click('[data-act="lg-submit"]')
        pg.wait_for_selector('#gtTeam', timeout=15000); pg.fill('#gtTeam', '인쇄팀' + tag); pg.click('[data-act="team-create"]')
        pg.wait_for_selector('.shell[data-page]', timeout=15000)
        pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
        pg.fill('[data-f="svc.name"]', '9/26 주일')
        pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]')
        pg.fill('[data-f="item.title"]', '주님 찬양'); pg.fill('[data-f="item.key"]', 'G'); pg.fill('[data-f="item.form"]', 'Intro - a1 - b - a2 - outro')
        pg.wait_for_timeout(300)
        pg.set_input_files('#pieceFile', [SHEET])
        pg.wait_for_function("(()=>{const p=(CONTI.S.services[0].items[0].pieces||[])[0];return p&&p.w>0})()", timeout=90000)
        pg.wait_for_timeout(800)
        sid = pg.evaluate("CONTI.S.services[0].id")
        pg.evaluate("(x)=>{location.hash=x}", '#/view/' + sid); pg.wait_for_selector('.top [data-act="print"]', timeout=10000); pg.wait_for_timeout(1000)
        # 마커 · 하이라이트(넓게 — 종이에서 픽셀로 본다) · 전체 메모
        pg.evaluate("""(tag)=>{const it=CONTI.S.services[0].items[0];const p=it.pieces[0];
          p.markers=[{id:'m1',label:'A',x:Math.round(p.w*0.08),y:Math.round(p.h*0.35),cut:null}];
          p.hls=[{id:'h1',x:Math.round(p.w*0.1),y:Math.round(p.h*0.4),w:Math.round(p.w*0.6),h:Math.round(p.h*0.06),kind:'hl'}];
          it.notes=[{id:'nsfp1'+tag,marker:'m1',layer:'leader',text:'천천히'}];
          CONTI.save()}""", tag)
        pg.wait_for_timeout(400)
        if pg.evaluate("(CONTI.S.team.me||{}).session") != '인도자': fail('검사 준비: 팀을 만든 사람의 세션이 인도자가 아님')

        # ================= C6 =================
        pg.evaluate("CONTI.PRT.session=''")
        open_sheet(pg)
        on = pg.evaluate(SESS_JS)
        if on != ['전체']: fail('C6 인도자가 연 인쇄 시트의 켜진 세션이 %r (전체 하나여야)' % on)
        preview(pg)
        hint = pg.locator('.pvbar .hint').first.inner_text()
        foot = pg.locator('#printArea .pfoot2').first.inner_text()
        if not hint.endswith('· 전체') or '인도자' in hint: fail('C6 미리보기 머리가 %r' % hint)
        if '인도자' in foot or '전체' not in foot: fail('C6 바닥글이 %r' % foot)
        if '천천히' not in pg.locator('#printArea').inner_text(): fail('C6 전체로 바꾼 뒤 인도자 메모가 빠짐')
        close_preview(pg)
        # 목록에 있는 세션은 그대로
        open_sheet(pg); pg.click('#modal [data-po="session"][data-v="드럼"]'); pg.wait_for_timeout(200)
        pg.click('#modal [data-close]'); pg.wait_for_timeout(200)
        open_sheet(pg)
        if pg.evaluate(SESS_JS) != ['드럼']: fail('C6 고른 세션(드럼)이 다시 열 때 유지되지 않음: %r' % pg.evaluate(SESS_JS))
        pg.click('#modal [data-close]'); pg.wait_for_timeout(200)
        # 무대에서 내보낼 때(stageExport)처럼 인도자 세션이 들어와도
        pg.evaluate("CONTI.PRT.session='인도자'")
        open_sheet(pg)
        if pg.evaluate(SESS_JS) != ['전체']: fail('C6 PRT.session=인도자 로 열었는데 켜진 세션이 %r' % pg.evaluate(SESS_JS))
        print('C6 인도자 → 세션 \'전체\' 가 켜져 열림 · 머리·바닥글 전체 · 고른 세션은 유지 ok')

        # ================= C7 · C2 · C1 (합주용 = A4 가로) =================
        pg.click('#modal [data-po="mode"][data-v="stage"]'); pg.wait_for_timeout(200)
        preview(pg)
        m = check_fit(pg, 'C7 폰 세로')
        if abs(m['pw'] - 1122.5) > 1: fail('C7 합주용 쪽이 A4 가로가 아님: %s' % m)
        # 돌리면 다시 맞춘다
        pg.set_viewport_size({'width': 844, 'height': 390}); pg.wait_for_timeout(400)
        check_fit(pg, 'C7 폰 가로')
        pg.set_viewport_size({'width': 390, 'height': 844}); pg.wait_for_timeout(400)
        check_fit(pg, 'C7 폰 세로(다시)')
        pg.screenshot(path=os.path.join(tempfile.gettempdir(), 't_simfix_print_phone.png'))
        print('C7 폰 미리보기: 쪽이 폭에 맞음 (%.0f/%.0fpx · 가로 스크롤 없음) · 돌려도 다시 맞음 ok' % (m['w'], m['clientW']))

        # C2 — 배경을 지우지 않는다
        pca = pg.evaluate("""(()=>['.pform2','.songhead .num','.hl','.pstrip .who','.pstrip .mk2'].map(s=>{
          const e=document.querySelector('#printArea .ppage '+s);return [s,e?getComputedStyle(e).printColorAdjust:null,e?getComputedStyle(e).webkitPrintColorAdjust:null]}))()""")
        for s, a, w in pca:
            if a is None: fail('C2 조판에 %s 가 없음 (검사 준비가 틀림)' % s)
            if a != 'exact' or w != 'exact': fail('C2 %s 의 print-color-adjust 가 %s/%s (exact 여야)' % (s, a, w))
        if '배경 그래픽' in pg.locator('#printArea .pvbar').inner_text(): fail('C2 필요 없어진 "배경 그래픽 켜기" 안내가 남음')

        # C1 — 인쇄 · PDF 가 방향·종이·쪽 크기를 넘긴다
        pg.click('[data-pv="print"]'); pg.wait_for_function("window.__prints.length>=1", timeout=5000)
        pr = pg.evaluate("window.__prints[0]")
        o = pr['o']
        if o.get('orient') != 'landscape' or o.get('paper') != 'A4': fail('C1 앱에 넘긴 방향·종이가 %r (A4 가로여야)' % o)
        if abs(o.get('pageW', 0) - 1122.52) > 0.5 or abs(o.get('pageH', 0) - 793.7) > 0.5: fail('C1 앱에 넘긴 쪽 크기가 %r' % o)
        if not o.get('name'): fail('C1 인쇄 이름이 빠짐: %r' % o)
        if not pr['nprint'] or pr['zoom'] != '1' or pr['pad'] != '0px' or abs(pr['pageW'] - 1123) > 1:
            fail('C1/C7 앱이 찍는 순간 조판이 실제 크기·여백 0 이 아님 (줄인 미리보기가 종이에 나감): %r' % pr)
        pg.wait_for_function("!document.body.classList.contains('nprint')", timeout=5000)
        m2 = check_fit(pg, 'C7 인쇄 뒤 미리보기')
        print('C1 앱에 넘김: %s · 찍는 순간 실제 크기(zoom 1 · 여백 0) ok' % {k: (round(v, 1) if isinstance(v, float) else v) for k, v in o.items()})

        # C2 — 종이: '배경 그래픽' 없이 찍어도 검은 송폼 띠·노란 하이라이트가 남는다 (크로미움 PDF · 앱처럼 nprint)
        if shutil.which('pdftoppm'):
            geo = pg.evaluate("""(()=>{const pp=document.querySelector('#printArea .ppage'),R=pp.getBoundingClientRect(),k=CONTI.PG.pw/R.width;
              const box=s=>{const r=pp.querySelector(s).getBoundingClientRect();return [(r.left-R.left)*k,(r.top-R.top)*k,r.width*k,r.height*k]};
              return {form:box('.pform2'),hl:box('.hl')}})()""")
            pg.evaluate("document.body.classList.add('nprint')")
            d = tempfile.mkdtemp(prefix='simfix_print_')
            try:
                pdf = os.path.join(d, 'out.pdf')
                pg.pdf(path=pdf, print_background=False, prefer_css_page_size=True)
                subprocess.run(['pdftoppm', '-r', '96', '-f', '1', '-l', '1', '-png', pdf, os.path.join(d, 'pg')], check=True)
                png = [f for f in os.listdir(d) if f.endswith('.png')][0]
                from PIL import Image
                im = Image.open(os.path.join(d, png)).convert('RGB')
                W, H = im.size
                if abs(W - 1123) > 3 or abs(H - 794) > 3: fail('C2 PDF 쪽이 A4 가로가 아님: %sx%s' % (W, H))
                x, y, w, h = geo['form']
                bar = [im.getpixel((int(x + w - 6 - i * 3), int(y + h / 2))) for i in range(5)]   # 띠 오른쪽 끝 — 글자 없는 곳
                if any(sum(px) > 150 for px in bar): fail('C2 종이에서 검은 송폼 띠가 지워짐: %s' % bar)
                x, y, w, h = geo['hl']
                pts = [im.getpixel((int(x + w * (i + .5) / 12), int(y + h * (j + .5) / 4))) for i in range(12) for j in range(4)]
                yellow = sum(1 for r, g, b_ in pts if r > 180 and g > 150 and b_ < r - 40)
                if yellow < len(pts) * 0.5: fail('C2 종이에서 하이라이트가 사라짐 (노란 점 %d/%d)' % (yellow, len(pts)))
                print('C2 종이(배경 그래픽 끔): 검은 송폼 띠 · 노란 하이라이트(%d/%d) 그대로 ok' % (yellow, len(pts)))
            finally:
                shutil.rmtree(d, ignore_errors=True)
                pg.evaluate("document.body.classList.remove('nprint')")
        else:
            print('C2 종이 픽셀 검사는 건너뜀 (pdftoppm 없음) — print-color-adjust:exact 만 봄')
        close_preview(pg)

        # ---- 보관용(세로)도 방향을 넘긴다 ----
        open_sheet(pg); pg.click('#modal [data-po="mode"][data-v="archive"]'); pg.wait_for_timeout(200)
        preview(pg)
        check_fit(pg, 'C7 보관용 세로 쪽')
        pg.evaluate("window.__prints=[]"); pg.click('[data-pv="print"]'); pg.wait_for_function("window.__prints.length>=1", timeout=5000)
        o = pg.evaluate("window.__prints[0].o")
        if o.get('orient') != 'portrait' or abs(o.get('pageW', 0) - 793.7) > 0.5 or abs(o.get('pageH', 0) - 1122.52) > 0.5:
            fail('C1 보관용(세로) 인쇄에 넘긴 값이 %r' % o)
        pg.wait_for_function("!document.body.classList.contains('nprint')", timeout=5000)
        close_preview(pg)
        print('C1 보관용: 세로 A4 로 넘김 ok')

        # ---- 넓은 화면: 실제 크기 그대로 (F62) ----
        pg.set_viewport_size({'width': 1400, 'height': 950}); pg.wait_for_timeout(300)
        open_sheet(pg); pg.click('#modal [data-po="mode"][data-v="stage"]'); pg.wait_for_timeout(200)
        preview(pg)
        m = pg.evaluate(FIT_JS)
        if abs(m['w'] - m['pw']) > 1 or m['left'] < 0: fail('C7 넓은 화면에서 쪽이 실제 크기가 아님: %s' % m)
        close_preview(pg)
        print('C7 넓은 화면: 실제 크기(%.0fpx) 그대로 ok' % m['w'])

        # ---- 앱 코드: 방향 · 쪽 비율 칸 · 배경 인쇄 (돌려 볼 수 없어 자리만) ----
        sw = open(os.path.join(ROOT, 'ios', 'App', 'App', 'PrinterPlugin.swift'), encoding='utf-8').read()
        for need in ('info.orientation = call.getString("orient") == "landscape" ? .landscape : .portrait',
                     'class PagePrintRenderer: UIPrintPageRenderer', 'override var printableRect: CGRect',
                     'controller.printPageRenderer = renderer', 'shouldPrintBackgrounds = true'):
            if need not in sw: fail('PrinterPlugin.swift 에 %r 가 없음' % need)
        print('PrinterPlugin.swift: 방향 · 쪽 비율 칸(PagePrintRenderer) · 배경 인쇄 자리 ok (실제 인쇄는 시뮬레이터에서)')

        if errs: fail('페이지 오류: %s' % errs[:3])
        b.close()
    print('OK test_simfix_print')

run()
