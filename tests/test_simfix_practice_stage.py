# 아이폰·아이패드 시뮬레이터 점검(2026-09-26) — 연습·무대 회귀 검사
#   C3  연습에서 보기(세션)를 바꾸면 화면을 통째로 다시 그려 재생 중인 영상이 멈추고 시작 시각으로 돌아가며 폰 스크롤이 맨 위로 튀던 것
#       → 제자리에서 고친다(playSession): 영상·스크롤 그대로 · 이미 고른 세션은 아무 일 없음 · 세션 메모 칩 이름 · 세션 전용 영상이 바뀔 때만 미디어 칩을
#       다시 그리고 보던 영상이 새 세션에도 보이면 그대로, 안 보이면 첫 영상
#   C4  폰 연습 상단 바 — 긴 곡 제목이 곡 이동 칸을 못 줄여 메트로놈·무대 버튼이 화면 밖으로 밀리던 것 · 제목은 … 로 줄고 키 표시는 남는다
#   C5  콘티 보기 곡 카드 메모 줄에 '이 곡에 항상'(편곡 고정 메모)이 빠지던 것 — 연습·무대·인쇄처럼 고정 + 이번 예배 메모
#   C8  가로 폰 연습 — 미디어 칸이 128px 이라 영상이 반만 보이고 재생 단추가 칸 밖 → 영상·재생 단추·시간 줄이 함께 보인다 · 송폼 칸은 아래로 이어진다
#   E7  가로 아이패드 연습 — 미디어 칸을 절반으로 묶어 재생 단추·여기에 메모·유튜브에서 열기가 칸 밖 → 제 내용만큼
#   C9  무대 크기 ＋ 가 열 폭(자동 최대)을 넘어도 숫자만 오르던 것 → 끝에서 멈추고(＋ 끔) 예전에 올려 둔 값도 보이는 값에서 내려간다
#   C10 콘티 보기 곡 카드 악보 미리보기에 인도자의 가리개·하이라이트가 빠지던 것 (마커·전조 코드는 연습 화면에서)
#   E1  무대 편집 ‹ › 로 옆 화면에 보낸 블록이 2% 오른쪽으로 밀려 전체 폭 블록의 오른쪽 끝이 잘리던 것
#   E8  무대 편집 — 아주 얇은 악보 조각의 이름표·손잡이가 옆 블록 것과 쌓이고 이름표가 위 블록 왼쪽(마커 원)을 덮던 것
#   E9  무대에서 내보내기 → 설정·미리보기를 닫으면 연습 화면에 떨어지던 것 → 보던 무대 화면으로 돌아온다 (취소·바깥 탭·Esc·미리보기 닫기)
# 사용: CONTI_URL=http://localhost:8766/ .venv/bin/python tests/test_simfix_practice_stage.py   (SOFT=1 이면 실패해도 끝까지 · BROWSER=webkit · PART=c3,e9)
import os, sys, time
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
SOFT = os.environ.get('SOFT') == '1'
tag = str(int(time.time()))[-6:]
FAILS = []
def fail(m):
    print('FAIL:', m)
    if SOFT: FAILS.append(m); return
    sys.exit(1)

YT_ALL, YT_DRUM = 'jNQXAC9IVRw', 'dQw4w9WgXcQ'
LONG_TITLE = 'Amazing grace how sweet the sound that saved a wretch'

def new_page(br, vp, mobile=False, state=None):
    ctx = br.new_context(viewport=vp, is_mobile=mobile, has_touch=mobile, storage_state=state)
    pg = ctx.new_page()
    # 유튜브는 밖으로 나가지 않게 빈 쪽으로 (영상 자체는 보지 않는다 — iframe 이 새로 만들어졌는지·시각만 본다)
    pg.route('**/*youtube*/**', lambda r: r.fulfill(status=200, body='<html></html>', content_type='text/html'))
    pg.on('dialog', lambda d: d.accept())
    return ctx, pg

def go_view(pg, sid):
    pg.goto(URL + '#/view/' + sid)
    pg.wait_for_selector('[data-act="play"][data-stage="1"]', timeout=15000); pg.wait_for_timeout(900)

def go_play(pg, sid, i=0):
    go_view(pg, sid)
    pg.goto(URL + '#/play/%s/%d' % (sid, i)); pg.wait_for_selector('#sheet', timeout=15000); pg.wait_for_timeout(900)

def open_stage(pg, sid):
    go_view(pg, sid)
    pg.click('[data-act="play"][data-stage="1"]')
    pg.wait_for_selector('#stageWrap .stgpage', timeout=15000); pg.wait_for_timeout(800)

