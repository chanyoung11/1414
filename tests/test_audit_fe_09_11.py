# 전역감사 fe-09-11 회귀 검사 — 조판 엔진(인쇄·무대) · 앱 광고 · 무대 편집
#  F26  큰 빈 여백을 접을 때 메모 띠·배지·코드·하이라이트가 빠지던 것 (인쇄·무대)
#       + 무대 자동 조판이 띠가 달린 줄(악보)을 통째로 빼먹던 것
#  F27  인쇄에서 띠가 열을 넘길 때마다 또 찍히고, 짧은 곡은 미리보기가 끝없이 쪽을 늘리던 것
#  F136 첫 광고를 준비하는 사이 무대를 열면 배너가 무대 악보 위에 남던 것 (앱 전용 — 가짜 AdMob)
#  F139 크기를 바꾼 무대 조각을 자르면 아래 반쪽이 원래 크기 기준으로 놓이던 것
#  F140 송폼 모드를 한 바퀴 돌리면 손으로 옮긴 송폼 블록 자리가 사라지던 것 · 송폼 블록뿐인 조판이 편집 불가
#  F141 여러 곡 화면에서 다른 곡 조각을 탭하면 첫 탭이 먹히던 것
#  G36  화면 밖으로 걸친 무대 블록이 인쇄에서는 여백·쪽번호 위로 찍히던 것
#       + 그 고침 뒤, 큰 화면(r<1)에서 무대에 다 보이던 아래끝 송폼·글 상자가 종이에서 잘리던 것
#   CONTI_URL=http://localhost:8808/ .venv/bin/python tests/test_audit_fe_09_11.py
import os, sys, time, base64
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
BLK = "CONTI.STG.layout.screens[CONTI.STG.screen].blocks"
def fail(m): print('FAIL:', m); sys.exit(1)

def signup(pg, tag, who):
    pg.goto(URL); pg.wait_for_selector('#lgUser')
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
    pg.fill('#lgName', '하은'); pg.fill('#lgUser', who + tag); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam'); pg.fill('#gtTeam', '감사팀'); pg.click('#gtSess .q:has-text("건반")'); pg.click('[data-act="team-create"]')
    pg.wait_for_selector('.shell[data-page]', timeout=10000)

def new_service(pg, name, songs, crop=None):
    """songs: [(제목, 키, 송폼)] — 곡마다 악보 사진 한 장. crop 이 있으면 악보 윗부분만 잘라 짧은 곡으로"""
    pg.evaluate("()=>{location.hash='#/home'}"); pg.wait_for_timeout(500)
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
    pg.fill('[data-f="svc.name"]', name)
    for title, key, form in songs:
        pg.click('[data-act="add-item"]'); pg.wait_for_timeout(400)
        pg.fill('[data-f="item.title"]', title); pg.fill('[data-f="item.key"]', key); pg.fill('[data-f="item.form"]', form)
        if crop:
            d64 = base64.b64encode(open(SHEET, 'rb').read()).decode()
            pg.evaluate("""async([d,k])=>{const bin=atob(d);const u=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)u[i]=bin.charCodeAt(i);
              const img=await CONTI.loadImg(URL.createObjectURL(new Blob([u],{type:'image/jpeg'})));
              const cv=document.createElement('canvas');cv.width=img.naturalWidth;cv.height=Math.round(img.naturalHeight*k);cv.getContext('2d').drawImage(img,0,0);
              const bl=await new Promise(res=>cv.toBlob(res,'image/jpeg',0.92));
              const dt=new DataTransfer();dt.items.add(new File([bl],'short.jpg',{type:'image/jpeg'}));
              const inp=document.querySelector('#pieceFile');inp.files=dt.files;inp.dispatchEvent(new Event('change',{bubbles:true}))}""", [d64, crop])
        else:
            pg.set_input_files('#pieceFile', [SHEET])
        pg.wait_for_function("(()=>{const s=CONTI.S.services.find(x=>x.name===%r);const it=s&&s.items[s.items.length-1];const p=it&&(it.pieces||[])[0];return p&&p.w>0})()" % name, timeout=90000)
        pg.wait_for_timeout(600)
    return pg.evaluate("(n)=>CONTI.S.services.find(x=>x.name===n).id", name)

def open_print(pg, sid):
    pg.goto(URL + '#/view/' + sid); pg.wait_for_selector('[data-act="print"]', timeout=10000); pg.wait_for_timeout(800)
    pg.click('[data-act="print"]'); pg.wait_for_selector('#pvGo', timeout=8000)
    pg.click('#pvGo'); pg.wait_for_selector('#printArea.pv .ppage', timeout=15000); pg.wait_for_timeout(500)

