# 시뮬레이터 점검(편집기) — 폰·아이패드 편집기에서 나온 것들
#  B1  폰(≤820px)에서 도구 바꾸기·사진 추가·유튜브 추가처럼 다시 그릴 때마다 편집기가 맨 위로 튀던 것 (.ws 가 넘기는 칸인데 안 적어 둠)
#  B4·E5  악보 패널 머리가 한 줄로 옆으로 흘러 '조각 추가'·배율·메모 도구가 화면 밖에 숨던 것 (폰 · 아이패드 세로) → 두 줄
#  B12 폰에 '끌어다 놓거나 붙여넣기(⌘V)' 안내 · 금색 '∞ 코드 인식' 알약이 두 번째 코드 인식 단추처럼 보이던 것
#  B11 폰에서 편집기·미리보기의 초안/발행 상태 알약이 통째로 숨고, 한 번도 발행 안 한 초안 미리보기 제목이 '예배'
#  B5  자르기가 마커 절단선을 모두 지우던 것 (말없이 배지 모드)
#  B3  아래 시트(메모 창)가 자판 밑에 남아 입력 칸·저장이 가려지던 것 (iOS 는 코드 포커스에 화면을 안 올린다 — visualViewport 흉내)
#  B7  '이 곡에 항상'(인도자 기본)으로 남긴 섹션 메모가 곡 편집의 '섹션 메모'에 '0개 · 없음'
#  B2  새 곡의 송폼을 쓰다 3초 멈추면 반쪽 값이 라이브러리에 들어가고 이어 친 글자부터 '라이브러리 편곡과 다름'
#  E4  마커를 놓았다 지워 악보가 라이브러리와 똑같아도 '라이브러리 편곡과 다름 · 악보'가 남던 것
# 실행: CONTI_URL=http://localhost:8766/ python tests/test_simfix_editor.py
import os, sys, time
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
tag = str(int(time.time()))[-6:]
def fail(m): print('FAIL:', m); sys.exit(1)

# iOS 자판: 레이아웃 창(innerHeight)은 그대로, 보이는 화면(visualViewport)만 준다. 데스크톱 브라우저로는 못 여니 흉내 낸다
FAKE_VV = """(()=>{const vv=new EventTarget();vv.offsetTop=0;vv.offsetLeft=0;vv.scale=1;vv.pageTop=0;vv.pageLeft=0;
 Object.defineProperty(vv,'height',{get(){return vv._h!=null?vv._h:innerHeight}});
 Object.defineProperty(vv,'width',{get(){return innerWidth}});
 Object.defineProperty(window,'visualViewport',{configurable:true,get(){return vv}});window.__vv=vv})()"""

def signup(pg, user, team):
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=10000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
    pg.check('#lgAgree')
    pg.fill('#lgName', '인도'); pg.fill('#lgUser', user); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam', timeout=10000); pg.fill('#gtTeam', team); pg.click('[data-act="team-create"]')
    pg.wait_for_selector('.shell[data-page]', timeout=10000); pg.wait_for_timeout(800)
    for _ in range(3):
        if pg.locator('#modal .ov').count(): pg.keyboard.press('Escape'); pg.wait_for_timeout(300)

def act(pg, sel):   # 화면 밖(가로로 넘긴 머리 등)에 있어도 누른다 — 누르는 것이 아니라 그 뒤를 보는 검사에 쓴다
    pg.evaluate("(s)=>document.querySelector(s).click()", sel)

def close_modal(pg):
    for _ in range(3):
        if not pg.evaluate("!!document.querySelector('#modal').firstChild"): return
        pg.keyboard.press('Escape'); pg.wait_for_timeout(300)
    fail('창이 안 닫힘')

IT = "CONTI.S.services.find(s=>s.id===CONTI.route().a).items"   # 지금 연 콘티의 곡들