def seed(br, errs):
    ctx, pg = new_page(br, {'width': 1366, 'height': 900})
    pg.on('pageerror', lambda e: errs.append(repr(e)[:300]))
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=10000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
    pg.check('#lgAgree')
    pg.fill('#lgName', '하은'); pg.fill('#lgUser', 'sps' + tag); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam', timeout=10000); pg.fill('#gtTeam', '연습팀'); pg.click('#gtSess .q:has-text("건반")')
    pg.click('[data-act="team-create"]'); pg.wait_for_selector('.shell[data-page]', timeout=15000)
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
    pg.fill('[data-f="svc.name"]', '점검 예배'); pg.wait_for_timeout(300)
    si = pg.evaluate("CONTI.S.services.findIndex(s=>s.name==='점검 예배')")
    for n, t in enumerate(['주님 찬양', LONG_TITLE, 'QA 세번째 곡']):
        pg.click('[data-act="add-item"]'); pg.wait_for_timeout(400)
        pg.fill('[data-f="item.title"]', t); pg.fill('[data-f="item.key"]', 'GDE'[n]); pg.fill('[data-f="item.form"]', 'Intro – A – B – A – Outro')
        pg.set_input_files('#pieceFile', [SHEET])
        pg.wait_for_function("([si,n])=>{const it=CONTI.S.services[si].items[n];const p=it&&(it.pieces||[])[0];return p&&p.w>0}", arg=[si, n], timeout=120000)
        pg.wait_for_timeout(500)
    # 마커 A(띠 자리)·B · 가리개(윗부분 가사 한 줄)·하이라이트 · 1곡에 영상 둘(전체 · 드럼 전용)
    pg.evaluate("""([si,a,d])=>{const s=CONTI.S.services[si];
      s.items.forEach((it,n)=>{const p=it.pieces[0];
        p.markers=[{id:'mA'+n,label:'A',x:Math.round(p.w*0.08),y:Math.round(p.h*0.30),cut:Math.round(p.h*0.27)},
                   {id:'mB'+n,label:'B',x:Math.round(p.w*0.08),y:Math.round(p.h*0.55),cut:null}];
        p.hls=[{id:'hm'+n,kind:'mask',x:Math.round(p.w*0.05),y:Math.round(p.h*0.10),w:Math.round(p.w*0.9),h:Math.round(p.h*0.05)},
               {id:'hh'+n,x:Math.round(p.w*0.3),y:Math.round(p.h*0.4),w:Math.round(p.w*0.3),h:Math.round(p.h*0.05)}];
        it.media=n===0?[{id:'ytAll',type:'youtube',url:'https://youtu.be/'+a,name:'전체 영상',start:5,notes:[]},
                        {id:'ytDrum',type:'youtube',url:'https://youtu.be/'+d,name:'드럼 영상',sessions:['드럼'],notes:[]}]:[]});
      CONTI.save()}""", [si, YT_ALL, YT_DRUM])
    pg.wait_for_timeout(800)
    pg.click('[data-act="publish"]'); pg.wait_for_selector('#pubOnly', timeout=8000)
    pg.click('#pubOnly'); pg.wait_for_timeout(3000)
    sid = pg.evaluate("(si)=>CONTI.S.services[si].id", si)
    if pg.evaluate("(si)=>(CONTI.S.services[si].published.items[0].media||[]).length", si) != 2: fail('준비: 발행본에 영상 둘이 없음')
    state = ctx.storage_state()
    ctx.close()
    return sid, state