def open_stage(pg, sid):
    # 무대에서 내보낸 뒤 미리보기를 닫으면 보던 무대로 돌아온다(E9) — 남아 있으면 닫고 콘티 보기에서 다시 연다
    pg.evaluate("document.getElementById('stageWrap')&&CONTI.stageExit()")
    pg.goto(URL + '#/view/' + sid)
    pg.wait_for_selector('[data-act="play"][data-stage="1"]', timeout=10000); pg.wait_for_timeout(800)
    pg.click('[data-act="play"][data-stage="1"]')
    pg.wait_for_selector('#stageWrap .stgpage', timeout=15000); pg.wait_for_timeout(700)

# 인도자 메모는 서버 메모 목록이 기준이다 (화면을 옮길 때 서버 것으로 덮는다) → 서버에 바로 올리고 로컬에도 둔다
NOTE = """const addNote=async(sid,it,marker,id,text)=>{
  const r=await fetch('/api/notes',{method:'POST',credentials:'include',headers:{'content-type':'application/json','x-conti':'1'},
   body:JSON.stringify({teamId:CONTI.S.team.id,serviceId:sid,notes:[{id,itemId:it.id,markerId:marker,layer:'leader',session:null,text,at:Date.now()}]})});
  if(!r.ok)throw new Error('note '+r.status);
  it.notes=[{id,marker,layer:'leader',session:null,text,author:'인도자',at:Date.now()}]};"""

# 곡 하나의 악보에 큰 빈 여백 둘을 만들고, 거기에 메모 마커 · 사람이 적은 코드 · 하이라이트를 둔다.
# 여백 좌표는 데이터일 뿐이라 사진 내용과 상관없이 조판 엔진이 그대로 쓴다
SEED = "async([sid,idx])=>{" + NOTE + """const s=CONTI.S.services.find(x=>x.id===sid);const it=s.items[idx];const p=it.pieces[0];
  const h=p.h,g1={s:Math.round(h*0.30),e:Math.round(h*0.30)+80},g2={s:Math.round(h*0.62),e:Math.round(h*0.62)+80};
  p.gaps=[g1,g2];
  p.markers=[{id:'mkB'+idx,label:'B',x:40,y:g1.e+3,cut:null}];
  await addNote(sid,it,'mkB'+idx,'noteB'+idx+'x'+Date.now().toString(36),'여기서 천천히');
  // 빨간 코드는 옮길 것이 있을 때만 그린다(연습과 같게) — 악보 키 F → 연주 키 G(+2)라 Am7 은 Bm7 로 나온다
  p.sheetKey='F';p.keyConfirmed=true;p.offset=null;
  p.chords=[{id:'cA'+idx,text:'Am7',x:80,y:g2.e-34,w:40,h:16,conf:100,fixed:true}];
  p.hls=[{id:'hA'+idx,x:30,y:g2.s+22,w:220,h:120}];
  CONTI.save();return {h,g1,g2,cut:CONTI.autoCut(p,g1.e+3)}}"""

def check_print(pg, sid):
    open_print(pg, sid)
    got = pg.evaluate("""(()=>{const a=document.querySelector('#printArea');
      return {strips:[...a.querySelectorAll('.pstrip')].map(e=>e.textContent),
        chords:[...a.querySelectorAll('.pchord')].map(e=>e.textContent),hls:a.querySelectorAll('.hl').length,
        badges:[...a.querySelectorAll('.pmk')].map(e=>e.textContent),pages:a.querySelectorAll('.ppage').length}})()""")
    pg.click('#printArea [data-pv="close"]'); pg.wait_for_timeout(300)
    return got

