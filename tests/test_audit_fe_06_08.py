# 감사 fe-06-08 회귀 확인
#  F87  팀 설정 자동 저장 — 바꾸고 0.7초 안에 다른 화면으로 가도 바꾼 값이 저장되고, 말씀 요청·목회자 메모가 꺼지지 않는다
#  F134 초대 링크 — 복사가 막혀도(앱 웹뷰) 영어 오류 대신 링크를 보여 주고 버튼으로 복사한다
#  F88  코드 ▲▼ 를 한 번 눌러도 연주 키를 바꾸면 코드가 따라간다
#  F92  조각을 자르면 마커·코드가 같은 음표 위에 그대로 있다 (자른 뒤 여백을 또 잘라 어긋나던 것)
#  F135 악보 다시 만들기 — 이미 그 악보 화면에 있으면 새 악보로 다시 그린다 · 다른 화면으로 갔으면 끌고 가지 않는다
#  G18  옥타브 바로잡기가 제대로 적힌 낮은 벌스 줄을 한 옥타브 올리지 않는다
import os, sys, time, json, base64
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
tag = str(int(time.time()))[-6:]
H = {'x-conti': '1'}
fails = []
def bad(m): print('FAIL:', m); fails.append(m)

def open_sect(pg, key):
    if not pg.locator(f'.tsec[data-sect="{key}"].on').count():
        pg.click(f'[data-sopen="{key}"]'); pg.wait_for_timeout(250)

def team_page(pg):
    pg.evaluate("()=>location.hash='#/team'"); pg.wait_for_selector('.tpage', timeout=8000); pg.wait_for_timeout(300)

# 흰 바탕 1200x900 에 네 귀퉁이 점(가져올 때 여백이 거의 안 잘리게) + 표적 네모 + 그 아래 가로 막대.
# 오른쪽 아래를 자르면 위·왼쪽은 빈 여백이고 잉크(표적~막대)가 틀의 30% 넘게 걸쳐 있어 예전엔 여백을 또 잘랐다
IMG_JS = """()=>{const c=document.createElement('canvas');c.width=1200;c.height=900;const x=c.getContext('2d');
 x.fillStyle='#fff';x.fillRect(0,0,1200,900);x.fillStyle='#000';
 [[20,20],[1160,20],[20,860],[1160,860]].forEach(([a,b])=>x.fillRect(a,b,20,20));
 x.fillRect(790,590,40,40);x.fillRect(700,780,400,20);
 return c.toDataURL('image/png').split(',')[1]}"""

# 조각 이미지에서 표적(가운데, 막대 위쪽)의 어두운 점 무게중심 (귀퉁이 점·막대는 뺀다)
FIND_JS = """async(pid)=>{const it=CONTI.S.services[0].items[0];const p=it.pieces.find(x=>x.id===pid);
 const b=await CONTI.IDB.get('blobs',p.blob);const im=await CONTI.loadImg(URL.createObjectURL(b));
 const c=document.createElement('canvas');c.width=im.naturalWidth;c.height=im.naturalHeight;const x=c.getContext('2d');x.drawImage(im,0,0);
 const d=x.getImageData(0,0,c.width,c.height).data;let sx=0,sy=0,n=0;
 for(let y=100;y<c.height*0.75;y++)for(let X=100;X<c.width-100;X++){const i=(y*c.width+X)*4;if(d[i]<100){sx+=X;sy+=y;n++}}
 return {w:c.width,h:c.height,pw:p.w,ph:p.h,cx:n?Math.round(sx/n):null,cy:n?Math.round(sy/n):null,n}}"""

# (x,y) 가 어두운지 — 조각 이미지를 그대로 읽는다
DARK_JS = """async([pid,x0,y0])=>{const it=CONTI.S.services[0].items[0];const p=it.pieces.find(x=>x.id===pid);
 const b=await CONTI.IDB.get('blobs',p.blob);const im=await CONTI.loadImg(URL.createObjectURL(b));
 const c=document.createElement('canvas');c.width=im.naturalWidth;c.height=im.naturalHeight;const x=c.getContext('2d');x.drawImage(im,0,0);
 if(x0<0||y0<0||x0>=c.width||y0>=c.height)return {v:null,w:c.width,h:c.height};
 return {v:x.getImageData(x0,y0,1,1).data[0],w:c.width,h:c.height}}"""