def c3(br, sid, state, errs):
    ctx, pg = new_page(br, {'width': 390, 'height': 844}, True, state)
    pg.on('pageerror', lambda e: errs.append(repr(e)[:300]))
    go_play(pg, sid); pg.wait_for_timeout(2500)   # 켤 때 동기화가 끝난 뒤에 (메모를 넣으면 받은 목록이 덮는다)
    ses = pg.evaluate("CONTI.pl().session||CONTI.S.team.me&&CONTI.S.team.me.session||''")
    # 재생 중인 척 — 시각·재생 상태를 두고 iframe 에 표시를 단다 (새로 만들어지면 표시가 없다)
    START = """()=>{const y=document.getElementById('yt');y.__keep=1;CONTI.P.t=7.7;CONTI.P.playing=true;
      const ws=document.getElementById('ws');ws.scrollTop=400;return ws.scrollTop}"""
    NOW = """()=>({keep:(document.getElementById('yt')||{}).__keep||0,src:(document.getElementById('yt')||{}).src||'',t:CONTI.P.t,playing:CONTI.P.playing,
      st:document.getElementById('ws').scrollTop,sess:CONTI.pl().session||'',
      on:[...document.querySelectorAll('[data-act="psess"].on')].map(b=>b.dataset.s),
      chip:(document.querySelector('[data-act="pf"][data-k="session"]')||{}).textContent||null,
      media:[...document.querySelectorAll('[data-act="msel"]')].map(b=>(b.classList.contains('on')?'*':'')+b.textContent.trim())})"""
    st0 = pg.evaluate(START)
    if st0 < 200: fail('C3 준비: 폰 연습 화면을 내릴 수 없음 (%s)' % st0)
    pick = '베이스' if ses != '베이스' else '일렉'
    pg.click('[data-act="psess"][data-s="%s"]' % pick); pg.wait_for_timeout(500)
    n = pg.evaluate(NOW)
    if not n['keep']: fail('C3 보기를 바꾸자 영상(iframe)이 새로 만들어짐 %s' % n)
    if abs(n['t'] - 7.7) > 0.01 or not n['playing']: fail('C3 보기를 바꾸자 재생이 멈추거나 되감김 %s' % n)
    if abs(n['st'] - st0) > 2: fail('C3 보기를 바꾸자 스크롤이 튐 %s → %s' % (st0, n['st']))
    if n['sess'] != pick or n['on'] != [pick]: fail('C3 보기가 %s 로 안 바뀜 %s' % (pick, n))
    if n['chip'] != pick: fail('C3 세션 메모 칩 이름이 %s 가 아님 %s' % (pick, n['chip']))
    # 이미 고른 세션을 다시 눌러도 아무 일 없음
    pg.click('[data-act="psess"][data-s="%s"]' % pick); pg.wait_for_timeout(400)
    n2 = pg.evaluate(NOW)
    if not n2['keep'] or abs(n2['st'] - st0) > 2 or not n2['playing']: fail('C3 같은 세션을 다시 누르자 다시 그려짐 %s' % n2)
    # 메모는 새 세션대로 거른다 (세션 메모 · 예전처럼)
    pg.evaluate("""([sid,s])=>{const it=CONTI.S.services.find(x=>x.id===sid).items[0];
      it.notes=[{id:'c3s',marker:'mA0',layer:'session',session:s,text:'세션 메모 '+s,author:'하은'}]}""", [sid, pick])   # 저장(동기화)하지 않는다 — 서버에 없는 메모라 받은 목록이 지운다
    pg.click('[data-act="psess"][data-s="드럼"]'); pg.wait_for_timeout(500)
    if pg.locator('#sheet .m:has-text("세션 메모")').count(): fail('C3 드럼으로 바꿨는데 %s 세션 메모가 보임' % pick)
    n3 = pg.evaluate(NOW)
    # 드럼: 드럼 전용 영상이 앞에 붙고, 보던 전체 영상은 그대로 (칩만 다시)
    if not n3['keep'] or not n3['playing']: fail('C3 드럼 전용 영상이 생기자 보던 영상이 멈춤 %s' % n3)
    if len(n3['media']) != 2 or not n3['media'][1].startswith('*'): fail('C3 드럼 미디어 칩이 틀림 (보던 전체 영상이 골라져 있어야) %s' % n3['media'])
    pg.click('[data-act="psess"][data-s="%s"]' % pick); pg.wait_for_timeout(500)
    if not pg.locator('#sheet .m:has-text("세션 메모")').count(): fail('C3 %s 로 돌아왔는데 세션 메모가 안 보임 %s' % (pick, pg.evaluate("(sid)=>JSON.stringify({n:CONTI.S.services.find(x=>x.id===sid).items[0].notes,m:[...document.querySelectorAll('#sheet .m')].map(e=>e.textContent),s:CONTI.pl().session,f:CONTI.pl().f})", sid)))
    # 드럼 전용 영상을 보다가 그 영상이 안 보이는 세션으로 → 첫 영상(전체)으로
    pg.click('[data-act="psess"][data-s="드럼"]'); pg.wait_for_timeout(400)
    pg.click('[data-act="msel"][data-i="0"]'); pg.wait_for_timeout(400)
    if YT_DRUM not in pg.evaluate(NOW)['src']: fail('C3 준비: 드럼 영상이 안 골라짐')
    pg.click('[data-act="psess"][data-s="%s"]' % pick); pg.wait_for_timeout(500)
    n4 = pg.evaluate(NOW)
    if YT_ALL not in n4['src'] or len(n4['media']) != 1 or not n4['media'][0].startswith('*'): fail('C3 안 보이는 영상을 보던 중 세션을 바꾸면 첫 영상으로 가야 함 %s' % n4)
    if pg.locator('#ctrls').is_hidden(): fail('C3 재생 단추 줄이 숨음')
    print('C3 보기 바꾸기 — 영상·시각·스크롤 그대로 · 같은 세션 무시 · 메모·미디어 칩 새 세션대로 ok')
    ctx.close()

