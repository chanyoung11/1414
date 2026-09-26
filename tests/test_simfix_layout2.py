# 아이폰·아이패드 시뮬레이터 재점검(2026-09-26) — 화면 배치 회귀 검사
#   E7  가로 아이패드(11인치) + 광고 배너(90px): 연습 미디어 칸이 432px 인데 내용이 527px — 영상이 줄지 않아 재생·±5 단추가 칸 끝에 반쯤 잘림
#       → 영상 높이를 남는 자리에 맞춰 줄인다(16:9 그대로) · 120px 아래로 줄어야 하면(아이패드 미니 가로 + 배너) 왼쪽 칸을 한 줄로 흘린다
#   N7  가로 폰 + 배너(50px): 시간 줄·여기에 메모가 14px 만 보임 → 영상 + 재생 단추 + 시간 줄이 첫 화면에 (배너가 늦게 떠도 다시 잰다)
#   N8·N12 무대 편집: 화면 맨 위 블록의 '송폼 1' 이름표가 무대 바 밑에 반쯤 숨음 → 캔버스 안(바 아래)
#   N6  폰 인쇄 미리보기: zoom 으로 줄이면 웹킷이 글자를 최소 크기(9px)로 되돌려 키워 쪽보다 2.5배 큰 글자 — 메모 띠가 송폼 띠 밑에 끼고
#       마커 원이 납작 → transform 으로 줄인다(글자 크기·자리 = 종이) · 가로 스크롤 없음 · 찍을 때는 실제 크기
#   N5·N9 폰 편집기: '라이브러리 편곡과 다름' 띠가 동기화 몇 초 뒤에 생기며(마커·하이라이트 뒤) 아래 악보를 66pt 밀어 다음 획이 엉뚱한 데
#       → 띠를 지나쳐 내려와 있으면 스크롤을 옮겨 보던 것을 제자리에 (다시 그릴 때도) · 띠가 보이는 중이면 띠가 보이게 둔다
#   N10 폰 곡 상세: 긴 제목이 글자 중간에서 … 없이 잘림 → 제목을 .vttl 로 싸서 … (재구성 악보 머리도)
#   N11 로마자 이름 뒤 조사: 'Qadrum가 드럼으로 들어왔어요' → 'Qadrum이' (서버·앱) · '으로/로' 는 ㄹ 받침이면 '로'(보컬로 · Paul로 · 1로)
#   N2  아래 시트를 화면 아래 끝(홈 인디케이터 자리)까지 끌어 놓으면 iOS 가 touchend 를 쥐고 있어 반쯤 내려간 채 멈춤
#       → 끝 근처에서 멈추면 0.45초 뒤 놓은 것으로 · 끝나지 않은 끌기 뒤에 온 touchstart 도 먼저 그 끌기를 끝낸다
# 사용: CONTI_URL=http://localhost:8766/ .venv/bin/python tests/test_simfix_layout2.py   (SOFT=1 이면 실패해도 끝까지 · BROWSER=chromium · PART=e7,n6)
#   기본은 웹킷(아이폰·아이패드와 같은 엔진 — N6 글자 부풀림은 웹킷에서만 재현된다). 웹킷이 없으면 크로미움으로 돌고 N6 글자 크기만 건너뛴다
import os, sys, time, json
from playwright.sync_api import sync_playwright
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
SOFT = os.environ.get('SOFT') == '1'
H = {'x-conti': '1'}
tag = str(int(time.time()))[-6:]
FAILS = []
def fail(m):
    print('FAIL:', m)
    if SOFT: FAILS.append(m); return
    sys.exit(1)

YT = 'jNQXAC9IVRw'
LONG = '주님의 크신 사랑 영원히 노래합니다 할렐루야 아멘 영광'

def new_page(br, vp, state=None, touch=False, errs=None):
    ctx = br.new_context(viewport=vp, has_touch=touch, storage_state=state)
    pg = ctx.new_page()
    pg.route('**/*youtube*/**', lambda r: r.fulfill(status=200, body='<html></html>', content_type='text/html'))
    pg.on('dialog', lambda d: d.accept())
    if errs is not None: pg.on('pageerror', lambda e: errs.append(repr(e)[:300]))
    return ctx, pg