HEAD = """()=>{const ed=document.querySelector('#edsheet');const pt=ed.querySelector('.ptab');const pr=ed.getBoundingClientRect();
 const vis=el=>{if(!el)return null;const r=el.getBoundingClientRect();return r.width>0&&r.left>=pr.left-1&&r.right<=pr.right+1&&r.left>=-1&&r.right<=innerWidth+1};
 const lb=pt.querySelector('label[for=pieceFile]');
 return {over:pt.scrollWidth-pt.clientWidth,cls:ed.className,add:vis(lb),zoom:vis(pt.querySelector('[data-act=edzoom][data-d="1"]')),
  tools:[...pt.querySelectorAll('[data-act=tool]')].map(b=>vis(b)),panelW:Math.round(pr.width)}}"""

def check_head(pg, what):
    h = pg.evaluate(HEAD)
    if h['over'] > 1: fail('%s: 악보 패널 머리가 옆으로 넘침 %s' % (what, h))
    if not h['add']: fail('%s: "조각 추가"가 화면(패널) 밖 %s' % (what, h))
    if not h['zoom']: fail('%s: 배율 단추가 화면 밖 %s' % (what, h))
    if not all(h['tools']) or len(h['tools']) != 5: fail('%s: 도구 단추 중 화면 밖이 있음 %s' % (what, h))
    return h

def ws_top(pg): return pg.evaluate("document.querySelector('#ws').scrollTop")

def srv_arr(c, team, title):
    for s in c.request.get(URL + 'api/songs?team=' + team).json()['songs']:
        if s['title'] == title: return s['arrangements'][0]
    return None

def srv_wait(pg, c, team, title, want, ms=12000):   # 3초 디바운스 + 새 콘티는 초안 올리기(2.5초)가 한 번 더 미룬다
    t = time.time() + ms / 1000.0; a = None
    while time.time() < t:
        a = srv_arr(c, team, title)
        if a and a['form'] == want: return a
        pg.wait_for_timeout(500)
    return a

def wait_for(pg, js, ms=12000, what=''):
    try: pg.wait_for_function(js, timeout=ms)
    except Exception: fail('기다려도 안 됨: %s (%s)' % (what, js))