def c4(br, sid, state, errs):
    ctx, pg = new_page(br, {'width': 402, 'height': 874}, True, state)
    pg.on('pageerror', lambda e: errs.append(repr(e)[:300]))
    for i in range(3):
        go_play(pg, sid, i)
        r = pg.evaluate("""()=>{const t=document.querySelector('.top'),W=innerWidth;const c=document.querySelector('.nb.cur'),tt=c.querySelector('.tt'),k=c.querySelector('.pill.key');
          const kr=k.getBoundingClientRect(),cr=c.getBoundingClientRect();
          return {sw:t.scrollWidth,cw:t.clientWidth,out:[...t.querySelectorAll(':scope>button')].filter(b=>{const r=b.getBoundingClientRect();return r.left<0||r.right>W+0.5}).map(b=>b.dataset.act),
            key:kr.width>0&&kr.left>=cr.left-0.5&&kr.right<=Math.min(cr.right,W)+0.5,cut:tt?tt.scrollWidth>tt.clientWidth+1:null,ell:tt?getComputedStyle(tt).textOverflow:null}}""")
        if r['sw'] > r['cw'] + 1: fail('C4 %d번째 곡 상단 바가 옆으로 넘침 %s' % (i + 1, r))
        if r['out']: fail('C4 %d번째 곡 상단 버튼이 화면 밖 %s' % (i + 1, r['out']))
        if not r['key']: fail('C4 %d번째 곡 키 표시가 밀려남 %s' % (i + 1, r))
        if i == 1 and not (r['cut'] and r['ell'] == 'ellipsis'): fail('C4 긴 제목이 … 로 줄지 않음 %s' % r)
    print('C4 폰 연습 상단 바 — 세 곡 모두 버튼이 화면 안 · 긴 제목은 … · 키 표시 남음 ok')
    ctx.close()

def c5_c10(br, sid, state, errs):
    ctx, pg = new_page(br, {'width': 1366, 'height': 900}, False, state)
    pg.on('pageerror', lambda e: errs.append(repr(e)[:300]))
    go_view(pg, sid); pg.wait_for_timeout(2500)   # 켤 때 동기화가 끝난 뒤에 메모를 넣는다
    pg.evaluate("""(sid)=>{const s=CONTI.S.services.find(x=>x.id===sid);
      s.published.items[0].fixedNotes=[{id:'fx1',markerLabel:'A',layer:'all',text:'Down 천천히',authorName:'인도자'},
                                       {id:'fx2',markerLabel:'B',layer:'all',text:'B 는 크게',authorName:'인도자'}];
      s.published.items[2].fixedNotes=[{id:'fx3',markerLabel:'A',layer:'all',text:'고정 메모만',authorName:'인도자'}];
      s.items[0].notes=[{id:'nq',marker:'mA0',layer:'leader',session:null,text:'QA 이번만 전체',author:'인도자'}];
      s.items[2].notes=[];CONTI.render()}""", sid)
    pg.wait_for_timeout(500)
    rows = pg.evaluate("""()=>[...document.querySelectorAll('.card')].filter(c=>c.querySelector('.thumb.vsheet')).map(c=>
      [...c.querySelectorAll('.m')].map(m=>{const r=m.closest('.row');return (r&&r.querySelector('.mk')?r.querySelector('.mk').textContent:'?')+':'+m.textContent}))""")
    if len(rows) != 3: fail('C5 준비: 곡 카드가 셋이 아님 %s' % rows)
    else:
        want = ['A:전체Down 천천히', 'A:전체QA 이번만 전체', 'B:전체B 는 크게']
        if rows[0] != want: fail('C5 1곡 메모 줄 %s (기대 %s)' % (rows[0], want))
        if rows[2] != ['A:전체고정 메모만']: fail('C5 고정 메모만 있는 곡에 메모 줄이 없음 %s' % rows[2])
    print('C5 콘티 보기 메모 줄 — 이 곡에 항상 + 이번 예배 메모, 마커 차례 ok')
    # C10 미리보기에 가리개·하이라이트 (데스크톱 96px 미리보기에서도 그림 좌표대로)
    def hls():
        return pg.evaluate("""()=>{const t=document.querySelector('.card .thumb.vsheet');const img=t.querySelector('img');const ir=img.getBoundingClientRect();
          return [...t.querySelectorAll('.hl')].map(h=>{const r=h.getBoundingClientRect();return {mask:h.classList.contains('mask'),
            x:(r.left-ir.left)/ir.width,y:(r.top-ir.top)/ir.height,w:r.width/ir.width,h:r.height/ir.height,bg:getComputedStyle(h).backgroundColor}})}""")
    def check_hls(where):
        hs = hls()
        m = [h for h in hs if h['mask']]; y = [h for h in hs if not h['mask']]
        if len(m) != 1 or len(y) != 1: fail('C10 %s 미리보기에 가리개·하이라이트가 없음 %s' % (where, hs)); return
        m = m[0]
        if abs(m['x'] - 0.05) > 0.01 or abs(m['y'] - 0.10) > 0.01 or abs(m['w'] - 0.9) > 0.01 or abs(m['h'] - 0.05) > 0.01: fail('C10 %s 가리개 자리가 그림과 다름 %s' % (where, m))
        if 'rgb(255, 255, 255)' not in m['bg']: fail('C10 %s 가리개가 흰색이 아님 %s' % (where, m['bg']))
    check_hls('데스크톱')
    ctx.close()
    ctx, pg = new_page(br, {'width': 390, 'height': 844}, True, state)
    pg.on('pageerror', lambda e: errs.append(repr(e)[:300]))
    go_view(pg, sid)
    pg.wait_for_function("()=>{const i=document.querySelector('.card .thumb.vsheet img');return i&&i.complete&&i.naturalWidth>0}", timeout=15000)
    check_hls('폰')
    print('C10 곡 카드 미리보기에 가리개·하이라이트 (데스크톱·폰) ok')
    ctx.close()