def run():
  with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    ctx = b.new_context(viewport={'width': 1300, 'height': 950}); L = ctx.new_page()
    L.on('pageerror', lambda e: errs.append(repr(e)[:200]))
    answers = []   # prompt 에 줄 답 (없으면 기본값)
    def on_dialog(d):
        if d.type == 'prompt' and answers: d.accept(answers.pop(0))
        else: d.accept()
    L.on('dialog', on_dialog)
    L.goto(URL); L.wait_for_selector('#lgUser', timeout=8000)
    L.click('[data-act="lg-mode"][data-m="signup"]'); L.wait_for_selector('#lgName'); L.check('#lgAgree')
    L.fill('#lgName', '하은'); L.fill('#lgUser', 'a68' + tag); L.fill('#lgPass', 'secret1')
    L.click('[data-act="lg-submit"]')
    L.wait_for_selector('#gtTeam', timeout=8000); L.fill('#gtTeam', '감사팀'); L.click('[data-act="team-create"]')
    L.wait_for_selector('.shell[data-page]', timeout=8000)
    team = L.evaluate("CONTI.S.team.id")
    getst = lambda: ctx.request.get(URL + 'api/teams/' + team).json()['settings']

    # ---------- F87 팀 설정: 바꾸고 바로 떠나기 ----------
    r = ctx.request.patch(URL + 'api/teams/%s/settings' % team, headers=H, data={'pastorCanMemo': True, 'reminderDay': 25, 'wordRequestOn': True})
    if r.status != 200: bad('설정 준비 실패: ' + r.text()[:120])
    team_page(L); open_sect(L, 'noti')
    L.select_option('#stRem', '22'); L.evaluate("()=>location.hash='#/home'"); L.wait_for_timeout(1800)
    st = getst()
    if st.get('reminderDay') != 22: bad('F87 알림일을 바꾸고 바로 떠나면 저장이 안 됨: %s' % st.get('reminderDay'))
    if st.get('wordRequestOn') is not True: bad('F87 말씀 요청이 꺼짐: %s' % st.get('wordRequestOn'))
    if st.get('pastorCanMemo') is not True: bad('F87 목회자 메모가 꺼짐: %s' % st.get('pastorCanMemo'))
    # 체크박스 하나만 끄고 떠나기 → 그것만 꺼지고 나머지는 그대로
    team_page(L); open_sect(L, 'etc')
    L.uncheck('#stPastorMemo'); L.evaluate("()=>location.hash='#/home'"); L.wait_for_timeout(1800)
    st = getst()
    if st.get('pastorCanMemo') is not False: bad('F87 목회자 메모 끄기가 저장 안 됨')
    if st.get('wordRequestOn') is not True: bad('F87 목회자 메모만 껐는데 말씀 요청이 꺼짐')
    if st.get('reminderDay') != 22: bad('F87 알림일이 되돌아감: %s' % st.get('reminderDay'))
    # 세션 정원도 떠나기 전에 바꾼 값이 들어간다
    team_page(L); open_sect(L, 'sessions')
    sess = L.get_attribute('[data-slot]', 'data-slot')
    L.fill('[data-slot="%s"]' % sess, '3'); L.dispatch_event('[data-slot="%s"]' % sess, 'change')
    L.evaluate("()=>location.hash='#/home'"); L.wait_for_timeout(1800)
    st = getst()
    if (st.get('slots') or {}).get(sess) != 3: bad('F87 세션 정원을 바꾸고 떠나면 저장 안 됨: %s' % st.get('slots'))
    if st.get('wordRequestOn') is not True or st.get('pastorCanMemo') is not False: bad('F87 정원만 바꿨는데 다른 설정이 바뀜: %s' % st)
    # 머무르면 예전처럼 저장된다
    team_page(L); open_sect(L, 'noti')
    L.select_option('#stAhead', '2'); L.wait_for_timeout(1500)
    if getst().get('reminderMonthsAhead') != 2: bad('F87 화면에 머무를 때 저장이 안 됨')
    print('F87 checked')

    # ---------- F134 초대 링크 복사가 막힐 때 ----------
    team_page(L); open_sect(L, 'invites')
    L.evaluate("""()=>{window.__cp=[];Object.defineProperty(navigator.clipboard,'writeText',{configurable:true,writable:true,
      value:()=>Promise.reject(new DOMException('The request is not allowed by the user agent or the platform in the current context, possibly because the user denied permission.','NotAllowedError'))})}""")
    n0 = len(L.evaluate("CONTI.TM.invites") or [])
    L.click('.tsec[data-sect="invites"] [data-act="tm-invite"]'); L.wait_for_selector('[data-ir]', timeout=5000)
    L.click('#ivOk'); L.wait_for_timeout(1500)
    toast = L.locator('#toast').inner_text()
    if 'not allowed' in toast or 'request' in toast.lower(): bad('F134 영어 오류가 그대로 뜸: ' + toast)
    invs = L.evaluate("CONTI.TM.invites") or []
    if len(invs) != n0 + 1: bad('F134 링크가 한 개 만들어지지 않음: %d → %d' % (n0, len(invs)))
    shown = L.locator('#modal .linkbox').inner_text() if L.locator('#modal .linkbox').count() else ''
    if '#/join/' not in shown: bad('F134 복사가 막혔는데 링크를 보여 주지 않음 (toast: %s)' % toast)
    else:
      L.evaluate("()=>{Object.defineProperty(navigator.clipboard,'writeText',{configurable:true,writable:true,value:t=>{window.__cp.push(t);return Promise.resolve()}})}")
      L.click('#modal #ivCopy'); L.wait_for_timeout(400)
      cp = L.evaluate("window.__cp")
      if not cp or cp[0] != shown.strip(): bad('F134 복사 버튼이 링크를 복사하지 않음: %s / %s' % (cp, shown))
      L.click('#modal [data-close]'); L.wait_for_timeout(300)
    # 복사가 되면 예전처럼 바로 복사하고 창 없이 끝난다
    L.click('.tsec[data-sect="invites"] [data-act="tm-invite"]'); L.wait_for_selector('[data-ir]', timeout=5000)
    L.click('#ivOk'); L.wait_for_timeout(1500)
    cp = L.evaluate("window.__cp")
    if len(cp) < 2 or '#/join/' not in cp[-1]: bad('F134 복사가 될 때 바로 복사하지 않음: %s' % cp)
    if L.locator('#modal .linkbox').count(): bad('F134 복사가 됐는데 창이 뜸')
    print('F134 checked')

    # ---------- 곡 하나 · 조각 하나 ----------
    L.evaluate("()=>location.hash='#/home'"); L.wait_for_selector('[data-act="new-svc"]', timeout=8000)
    L.click('[data-act="new-svc"]'); L.wait_for_selector('[data-f="svc.name"]')
    L.fill('[data-f="svc.name"]', '감사 예배')
    L.click('[data-act="add-item"]'); L.wait_for_selector('[data-f="item.title"]')
    L.fill('[data-f="item.title"]', '시험곡'); L.fill('[data-f="item.key"]', 'A'); L.wait_for_timeout(300)
    png = base64.b64decode(L.evaluate(IMG_JS))
    L.set_input_files('#pieceFile', files=[{'name': 't.png', 'mimeType': 'image/png', 'buffer': png}])
    L.wait_for_function("(()=>{const it=CONTI.S.services[0].items[0];const p=(it.pieces||[])[0];return p&&p.w>0})()", timeout=30000)
    L.wait_for_timeout(600)
    svc = L.evaluate("CONTI.S.services[0].id"); item = L.evaluate("CONTI.S.services[0].items[0].id")
    pid = L.evaluate("CONTI.S.services[0].items[0].pieces[0].id")

    # ---------- F88 코드 ▲▼ 뒤 연주 키 바꾸기 ----------
    L.evaluate("""()=>{const it=CONTI.S.services[0].items[0];const p=it.pieces[0];p.sheetKey='G';p.keyConfirmed=true;p.offset=null;
      p.chords=[{id:'c1',text:'G',x:40,y:40,w:30,h:20,conf:99,fixed:true}];CONTI.save();CONTI.render()}""")
    L.wait_for_selector('[data-act="chord-off"][data-d="1"]', timeout=6000)
    L.click('[data-act="chord-off"][data-d="1"]'); L.wait_for_timeout(300)
    L.click('[data-act="chord-off"][data-d="-1"]'); L.wait_for_timeout(300)
    off = L.evaluate("(()=>{const it=CONTI.S.services[0].items[0];return CONTI.chordOffset(it,it.pieces[0])})()")
    if off != 2: bad('F88 ▲▼ 뒤 G→A 가 +2 가 아님: %s' % off)
    L.fill('[data-f="item.key"]', 'C'); L.wait_for_timeout(500)
    got = L.evaluate("(()=>{const it=CONTI.S.services[0].items[0];const p=it.pieces[0];const o=CONTI.chordOffset(it,p);return [o,CONTI.transposeChord('G',o,it.key)]})()")
    if got[1] != 'C': bad('F88 연주 키를 C 로 바꿨는데 G 코드가 %s (offset %s)' % (got[1], got[0]))
    # ▲ 한 번(악보 키 보정 +1)은 키를 바꿔도 +1 로 남는다
    L.evaluate("()=>CONTI.render()"); L.wait_for_selector('[data-act="chord-off"][data-d="1"]', timeout=6000)
    L.click('[data-act="chord-off"][data-d="1"]'); L.wait_for_timeout(300)
    L.fill('[data-f="item.key"]', 'D'); L.wait_for_timeout(500)
    got = L.evaluate("(()=>{const it=CONTI.S.services[0].items[0];const p=it.pieces[0];const o=CONTI.chordOffset(it,p);return [o,CONTI.transposeChord('G',o,it.key)]})()")
    if got[0] != 8 - 12 and got[0] != 8: bad('F88 ▲ 보정이 키를 따라가지 않음: %s' % got)
    # 예전 데이터(offset 만 있고 기준 키가 없음)는 예전처럼 그 값 그대로
    old = L.evaluate("CONTI.chordOffset({key:'C'},{sheetKey:'G',offset:2})")
    if old != 2: bad('F88 예전 데이터의 offset 이 달라짐: %s' % old)
    # 악보 키를 다시 고르면 보정이 풀린다
    L.evaluate("""()=>{const it=CONTI.S.services[0].items[0];const p=it.pieces[0];p.offset=null;it.key='A';CONTI.save();CONTI.render()}""")
    print('F88 checked')

    # ---------- F92 자르기 뒤 마커·코드 자리 ----------
    f = L.evaluate(FIND_JS, pid)
    if not f['cx']: bad('F92 표적을 못 찾음: %s' % f)
    else:
      cx, cy = f['cx'], f['cy']
      L.evaluate("""([cx,cy])=>{const it=CONTI.S.services[0].items[0];const p=it.pieces[0];
        p.markers=[{id:'mk1',label:'V1',x:cx,y:cy,cut:null}];p.chords=[{id:'c2',text:'G',x:cx-10,y:cy-10,w:20,h:20,conf:99,fixed:true}];p.hls=[{id:'h1',x:cx-15,y:cy-15,w:30,h:30}];
        CONTI.save();CONTI.render()}""", [cx, cy])
      L.wait_for_selector('[data-act="crop-piece"][data-id="%s"]' % pid, timeout=6000)
      L.click('[data-act="crop-piece"][data-id="%s"]' % pid); L.wait_for_selector('#cropImg', timeout=6000); L.wait_for_timeout(500)
      bb = L.locator('#cropImg').bounding_box()
      # 표적은 (0.66,0.66) 쯤 · 오른쪽 아래 귀퉁이 점은 (0.97,0.96) → 0.45~0.93 으로 고르면 표적만 들어오고 위·왼쪽은 빈 여백
      L.mouse.move(bb['x'] + bb['width'] * 0.45, bb['y'] + bb['height'] * 0.45); L.mouse.down()
      L.mouse.move(bb['x'] + bb['width'] * 0.7, bb['y'] + bb['height'] * 0.7, steps=4)
      L.mouse.move(bb['x'] + bb['width'] * 0.93, bb['y'] + bb['height'] * 0.93, steps=4); L.mouse.up()
      L.click('#cpOk')
      L.wait_for_function("(b0)=>CONTI.S.services[0].items[0].pieces[0].blob!==b0", arg=L.evaluate("CONTI.S.services[0].items[0].pieces[0].blob"), timeout=15000)
      L.wait_for_timeout(500)
      pc = L.evaluate("(()=>{const p=CONTI.S.services[0].items[0].pieces[0];return {w:p.w,h:p.h,m:p.markers,c:p.chords,hl:p.hls}})()")
      if not pc['m']: bad('F92 마커가 사라짐')
      else:
        m = pc['m'][0]
        d = L.evaluate(DARK_JS, [pid, m['x'], m['y']])
        if d['v'] is None or d['v'] > 100: bad('F92 자른 뒤 마커가 표적 위에 없음: 마커 (%s,%s) · 이미지 %sx%s · 밝기 %s' % (m['x'], m['y'], d['w'], d['h'], d['v']))
        c = pc['c'][0]; d2 = L.evaluate(DARK_JS, [pid, c['x'] + c['w'] // 2, c['y'] + c['h'] // 2])
        if d2['v'] is None or d2['v'] > 100: bad('F92 자른 뒤 코드가 표적 위에 없음: %s · 밝기 %s' % (c, d2['v']))
        h = pc['hl'][0]; d3 = L.evaluate(DARK_JS, [pid, h['x'] + h['w'] // 2, h['y'] + h['h'] // 2])
        if d3['v'] is None or d3['v'] > 100: bad('F92 자른 뒤 하이라이트가 표적 위에 없음: %s · 밝기 %s' % (h, d3['v']))
        if d['w'] != pc['w'] or d['h'] != pc['h']: bad('F92 조각 크기와 이미지 크기가 다름: %s vs %sx%s' % (pc, d['w'], d['h']))
    print('F92 checked')

    # ---------- F135 악보 다시 만들기가 끝날 때 ----------
    ONE = {'at': 1, 'model': 'test', 'lines': 1, 'title': '시험곡', 'key': 'A', 'time': '4/4', 'tempo': 70, 'verses': 1, 'pickup': False,
           'measures': [{'c': [{'b': 0, 't': 'A'}], 'n': [{'p': 'A4', 'd': 1}]}]}
    HOLD = """()=>{window.__hold=new Promise(r=>window.__release=r);if(!window.__of){window.__of=window.fetch;
      window.fetch=async(u,o)=>{if(/\\/api\\/score$/.test(String(u))&&o&&o.method==='POST')await window.__hold;return window.__of(u,o)}}}"""
    def start_rebuild():
        L.evaluate("(sc)=>{const it=CONTI.S.services[0].items[0];it.score=JSON.parse(JSON.stringify(sc));CONTI.save()}", ONE)
        L.evaluate("(id)=>location.hash='#/edit/'+id", svc); L.wait_for_timeout(800)
        L.evaluate("()=>CONTI.render()"); L.wait_for_selector('[data-act="score-make"]', timeout=8000)
        L.evaluate(HOLD); answers[:] = ['2']
        L.click('[data-act="score-make"]'); L.wait_for_timeout(600)
    # 1) 기다리는 동안 그 악보 화면을 열어 둔 경우 → 새 악보로 다시 그린다
    start_rebuild()
    # 앱 안에서 여는 길(「악보 N마디」 = go('score/…')) 그대로 — 주소가 한 글자라도 다르면 hashchange 가 나서 재현이 안 된다
    L.click('[data-act="score-open"]'); L.wait_for_selector('#osmd svg', timeout=25000); L.wait_for_timeout(800)
    if L.evaluate("CONTI.route().name") != 'score': bad('F135 시험 준비 실패: 악보 화면이 안 열림')
    n_old = L.evaluate("CONTI.SC.osmd?CONTI.SC.osmd.GraphicSheet.MeasureList.length:null")
    L.evaluate("()=>window.__release()"); L.wait_for_timeout(3500)
    want = L.evaluate("CONTI.S.services[0].items[0].score.measures.length")
    n_new = L.evaluate("CONTI.SC.osmd?CONTI.SC.osmd.GraphicSheet.MeasureList.length:null")
    if want == n_old: bad('F135 시험 준비 실패: 새 악보 마디 수가 옛것과 같음 %s' % want)
    if n_new != want: bad('F135 같은 악보 화면에서 새 악보로 안 그려짐: 그림 %s마디 · 데이터 %s마디' % (n_new, want))
    # 2) 기다리는 동안 홈으로 간 경우 → 끝나도 악보 화면으로 끌고 가지 않는다
    start_rebuild()
    L.evaluate("()=>location.hash='#/home'"); L.wait_for_timeout(800)
    L.evaluate("()=>window.__release()"); L.wait_for_timeout(3000)
    rt = L.evaluate("CONTI.route().name")
    if rt != 'home': bad('F135 다른 화면으로 갔는데 악보 화면으로 끌려감: %s' % rt)
    # 3) 편집 화면에 그대로 있으면 예전처럼 악보 화면으로 간다
    start_rebuild()
    L.evaluate("()=>window.__release()"); L.wait_for_timeout(3000)
    rt = L.evaluate("CONTI.route()")
    if rt['name'] != 'score' or rt['b'] != item: bad('F135 편집 화면에서 기다리면 악보 화면으로 가야 함: %s' % rt)
    print('F135 checked')

    # ---------- G18 옥타브 바로잡기 ----------
    line = lambda ps: {'key': 'D', 'time': '4/4', 'measures': [{'c': [], 'n': [{'p': x, 'd': 4} for x in ps[i:i+4]]} for i in range(0, len(ps), 4)]}
    V1 = ['A3', 'D4', 'D4', 'E4', 'F#4', 'E4', 'D4', 'C#4']
    V2 = ['D4', 'D4', 'E4', 'F#4', 'E4', 'D4', 'B3', 'A3']
    C1 = ['B4', 'C#5', 'D5', 'C#5', 'B4', 'A4', 'B4', 'A4']
    C2 = ['A4', 'B4', 'C#5', 'D5', 'B4', 'A4', 'F#4', 'A4']
    pitches = "(sc)=>sc.measures.flatMap(m=>m.n.map(n=>n.p))"
    for parts, name in [([V1, V2, C1, C2], '벌스 둘 + 후렴 둘'), ([V1, C1], '벌스 + 후렴'), ([V1, C1, C2], '벌스 + 후렴 둘')]:
      sc = L.evaluate("(ps)=>CONTI.mergeScoreParts(ps)", [line(x) for x in parts])
      got = L.evaluate(pitches, sc); want = sum(parts, [])
      if got != want: bad('G18 %s: 제대로 적힌 줄이 옮겨짐\n  want %s\n  got  %s' % (name, want, got))
    # AI 가 한 줄을 한 옥타브 아래로 적은 것은 여전히 바로잡는다
    low = lambda ps: [x[:-1] + str(int(x[-1]) - 1) for x in ps]
    sc = L.evaluate("(ps)=>CONTI.mergeScoreParts(ps)", [line(C1), line(low(C2)), line(C1)])
    got = L.evaluate(pitches, sc)
    if got != C1 + C2 + C1: bad('G18 한 옥타브 아래로 적힌 후렴 줄을 못 바로잡음: %s' % got[8:16])
    sc = L.evaluate("(ps)=>CONTI.mergeScoreParts(ps)", [line(V1), line(low(V2)), line(C1), line(C2)])
    got = L.evaluate(pitches, sc)
    if got != V1 + V2 + C1 + C2: bad('G18 한 옥타브 아래로 적힌 벌스 줄을 못 바로잡음: %s' % got[8:16])
    # 높은 곡에서 한 옥타브 아래로 적혀 C4 위에 걸친 줄 (한 옥타브 넘게 벌어짐) 도 바로잡는다
    HI = ['D5', 'E5', 'F#5', 'E5', 'D5', 'C#5', 'D5', 'E5']
    HI2 = ['C#5', 'D5', 'E5', 'D5', 'C#5', 'B4', 'C#5', 'D5']
    sc = L.evaluate("(ps)=>CONTI.mergeScoreParts(ps)", [line(HI), line(low(HI2)), line(HI)])
    got = L.evaluate(pitches, sc)
    if got != HI + HI2 + HI: bad('G18 높은 곡에서 한 옥타브 아래로 적힌 줄을 못 바로잡음: %s' % got[8:16])
    print('G18 checked')

    if errs: bad('콘솔 오류: ' + errs[0])
    b.close()
  if fails: print('FAILED %d' % len(fails)); sys.exit(1)
  print('OK — 설정 자동 저장 · 초대 링크 복사 · 코드 보정 · 자르기 좌표 · 악보 다시 그리기 · 옥타브 바로잡기')

run()