def run():
    with sync_playwright() as p:
        b = p.chromium.launch(); errs = []

        # ================= 컴퓨터: 끌어 놓기·붙여넣기 안내는 그대로 (B12 반대쪽) =================
        cd = b.new_context(viewport={'width': 1366, 'height': 900}); pd = cd.new_page()
        pd.on('pageerror', lambda e: errs.append(str(e))); pd.on('dialog', lambda d: d.accept())
        signup(pd, 'sfd' + tag, '컴퓨터팀')
        pd.click('[data-act="new-svc"]'); pd.wait_for_selector('[data-f="svc.name"]', timeout=8000)
        pd.click('[data-act="add-item"]'); pd.wait_for_selector('[data-f="item.title"]')
        pd.fill('[data-f="item.title"]', '컴퓨터곡'); pd.wait_for_timeout(300)
        pd.set_input_files('#pieceFile', [SHEET])
        pd.wait_for_function("(()=>{const p=(%s[0].pieces||[])[0];return p&&p.w>0})()" % IT, timeout=60000)
        pd.wait_for_selector('#edsheet .pfoot', timeout=10000); pd.wait_for_timeout(400)
        hint = pd.locator('#edsheet .pfoot .hint').inner_text()
        if '붙여넣기' not in hint: fail('B12 컴퓨터에서 끌어 놓기·붙여넣기 안내가 사라짐: %r' % hint)
        if 'narrow' in pd.evaluate("document.querySelector('#edsheet').className"): fail('B4 넓은 화면인데 악보 머리가 두 줄')
        cd.close()
        print('B12 컴퓨터 안내 그대로 · 넓은 화면 한 줄 ok')

        # ================= 폰 =================
        c = b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
        c.add_init_script(FAKE_VV)
        pg = c.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
        signup(pg, 'sfe' + tag, '폰편집팀')
        team = pg.evaluate('CONTI.S.team.id')
        act(pg, '[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
        act(pg, '[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]')
        pg.fill('[data-f="item.title"]', '폰곡' + tag); pg.fill('[data-f="item.key"]', 'G')
        pg.locator('[data-f="item.title"]').blur(); pg.wait_for_timeout(300)
        sid = pg.evaluate("CONTI.route().a")

        # ---- B4: 빈 악보 — 머리가 한 줄에 안 들어가면 두 줄, 조각 추가·도구·배율이 다 보인다 · 빈 칸에도 조각 추가 ----
        h = check_head(pg, 'B4 폰 빈 악보')
        if 'narrow' not in h['cls']: fail('B4 폰인데 두 줄이 아님 %s' % h)
        if not pg.locator('#sheet label[for=pieceFile]').count(): fail('B4 빈 악보 안내에 "조각 추가" 단추가 없음')
        pg.set_viewport_size({'width': 360, 'height': 780}); pg.wait_for_timeout(400)
        h = check_head(pg, 'B4 좁은 폰(360)')
        pg.set_viewport_size({'width': 390, 'height': 844}); pg.wait_for_timeout(400)
        print('B4 폰 악보 머리 두 줄 ok', h)

        # ---- 사진 추가 (B1: 추가한 뒤에도 보던 자리) ----
        pg.evaluate("(()=>{const w=document.querySelector('#ws');w.scrollTop=document.querySelector('#edsheet').offsetTop-20})()")
        pg.wait_for_timeout(200); y0 = ws_top(pg)
        if y0 < 400: fail('B1 준비: 악보 패널까지 넘기지 못함 (%d)' % y0)
        pg.set_input_files('#pieceFile', [SHEET])
        pg.wait_for_function("(()=>{const p=(%s[0].pieces||[])[0];return p&&p.w>0})()" % IT, timeout=60000)
        pg.wait_for_selector('#sheet .slice', timeout=10000); pg.wait_for_timeout(700)
        y1 = ws_top(pg)
        if abs(y1 - y0) > 40: fail('B1 사진을 추가하니 편집기가 다른 자리로 튐: %d → %d' % (y0, y1))
        print('B1 사진 추가 뒤 자리 ok', y0, y1)

        # ---- B1: 도구 바꾸기 — 진짜 탭 ----
        pg.evaluate("(()=>{const w=document.querySelector('#ws');w.scrollTop=document.querySelector('#edsheet').offsetTop-4})()")
        pg.wait_for_timeout(200); y0 = ws_top(pg)
        for t in ('hl', 'mask', 'memo', 'chord', 'marker'):
            pg.locator('[data-act="tool"][data-t="%s"]' % t).scroll_into_view_if_needed(); pg.wait_for_timeout(100)
            if abs(ws_top(pg) - y0) > 2: fail('B1 준비: 도구 단추가 화면 밖 (%d → %d)' % (y0, ws_top(pg)))
            pg.tap('[data-act="tool"][data-t="%s"]' % t); pg.wait_for_timeout(350)
            if pg.evaluate("document.querySelector('[data-act=tool].on').dataset.t") != t: fail('B1 준비: 도구 %s 가 안 골라짐' % t)
            y = ws_top(pg)
            if abs(y - y0) > 2: fail('B1 도구 %s 를 누르니 편집기가 맨 위로 튐: %d → %d' % (t, y0, y))
        check_head(pg, 'B4 사진 있는 폰')
        print('B1 도구 바꿔도 자리 그대로 ok', y0)

        # ---- B1: 유튜브 추가 ----
        pg.evaluate("document.querySelector('#ytUrl').scrollIntoView({block:'center'})"); pg.wait_for_timeout(200)
        y0 = ws_top(pg)
        if y0 < 200: fail('B1 준비: 유튜브 칸까지 넘기지 못함 (%d)' % y0)
        pg.fill('#ytUrl', 'https://youtu.be/dQw4w9WgXcQ'); pg.tap('[data-act="add-yt"]'); pg.wait_for_timeout(600)
        if pg.evaluate("%s[0].media.length" % IT) != 1: fail('B1 준비: 유튜브가 안 들어감')
        y1 = ws_top(pg)
        if abs(y1 - y0) > 2: fail('B1 유튜브를 추가하니 편집기가 튐: %d → %d' % (y0, y1))
        print('B1 유튜브 추가 뒤 자리 ok', y0, y1)

        # ---- B12: 폰 — 끌어 놓기·⌘V 안내 없음 · 무제한은 알약 하나('∞ 무제한'), 단추는 그냥 '코드 인식' ----
        hint = pg.locator('#edsheet .pfoot .hint').inner_text()
        if '붙여넣기' in hint or '⌘V' in hint: fail('B12 폰에 컴퓨터용 안내: %r' % hint)
        unl = pg.evaluate("CONTI.PLANQ.ocr.cap==null")
        if unl:
            pill = pg.locator('#sheet .cb-credit').first.inner_text().strip()
            btn = pg.locator('#sheet [data-act="ocr"]').first.inner_text().strip()
            if '코드 인식' in pill: fail('B12 무제한 알약이 또 "코드 인식"이라 단추처럼 읽힘: %r' % pill)
            if '무제한' not in pill: fail('B12 무제한 알약에 무제한이 없음: %r' % pill)
            if '무제한' in btn: fail('B12 단추에도 무제한이 한 번 더: %r' % btn)
            print('B12 무제한 알약 하나 ok', pill, '|', btn)
        print('B12 폰 안내 ok', hint)

        # ---- B11: 폰에서도 상태 알약 · 미리보기 제목 ----
        st = pg.evaluate("(()=>{const e=document.querySelector('.top h1 .pill.st');const r=e&&e.getBoundingClientRect();return e&&{t:e.innerText.trim(),w:r.width,r:r.right}})()")
        if not st or st['w'] < 10 or st['r'] > 391: fail('B11 폰 편집기에서 초안 상태가 안 보임: %s' % st)
        if st['t'] != '초안': fail('B11 폰 편집기 상태 글: %s' % st)
        want = pg.evaluate("document.querySelector('[data-f=\"svc.name\"]').placeholder")
        act(pg, '[data-act="view-svc"]'); pg.wait_for_selector('.top h1 .vttl', timeout=8000); pg.wait_for_timeout(400)
        v = pg.evaluate("(()=>{const e=document.querySelector('.top h1 .pill.st');const r=e&&e.getBoundingClientRect();return {t:e&&e.innerText.trim(),w:r&&r.width,r:r&&r.right,ttl:document.querySelector('.top h1 .vttl').innerText.trim()}})()")
        if not v['w'] or v['w'] < 10 or v['r'] > 391: fail('B11 폰 미리보기에서 초안 표시가 안 보임: %s' % v)
        if v['t'] != '초안': fail('B11 폰 미리보기 상태 글: %s' % v)
        if v['ttl'] != want or v['ttl'] == '예배': fail('B11 미발행 초안 미리보기 제목이 편집기와 다름: %r ≠ %r' % (v['ttl'], want))
        pg.set_viewport_size({'width': 1200, 'height': 844}); pg.wait_for_timeout(300)
        wide = pg.locator('.top h1 .pill.st').inner_text().strip()
        if wide != '미발행 초안': fail('B11 넓은 화면 미리보기 상태가 바뀜: %r' % wide)
        pg.set_viewport_size({'width': 390, 'height': 844}); pg.wait_for_timeout(300)
        act(pg, '.top [data-act="edit-svc"]'); pg.wait_for_selector('#edsheet', timeout=8000); pg.wait_for_timeout(500)
        print('B11 폰 상태 알약 · 미리보기 제목 ok', st, v)

        # ---- B5: 자르기 뒤에도 절단선 ----
        pg.evaluate("""(()=>{const it=%s[0];const p=it.pieces[0];
          const yA=Math.round(p.h*0.5),yB=Math.round(p.h*0.3),yC=Math.round(p.h*0.7);
          const cA=CONTI.autoCut(p,yA);
          p.markers=[{id:'mA',label:'A',x:Math.round(p.w*0.3),y:yA,cut:cA},
                     {id:'mB',label:'B',x:Math.round(p.w*0.3),y:yB,cut:Math.round(p.h*0.03)},
                     {id:'mC',label:'C',x:Math.round(p.w*0.3),y:yC,cut:null}];
          CONTI.save();CONTI.render()})()""" % IT)
        pg.wait_for_selector('#sheet .mkabs[data-marker="mC"]', timeout=8000); pg.wait_for_timeout(300)
        m0 = pg.evaluate("%s[0].pieces[0].markers.map(m=>({id:m.id,y:m.y,cut:m.cut}))" % IT)
        if m0[0]['cut'] is None or not (m0[0]['cut'] > m0[0]['y'] * 0.3): fail('B5 준비: A 의 절단선이 자를 선 아래가 아님 %s' % m0)
        P0 = pg.evaluate("(()=>{const p=%s[0].pieces[0];return {w:p.w,h:p.h}})()" % IT)
        act(pg, '[data-act="crop-piece"]'); pg.wait_for_selector('#cropImg', timeout=8000)
        pg.wait_for_function("document.querySelector('#cropImg').complete&&document.querySelector('#cropImg').naturalWidth>0", timeout=8000)
        pg.wait_for_timeout(500)
        r = pg.evaluate("(()=>{const r=document.querySelector('#cropImg').getBoundingClientRect();return {x:r.left,y:r.top,w:r.width,h:r.height}})()")
        FX0, FY0, FX1, FY1 = 0.0, 0.2, 1.0, 1.0
        x0, y0_, x1, y1_ = r['x'] + 1, r['y'] + r['h'] * FY0, r['x'] + r['w'] - 1, r['y'] + r['h'] - 1
        pg.mouse.move(x0, y0_); pg.mouse.down(); pg.mouse.move((x0 + x1) / 2, (y0_ + y1_) / 2, steps=4); pg.mouse.move(x1, y1_, steps=4); pg.mouse.up()
        pg.wait_for_timeout(200)
        pg.click('#cpOk')
        pg.wait_for_function("%s[0].pieces[0].h!==%d" % (IT, P0['h']), timeout=30000); pg.wait_for_timeout(800)
        # 고른 틀(사진 비율)을 거꾸로 셈 — 앱과 같은 식 (R = (마우스-사진 왼·위)/사진 폭·높이)
        sy = round(((y0_ - r['y']) / r['h']) * P0['h'])
        m1 = pg.evaluate("(()=>{const p=%s[0].pieces[0];return {h:p.h,ms:p.markers.map(m=>({id:m.id,y:m.y,cut:m.cut,auto:CONTI.autoCut(p,m.y)}))}})()" % IT)
        ms = {m['id']: m for m in m1['ms']}
        if set(ms) != {'mA', 'mB', 'mC'}: fail('B5 준비: 자르며 마커가 빠짐 %s' % m1)
        A, B, C = ms['mA'], ms['mB'], ms['mC']
        if A['cut'] is None: fail('B5 자르니 A 의 절단선이 지워짐(배지 모드) %s' % m1)
        dy0 = m0[0]['y'] - m0[0]['cut']
        if abs((A['y'] - A['cut']) - dy0) > 3: fail('B5 A 절단선이 마커와 같이 안 옮겨짐: 전 %d · 뒤 %d (%s)' % (dy0, A['y'] - A['cut'], m1))
        if abs(A['cut'] - (m0[0]['cut'] - sy)) > 4: fail('B5 A 절단선 자리: %s (예상 %d)' % (A, m0[0]['cut'] - sy))
        if B['cut'] != B['auto']: fail('B5 잘려 나간 쪽 절단선(B)을 새 여백으로 다시 잡지 않음: %s' % B)
        if C['cut'] is not None: fail('B5 배지 모드였던 C 에 절단선이 생김: %s' % C)
        pg.evaluate("CONTI.render()"); pg.wait_for_timeout(300)
        act(pg, '[data-act="tool"][data-t="marker"]'); pg.wait_for_timeout(300)
        if pg.locator('#sheet .cutline[data-cut="mA"]').count() != 1: fail('B5 자른 뒤 마커 도구에서 A 절단선이 안 그려짐')
        print('B5 자르기 뒤 절단선 ok', m0, m1)

        # ---- 라이브러리 곡이 만들어지길 기다린다 (B7 의 '이 곡에 항상'은 곡이 있어야 한다) ----
        wait_for(pg, "!!%s[0].arrId" % IT, 15000, '폰곡이 라이브러리에 만들어짐')

        # ---- B3: 메모 창 — 자판이 올라오면 시트가 그 위로 ----
        act(pg, '[data-act="tool"][data-t="memo"]'); pg.wait_for_timeout(300)
        pg.evaluate("document.querySelector('#sheet .mkabs[data-marker=\"mA\"]').scrollIntoView({block:'center'})"); pg.wait_for_timeout(200)
        pg.tap('#sheet .mkabs[data-marker="mA"]'); pg.wait_for_selector('#cText', timeout=6000); pg.wait_for_timeout(300)
        if pg.evaluate("document.activeElement&&document.activeElement.id") != 'cText': fail('B3 준비: 메모 칸에 커서가 안 감')
        VV = 844 - 350   # 자판 350
        pg.evaluate("(h)=>{window.__vv._h=h;window.__vv.dispatchEvent(new Event('resize'))}", VV); pg.wait_for_timeout(300)
        k = pg.evaluate("""(()=>{const r=e=>{const b=document.querySelector(e).getBoundingClientRect();return [Math.round(b.top),Math.round(b.bottom)]};
          return {inp:r('#cText'),sheet:r('#modal .sheetm'),up:document.documentElement.classList.contains('kbup')}})()""")
        if not k['up']: fail('B3 자판이 올라와도 시트를 안 올림 %s' % k)
        if k['inp'][1] > VV or k['inp'][0] < 0: fail('B3 메모 칸이 자판 밑(보이는 화면 %d 밖): %s' % (VV, k))
        if k['sheet'][1] > VV + 1: fail('B3 시트 바닥이 자판 밑: %s' % k)
        pg.fill('#cText', '천천히 들어가기')
        # 시트 안에서 넘겨 저장 단추를 보이는 화면 안으로 가져올 수 있다
        sv = pg.evaluate("(()=>{const s=document.querySelector('#cSave');s.scrollIntoView({block:'nearest'});const b=s.getBoundingClientRect();return [Math.round(b.top),Math.round(b.bottom)]})()")
        if sv[1] > VV + 1: fail('B3 저장 단추를 자판 위로 못 가져옴: %s' % sv)
        pg.evaluate("()=>{window.__vv._h=null;window.__vv.dispatchEvent(new Event('resize'))}"); pg.wait_for_timeout(200)
        if pg.evaluate("document.documentElement.classList.contains('kbup')"): fail('B3 자판이 내려가도 시트가 떠 있음')
        pg.evaluate("()=>{window.__vv._h=%d;window.__vv.dispatchEvent(new Event('resize'))}" % VV); pg.wait_for_timeout(200)
        print('B3 자판 위 메모 창 ok', k)

        # ---- B7: '이 곡에 항상'(기본)으로 저장 → 섹션 메모에 보이고 지울 길이 있다 ----
        if not pg.locator('#cWhen [data-w2="always"].on').count(): fail('B7 준비: 인도자 기본이 "이 곡에 항상"이 아님')
        pg.tap('#cSave')
        wait_for(pg, "(%s[0]&&CONTI.arrOfItem(%s[0])&&(CONTI.arrOfItem(%s[0]).notes||[]).length===1)" % (IT, IT, IT), 10000, '고정 메모 저장')
        pg.evaluate("()=>{window.__vv._h=null;window.__vv.dispatchEvent(new Event('resize'))}")
        pg.wait_for_timeout(600)
        sec = pg.evaluate("(()=>{const l=[...document.querySelectorAll('.lbl')].find(x=>x.textContent.startsWith('섹션 메모'));return {lbl:l&&l.innerText,list:document.querySelector('#secMemo').innerText}})()")
        if '1개' not in (sec['lbl'] or ''): fail('B7 "이 곡에 항상" 메모가 섹션 메모 개수에 없음: %s' % sec)
        if '천천히 들어가기' not in sec['list'] or '이 곡에 항상' not in sec['list']: fail('B7 섹션 메모 목록에 곡 메모가 없음: %s' % sec)
        if pg.evaluate("%s[0].notes.length" % IT) != 0: fail('B7 준비: 이번 예배 메모로 저장됨')
        act(pg, '#secMemo [data-act="fx-note"]'); pg.wait_for_selector('#fnAll', timeout=5000)
        if '천천히 들어가기' not in pg.locator('#modal').inner_text(): fail('B7 곡 메모 메뉴가 다른 메모')
        close_modal(pg)
        print('B7 섹션 메모 ok', sec)

        # ================= B2: 새 곡을 쓰는 동안은 라이브러리가 따라온다 =================
        act(pg, '[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]'); pg.wait_for_timeout(300)
        T2 = '새노래' + tag
        pg.fill('[data-f="item.title"]', T2); pg.locator('[data-f="item.title"]').blur()
        wait_for(pg, "!!%s[1].arrId" % IT, 15000, '새 곡이 라이브러리에 만들어짐')
        pg.tap('[data-f="item.form"]'); pg.keyboard.type('A1 - b', delay=40)
        a = srv_wait(pg, c, team, T2, 'A1 - b')   # 멈춤 → 반쪽이 라이브러리로 간다 (여기까지는 원래도 된다)
        if not a or a['form'] != 'A1 - b': fail('B2 준비: 멈춘 사이 송폼이 라이브러리로 안 감: %s' % (a and a['form']))
        pg.tap('[data-f="item.form"]'); pg.keyboard.press('End'); pg.keyboard.type(' - c', delay=40)
        pg.wait_for_timeout(300)
        ov = pg.evaluate("JSON.stringify(%s[1].ov||{})" % IT)
        if 'form' in ov: fail('B2 방금 만든 곡을 마저 쓰는데 덮어쓰기로 표시: %s' % ov)
        if pg.locator('.ovbar').count(): fail('B2 방금 만든 곡에 "라이브러리 편곡과 다름": %s' % pg.locator('.ovbar').inner_text())
        a = srv_wait(pg, c, team, T2, 'A1 - b - c')
        if a['form'] != 'A1 - b - c': fail('B2 다 쓴 송폼이 라이브러리에 안 감 (반쪽이 남음): %r' % a['form'])
        if pg.locator('.ovbar').count(): fail('B2 다 쓴 뒤 "라이브러리 편곡과 다름"')
        print('B2 쓰는 동안 라이브러리가 따라옴 ok', a['form'])

        # 편집기를 떠나면 끝난다 — 다음에 고치는 것은 이 예배에서만 (원래 덮어쓰기 규칙)
        pg.evaluate("CONTI.go('home')"); pg.wait_for_timeout(4500)
        pg.evaluate("CONTI.go('edit/%s')" % sid); pg.wait_for_selector('#edsheet', timeout=8000); pg.wait_for_timeout(600)
        act(pg, '.list-item[data-id="%s"]' % pg.evaluate("%s[1].id" % IT)); pg.wait_for_timeout(400)
        pg.tap('[data-f="item.form"]'); pg.keyboard.press('End'); pg.keyboard.type(' - d', delay=30); pg.wait_for_timeout(300)
        if not pg.locator('.ovbar').count() or '송폼' not in pg.locator('.ovbar').inner_text(): fail('B2 편집기를 떠났다 온 뒤 고친 송폼이 덮어쓰기로 안 잡힘')
        pg.wait_for_timeout(4000)
        a = srv_arr(c, team, T2)
        if a['form'] != 'A1 - b - c': fail('B2 떠났다 온 뒤 고친 송폼이 라이브러리로 샘: %r' % a['form'])
        act(pg, '[data-act="ov-revert"]'); pg.wait_for_timeout(500)
        if pg.evaluate("%s[1].form" % IT) != 'A1 - b - c' or pg.locator('.ovbar').count(): fail('B2 되돌리기 실패')
        print('B2 떠난 뒤는 덮어쓰기 ok')

        # ================= E4: 마커를 놓았다 지우면 표시도 사라진다 =================
        act(pg, '.list-item[data-id="%s"]' % pg.evaluate("%s[0].id" % IT)); pg.wait_for_timeout(500)
        wait_for(pg, "!Object.keys(%s[0].ov||{}).some(k=>%s[0].ov[k])" % (IT, IT), 10000, '폰곡이 라이브러리와 같아짐')
        if pg.locator('.ovbar').count(): fail('E4 준비: 처음부터 "라이브러리 편곡과 다름": %s' % pg.locator('.ovbar').inner_text())
        act(pg, '[data-act="tool"][data-t="marker"]'); pg.wait_for_timeout(300)
        pt = pg.evaluate("""(()=>{const s=[...document.querySelectorAll('#sheet .slice')].pop();s.scrollIntoView({block:'center'});const r=s.getBoundingClientRect();
          return {x:r.left+r.width*0.8,y:r.top+r.height*0.6}})()""")
        pg.wait_for_timeout(200)
        pg.mouse.click(pt['x'], pt['y']); pg.wait_for_selector('#modal [data-l="D"]', timeout=5000)
        pg.click('#modal [data-l="D"]'); pg.wait_for_timeout(300)
        n = pg.evaluate("%s[0].pieces[0].markers.length" % IT)
        if n != 4: fail('E4 준비: 마커가 안 놓임 (%d)' % n)
        wait_for(pg, "!!(%s[0].ov||{}).pieces" % IT, 10000, '마커를 놓은 악보가 덮어쓰기로 잡힘')
        pg.wait_for_selector('.ovbar', timeout=3000)
        mid = pg.evaluate("%s[0].pieces[0].markers.find(m=>m.label==='D').id" % IT)
        pg.evaluate("document.querySelector('#sheet .mkabs[data-marker=\"%s\"]').scrollIntoView({block:'center'})" % mid); pg.wait_for_timeout(200)
        pg.tap('#sheet .mkabs[data-marker="%s"]' % mid); pg.wait_for_selector('#mmDel', timeout=5000)
        pg.click('#mmDel'); pg.wait_for_timeout(500)
        if pg.locator('.ovbar').count(): fail('E4 마커를 지워 라이브러리와 같은데 "라이브러리 편곡과 다름"이 남음: %s' % pg.locator('.ovbar').inner_text())
        pg.wait_for_timeout(4500)
        ov = pg.evaluate("JSON.stringify(%s[0].ov||{})" % IT)
        if 'pieces' in ov and 'true' in ov: fail('E4 밀고 난 뒤에도 악보 덮어쓰기 표시: %s' % ov)
        pg.evaluate("CONTI.go('home')"); pg.wait_for_timeout(500)
        pg.evaluate("CONTI.go('edit/%s')" % sid); pg.wait_for_selector('#edsheet', timeout=8000); pg.wait_for_timeout(600)
        act(pg, '.list-item[data-id="%s"]' % pg.evaluate("%s[0].id" % IT)); pg.wait_for_timeout(400)
        if pg.locator('.ovbar').count(): fail('E4 다시 연 편집기에 "라이브러리 편곡과 다름": %s' % pg.locator('.ovbar').inner_text())
        print('E4 마커 놓았다 지운 뒤 표시 없음 ok')

        # ================= E5: 아이패드 세로 (창이 넓어도 악보 칸이 좁다) =================
        pg.set_viewport_size({'width': 1024, 'height': 1366}); pg.wait_for_timeout(600)
        h = check_head(pg, 'E5 아이패드 세로')
        if 'narrow' not in h['cls']: fail('E5 아이패드 세로에서 두 줄이 아님 %s' % h)
        pg.set_viewport_size({'width': 1366, 'height': 1024}); pg.wait_for_timeout(600)
        h2 = check_head(pg, 'E5 아이패드 가로')
        print('E5 아이패드 세로·가로 머리 ok', h, h2)

        if errs: fail('페이지 오류:\n' + '\n'.join(errs[:6]))
        b.close()
    print('OK test_simfix_editor')

run()