def c8_e7(br, sid, state, errs):
    # (가로 폰 — 짧은 화면은 왼쪽 칸이 한 줄로 흐른다) · (가로 아이패드·노트북 — 미디어 칸이 제 내용만큼)
    for vp, mob, short in [({'width': 874, 'height': 402}, True, True), ({'width': 844, 'height': 390}, True, True),
                           ({'width': 1366, 'height': 1024}, False, False), ({'width': 1180, 'height': 820}, False, False),
                           ({'width': 1366, 'height': 900}, False, False)]:
        ctx, pg = new_page(br, vp, mob, state)
        pg.on('pageerror', lambda e: errs.append(repr(e)[:300]))
        go_play(pg, sid)
        r = pg.evaluate("""()=>{const R=e=>{const r=e.getBoundingClientRect();return [r.top,r.bottom]};const st=document.getElementById('stack'),pb=document.querySelector('.panel.media .pbody');
          const lim=Math.min(R(st)[1],R(document.querySelector('.panel.media'))[1]);
          return {stack:R(st),lim,vid:R(document.querySelector('.vid')),play:R(document.getElementById('playBtn')),tnote:R(document.querySelector('[data-act=tnote]')),
            ytfb:R(document.getElementById('ytfb')),inner:[pb.scrollHeight,pb.clientHeight],stackScroll:[st.scrollHeight,st.clientHeight],
            tl:(()=>{const t=document.getElementById('tlist');return t?[t.clientHeight,t.scrollHeight]:[0,0]})(),
            form:!!document.querySelector('#stack .songbar')}}""")
        w = '%dx%d' % (vp['width'], vp['height'])
        # 타임라인 목록은 제 안에서 스크롤한다(두 줄은 늘 보인다). 칸이 조금 스크롤돼도 조작 단추(아래 검사)만 안 가리면 된다
        if r['tl'][1] > 0 and r['tl'][0] < min(60, r['tl'][1]) - 1: fail('E7 %s 타임라인 메모 목록이 두 줄도 안 보임 %s' % (w, r['tl']))
        for k in ['vid', 'play', 'tnote']:
            if r[k][1] > r['lim'] + 1: fail('E7/C8 %s %s 가 칸 밖(아래 %d > %d)' % (w, k, r[k][1], r['lim']))
        if not short and r['ytfb'][1] > r['lim'] + 1: fail('E7 %s 유튜브에서 열기가 잘림 %s' % (w, r))
        if short:
            if r['vid'][1] - r['vid'][0] < 80: fail('C8 %s 영상이 너무 작음 %s' % (w, r['vid']))
            if r['stackScroll'][0] <= r['stackScroll'][1] or not r['form']: fail('C8 %s 송폼 칸이 아래로 이어지지 않음 %s' % (w, r))
            # 한 번 내리면 송폼·필터가 보인다
            pg.evaluate("document.getElementById('stack').scrollTop=9999"); pg.wait_for_timeout(200)
            if not pg.evaluate("(()=>{const s=document.getElementById('stack').getBoundingClientRect(),f=document.querySelector('#stack .filters').getBoundingClientRect();return f.bottom<=s.bottom+1&&f.top>=s.top-1})()"):
                fail('C8 %s 내려도 메모 필터가 안 보임' % w)
        ctx.close()
    print('C8·E7 가로 폰·아이패드·노트북 연습 — 영상·재생 단추·여기에 메모가 칸 안 ok')