def run():
    tag = str(int(time.time()))[-6:]
    with sync_playwright() as p:
        b = p.chromium.launch()
        c = b.new_context(viewport={'width': 1180, 'height': 820})   # iPad 가로
        pg = c.new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(repr(e)[:300])); pg.on('dialog', lambda d: d.accept())
        signup(pg, tag, 'fx')

        # ================= F26 · 인쇄 =================
        sid = new_service(pg, '감사 예배', [('예수로 나의 구주 삼고', 'G', 'Int – A – B – A')])
        geo = pg.evaluate(SEED, [sid, 0])
        if not (geo['g1']['s'] + 10 <= geo['cut'] <= geo['g1']['e'] - 10): fail('준비가 잘못됨 — 메모 자리가 접히는 곳 밖: %s' % geo)
        got = check_print(pg, sid)
        print('인쇄:', got)
        if got['strips'] != [s for s in got['strips'] if '여기서 천천히' in s] or len(got['strips']) != 1:
            fail('F26 메모 띠가 한 번 나와야 함: %s' % got['strips'])
        if not any('Bm7' in x for x in got['chords']): fail('F26 접히는 여백 안에 적은 코드(Am7 → 연주 키 Bm7)가 인쇄에서 빠짐')
        if got['hls'] < 1: fail('F26 여백에서 시작해 아래 줄로 걸친 하이라이트가 인쇄에서 빠짐')
        print('F26 인쇄 ok — 띠 %d · 코드 · 하이라이트' % len(got['strips']))

        # ================= F27 · 짧은 곡 + 메모 =================
        sid2 = new_service(pg, '짧은 곡 예배', [('짧은 곡', 'D', 'A – B')], crop=0.30)
        info = pg.evaluate("async(sid)=>{" + NOTE + """const s=CONTI.S.services.find(x=>x.id===sid);const it=s.items[0];const p=it.pieces[0];
          // 접히지 않는(작은) 여백 바로 아래 줄 첫머리에 메모 마커 — 띠가 그 줄과 함께 다녀야 한다
          const thr=Math.max(40,p.h*0.03),gs=p.gaps||[];
          const g=gs.find(q=>q.e-q.s<=thr&&q.s>p.h*0.3)||gs.find(q=>q.s>p.h*0.3)||gs[0];
          p.markers=[{id:'mkS',label:'B',x:40,y:g?g.e+2:Math.round(p.h/2),cut:null}];
          await addNote(sid,it,'mkS','noteS'+Date.now().toString(36),'여기부터 천천히');
          CONTI.save();return {w:p.w,h:p.h,gap:g,cut:CONTI.autoCut(p,p.markers[0].y)}}""", sid2)
        print('짧은 곡', info)
        t0 = time.time()
        got = check_print(pg, sid2)
        print('인쇄(짧은 곡):', got, '%.1fs' % (time.time() - t0))
        if info['cut'] is not None and len(got['strips']) != 1: fail('F27 메모 띠는 한 번만: %s' % got['strips'])
        if got['pages'] != 1: fail('F27 짧은 곡이 %d장' % got['pages'])
        # 좁은 칸(두 열 고르게 나누기 변형)에서도 띠가 한 번만, 쪽이 끝없이 늘지 않는다
        lay = pg.evaluate("""(sid)=>{const s=CONTI.S.services.find(x=>x.id===sid);const it=s.items[0];
          const out=[];for(const fillH of [60,120,200,300]){const box={cols:2,cw:400,ch:600,gutter:18,top:0};
           const pages=CONTI.pgLayout([it],box,{memos:true,session:'',ctx:{mode:'play',session:'',f:{leader:true}},gutter:18,scale:1,songPage:false,head:false,fillH});
           out.push({fillH,pages:pages.length,strips:pages.flatMap(p=>p.blocks).filter(b=>b.type==='strip').length})}
          return out}""", sid2)
        print('좁은 칸:', lay)
        for r in lay:
            if r['strips'] != 1: fail('F27 좁은 칸에서 띠가 %d번 찍힘: %s' % (r['strips'], r))
            if r['pages'] > 6: fail('F27 쪽이 너무 늘어남: %s' % r)
        print('F27 ok — 띠 한 번 · 미리보기 멈추지 않음')

        # ================= F26 · 무대 (띠 + 띠가 달린 줄) =================
        open_stage(pg, sid)
        st = pg.evaluate("""(()=>{const bs=CONTI.STG.lay.screens.flatMap(s=>s.blocks);
          const pc=bs.find(b=>b.type==='slice').pc;
          const cover=bs.filter(b=>b.type==='slice').flatMap(b=>b.ranges);
          return {strips:[...document.querySelectorAll('#stageWrap .pstrip')].map(e=>e.textContent),
            chords:[...document.querySelectorAll('#stageWrap .pchord')].map(e=>e.textContent),
            hls:document.querySelectorAll('#stageWrap .hl').length,
            units:pc.units.map(u=>[u.a,u.b,!!u.strip]),cover}})()""")
        print('무대:', {k: st[k] for k in ('strips', 'chords', 'hls')})
        if len(st['strips']) != 1 or '여기서 천천히' not in st['strips'][0]: fail('F26 무대에 메모 띠가 없음: %s' % st['strips'])
        if not any('Bm7' in x for x in st['chords']): fail('F26 무대에서 여백 안 코드(Am7 → 연주 키 Bm7)가 빠짐')
        if st['hls'] < 1: fail('F26 무대에서 하이라이트가 빠짐')
        # 조각의 모든 줄(접힌 여백 말고)이 어느 블록엔가 들어 있어야 한다 — 띠가 달린 줄도
        for a, bb, strip in st['units']:
            if not any(r[0] <= a and bb <= r[1] for r in st['cover']): fail('무대에서 악보 줄 %s~%s 이(가) 빠짐 (띠 %s)' % (a, bb, strip))
        print('F26 무대 ok — 띠 · 코드 · 하이라이트 · 띠가 달린 줄까지')
        pg.keyboard.press('Escape'); pg.wait_for_timeout(400)

        # ================= F136 · 앱 광고 (가짜 AdMob) =================
        # 광고 코드는 앱(NATIVE)에서만 돈다. 지금 받은 index.html 에서 그 부분만 떼어 가짜 AdMob 으로 돌린다
        ads = pg.evaluate("""async()=>{const html=await (await fetch('/')).text();
          const code=html.slice(html.indexOf('const ADSTATE='),html.indexOf('// 무대 모드·연습 중에는 화면이 꺼지지 않게 한다'));
          const sleep=ms=>new Promise(r=>setTimeout(r,ms));let banner=false,inits=0,STAGE=false;
          const AdMob={trackingAuthorizationStatus:async()=>({status:'authorized'}),initialize:async()=>{inits++;await sleep(20)},
            requestConsentInfo:async()=>{await sleep(700);return {status:'NOT_REQUIRED'}},showConsentForm:async()=>{},addListener:()=>{},
            showBanner:async()=>{await sleep(50);banner=true},hideBanner:async()=>{banner=false}};
          const win={Capacitor:{getPlatform:()=>'android',Plugins:{AdMob}},innerWidth:400};
          const doc={body:{classList:{add(){},remove(){}}},documentElement:{style:{setProperty(){}}},getElementById:id=>id==='stageWrap'&&STAGE?{}:null};
          const E=new Function('NATIVE','S','CapPlug','$','route','ADS','PL','window','document',code+';return {adsSync,adsHide,adsShow};')(
            true,{team:{plan:'free'}},()=>win.Capacitor.Plugins,()=>null,()=>({name:'play'}),{android:{banner:'x'}},{stage:false},win,doc);
          E.adsSync();E.adsSync();E.adsSync();          // 연습 화면 첫 렌더 몇 번
          await sleep(300);STAGE=true;E.adsHide();       // 준비(동의 확인) 중에 무대를 연다
          await sleep(1200);const r1={banner,inits};
          STAGE=false;E.adsSync();await sleep(300);const r2={banner};   // 무대를 닫으면 다시 뜬다
          E.adsShow();await sleep(5);STAGE=true;E.adsHide();await sleep(300);const r3={banner};   // 띄우는 도중 내리기
          return {r1,r2,r3}}""")
        print('광고:', ads)
        if ads['r1']['banner']: fail('F136 준비 중에 무대를 열었는데 배너가 무대 위에 뜸')
        if ads['r1']['inits'] != 1: fail('F136 광고 초기화가 %d번 돎' % ads['r1']['inits'])
        if not ads['r2']['banner']: fail('F136 무대를 닫았는데 배너가 다시 안 뜸')
        if ads['r3']['banner']: fail('F136 띄우는 도중 내리라 했는데 배너가 남음')
        print('F136 ok — 무대 위 배너 없음 · 초기화 한 번')

        # ================= 무대 편집: 짧은 곡 셋 (세로 iPad = 1열, 한 화면에 두 곡) =================
        sid3 = new_service(pg, '무대 예배', [('첫 곡', 'G', 'A – B'), ('둘째 곡', 'D', 'A – B'), ('셋째 곡', 'E', 'A – B')], crop=0.30)
        pg.set_viewport_size({'width': 820, 'height': 1180})
        open_stage(pg, sid3)

        # ---- F141: 조각 위 블록(기본) 모드에서 다른 곡 조각 첫 탭에 넘어간다 ----
        st = pg.evaluate("({form:CONTI.STG.pref.form,n:CONTI.STG.nscreens,idx:CONTI.STG.idx,screen:CONTI.STG.screen})")
        if st['form'] != 'block' or st['n'] < 2: fail('준비가 잘못됨 — %s' % st)
        other = pg.locator('#stageWrap .blk[data-si]:not([data-si="%d"])' % st['idx']).first
        if not other.count(): fail('준비가 잘못됨 — 한 화면에 곡이 하나뿐')
        other.click(); pg.wait_for_timeout(500)
        if pg.evaluate("CONTI.STG.screen") != st['screen'] + 1: fail('F141 다른 곡 조각을 탭했는데 첫 탭에 안 넘어감')
        pg.keyboard.press('ArrowLeft'); pg.wait_for_timeout(400)
        # 바에 곡이 나오는 모드(상단 바)에서는 기획 §5 대로 바만 그 곡으로 바뀐다
        pg.evaluate("()=>{CONTI.STG.pref.form='bar';CONTI.STG.idx=0}"); pg.click('[data-stg="cfg"]'); pg.click('[data-stg="cfg"]'); pg.wait_for_timeout(400)
        pg.locator('#stageWrap .blk[data-si="1"]').first.click(); pg.wait_for_timeout(400)
        st2 = pg.evaluate("({idx:CONTI.STG.idx,screen:CONTI.STG.screen,bar:document.querySelector('.stgbar b').textContent})")
        if st2['screen'] != 0 or st2['idx'] != 1 or '둘째 곡' not in st2['bar']: fail('F141 상단 바 모드에서 탭하면 바가 그 곡으로 바뀌어야 함: %s' % st2)
        pg.evaluate("()=>{CONTI.STG.pref.form='block'}")
        print('F141 ok — 첫 탭에 다음 화면 · 상단 바 모드는 바만 바뀜')

        # ---- F140: 송폼 블록을 옮기고 송폼 모드를 한 바퀴 돌려도 그 자리 ----
        pg.click('[data-stg="edit"]'); pg.wait_for_timeout(500)
        hb = pg.locator('.sblk[data-sid="h0"]')
        if not hb.count(): fail('준비가 잘못됨 — 송폼 블록 h0 이 없음')
        bb = hb.bounding_box()
        pg.mouse.move(bb['x'] + 40, bb['y'] + 12); pg.mouse.down()
        pg.mouse.move(bb['x'] + 40 + 180, bb['y'] + 12 + 60, steps=10); pg.mouse.up(); pg.wait_for_timeout(500)
        HEAD = "(()=>{const L=CONTI.STG.layout;if(!L)return null;for(const sc of L.screens)for(const b of sc.blocks)if(b.id==='h0')return {x:b.x,y:b.y};return 'gone'})()"
        h0 = pg.evaluate(HEAD)
        if not isinstance(h0, dict): fail('준비가 잘못됨 — 옮긴 송폼 블록: %s' % h0)
        modes = []
        for _ in range(4):
            pg.click('[data-sc="form"]'); pg.wait_for_timeout(400)
            modes.append((pg.evaluate("CONTI.STG.pref.form"), pg.evaluate("!!CONTI.STG.layout")))
        h1 = pg.evaluate(HEAD)
        print('송폼 모드 한 바퀴:', modes, h0, '->', h1)
        if not all(m[1] for m in modes): fail('F140 송폼 모드를 바꾸는 사이 손으로 고친 조판이 없어짐: %s' % modes)
        if not isinstance(h1, dict) or abs(h1['x'] - h0['x']) > 0.002 or abs(h1['y'] - h0['y']) > 0.002:
            fail('F140 송폼 모드를 한 바퀴 돌렸더니 옮긴 송폼 블록 자리가 사라짐: %s -> %s' % (h0, h1))
        # 숨김 모드에서 저장하고(편집 끝) 무대를 다시 열어도 송폼 블록 자리가 저장본에 남아 있다
        pg.click('[data-sc="form"]'); pg.wait_for_timeout(300)   # block → hide
        pg.click('[data-stg="edit"]'); pg.wait_for_timeout(500)   # 편집 끝 = 저장
        pg.click('[data-stg="exit"]'); pg.wait_for_timeout(500)
        open_stage(pg, sid3)
        if pg.evaluate("CONTI.STG.pref.form") != 'hide': fail('준비가 잘못됨 — 숨김 모드가 저장 안 됨')
        pg.click('[data-stg="edit"]'); pg.wait_for_timeout(500)
        for _ in range(3):
            pg.click('[data-sc="form"]'); pg.wait_for_timeout(300)   # hide → auto → bar → block
        h2 = pg.evaluate(HEAD)
        if not isinstance(h2, dict) or abs(h2['x'] - h0['x']) > 0.002: fail('F140 숨김 모드에서 저장하고 돌아오니 자리가 사라짐: %s' % h2)
        print('F140 ok — 옮긴 송폼 블록 자리 유지')

        # ---- F139: 줄인 조각을 자르면 두 반쪽이 딱 붙어 있다 ----
        sl = pg.evaluate(BLK + ".find(b=>b.type==='slice'&&!/[#~]/.test(b.id)&&b.pc.units.length>=3).id")
        el = pg.locator('.sblk[data-sid="%s"]' % sl); r0 = el.bounding_box()
        pg.mouse.click(r0['x'] + r0['width'] / 2, r0['y'] + r0['height'] / 2); pg.wait_for_timeout(400)
        for _ in range(3):
            pg.click('.sblkmenu [data-sm="small"]'); pg.wait_for_timeout(300)
        pg.click('.sblkmenu [data-sm="cut"]'); pg.wait_for_timeout(600)
        halves = pg.evaluate("""(root)=>{const H=CONTI.STG.layout.screens[CONTI.STG.screen].blocks.filter(b=>String(b.id).split('#')[0]===root&&b.type==='slice');
          return H.map(b=>{const e=document.querySelector('.sblk[data-sid="'+CSS.escape(b.id)+'"]');const r=e.getBoundingClientRect();
            const img=e.querySelector('.blk').getBoundingClientRect();return {id:b.id,top:r.top,bottom:r.top+img.height,h:b.h}}).sort((a,b)=>a.top-b.top)}""", sl)
        Hc = pg.evaluate("document.querySelector('#stageWrap .stgpage').getBoundingClientRect().height")
        print('자른 두 반쪽:', [(round(x['top']), round(x['bottom'])) for x in halves])
        if len(halves) != 2: fail('F139 자르기가 안 됨: %s' % halves)
        gapPx = halves[1]['top'] - halves[0]['bottom']
        if gapPx < -1 or gapPx > 0.02 * Hc: fail('F139 줄인 조각을 자르니 두 반쪽 사이가 %.0fpx (겹치거나 벌어짐)' % gapPx)
        for x in halves:   # 저장된 높이(비율)도 그려진 높이와 같다 — 겹침·붙이기 판정이 이것을 쓴다
            if abs(x['h'] * Hc - (x['bottom'] - x['top'])) > 3: fail('F139 저장된 높이가 그려진 높이와 다름: %s' % x)
        print('F139 ok — 두 반쪽 사이 %.1fpx' % gapPx)

        # ---- G36: 화면 밖으로 걸친 블록은 종이에서도 화면 칸에서 잘린다 ----
        pg.evaluate("""(root)=>{const L=CONTI.STG.layout.screens[CONTI.STG.screen];
          const b=L.blocks.find(x=>String(x.id).split('#')[0]===root&&x.type==='slice');b.x=-0.15;b.y=0.8;
          window.dispatchEvent(new Event('resize'))}""", sl); pg.wait_for_timeout(600)
        pg.click('[data-stg="export"]'); pg.wait_for_selector('#pvGo', timeout=8000)
        pg.click('#pvGo'); pg.wait_for_selector('#printArea.pv .ppage.pstage', timeout=15000); pg.wait_for_timeout(600)
        clip = pg.evaluate("""(()=>{const out=[];document.querySelectorAll('#printArea .ppage.pstage').forEach(p=>{
          const pr=p.getBoundingClientRect(),c=p.querySelector('.pclip'),f=p.querySelector('.pfoot2').getBoundingClientRect();
          const loose=[...p.querySelectorAll('.blk,.pstrip')].filter(b=>!b.closest('.pclip')).length;
          if(!c){out.push({noclip:true,loose});return}
          const r=c.getBoundingClientRect();
          out.push({loose,of:getComputedStyle(c).overflow,left:r.left-pr.left,top:r.top-pr.top,right:pr.right-r.right,gapToFoot:f.top-r.bottom})});return out})()""")
        print('종이:', clip)
        for x in clip:
            if x.get('noclip') or x['loose']: fail('G36 무대 블록이 화면 칸 밖에 그대로 찍힘: %s' % x)
            if x['of'] != 'hidden': fail('G36 화면 칸이 넘친 부분을 자르지 않음: %s' % x)
            if x['left'] < 40 or x['top'] < 40 or x['right'] < 40 or x['gapToFoot'] < 0: fail('G36 화면 칸이 여백·쪽번호를 침범: %s' % x)
        pg.click('#printArea [data-pv="close"]'); pg.wait_for_timeout(300)
        pg.evaluate("document.getElementById('stageWrap')&&CONTI.stageExit()")   # 미리보기를 닫으면 무대로 돌아온다(E9) — 닫고 다음으로
        print('G36 ok — 종이에서도 화면 칸에서 잘림')

        # ---- F140: 송폼 블록뿐인 조판 (악보 없는 곡들) — 숨김 모드에서도 편집이 된다 ----
        pg.set_viewport_size({'width': 1180, 'height': 820})
        pg.evaluate("()=>{location.hash='#/home'}"); pg.wait_for_timeout(500)
        pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
        pg.fill('[data-f="svc.name"]', '악보 없는 예배')
        for title in ['첫 곡', '둘째 곡']:
            pg.click('[data-act="add-item"]'); pg.wait_for_timeout(400)
            pg.fill('[data-f="item.title"]', title); pg.fill('[data-f="item.key"]', 'G'); pg.fill('[data-f="item.form"]', 'A – B')
        pg.wait_for_timeout(800)
        sid4 = pg.evaluate("CONTI.S.services.find(x=>x.name==='악보 없는 예배').id")
        open_stage(pg, sid4)
        pg.evaluate("()=>{CONTI.STG.pref.form='block'}")
        pg.click('[data-stg="edit"]'); pg.wait_for_timeout(500)
        for _ in range(4):
            pg.click('[data-sc="form"]'); pg.wait_for_timeout(300)
            if pg.evaluate("CONTI.STG.pref.form") == 'hide': break
        if not pg.evaluate("!!CONTI.STG.layout"): fail('F140 송폼 블록뿐인 조판이 숨김 모드에서 통째로 없어짐 (편집 불가)')
        pg.click('[data-sc="text"]'); pg.wait_for_timeout(400)
        if not pg.locator('.sblk .ptext').count(): fail('F140 숨김 모드에서 글 블록을 더할 수 없음')
        print('F140 ok — 송폼 블록뿐인 조판도 숨김 모드에서 편집됨')
        pg.keyboard.press('Escape'); pg.wait_for_timeout(300)

        # ---- G36 (되돌려진 수정): 무대에서 다 보이는 송폼·글 상자는 종이에서도 다 나온다 ----
        # 큰 화면(아이패드 프로 1366×1024 → 종이 배율 r≈0.7)에서 자리·폭만 r 배로 줄이고 글자·안쪽 여백은 그대로 두면
        # 종이의 상자가 무대보다 길어져, 화면 아래에 붙여 둔 송폼 상자(20px)·글 상자(12px)가 화면 칸에서 잘렸다
        pg.goto(URL); pg.wait_for_selector('.shell[data-page]', timeout=10000)   # 앞의 무대·편집 상태를 털어 낸다
        pg.set_viewport_size({'width': 1366, 'height': 1024})
        pg.evaluate("()=>{location.hash='#/home'}"); pg.wait_for_timeout(500)
        pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
        pg.fill('[data-f="svc.name"]', '큰 화면 예배')
        for title in ['첫 곡', '둘째 곡']:
            pg.click('[data-act="add-item"]'); pg.wait_for_timeout(400)
            pg.fill('[data-f="item.title"]', title); pg.fill('[data-f="item.key"]', 'G')
            pg.fill('[data-f="item.form"]', 'I – V1 – C – V2 – C – B – C – C – O')
        pg.wait_for_timeout(800)
        sid5 = pg.evaluate("CONTI.S.services.find(x=>x.name==='큰 화면 예배').id")
        open_stage(pg, sid5)
        pg.click('[data-stg="edit"]'); pg.wait_for_timeout(500)
        pg.click('[data-sc="text"]'); pg.wait_for_timeout(400)
        placed = pg.evaluate("""()=>{const bs=%s.filter(b=>!b.hidden);const t=bs.find(b=>b.type==='text'),hs=bs.filter(b=>b.type==='head');
          if(!t||hs.length<2)return null;
          t.text='맨 아래 글 — 여기까지 보여야 한다';t.x=0.02;t.w=0.3;hs[0].x=0.34;hs[0].w=0.3;hs[1].x=0.66;hs[1].w=0.32;
          window.dispatchEvent(new Event('resize'));return bs.length}""" % BLK)
        if not placed: fail('준비가 잘못됨 — 글 블록·송폼 블록이 없음')
        pg.wait_for_timeout(600)
        # 그려진 높이를 재서 화면 아래끝에 붙인다 (편집 중에는 화면이 ek 배로 줄어 있다)
        pg.evaluate("""()=>{const pe=document.querySelector('#stageWrap .stgpage');const H=pe.offsetHeight,ek=pe.getBoundingClientRect().height/H;
          for(const b of %s.filter(b=>!b.hidden&&(b.type==='text'||b.type==='head'))){
            const el=document.querySelector('.sblk[data-sid="'+CSS.escape(b.id)+'"] .blk');if(!el)continue;
            b.y=(H-el.getBoundingClientRect().height/ek-1)/H}
          window.dispatchEvent(new Event('resize'))}""" % BLK); pg.wait_for_timeout(600)
        pg.click('[data-stg="edit"]'); pg.wait_for_timeout(600)   # 편집 끝 — 무대 그대로 보기
        # 상자마다 화면 안 자리(화면 크기에 대한 비율). 종이에서는 화면 칸에 대한 비율이 같아야 한다
        REL = """([sel,box])=>{const B=document.querySelector(box).getBoundingClientRect();
          return [...document.querySelectorAll(sel)].map(e=>{const r=e.getBoundingClientRect();
            return {c:e.className,l:(r.left-B.left)/B.width,t:(r.top-B.top)/B.height,r:(r.right-B.left)/B.width,b:(r.bottom-B.top)/B.height,px:B.bottom-r.bottom}})}"""
        on_stage = pg.evaluate(REL, ['#stageWrap .stgpage .songhead,#stageWrap .stgpage .ptext', '#stageWrap .stgpage'])
        if len(on_stage) != 3 or any(x['b'] > 1.0005 or x['b'] < 0.95 for x in on_stage): fail('준비가 잘못됨 — 무대에서 상자가 아래끝에 다 보이지 않음: %s' % on_stage)
        pg.click('[data-stg="export"]'); pg.wait_for_selector('#pvGo', timeout=8000)
        pg.click('#pvGo'); pg.wait_for_selector('#printArea.pv .ppage.pstage', timeout=15000); pg.wait_for_timeout(600)
        on_paper = pg.evaluate(REL, ['#printArea .ppage.pstage .pclip .songhead,#printArea .ppage.pstage .pclip .ptext', '#printArea .ppage.pstage .pclip'])
        print('무대:', [(x['c'], round(x['t'], 3), round(x['b'], 3)) for x in on_stage])
        print('종이:', [(x['c'], round(x['t'], 3), round(x['b'], 3), round(x['px'], 1)) for x in on_paper])
        if len(on_paper) != len(on_stage): fail('G36 종이의 상자 수가 무대와 다름: %s' % on_paper)
        for s, q in zip(on_stage, on_paper):
            if q['px'] < -0.5: fail('G36 무대에서 다 보이던 %s 상자가 종이에서 %.1fpx 잘림' % (q['c'], -q['px']))
            if max(abs(s[k] - q[k]) for k in 'ltrb') > 0.004: fail('G36 종이의 상자 자리·크기가 무대와 다름: 무대 %s · 종이 %s' % (s, q))
        pg.click('#printArea [data-pv="close"]'); pg.wait_for_timeout(300)
        pg.evaluate("document.getElementById('stageWrap')&&CONTI.stageExit()")   # 무대로 돌아온다(E9) — 닫고 다음으로
        print('G36 ok — 큰 화면에서도 종이가 무대와 같은 비율 · 아래끝 상자가 잘리지 않음')

        # 자동 조판도 같다 — 악보 없는 12곡을 큰 화면에 자동으로 쌓으면 맨 아래 송폼 상자가 종이에서 잘리고(8px),
        # 높이가 안 줄어든 송폼 상자끼리 종이에서 더 겹쳤다
        pg.evaluate("()=>{location.hash='#/home'}"); pg.wait_for_timeout(500)
        pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
        pg.fill('[data-f="svc.name"]', '열두 곡 예배')
        for i in range(12):
            pg.click('[data-act="add-item"]'); pg.wait_for_timeout(300)
            pg.fill('[data-f="item.title"]', '곡 %d' % (i + 1)); pg.fill('[data-f="item.key"]', 'A')
            pg.fill('[data-f="item.form"]', 'I – V1 – C – V2 – C – B – C – O')
        pg.wait_for_timeout(800)
        sid6 = pg.evaluate("CONTI.S.services.find(x=>x.name==='열두 곡 예배').id")
        open_stage(pg, sid6)
        on_stage = pg.evaluate(REL, ['#stageWrap .stgpage .songhead', '#stageWrap .stgpage'])
        if len(on_stage) < 6 or max(x['b'] for x in on_stage) < 0.9: fail('준비가 잘못됨 — 자동 조판이 화면 아래까지 차지 않음: %s' % on_stage)
        pg.click('[data-stg="export"]'); pg.wait_for_selector('#pvGo', timeout=8000)
        pg.click('#pvGo'); pg.wait_for_selector('#printArea.pv .ppage.pstage', timeout=15000); pg.wait_for_timeout(600)
        on_paper = pg.evaluate(REL, ['#printArea .ppage.pstage:first-child .pclip .songhead', '#printArea .ppage.pstage:first-child .pclip'])
        if len(on_paper) != len(on_stage): fail('G36 자동 조판 — 종이 첫 쪽의 송폼 상자 수가 무대 첫 화면과 다름: %d · %d' % (len(on_paper), len(on_stage)))
        for s, q in zip(on_stage, on_paper):
            if s['b'] <= 1.0005 and q['px'] < -0.5: fail('G36 자동 조판 — 무대에서 다 보이던 송폼 상자가 종이에서 %.1fpx 잘림' % -q['px'])
            if max(abs(s[k] - q[k]) for k in 'ltrb') > 0.004: fail('G36 자동 조판 — 종이의 송폼 상자 자리·크기가 무대와 다름: 무대 %s · 종이 %s' % (s, q))
        pg.click('#printArea [data-pv="close"]'); pg.wait_for_timeout(300)
        print('G36 ok — 자동 조판(12곡) 송폼 상자도 무대와 같은 비율 · %d개 · 맨 아래 %.3f' % (len(on_paper), max(x['b'] for x in on_paper)))

        if errs: fail('콘솔 오류: %s' % errs[:3])
        b.close()
    print('OK — fe-09-11')

run()