def signup(pg, uid, name):
    pg.wait_for_selector('#lgUser', timeout=15000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
    pg.fill('#lgName', name); pg.fill('#lgUser', uid); pg.fill('#lgPass', 'secret12'); pg.click('[data-act="lg-submit"]')

def seed(br, errs):
    ctx, pg = new_page(br, {'width': 1366, 'height': 900}, errs=errs)
    pg.goto(URL); signup(pg, 'lay' + tag, '하은')
    pg.wait_for_selector('#gtTeam', timeout=15000); pg.fill('#gtTeam', '배치팀'); pg.click('#gtSess .q:has-text("건반")')
    pg.click('[data-act="team-create"]'); pg.wait_for_selector('.shell[data-page]', timeout=15000)
    team = pg.evaluate('CONTI.S.team.id'); link = pg.evaluate("location.origin+location.pathname+'#/join/'+CONTI.S.team.invite")
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
    pg.fill('[data-f="svc.name"]', '배치 예배'); pg.wait_for_timeout(300)
    for n, t in enumerate(['Afresh', '주님 찬양', 'QA 세번째 곡']):
        pg.click('[data-act="add-item"]'); pg.wait_for_timeout(400)
        pg.fill('[data-f="item.title"]', t); pg.fill('[data-f="item.key"]', 'GDE'[n]); pg.fill('[data-f="item.form"]', 'Intro – A – B – A – Outro')
        pg.wait_for_timeout(300)
    pg.evaluate("""(a)=>{const s=CONTI.S.services.find(x=>x.name==='배치 예배');
      s.items[0].media=[{id:'ytL2',type:'youtube',url:'https://youtu.be/'+a,name:'전체 영상',notes:[
        {id:'tn1',t:12,text:'여기서 들어가기',layer:'leader'},{id:'tn2',t:40,text:'브릿지 조용히',layer:'leader'},{id:'tn3',t:70,text:'끝 반복',layer:'leader'}]}];
      CONTI.save()}""", YT)
    pg.wait_for_timeout(2500)   # 곡이 라이브러리에 들어가게(편곡 연결)
    pg.click('[data-act="publish"]'); pg.wait_for_selector('#pubOnly', timeout=8000)
    pg.click('#pubOnly'); pg.wait_for_timeout(3000)
    sid = pg.evaluate("CONTI.S.services.find(x=>x.name==='배치 예배').id")
    if not pg.evaluate("(sid)=>CONTI.S.services.find(x=>x.id===sid).items[0].arrId", sid): fail('준비: 첫 곡이 라이브러리 편곡에 안 이어짐')
    state = ctx.storage_state()
    ctx.close()
    return sid, state, team, link

def go_view(pg, sid):
    pg.goto(URL + '#/view/' + sid)
    pg.wait_for_selector('[data-act="play"][data-stage="1"]', timeout=15000); pg.wait_for_timeout(700)

def insets(pg, sat=0, sab=0, sal=0, sar=0):
    pg.evaluate("""(v)=>{const d=document.documentElement.style;['sat','sab','sal','sar'].forEach((k,i)=>d.setProperty('--'+k,v[i]+'px'))}""", [sat, sab, sal, sar])

def banner(pg, h):
    pg.evaluate("(h)=>{if(h){document.documentElement.style.setProperty('--adh',h+'px');document.body.classList.add('hasad')}else document.body.classList.remove('hasad')}", h)
    pg.wait_for_timeout(350)   # ResizeObserver → 다음 프레임에 fitPlay

PLAY_M = """()=>{const R=e=>{const r=e.getBoundingClientRect();return [r.top,r.bottom,r.left,r.right]};const st=document.getElementById('stack'),pb=document.querySelector('.panel.media>.pbody');
  const flow=st.classList.contains('flow'),v=document.querySelector('#mediaBox .vid');
  const lim=flow?R(st)[1]:Math.min(R(st)[1],R(document.querySelector('.panel.media'))[1],R(pb)[1]);
  const tl=document.getElementById('tlist');
  return {flow,lim,top:R(st)[0],vid:R(v),play:R(document.getElementById('playBtn')),b5:R(document.querySelector('[data-act=skip][data-d="-5"]')),
    tnote:R(document.querySelector('[data-act=tnote]')),ytfb:R(document.getElementById('ytfb')),inner:[pb.scrollHeight,pb.clientHeight],
    tl:[tl.clientHeight,tl.scrollHeight],capped:v.classList.contains('capped')}}"""

def check_play(pg, label, want_flow=None):
    r = pg.evaluate(PLAY_M)
    for k in ['play', 'b5', 'tnote']:
        if r[k][1] > r['lim'] + 1 or r[k][0] < r['top'] - 1: fail('%s: %s 가 칸 밖(잘림) %s' % (label, k, r))
    vh, vw = r['vid'][1] - r['vid'][0], r['vid'][3] - r['vid'][2]
    if r['vid'][1] > r['lim'] + 1: fail('%s: 영상이 칸 밖 %s' % (label, r))
    if vh < (72 if r['flow'] else 110): fail('%s: 영상이 너무 작음 %.0fpx %s' % (label, vh, r))
    if r['capped'] and abs(vw / vh - 16 / 9) > 0.04: fail('%s: 줄인 영상이 16:9 가 아님 %.0fx%.0f' % (label, vw, vh))
    if not r['flow']:
        if r['inner'][0] > r['inner'][1] + 1: fail('%s: 미디어 칸 속이 넘침(속 스크롤) %s' % (label, r['inner']))
        if r['ytfb'][1] > r['lim'] + 1: fail('%s: 유튜브에서 열기가 칸 밖 %s' % (label, r))
        if r['tl'][0] < min(60, r['tl'][1]) - 1: fail('%s: 타임라인 목록이 두 줄도 안 보임 %s' % (label, r['tl']))
    if want_flow is not None and r['flow'] != want_flow: fail('%s: 한 줄로 흘리기(.flow)가 %s 여야 %s' % (label, want_flow, r))
    return r, vh

def e7(br, ctx0, errs):
    sid, state = ctx0['sid'], ctx0['state']
    # (폭, 높이, 폰, 위·아래·옆 안전 영역, 배너, 흘려야 하나)
    cases = [(1194, 834, False, (24, 20, 0, 0), 90, False),    # 11인치 가로 + 리더보드 (E7)
             (1180, 820, False, (24, 20, 0, 0), 90, False),    # 10.9인치 가로 + 리더보드
             (1133, 744, False, (24, 20, 0, 0), 90, True),     # 미니 가로 + 리더보드 → 한 줄로
             (1366, 1024, False, (24, 20, 0, 0), 90, False),   # 13인치 — 줄일 필요 없음
             (874, 402, True, (0, 21, 62, 62), 50, True),      # 아이폰 16 Pro 가로 + 배너 (N7)
             (844, 390, True, (0, 21, 47, 47), 50, True)]      # 아이폰 16 가로 + 배너
    for w, h, mob, ins, adh, flow in cases:
        ctx, pg = new_page(br, {'width': w, 'height': h}, state, mob, errs)
        go_view(pg, sid); insets(pg, *ins)
        pg.goto(URL + '#/play/%s/0' % sid); pg.wait_for_selector('#playBtn', timeout=15000); pg.wait_for_timeout(900)
        label = '%dx%d' % (w, h)
        _, v0 = check_play(pg, label + ' 배너 없음')
        banner(pg, adh)   # 배너는 연습 화면을 연 뒤에 들어온다 — 칸이 줄면 다시 잰다
        _, v1 = check_play(pg, label + ' + 배너 %dpx' % adh, flow)
        if v1 > v0 + 1 and not flow: fail('%s: 배너가 떴는데 영상이 커짐 %.0f→%.0f' % (label, v0, v1))   # 한 줄로 흘리면 영상은 제 폭만큼 커질 수 있다
        banner(pg, 0)
        _, v2 = check_play(pg, label + ' 배너 걷음')
        if abs(v2 - v0) > 2: fail('%s: 배너를 걷었는데 영상이 처음 크기로 안 돌아옴 %.0f→%.0f' % (label, v0, v2))
        print('E7/N7 %s: 영상 %.0f → 배너 %dpx %.0f(%s) → 걷음 %.0f · 재생·±5·여기에 메모 칸 안 ok' % (label, v0, adh, v1, '한 줄' if flow else '나눈 칸', v2))
        ctx.close()
    # 손으로 끈 높이(세로 막대)는 흘리지 않고 칸 속 스크롤로 둔다 · 막대를 올리면 영상이 줄어 재생 단추가 칸 안에 남는다
    ctx, pg = new_page(br, {'width': 1194, 'height': 834}, state, False, errs)
    go_view(pg, sid); insets(pg, 24, 20)
    pg.goto(URL + '#/play/%s/0' % sid); pg.wait_for_selector('#playBtn', timeout=15000); pg.wait_for_timeout(900)
    pg.evaluate("document.getElementById('stack').style.gridTemplateRows='clamp(80px,470px,calc(100% - 120px)) 6px minmax(0,1fr)'"); pg.wait_for_timeout(350)
    r, vh = check_play(pg, '11인치 · 막대로 미디어 칸 470px', False)
    if not r['capped']: fail('E7 막대로 칸을 줄였는데 영상이 안 줄어듦 %s' % r)
    print('E7 막대로 줄인 칸 → 영상 %.0fpx 로 줄고 단추 칸 안 ok' % vh)
    ctx.close()

def n8(br, ctx0, errs):
    sid, state = ctx0['sid'], ctx0['state']
    for w, h in [(1032, 1376), (1366, 1024), (820, 1180)]:
        ctx, pg = new_page(br, {'width': w, 'height': h}, state, False, errs)
        go_view(pg, sid); insets(pg, 32, 20)
        pg.click('[data-act="play"][data-stage="1"]'); pg.wait_for_selector('#stageWrap .stgpage', timeout=15000); pg.wait_for_timeout(700)
        pg.click('[data-stg="edit"]'); pg.wait_for_selector('.sblk .stag', timeout=5000); pg.wait_for_timeout(500)
        r = pg.evaluate("""()=>{const bar=document.querySelector('.stgbar').getBoundingClientRect().bottom,cv=document.querySelector('.stgcanvas').getBoundingClientRect();
          const tags=[...document.querySelectorAll('.sblk .stag')].filter(t=>getComputedStyle(t).display!=='none').map(t=>{const r=t.getBoundingClientRect();return {t:t.textContent,top:r.top,bottom:r.bottom}});
          return {bar,cvTop:cv.top,tags}}""")
        top = min(r['tags'], key=lambda x: x['top'])
        bad = [t for t in r['tags'] if t['top'] < r['bar'] - 0.5]
        if bad: fail('N8/N12 %dx%d 이름표가 무대 바 밑에 숨음 (바 아래 %.1f) %s' % (w, h, r['bar'], bad))
        if not r['tags'] or top['t'] != '송폼 1': fail('N8 %dx%d 준비: 맨 위 이름표가 송폼 1 이 아님 %s' % (w, h, r['tags'][:3]))
        print('N8/N12 %dx%d 맨 위 %s 이름표 %.1f ≥ 바 %.1f ok' % (w, h, top['t'], top['top'], r['bar']))
        ctx.close()

def n6(br, ctx0, errs, webkit):
    sid, state = ctx0['sid'], ctx0['state']
    M = """()=>{const o=document.querySelector('#printArea .pvout'),pp=o.querySelector('.ppage'),R=pp.getBoundingClientRect(),k=CONTI.PG.pw/R.width;
      const f=s=>{const e=pp.querySelector(s);if(!e)return null;const r=e.getBoundingClientRect();return {fs:parseFloat(getComputedStyle(e).fontSize),box:[(r.left-R.left)*k,(r.top-R.top)*k,r.width*k,r.height*k]}};
      return {z:getComputedStyle(pp).zoom,tf:getComputedStyle(pp).transform,scale:R.width/CONTI.PG.pw,scrollW:o.scrollWidth,clientW:o.clientWidth,left:R.left,right:R.right,
        foot:f('.pfoot2'),form:f('.pform2'),gaps:[...o.querySelectorAll('.ppage')].map(p=>p.getBoundingClientRect()).map((r,i,a)=>i?r.top-a[i-1].bottom:0).slice(1)}}"""
    base = None
    for vp in [{'width': 1400, 'height': 900}, {'width': 390, 'height': 844}, {'width': 844, 'height': 390}]:
        ctx, pg = new_page(br, vp, state, vp['width'] < 900, errs)
        go_view(pg, sid)
        pg.evaluate("document.querySelector('.top [data-act=print]').click()"); pg.wait_for_selector('#pvGo', timeout=8000); pg.wait_for_timeout(200)
        pg.click('#modal [data-po="mode"][data-v="stage"]'); pg.wait_for_timeout(200)
        pg.click('#pvGo'); pg.wait_for_selector('#printArea.pv .ppage', timeout=10000); pg.wait_for_timeout(600)
        m = pg.evaluate(M)
        label = '%dx%d' % (vp['width'], vp['height'])
        if not m['foot'] or not m['form']: fail('N6 준비: 조판에 바닥글·송폼 띠가 없음 %s' % m)
        if m['z'] not in ('1', 'normal', None) and float(m['z']) != 1: fail('N6 %s: 미리보기가 아직 zoom 으로 줄임 (%s)' % (label, m['z']))
        if base is None:
            base = m
            if m['scale'] < 0.99: fail('N6 준비: 넓은 화면인데 쪽이 줄어듦 %s' % m)
        else:
            if m['scale'] > 0.95: fail('N6 %s: 폰 미리보기가 줄지 않음 %s' % (label, m))
            if m['scrollW'] > m['clientW'] + 1 or m['left'] < -0.5 or m['right'] > m['clientW'] + 0.5: fail('N6/C7 %s: 옆으로 넘침 %s' % (label, m))
            if webkit:
                for k in ['foot', 'form']:
                    if abs(m[k]['fs'] - base[k]['fs']) > 0.05: fail('N6 %s: %s 글자 크기가 %.2fpx (종이 %.2fpx) — 최소 글자 크기로 부풀었다' % (label, k, m[k]['fs'], base[k]['fs']))
                    if any(abs(a - b) > 2 for a, b in zip(m[k]['box'], base[k]['box'])): fail('N6 %s: %s 자리·크기가 종이와 다름 %s vs %s' % (label, k, m[k]['box'], base[k]['box']))
            if any(abs(g - 20) > 1.5 for g in m['gaps']): fail('N6 %s: 쪽 사이가 20px 가 아님(줄인 쪽이 제자리를 다 차지) %s' % (label, m['gaps']))
        # 찍는 순간(nprint)에는 실제 크기
        t = pg.evaluate("()=>{document.body.classList.add('nprint');const pp=document.querySelector('#printArea .ppage');const r=[getComputedStyle(pp).transform,pp.getBoundingClientRect().width,CONTI.PG.pw];document.body.classList.remove('nprint');return r}")
        if t[0] not in ('none', 'matrix(1, 0, 0, 1, 0, 0)') or abs(t[1] - t[2]) > 1: fail('N6 %s: 찍을 때 쪽이 실제 크기가 아님 %s' % (label, t))
        print('N6 %s: 쪽 배율 %.3f · 바닥글 %.1fpx(종이 %.1fpx) · 찍을 때 실제 크기 ok' % (label, m['scale'], m['foot']['fs'], base['foot']['fs']))
        ctx.close()
    if not webkit: print('N6 글자 크기 부풀림은 웹킷에서만 재현 — 이번엔 자리·배율만 봄')

def n59(br, ctx0, errs):
    sid, state = ctx0['sid'], ctx0['state']
    ctx, pg = new_page(br, {'width': 390, 'height': 844}, state, True, errs)
    pg.goto(URL + '#/edit/' + sid); pg.wait_for_selector('#edsheet', timeout=15000); pg.wait_for_timeout(2500)
    # 스스로 자리를 지키는 브라우저(크로미움 scroll anchoring)가 대신 고쳐 주지 않게 끈다 — 아이폰 웹킷처럼
    pg.add_style_tag(content='.ws,.pbody{overflow-anchor:none!important}')
    if pg.input_value('[data-f="item.title"]') != 'Afresh': fail('N5 준비: 편집기 첫 곡이 Afresh 가 아님')
    POS = "()=>{const ws=document.querySelector('#app .ws'),e=document.getElementById('edsheet'),o=document.getElementById('ovbar');return {y:e.getBoundingClientRect().top-ws.getBoundingClientRect().top,st:ws.scrollTop,ov:o?o.offsetHeight:0,ovTop:o?o.getBoundingClientRect().top-ws.getBoundingClientRect().top:0}}"
    SET = """([sid,on])=>{const it=CONTI.S.services.find(x=>x.id===sid).items[0];if(on){it.key='A';it.ov={key:true}}else{it.key='G';it.ov={}}return it}"""
    PAINT = """([sid,on])=>{const it=CONTI.S.services.find(x=>x.id===sid).items[0];if(on){it.key='A';it.ov={key:true}}else{it.key='G';it.ov={}}CONTI.paintOvBar(it)}"""
    pg.evaluate("()=>{const ws=document.querySelector('#app .ws'),e=document.getElementById('edsheet');ws.scrollTop+=e.getBoundingClientRect().top-ws.getBoundingClientRect().top-80}")
    pg.wait_for_timeout(300)
    a = pg.evaluate(POS)
    if a['st'] < 200: fail('N5 준비: 폰 편집기를 악보까지 못 내림 %s' % a)
    pg.evaluate(PAINT, [sid, True]); pg.wait_for_timeout(150)
    b = pg.evaluate(POS)
    if b['ov'] < 20: fail('N5 준비: 다름 띠가 안 뜸 %s' % b)
    if abs(b['y'] - a['y']) > 1: fail('N5/N9 동기화 뒤 뜬 다름 띠가 아래 악보를 밀어냄 %.0f → %.0f (띠 %dpx)' % (a['y'], b['y'], b['ov']))
    pg.evaluate(PAINT, [sid, False]); pg.wait_for_timeout(150)
    c = pg.evaluate(POS)
    if abs(c['y'] - a['y']) > 1: fail('N5 다름 띠가 없어지며 악보가 당겨짐 %.0f → %.0f' % (a['y'], c['y']))
    # 다시 그릴 때(render) 띠가 생겨도 제자리
    pg.evaluate(SET, [sid, True]); pg.evaluate('CONTI.render()'); pg.wait_for_timeout(600)
    d = pg.evaluate(POS)
    if d['ov'] < 20: fail('N9 준비: 다시 그린 뒤 다름 띠가 없음 %s' % d)
    if abs(d['y'] - a['y']) > 1: fail('N9 다시 그리며 다름 띠가 생기자 악보가 밀림 %.0f → %.0f' % (a['y'], d['y']))
    pg.evaluate(SET, [sid, False]); pg.evaluate('CONTI.render()'); pg.wait_for_timeout(600)
    e = pg.evaluate(POS)
    if abs(e['y'] - a['y']) > 1: fail('N9 다시 그리며 띠가 없어지자 악보가 당겨짐 %.0f → %.0f' % (a['y'], e['y']))
    # 맨 위(띠 자리)가 보이는 중이면 띠가 보이게 둔다 (스크롤을 옮겨 띠를 숨기지 않는다)
    pg.evaluate("document.querySelector('#app .ws').scrollTop=0"); pg.wait_for_timeout(200)
    pg.evaluate(PAINT, [sid, True]); pg.wait_for_timeout(150)
    f = pg.evaluate(POS)
    if f['st'] != 0 or f['ovTop'] < -1: fail('N5 맨 위를 보던 중 뜬 띠가 스크롤로 숨음 %s' % f)
    pg.evaluate(SET, [sid, False])
    print('N5·N9 폰 편집기: 다름 띠가 생기고 없어져도(칠하기·다시 그리기) 보던 악보 제자리(%dpx 띠) · 맨 위에서는 띠가 보임 ok' % b['ov'])
    ctx.close()

def n10(br, ctx0, errs):
    ctx, pg = new_page(br, {'width': 390, 'height': 844}, ctx0['state'], True, errs)
    pg.goto(URL); pg.wait_for_selector('.shell[data-page]', timeout=15000)
    r = ctx.request.post(URL + 'api/songs', headers=H, data={'teamId': ctx0['team'], 'title': LONG, 'key': 'G', 'form': 'A – B'}).json()
    song = r['song']['id']
    pg.evaluate("CONTI.pullSongs(true)"); pg.wait_for_timeout(1500)
    pg.evaluate("(id)=>{CONTI.LIB.detail=null;CONTI.go('library/'+id)}", song); pg.wait_for_selector('.songtop h1', timeout=8000); pg.wait_for_timeout(600)
    m = pg.evaluate("""()=>{const h=document.querySelector('.songtop h1'),v=h.querySelector('.vttl');if(!v)return null;const cs=getComputedStyle(v),hr=h.getBoundingClientRect(),vr=v.getBoundingClientRect();
      return {t:v.textContent,title:v.title,to:cs.textOverflow,ws:cs.whiteSpace,sw:v.scrollWidth,cw:v.clientWidth,vr:vr.right,hr:hr.right,hsw:h.scrollWidth,hcw:h.clientWidth}}""")
    if not m: fail('N10 곡 상세 제목이 .vttl 로 싸여 있지 않음 (flex h1 의 맨 글은 … 가 안 붙는다)')
    elif m['t'] != LONG or m['to'] != 'ellipsis' or m['ws'] != 'nowrap' or m['sw'] <= m['cw'] or m['vr'] > m['hr'] + 0.5:
        fail('N10 긴 제목이 … 로 줄지 않음 %s' % m)
    elif m['title'] != LONG: fail('N10 줄인 제목의 전체 글(title)이 없음 %s' % m)
    else: print('N10 폰 곡 상세 긴 제목 … (%d/%dpx) ok' % (m['cw'], m['sw']))
    ctx.close()

def n11(br, ctx0, errs):
    ctx, pg = new_page(br, {'width': 1180, 'height': 820}, ctx0['state'], False, errs)
    pg.goto(URL); pg.wait_for_selector('.shell[data-page]', timeout=15000)
    cases = [('Qadrum', '이', 'Qadrum으로'), ('Peter', '가', None), ('Paul', '이', 'Paul로'), ('John', '이', None), ('Kang', '이', None), ('MC', '가', None),
             ('DJ', '가', None), ('BTS', '가', None), ('Luke', '가', None), ('하은', '이', None), ('지수', '가', None), ('7', '이', '7로'), ('3', '이', '3으로'),
             ('보컬', '이', '보컬로'), ('일렉', '이', '일렉으로'), ('싱어', '가', '싱어로'), ('Nick', '이', None), ('Bob', '이', None)]
    for w, jo, ro in cases:
        got = pg.evaluate("(w)=>[CONTI.josa(w,'이','가'),CONTI.josaRo(w)]", w)
        if got[0] != w + jo: fail('N11 앱 조사: %s → %s (기대 %s)' % (w, got[0], w + jo))
        if ro and got[1] != ro: fail('N11 앱 으로/로: %s → %s (기대 %s)' % (w, got[1], ro))
    ctx.close()
    # 서버 알림 — 로마자 이름 멤버가 초대로 들어오면 인도자 알림 제목의 조사
    for name, want in [('Qadrum', 'Qadrum이 드럼으로 들어왔어요'), ('Peter', 'Peter가 드럼으로 들어왔어요')]:
        c, pm = new_page(br, {'width': 1180, 'height': 820}, None, False, errs)
        pm.goto(ctx0['link']); signup(pm, ('q%s' % name.lower())[:6] + tag, name)
        pm.wait_for_selector('#jnName', timeout=10000); pm.click('#gtSess .q[data-s="드럼"]'); pm.click('[data-act="team-join"]')
        pm.wait_for_selector('.shell[data-page]', timeout=10000); c.close()
    cl = br.new_context(storage_state=ctx0['state'])
    ns = cl.request.get(URL + 'api/notifications?team=' + ctx0['team']).json()['notifications']
    titles = [n['title'] for n in ns if n['type'] == 'member.join']
    for name, want in [('Qadrum', 'Qadrum이 드럼으로 들어왔어요'), ('Peter', 'Peter가 드럼으로 들어왔어요')]:
        if want not in titles: fail('N11 서버 가입 알림 조사: %r 가 없음 %s' % (want, titles))
    cl.close()
    print('N11 조사 — 로마자 끝소리(Qadrum이·Peter가·Paul로)·글자 이름(MC가)·숫자(7로·3으로)·ㄹ 받침(보컬로) · 서버 가입 알림 %s ok' % titles)

def n2(br, ctx0, errs):
    ctx, pg = new_page(br, {'width': 390, 'height': 844}, ctx0['state'], True, errs)
    pg.goto(URL); pg.wait_for_selector('.shell[data-page]', timeout=15000); pg.wait_for_timeout(2500)
    print('N2 켤 때 떠 있던 창: %s' % pg.evaluate("(document.querySelector('#modal .ov')||{}).textContent||''")[:60])
    pg.evaluate('CONTI.closeModal()'); pg.wait_for_timeout(400)   # 켤 때 뜨는 안내 창이 있으면 닫는다
    # 터치 이벤트를 만든다 (엔진마다 Touch 생성자가 달라 touches·changedTouches 만 가진 이벤트로)
    pg.evaluate("""()=>{window.__tev=(type,x,y,el)=>{const e=new Event(type,{bubbles:true,cancelable:false});const t=[{clientX:x,clientY:y,identifier:1,target:el}];
        Object.defineProperty(e,'touches',{value:type==='touchend'||type==='touchcancel'?[]:t});Object.defineProperty(e,'changedTouches',{value:t});el.dispatchEvent(e)}}""")
    OPEN = "()=>{CONTI.modal('<div class=\"pad\" id=\"n2pad\" style=\"height:380px\">시트</div>',{sheet:true})}"
    ST = "()=>{const p=document.querySelector('#modal #n2pad');const sh=p&&p.closest('.sheetm');return {open:!!p,other:!p&&!!document.querySelector('#modal .ov'),tf:sh?sh.style.transform:null}}"
    def drag(to_y, end=False):
        pg.evaluate("""([ty,end])=>{const h=document.querySelector('#modal .handle'),r=h.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2;
          __tev('touchstart',x,y,h);const n=8;for(let i=1;i<=n;i++)__tev('touchmove',x,y+(ty-y)*i/n,h);if(end)__tev('touchend',x,ty,h)}""", [to_y, end])
    # 1 화면 아래 끝(16px 위)까지 끌고 touchend 가 오지 않음 → 0.45초 뒤 놓은 것으로 → 닫힘
    pg.evaluate(OPEN); pg.wait_for_timeout(500)
    drag(844 - 16); pg.wait_for_timeout(120)
    s = pg.evaluate(ST)
    if not s['open'] or 'translate' not in (s['tf'] or ''): fail('N2 준비: 끄는 동안 시트가 따라오지 않음 %s' % s)
    pg.wait_for_timeout(700)
    s = pg.evaluate(ST)
    if s['open']: fail('N2 아래 끝에서 놓은(touchend 없음) 시트가 반쯤 내려간 채 멈춤 %s' % s)
    # 2 가운데서 조금 끌다 touchend 없이 멈춤 — 시간으로 끝내지 않는다(손가락이 아직 있을 수 있다) · 다음 touchstart 가 끝내 제자리로
    pg.evaluate(OPEN); pg.wait_for_timeout(500)
    y0 = pg.evaluate("document.querySelector('#modal .handle').getBoundingClientRect().top")
    drag(y0 + 40); pg.wait_for_timeout(700)
    s = pg.evaluate(ST)
    if not s['open'] or 'translate' not in (s['tf'] or ''): fail('N2 가운데서 멈춘 끌기를 시간으로 끝냄(손가락이 아직 있을 수 있다) %s' % s)
    pg.evaluate("()=>{const p=document.querySelector('#modal .pad');__tev('touchstart',100,600,p)}"); pg.wait_for_timeout(400)
    s = pg.evaluate(ST)
    if not s['open'] or s['tf']: fail('N2 끝나지 않은 조금 끈 시트가 다음 터치에 제자리로 안 돌아옴 %s' % s)
    # 3 멀리 끌고 touchend 없이 → 다음 touchstart 가 끝내 닫힘
    drag(y0 + 300); pg.wait_for_timeout(100)
    pg.evaluate("()=>{const p=document.querySelector('#modal .pad');__tev('touchstart',100,600,p)}"); pg.wait_for_timeout(500)
    if pg.evaluate(ST)['open']: fail('N2 멀리 끈 뒤 끝나지 않은 끌기가 다음 터치에 닫히지 않음')
    # 4 보통 끌기 — touchend 로 닫힘(대기 타이머가 두 번 닫지 않는다: 다음에 연 시트가 그대로)
    pg.evaluate(OPEN); pg.wait_for_timeout(500)
    drag(844 - 10, True); pg.wait_for_timeout(300)
    if pg.evaluate(ST)['open']: fail('N2 보통 끌기(touchend)로 안 닫힘')
    pg.evaluate(OPEN); pg.wait_for_timeout(800)
    if not pg.evaluate(ST)['open']: fail('N2 앞 끌기의 대기 타이머가 새로 연 시트를 닫음')
    pg.evaluate("CONTI.closeModal()")
    print('N2 아래 시트 — 끝에서 놓고 touchend 없음 → 닫힘 · 가운데 멈춤은 기다림 · 다음 터치가 끝냄 · 보통 끌기 그대로 ok')
    ctx.close()

def run():
    with sync_playwright() as p:
        want = os.environ.get('BROWSER', 'webkit'); webkit = False
        try:
            br = getattr(p, want).launch(); webkit = want == 'webkit'
        except Exception as e:
            print('%s 를 못 띄움 → chromium (%s)' % (want, str(e).splitlines()[0][:80])); br = p.chromium.launch()
        errs = []
        sid, state, team, link = seed(br, errs)
        c0 = {'sid': sid, 'state': state, 'team': team, 'link': link}
        only = [x for x in os.environ.get('PART', '').split(',') if x]
        for f in (e7, n8, n6, n59, n10, n11, n2):
            if only and f.__name__ not in only: continue
            if f is n6: f(br, c0, errs, webkit)
            else: f(br, c0, errs)
        if errs: fail('페이지 오류: %s' % errs[:3])
        br.close()
    if FAILS: print('FAILS %d' % len(FAILS)); sys.exit(1)
    print('OK test_simfix_layout2')

run()