def c9(br, sid, state, errs):
    ctx, pg = new_page(br, {'width': 390, 'height': 844}, True, state)
    pg.on('pageerror', lambda e: errs.append(repr(e)[:300]))
    open_stage(pg, sid)
    W = "()=>[...document.querySelectorAll('#stageWrap .stgpage .blk')].map(e=>Math.round(e.getBoundingClientRect().width))"
    POP = "()=>({lbl:document.querySelector('.stgpop b').textContent,plus:document.querySelector('.stgpop [data-stg=z][data-d=\"1\"]').disabled,z:CONTI.STG.pref.zoom,zmax:CONTI.STG.lay.zmax||1})"
    w0 = pg.evaluate(W)
    pg.click('[data-stg="cfg"]'); pg.wait_for_selector('.stgpop')
    p0 = pg.evaluate(POP)
    if p0['zmax'] != 1: print('  (참고) 이 폰 조판의 크기 끝 ×%s' % p0['zmax'])
    for _ in range(3):
        if pg.evaluate(POP)['plus']: break
        pg.click('.stgpop [data-stg="z"][data-d="1"]'); pg.wait_for_timeout(250)
    p1 = pg.evaluate(POP)
    if not p1['plus']: fail('C9 끝까지 올려도 ＋ 가 꺼지지 않음 %s' % p1)
    if abs(p1['z'] - p1['zmax']) > 0.001 or p1['lbl'] != '×%.1f' % p1['zmax']: fail('C9 크기가 끝(×%s)을 넘거나 표시가 다름 %s' % (p1['zmax'], p1))
    # 예전에 ×3.0 까지 올려 둔 값 — 표시는 보이는 값, − 한 번이면 줄어든다
    pg.evaluate("CONTI.STG.pref.zoom=3;window.dispatchEvent(new Event('resize'))"); pg.wait_for_timeout(500)
    p2 = pg.evaluate(POP)
    if p2['lbl'] != '×%.1f' % p2['zmax']: fail('C9 저장된 ×3.0 이 그대로 표시됨 %s' % p2)
    wb = pg.evaluate(W)
    pg.click('.stgpop [data-stg="z"][data-d="-1"]'); pg.wait_for_timeout(400)
    p3 = pg.evaluate(POP); w3 = pg.evaluate(W)
    if abs(p3['z'] - (p2['zmax'] - 0.1)) > 0.001: fail('C9 − 한 번에 끝에서 한 칸 내려가야 함 %s' % p3)
    if not (w3 and wb and sum(w3) < sum(wb)): fail('C9 − 를 눌러도 악보가 안 줄어듦 %s → %s' % (wb, w3))
    if p3['plus']: fail('C9 내린 뒤에도 ＋ 가 꺼져 있음')
    pg.click('[data-stg="reset"]'); pg.wait_for_timeout(300)
    ctx.close()
    # 자동이 줄여 넣은 곡이 있으면(가로 폰 한 열 — 긴 곡) ＋ 가 그만큼은 키운다
    ctx, pg = new_page(br, {'width': 844, 'height': 390}, True, state)
    pg.on('pageerror', lambda e: errs.append(repr(e)[:300]))
    open_stage(pg, sid)
    pg.evaluate("CONTI.STG.pref.cols=1;window.dispatchEvent(new Event('resize'))"); pg.wait_for_timeout(500)
    zmax = pg.evaluate("CONTI.STG.lay.zmax||1")
    if zmax > 1:
        wb = pg.evaluate(W)
        pg.click('[data-stg="cfg"]'); pg.wait_for_selector('.stgpop')
        pg.click('.stgpop [data-stg="z"][data-d="1"]'); pg.wait_for_timeout(400)
        wa = pg.evaluate(W)
        if not (sum(wa) > sum(wb)): fail('C9 끝 아래의 ＋ 가 악보를 안 키움 %s → %s (끝 ×%s)' % (wb, wa, zmax))
    else: print('  (참고) 가로 폰 한 열에서도 자동이 줄이지 않음 — ＋ 키우기 건너뜀')
    if not pg.locator('.stgpop').count(): pg.click('[data-stg="cfg"]'); pg.wait_for_selector('.stgpop')
    pg.click('.stgpop [data-stg="reset"]'); pg.wait_for_timeout(300)   # 이 기기 종류 조판 값을 처음으로 (뒤 검사에 안 남게)
    ctx.close()
    print('C9 무대 크기 ＋ — 열 폭에서 멈춤 · 옛 값도 − 한 번에 줄어듦 ok')

def e1_e8(br, sid, state, errs):
    ctx, pg = new_page(br, {'width': 1032, 'height': 1376}, False, state)
    pg.on('pageerror', lambda e: errs.append(repr(e)[:300]))
    open_stage(pg, sid)
    if pg.evaluate("CONTI.STG.lay.cols") != 1: fail('E1 준비: 세로 아이패드가 한 열이 아님')
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(500)
    hid = pg.evaluate("CONTI.STG.layout.screens[0].blocks.find(b=>b.type==='head').id")
    if pg.evaluate("(id)=>CONTI.STG.layout.screens[0].blocks.find(b=>b.id===id).w", hid) < 0.99: fail('E1 준비: 송폼 블록이 전체 폭이 아님')
    pg.locator('.sblk[data-sid="%s"]' % hid).click(); pg.wait_for_timeout(300)
    pg.click('[data-sm="next"][data-id="%s"]' % hid); pg.wait_for_timeout(500)
    si = pg.evaluate("(id)=>CONTI.STG.layout.screens.findIndex(sc=>sc.blocks.some(b=>b.id===id))", hid)
    if si != 1: fail('E1 › 로 다음 화면에 안 감 (%s)' % si)
    pg.click('[data-sc="go"][data-i="%d"]' % si); pg.wait_for_timeout(400)
    r = pg.evaluate("""(id)=>{const p=document.querySelector('#stageWrap .stgpage').getBoundingClientRect(),e=document.querySelector('.sblk[data-sid="'+id+'"]').getBoundingClientRect();
      const b=CONTI.STG.layout.screens[CONTI.STG.screen].blocks.find(x=>x.id===id);return {x:b.x,w:b.w,l:e.left-p.left,r:p.right-e.right}}""", hid)
    if r['x'] < -1e-6 or r['x'] + r['w'] > 1 + 1e-6 or r['l'] < -1 or r['r'] < -1: fail('E1 옆 화면에 보낸 전체 폭 블록이 화면 밖으로 나감 %s' % r)
    # 무대(편집 끝)에서도 오른쪽 끝이 화면 안
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(800)
    pg.evaluate("(i)=>{CONTI.STG.screen=i;window.dispatchEvent(new Event('resize'))}", si); pg.wait_for_timeout(500)
    r2 = pg.evaluate("""()=>{const p=document.querySelector('#stageWrap .stgpage').getBoundingClientRect();
      return [...document.querySelectorAll('#stageWrap .stgpage .blk')].map(e=>{const r=e.getBoundingClientRect();return [r.left-p.left,p.right-r.right]})}""")
    if any(a < -1 or b < -1 for a, b in r2): fail('E1 무대에서 블록이 화면 밖 %s' % r2)
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(400); pg.click('[data-stg="auto"]'); pg.wait_for_timeout(400); pg.click('[data-stg="edit"]'); pg.wait_for_timeout(1200)
    if pg.evaluate("CONTI.STG.layout"): fail('E1 정리: ↻ 뒤에도 고친 조판이 남음')
    print('E1 ‹ › 로 보낸 전체 폭 블록이 화면 안 ok')

    # E8 — 마커 A 가 악보 맨 위 가까이(절단선 18px) → 그 위 악보 조각이 몇 px. 메모 띠가 선다
    pg.wait_for_timeout(2000)
    pg.evaluate("""(sid)=>{const s=CONTI.S.services.find(x=>x.id===sid);
      s.items[0].notes=[{id:'e8a',marker:'mA0',layer:'leader',session:null,text:'Down 천천히',author:'인도자'},{id:'e8b',marker:'mA0',layer:'leader',session:null,text:'QA 이번만 전체',author:'인도자'}];
      const p=s.published.items[0].pieces[0];p.markers[0].cut=18;p.markers[0].y=40;
      CONTI.STG.pref.cols=2;   // 두 열이면 악보가 열 폭을 꽉 채워(줄이지 않음) 송폼·띠·악보 왼쪽 끝이 한 줄 — 시뮬레이터에서 본 모양
      CONTI.STG.screen=0;window.dispatchEvent(new Event('resize'))}""", sid)
    pg.wait_for_timeout(600)
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(600)
    r = pg.evaluate("""()=>{const hit=(a,b)=>a.left<b.right-0.5&&b.left<a.right-0.5&&a.top<b.bottom-0.5&&b.top<a.bottom-0.5;
      const vis=e=>getComputedStyle(e).display!=='none';
      const bl=[...document.querySelectorAll('.sblk')].map(e=>({id:e.dataset.sid,h:e.getBoundingClientRect().height,thin:e.classList.contains('thin'),
        tag:vis(e.querySelector('.stag')),top:[...e.querySelectorAll('.sgrip[data-c=nw],.sgrip[data-c=ne]')].filter(vis).length}));
      const tags=[...document.querySelectorAll('.sblk .stag')].filter(vis).map(t=>t.getBoundingClientRect());
      const mks=[...document.querySelectorAll('#stageWrap .stgpage .mk2,#stageWrap .stgpage .pmk')].map(m=>m.getBoundingClientRect());
      return {bl,strip:document.querySelectorAll('.sblk .pstrip').length,cover:mks.filter(m=>tags.some(t=>hit(m,t))).length,
        stack:tags.filter((t,i)=>tags.some((u,j)=>j!==i&&hit(t,u))).length}}""")
    thin = [b for b in r['bl'] if b['h'] < 24]
    if not r['strip'] or not thin: fail('E8 준비: 메모 띠·얇은 악보 조각이 없음 %s' % r)
    for b in thin:
        if not b['thin'] or b['tag'] or b['top']: fail('E8 얇은 블록에 이름표·위 손잡이가 붙음 %s' % b)
    if r['cover']: fail('E8 이름표가 마커 원을 덮음 (%d)' % r['cover'])
    if r['stack']: fail('E8 이름표끼리 겹침 (%d)' % r['stack'])
    # 고르면 이름표가 보인다
    pg.evaluate("(id)=>{CONTI.STG.sel=[id];window.dispatchEvent(new Event('resize'))}", thin[0]['id']); pg.wait_for_timeout(500)
    if not pg.evaluate("(id)=>getComputedStyle(document.querySelector('.sblk[data-sid=\"'+id+'\"] .stag')).display!=='none'", thin[0]['id']): fail('E8 고른 얇은 블록에 이름표가 없음')
    pg.evaluate("CONTI.STG.sel=[]")
    pg.click('[data-stg="auto"]'); pg.wait_for_timeout(400); pg.click('[data-stg="edit"]'); pg.wait_for_timeout(1200)
    pg.evaluate("CONTI.STG.pref.cols='auto'")
    print('E8 얇은 블록 이름표·손잡이 안 쌓임 · 마커 원을 안 덮음 ok')
    ctx.close()

def e9(br, sid, state, errs):
    ctx, pg = new_page(br, {'width': 1032, 'height': 1376}, False, state)
    pg.on('pageerror', lambda e: errs.append(repr(e)[:300]))
    go_play(pg, sid)
    h0 = pg.evaluate("location.hash")
    pg.click('.top [data-act="stage"]'); pg.wait_for_selector('#stageWrap .stgpage', timeout=15000); pg.wait_for_timeout(800)
    pg.click('[data-stg="next"]'); pg.wait_for_timeout(300)
    scr = pg.evaluate("CONTI.STG.screen")
    if scr < 1: fail('E9 준비: 다음 화면으로 못 감')
    S = "()=>({wrap:!!document.getElementById('stageWrap'),vis:(document.getElementById('stageWrap')||{}).offsetWidth||0,scr:CONTI.STG.screen,h:location.hash,modal:!!document.querySelector('#modal').firstChild,pv:!!document.querySelector('#printArea.pv')})"
    def back(what, r):
        if not r['wrap'] or not r['vis']: fail('E9 %s 뒤 무대로 안 돌아옴 %s' % (what, r))
        elif r['scr'] != scr: fail('E9 %s 뒤 보던 화면(%d)이 아님 %s' % (what, scr, r))
        if r['modal'] or r['pv']: fail('E9 %s 뒤에도 창이 남음 %s' % (what, r))
    pg.click('[data-stg="export"]'); pg.wait_for_selector('#pvGo', timeout=8000); pg.wait_for_timeout(300)
    r = pg.evaluate(S)
    if r['vis']: fail('E9 내보내기 설정 창 뒤에 무대가 덮여 있음 %s' % r)
    pg.click('#pvGo'); pg.wait_for_selector('#printArea.pv', timeout=8000); pg.wait_for_timeout(500)
    r = pg.evaluate(S)
    if r['vis'] or not r['pv']: fail('E9 미리보기 중 무대가 보이거나 미리보기가 없음 %s' % r)
    if pg.locator('#printArea .ppage').count() < 1: fail('E9 미리보기 쪽이 없음')
    pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(200)
    pg.click('[data-pv="opt"]'); pg.wait_for_selector('#pvGo', timeout=8000); pg.wait_for_timeout(300)
    if pg.evaluate(S)['vis']: fail('E9 미리보기 → 설정 사이에 무대가 튀어나옴')
    pg.click('#pvGo'); pg.wait_for_selector('#printArea.pv', timeout=8000); pg.wait_for_timeout(300)
    pg.click('[data-pv="close"]'); pg.wait_for_timeout(600)
    r = pg.evaluate(S); back('미리보기 닫기', r)
    if r['h'] != h0: fail('E9 주소가 바뀜 %s → %s' % (h0, r['h']))
    pg.click('[data-stg="export"]'); pg.wait_for_selector('#pvGo', timeout=8000)
    pg.click('#modal [data-close="1"]'); pg.wait_for_timeout(500); back('설정 취소', pg.evaluate(S))
    pg.click('[data-stg="export"]'); pg.wait_for_selector('#pvGo', timeout=8000)
    pg.mouse.click(5, 5); pg.wait_for_timeout(500); back('바깥 탭', pg.evaluate(S))
    pg.click('[data-stg="export"]'); pg.wait_for_selector('#pvGo', timeout=8000)
    pg.keyboard.press('Escape'); pg.wait_for_timeout(500); back('Esc', pg.evaluate(S))
    if not pg.evaluate("document.body.classList.contains('stgon')&&!document.body.classList.contains('stgout')"): fail('E9 돌아온 뒤 무대 표시(stgon/stgout)가 틀림')
    # 무대를 닫으면 전처럼 연습 화면
    pg.click('[data-stg="exit"]'); pg.wait_for_timeout(500)
    if pg.evaluate("!!document.getElementById('stageWrap')||document.body.classList.contains('stgout')"): fail('E9 무대를 닫았는데 남음')
    print('E9 무대에서 내보내기 — 미리보기·설정 취소·바깥 탭·Esc 뒤 보던 무대 화면으로 ok')
    ctx.close()

def run():
    with sync_playwright() as p:
        br = getattr(p, os.environ.get('BROWSER', 'chromium')).launch(); errs = []   # BROWSER=webkit — 아이폰·아이패드와 같은 엔진
        sid, state = seed(br, errs)
        only = [x for x in os.environ.get('PART', '').split(',') if x]   # PART=c9,e9 처럼 몇 부분만
        for f in (c3, c4, c5_c10, c8_e7, c9, e1_e8, e9):
            if not only or f.__name__ in only: f(br, sid, state, errs)
        if errs: fail('페이지 오류: %s' % errs[:3])
        br.close()
    if FAILS: print('FAILS %d' % len(FAILS)); sys.exit(1)
    print('OK test_simfix_practice_stage')

run()
