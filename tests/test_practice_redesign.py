# 폰 세로 연습 화면 리디자인 (폰 리디자인 A·B·C — 외부 기여 패치를 지금 main 에 맞춰 다시 넣은 것) 검사
#   A  폰 세로(폭 640 이하 · 세로): 위에 송폼 한 줄 + 곡 메모, 가운데 악보(혼자 스크롤), 아래 미디어 독.
#      재생·±5·시간 줄·여기에 메모·펼치기가 독 안 · 화면(배너 윗변 + 8px) 안 · 서로 안 겹침 · 가로 넘침 없음 · 악보 칸이 화면 대부분
#      상단: 건반·메트로놈·예배 노트·재구성 악보 단추는 숨고 '보기 설정'(안 읽은 노트면 빨간 점)·무대 단추만 — 모두 화면 안
#      반 줄: 샘플 악보의 줄이 마디선에서 반으로 나뉘어 1.3배 넘게 커진다 · 반 칸은 악보 폭 안 · 마커 원이 칸 안
#      미디어 없는 곡은 독째 숨고 악보가 그 자리까지
#   B  독 펼치기: 영상(유튜브 정책 — 보이는 채 재생) · 재생·±5·시간 줄·여기에 메모가 영상 바로 밑 · 타임라인 두 줄 이상 · 악보 칸 조금(96~140px) 남음 · 곡 메모 줄은 접힘
#      접힌 채 재생(단추·Space 페달)을 누르면 먼저 편다 · 영상이 돌고 있는데 접으면 멈춘다 · 펴고 접어도 영상(iframe)을 다시 불러오지 않는다
#      접힌 독 가운데에 미디어 이름 · 다음 타임라인 메모
#   C  보기 설정 시트: 세션(제자리 — 영상·재생 시각·악보 스크롤 그대로) · 메모 필터(옆 칸 칩과 같이) · 반 줄/원본 줄(이 기기에 기억 —
#      앱을 다시 켜도) · 크기 · 도구(건반·메트로놈·예배 노트) · 노트를 읽으면 점이 사라진다 · 시트 단추가 화면 안
#   H  반 줄 픽셀은 최근 악보 HALF_KEEP 장만 들고 있다 · 못 읽은 악보는 나누지 않는다
#   E  악보 칸이 화면 왼쪽 끝부터라도 가장자리에서 쓸면 뒤로 (확대해 옆으로 넘길 악보면 넘김) — 크로미움 터치 흉내
#   W  가로 폰(844x390)·아이패드(820x1180 · 1180x820 · 1024x1366): 예전 배치 그대로 — 송폼 줄·독·반 줄 없음, 상단 도구, 재생·±5·여기에 메모 보임
# 사용: CONTI_URL=http://localhost:8766/ .venv/bin/python tests/test_practice_redesign.py
#      BROWSERS=webkit,chromium(기본 둘 다) · SOFT=1 이면 실패해도 끝까지 · PART=a,b,c,h,w,e · SHOTS=폴더 (화면을 남긴다)
import os, sys, time
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
STACKED = os.path.join(ROOT, 'docs', 'sample_stacked.jpg')
SOFT = os.environ.get('SOFT') == '1'
SHOTS = os.environ.get('SHOTS')
H = {'x-conti': '1'}
tag = str(int(time.time()))[-6:]
FAILS = []
def fail(m):
    print('FAIL:', m)
    if SOFT: FAILS.append(m); return
    sys.exit(1)
def shot(pg, name):
    if SHOTS: os.makedirs(SHOTS, exist_ok=True); pg.screenshot(path=os.path.join(SHOTS, name + '.png'))

YT_ALL, YT_DRUM = 'jNQXAC9IVRw', 'dQw4w9WgXcQ'
FORM = '1414 – Int – A A B B – C – B B(Key up) C – Outro'
SONG_NOTE = '드럼: B 후반 Down, 하프타임 · 두 번째 C 는 인도자 신호 보고 들어가기'

# Playwright 웹킷(임시 저장소)은 IndexedDB 에 Blob 을 못 넣는다('Error preparing Blob/File data to be stored') — 악보 그림이 안 떠
# 연습 화면을 볼 수 없다. 시험에서만 그림은 페이지 메모리에 두고 IndexedDB 에는 넣지 않는다(다시 불러오면 없는 그림이라 새로 받는다).
# 아이폰 웹뷰는 그대로 넣는다
IDB_BLOB_SHIM = """(()=>{const mem=new Map(),put=IDBObjectStore.prototype.put,get=IDBObjectStore.prototype.get;
  IDBObjectStore.prototype.put=function(v,k){if(v instanceof Blob){mem.set(this.name+'|'+k,v);return put.call(this,0,'__shim')}return put.call(this,v,k)};
  IDBObjectStore.prototype.get=function(k){const r=get.call(this,k),key=this.name+'|'+k;
    if(mem.has(key))r.addEventListener('success',()=>Object.defineProperty(r,'result',{value:mem.get(key),configurable:true}));return r}})()"""

def new_page(br, vp, state=None, errs=None):
    ctx = br.new_context(viewport=vp, has_touch=vp['width'] < 1100, storage_state=state)
    if br.browser_type.name == 'webkit': ctx.add_init_script(IDB_BLOB_SHIM)
    pg = ctx.new_page()
    pg.yt = [0]   # 유튜브 틀을 불러온 횟수 (다시 불러오면 늘어난다)
    def yt(r):
        if '/embed/' in r.request.url: pg.yt[0] += 1
        r.fulfill(status=200, body='<html><body style="background:#222"></body></html>', content_type='text/html')
    pg.route('**/*youtube*/**', yt)
    pg.on('dialog', lambda d: d.accept())
    if errs is not None: pg.on('pageerror', lambda e: errs.append(repr(e)[:300]))
    return ctx, pg

def seed(br, errs):
    ctx, pg = new_page(br, {'width': 1366, 'height': 900}, None, errs)
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=15000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
    pg.fill('#lgName', '하은'); pg.fill('#lgUser', 'prd' + tag); pg.fill('#lgPass', 'secret12'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam', timeout=15000); pg.fill('#gtTeam', '폰연습팀'); pg.click('#gtSess .q:has-text("건반")')
    pg.click('[data-act="team-create"]'); pg.wait_for_selector('.shell[data-page]', timeout=15000)
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
    pg.fill('[data-f="svc.name"]', '폰 예배'); pg.wait_for_timeout(300)
    si = pg.evaluate("CONTI.S.services.findIndex(s=>s.name==='폰 예배')")
    for n, (t, f, form) in enumerate([('우리 주 하나님', SHEET, FORM), ('두 번째 곡', STACKED, 'A – B'), ('세 번째 곡', SHEET, '')]):
        pg.click('[data-act="add-item"]'); pg.wait_for_timeout(400)
        pg.fill('[data-f="item.title"]', t); pg.fill('[data-f="item.key"]', 'AGD'[n])
        if form: pg.fill('[data-f="item.form"]', form)
        pg.set_input_files('#pieceFile', [f])
        pg.wait_for_function("([si,n])=>{const it=CONTI.S.services[si].items[n];const p=it&&(it.pieces||[])[0];return p&&p.w>0}", arg=[si, n], timeout=120000)
        pg.wait_for_timeout(500)
    # 1곡: 마커 A(여백 자리에 메모 띠)·B · 곡 메모 · 영상 둘(전체 · 드럼 전용) · 예배 노트
    pg.evaluate("""([si,a,d,note])=>{const s=CONTI.S.services[si];
      s.items.forEach((it,n)=>{const p=it.pieces[0];
        p.markers=[{id:'mA'+n,label:'A',x:Math.round(p.w*0.03),y:Math.round(p.h*0.47),cut:CONTI.autoCut(p,Math.round(p.h*0.47))},
                   {id:'mB'+n,label:'B',x:Math.round(p.w*0.52),y:Math.round(p.h*0.62),cut:null}]});
      const it=s.items[0];it.songNote=note;
      it.media=[{id:'ytAll',type:'youtube',url:'https://youtu.be/'+a,name:'참고 영상',notes:[]},
                {id:'ytDrum',type:'youtube',url:'https://youtu.be/'+d,name:'드럼 영상',sessions:['드럼'],notes:[]}];
      s.message='이번 주 노트 — 2절 끝나고 한 번 쉬어요';CONTI.save()}""", [si, YT_ALL, YT_DRUM, SONG_NOTE])
    pg.wait_for_timeout(1500)
    info = pg.evaluate("(si)=>({team:CONTI.S.team.id,sid:CONTI.S.services[si].id,item:CONTI.S.services[si].items[0].id})", si)
    # 타임라인 메모·마커 메모는 메모 표(POST /notes)로 — 콘티 문서에 넣은 것은 동기화가 지운다
    r = ctx.request.post(URL + 'api/notes', headers=H, data={'teamId': info['team'], 'serviceId': info['sid'], 'notes': [
        {'id': 'tl1' + tag, 'itemId': info['item'], 'mediaId': 'ytAll', 't': 12, 'layer': 'leader', 'text': '필인 후 B 진입'},
        {'id': 'tl2' + tag, 'itemId': info['item'], 'mediaId': 'ytAll', 't': 40, 'layer': 'leader', 'text': '브릿지 조용히'},
        {'id': 'tl3' + tag, 'itemId': info['item'], 'mediaId': 'ytAll', 't': 70, 'layer': 'leader', 'text': 'Key up 직전 한 박 쉬고'},
        {'id': 'mk1' + tag, 'itemId': info['item'], 'markerId': 'mA0', 'layer': 'leader', 'text': '드럼 B 후반 Down'}]})
    if r.status != 200 or r.json().get('saved') != 4: fail('준비: 메모를 못 넣음 %s %s' % (r.status, r.text()[:200]))
    pg.click('[data-act="publish"]'); pg.wait_for_selector('#pubOnly', timeout=8000)
    pg.click('#pubOnly'); pg.wait_for_timeout(3000)
    if pg.evaluate("(si)=>(CONTI.S.services[si].published.items[0].media||[]).length", si) != 2: fail('준비: 발행본에 영상 둘이 없음')
    state = ctx.storage_state()
    ctx.close()
    return info['sid'], state

def insets(pg, sat=0, sab=0):
    pg.evaluate("(v)=>{const d=document.documentElement.style;d.setProperty('--sat',v[0]+'px');d.setProperty('--sab',v[1]+'px')}", [sat, sab])
def banner(pg, h):
    pg.evaluate("(h)=>{if(h){document.documentElement.style.setProperty('--adh',h+'px');document.body.classList.add('hasad')}else document.body.classList.remove('hasad')}", h)
    pg.wait_for_timeout(350)

def go_play(pg, sid, i=0, half=True):
    pg.goto(URL + '#/view/' + sid); pg.wait_for_selector('[data-act="play"][data-stage="1"]', timeout=15000); pg.wait_for_timeout(700)
    if pg.locator('#msgOk').count(): pg.click('#msgOk'); pg.wait_for_timeout(400)   # 첫 입장 예배 노트
    pg.goto(URL + '#/play/%s/%d' % (sid, i)); pg.wait_for_selector('#sheet .slice', timeout=15000)
    if half: pg.wait_for_function("document.querySelectorAll('#sheet .slice.half').length>=8", timeout=15000)
    pg.wait_for_timeout(600)

M = """()=>{const R=e=>{if(!e)return null;const r=e.getBoundingClientRect();return {t:r.top,b:r.bottom,l:r.left,r:r.right,w:r.width,h:r.height}};
  const q=s=>document.querySelector(s),vis=e=>!!e&&e.getClientRects().length>0&&getComputedStyle(e).visibility!=='hidden';
  const cs=getComputedStyle(document.documentElement),ad=document.body.classList.contains('hasad');
  const sab=parseFloat(cs.getPropertyValue('--sab'))||0,adh=ad?(parseFloat(cs.getPropertyValue('--adh'))||0):0;
  const med=q('#ws .media'),tl=q('#tlist'),pb=q('#ws .media>.pbody');
  const C=s=>{const e=q(s);return vis(e)?R(e):null};
  return {W:innerWidth,H:innerHeight,ad,limit:innerHeight-sab-adh-(ad?8:0),bottom:innerHeight-sab,docW:document.documentElement.scrollWidth,
    pv:CONTI.pvOn(),top:R(q('.top')),topBtns:[...q('.top').children].filter(vis).map(b=>({a:b.dataset.act||b.className,...R(b)})),
    hiddenTools:['piano','metro','msg'].filter(a=>{const e=q('.top [data-act="'+a+'"]');return e&&!vis(e)}),
    pview:C('.top [data-act="pview"]'),pviewDot:!!(q('.top [data-act="pview"]')||{classList:{contains:()=>false}}).classList.contains('dot'),
    form:C('#ws>.pform'),formText:(q('#ws>.pform')||{}).textContent||'',note:C('#ws>.pnote'),sheet:C('#sheetwrap'),
    dock:C('#ws .media'),open:!!med&&med.classList.contains('open'),nomedia:q('#ws').classList.contains('nomedia'),
    play:C('#playBtn'),b5:C('[data-act=skip][data-d="-5"]'),f5:C('[data-act=skip][data-d="5"]'),prog:C('#prog'),tcur:C('#tCur'),tdur:C('#tDur'),
    tnote:C('[data-act=tnote]'),exp:C('#ws .mdexp'),mini:C('#mdmini'),miniText:(q('#mdmini')||{}).textContent||'',
    vid:R(q('#mediaBox .vid')),ytfb:C('#ytfb'),tl:C('#tlist'),tlh:tl?[tl.clientHeight,tl.scrollHeight,tl.querySelectorAll('.tl').length]:null,
    pb:pb?{st:pb.scrollTop,sh:pb.scrollHeight,ch:pb.clientHeight,...R(pb)}:null,
    half:[...document.querySelectorAll('#sheet .slice.half')].map(e=>({...R(e),s:+e.dataset.s,p:e.dataset.piece})),
    full:[...document.querySelectorAll('#sheet .slice:not(.half)')].map(e=>({s:+e.dataset.s,p:e.dataset.piece})),
    sheetBox:R(q('#sheet')),sheetScroll:[q('#sheetwrap').scrollWidth,q('#sheetwrap').clientWidth],
    marks:[...document.querySelectorAll('#sheet .slice.half .mkabs')].map(m=>{const r=m.getBoundingClientRect(),s=m.closest('.slice').getBoundingClientRect();return [r.left+r.width/2-s.left,s.width]})}}"""

def inside(a, box, pad=1):
    return a and box and a['t'] >= box['t'] - pad and a['b'] <= box['b'] + pad and a['l'] >= box['l'] - pad and a['r'] <= box['r'] + pad
def overlap(a, b):
    return a and b and a['l'] < b['r'] - 1 and b['l'] < a['r'] - 1 and a['t'] < b['b'] - 1 and b['t'] < a['b'] - 1

def check_frame(m, label):
    if m['docW'] > m['W'] + 0.5: fail('%s: 화면이 옆으로 넘침 (%s > %s)' % (label, m['docW'], m['W']))
    for b in m['topBtns']:
        if b['l'] < -0.5 or b['r'] > m['W'] + 0.5: fail('%s: 상단 %s 가 화면 밖 %s' % (label, b['a'], b))

def check_collapsed(m, label, media=True):
    check_frame(m, label)
    if not m['pv']: fail('%s: 폰 세로인데 새 연습 화면(pvOn)이 아님' % label); return
    if sorted(m['hiddenTools']) != ['metro', 'msg', 'piano']: fail('%s: 상단 건반·메트로놈·노트 단추가 안 숨음 %s' % (label, m['hiddenTools']))
    if not m['pview'] or m['pview']['r'] > m['W']: fail('%s: 보기 설정 단추가 안 보임 %s' % (label, m['pview']))
    if media:
        if not m['form'] or abs(m['form']['h'] - 44) > 1 or m['form']['t'] < m['top']['b'] - 1: fail('%s: 송폼 한 줄이 상단 바 밑 44px 가 아님 %s' % (label, m['form']))
        if m['formText'] != FORM: fail('%s: 송폼 글이 다름 %r' % (label, m['formText']))
        if not m['note'] or m['note']['t'] < m['form']['b'] - 1 or m['note']['h'] > 60: fail('%s: 곡 메모 줄이 송폼 밑 두 줄 안이 아님 %s' % (label, m['note']))
    sh, dk = m['sheet'], m['dock']
    above = (m['note'] or m['form'] or m['top'])['b']
    if not sh or sh['t'] < above - 1: fail('%s: 악보 칸이 송폼·메모 줄을 덮음 %s' % (label, sh)); return
    if media:
        if not dk: fail('%s: 미디어 독이 안 보임' % label); return
        if m['open']: fail('%s: 독이 처음부터 펼쳐져 있음' % label)
        if sh['b'] > dk['t'] + 1: fail('%s: 악보 칸이 독 밑으로 들어감 %s %s' % (label, sh, dk))
        if dk['b'] > m['limit'] + 1: fail('%s: 독이 배너(윗변 %s)·홈 인디케이터에 깔림 %s' % (label, m['limit'], dk))
        if dk['b'] < m['limit'] - 2: fail('%s: 독 밑에 빈 띠 %s < %s' % (label, dk['b'], m['limit']))
        for k in ['play', 'b5', 'f5', 'prog', 'tcur', 'tdur', 'tnote', 'exp', 'mini']:
            if not m[k] or m[k]['w'] < 1: fail('%s: 접힌 독에 %s 가 안 보임' % (label, k)); continue
            if not inside(m[k], {'t': dk['t'], 'b': min(dk['b'], m['limit']), 'l': 0, 'r': m['W']}): fail('%s: %s 가 독·화면 밖(잘림) %s dock=%s' % (label, k, m[k], dk))
        for a, b in [('play', 'b5'), ('play', 'f5'), ('f5', 'mini'), ('mini', 'exp'), ('tdur', 'tnote'), ('prog', 'tnote'), ('play', 'prog')]:
            if overlap(m[a], m[b]): fail('%s: %s 와 %s 가 겹침' % (label, a, b))
        for k in ['play', 'b5', 'f5', 'exp']:
            if m[k] and min(m[k]['w'], m[k]['h']) < 39.5: fail('%s: %s 누를 자리가 40px 보다 작음 %s' % (label, k, m[k]))
        if m['vid'] and m['vid']['w'] > 8: fail('%s: 접힌 독에 영상이 보임 %s' % (label, m['vid']))
        if m['tl']: fail('%s: 접힌 독에 타임라인 목록이 보임' % label)
        avail = m['limit'] - m['top']['b']
        if sh['h'] < avail * (0.62 if m['H'] >= 800 else 0.5): fail('%s: 악보 칸이 좁음 %.0f / %.0f' % (label, sh['h'], avail))
    else:
        if not m['nomedia'] or dk: fail('%s: 미디어 없는 곡인데 독이 보임 %s' % (label, dk))
        if abs(sh['b'] - m['limit']) > 2: fail('%s: 미디어 없는 곡 악보 칸이 아래까지 안 내려옴 %s limit %s' % (label, sh, m['limit']))

def check_half(m, label):
    hs = m['half']
    if len(hs) < 8 or len(hs) % 2: fail('%s: 반 줄이 모자람/짝이 안 맞음 %d' % (label, len(hs))); return
    box = m['sheetBox']
    for h in hs:
        if h['r'] > box['r'] + 0.5 or h['l'] < box['l'] - 0.5: fail('%s: 반 줄 칸이 악보 폭 밖 %s %s' % (label, h, box)); break
    if m['sheetScroll'][0] > m['sheetScroll'][1] + 1: fail('%s: 반 줄 악보가 옆으로 넘침 %s' % (label, m['sheetScroll']))
    base = {f['p']: f['s'] for f in m['full']}
    ratio = min(h['s'] / base[h['p']] for h in hs if h['p'] in base) if base else 0
    if ratio < 1.3: fail('%s: 반 줄이 원본보다 충분히 크지 않음 ×%.2f' % (label, ratio))
    for x, w in m['marks']:
        if x < 12 or x > w - 12: fail('%s: 반 줄 마커 원이 칸 끝에서 잘림 %s/%s' % (label, x, w))
    return ratio

PHONES = [((390, 844), (47, 34)), ((412, 915), (24, 0)), ((375, 667), (20, 0)), ((375, 1180), (24, 20))]   # 마지막은 아이패드 나눠 보기(좁은 창)

def part_a(br, sid, state, errs, B):
    for (w, h), (sat, sab) in PHONES:
        ctx, pg = new_page(br, {'width': w, 'height': h}, state, errs)
        go_play(pg, sid)
        insets(pg, sat, sab); pg.wait_for_timeout(300)
        for adh in (0, 50):
            banner(pg, adh)
            label = '%s A %dx%d%s' % (B, w, h, ' + 배너' if adh else '')
            m = pg.evaluate(M)
            check_collapsed(m, label)
            r = check_half(m, label)
            shot(pg, '%s_a_%dx%d_%d' % (B, w, h, adh))
            print('%s: 악보 %.0fpx(%.0f%%) · 반 줄 %d칸 ×%.2f · 독 %.0fpx · 재생·±5·시간 줄·여기에 메모 칸 안 ok' % (label, m['sheet']['h'], m['sheet']['h'] / m['H'] * 100, len(m['half']), r or 0, m['dock']['h']))
            # B 독 펼치기
            n0 = pg.yt[0]
            pg.click('#ws .mdexp'); pg.wait_for_timeout(450)
            e = pg.evaluate(M)
            check_frame(e, label + ' 펼침')
            dk, pb = e['dock'], e['pb']
            view = {'t': max(dk['t'], pb['t']), 'b': min(dk['b'], pb['b'], e['limit']), 'l': 0, 'r': e['W']}
            if not e['open']: fail('%s: 펼치기를 눌러도 독이 안 펼쳐짐' % label)
            if dk['b'] > e['limit'] + 1: fail('%s 펼침: 독이 배너에 깔림 %s' % (label, dk))
            v = e['vid']
            if not v or v['w'] < min(300, e['W'] - 40) or v['h'] < (199 if e['W'] >= 390 else 180) or not inside(v, view): fail('%s 펼침: 영상이 작거나 칸 밖 %s view=%s' % (label, v, view))
            for k in ['play', 'b5', 'f5', 'prog', 'tnote', 'exp']:
                if not e[k] or not inside(e[k], view): fail('%s 펼침: %s 가 칸 밖(잘림) %s view=%s' % (label, k, e[k], view))
            if e['play'] and v and e['play']['t'] < v['b'] - 1: fail('%s 펼침: 재생 단추가 영상 위' % label)
            if e['sheet']['h'] < min(140, max(96, e['H'] * 0.18)) - 1: fail('%s 펼침: 악보 칸이 거의 안 남음 %s' % (label, e['sheet']))
            # 타임라인·유튜브에서 열기는 독 안에서 내려 보면 보인다 (작은 폰)
            pg.evaluate("document.querySelector('#ws .media>.pbody').scrollTop=9999"); pg.wait_for_timeout(150)
            e2 = pg.evaluate(M)
            tlh = e2['tlh']
            if not e2['tl'] or tlh[2] != 3 or tlh[0] < min(60, tlh[1]) - 1: fail('%s 펼침: 타임라인 메모 세 줄 중 두 줄도 안 보임 %s' % (label, tlh))
            view2 = {'t': e2['pb']['t'], 'b': min(e2['pb']['b'], e2['limit']), 'l': 0, 'r': e2['W']}
            for k in ['tl', 'ytfb']:
                if not e2[k] or e2[k]['t'] > view2['b'] - 20 or e2[k]['b'] < view2['t'] + 20: fail('%s 펼침: 내려도 %s 가 안 보임 %s view=%s' % (label, k, e2[k], view2))
            pg.evaluate("document.querySelector('#ws .media>.pbody').scrollTop=0")
            shot(pg, '%s_b_%dx%d_%d' % (B, w, h, adh))
            pg.click('#ws .mdexp'); pg.wait_for_timeout(450)
            c = pg.evaluate(M)
            if c['open'] or (c['vid'] and c['vid']['w'] > 8): fail('%s: 접기를 눌러도 독이 안 접힘' % label)
            if pg.yt[0] != n0: fail('%s: 독을 펴고 접자 영상을 다시 불러옴 (%d → %d)' % (label, n0, pg.yt[0]))
            print('%s 펼침: 영상 %.0fx%.0f · 조작 단추 영상 밑 · 타임라인 %d줄 · 악보 %.0fpx 남음 · 다시 불러오지 않음 ok' % (label, v['w'] if v else 0, v['h'] if v else 0, tlh[2], e['sheet']['h']))
        # 미디어 없는 곡(2곡) — 독째 숨고 악보가 아래까지
        banner(pg, 50)
        pg.evaluate("CONTI.go('play/%s/1')" % sid); pg.wait_for_selector('#ws.nomedia', timeout=10000); pg.wait_for_timeout(1500)
        m = pg.evaluate(M)
        check_collapsed(m, '%s A %dx%d 2곡(미디어 없음) + 배너' % (B, w, h), media=False)
        ctx.close()

def part_b(br, sid, state, errs, B):
    ctx, pg = new_page(br, {'width': 390, 'height': 844}, state, errs)
    go_play(pg, sid)
    label = '%s B 390' % B
    m = pg.evaluate(M)
    if '참고 영상' not in m['miniText'] or '0:12' not in m['miniText'] or '필인 후 B 진입' not in m['miniText']:
        fail('%s: 접힌 독 가운데에 미디어 이름·다음 메모가 없음 %r' % (label, m['miniText']))
    # 재생 시각이 지나면 다음 메모로
    pg.evaluate("()=>{CONTI.P.t=41;window.dispatchEvent(new Event('resize'))}"); pg.wait_for_timeout(300)
    t2 = pg.evaluate("document.getElementById('mdmini').textContent")
    if '1:10' not in t2: fail('%s: 41초인데 다음 메모(1:10)가 아님 %r' % (label, t2))
    pg.evaluate("CONTI.P.t=0")
    # 접힌 채 재생 단추 → 먼저 펼친다 (유튜브는 보이는 채로만)
    pg.click('#playBtn'); pg.wait_for_timeout(400)
    if not pg.evaluate("CONTI.pl().dock"): fail('%s: 접힌 채 재생을 눌렀는데 독이 안 펼쳐짐' % label)
    # 도는 중에 접으면 멈춘다
    pg.evaluate("()=>{window.__pz=0;const P=CONTI.P;P.__p=P.pause;P.pause=function(){window.__pz++;return P.__p.apply(P,arguments)};P.playing=true}")
    pg.click('#ws .mdexp'); pg.wait_for_timeout(300)
    if pg.evaluate("window.__pz") < 1: fail('%s: 영상이 도는 중에 접었는데 멈추지 않음' % label)
    pg.evaluate("()=>{const P=CONTI.P;P.pause=P.__p;P.playing=false}")
    # Space(블루투스 페달)도 같은 길
    if pg.evaluate("CONTI.pl().dock"): fail('%s: 접기가 안 됨' % label)
    pg.mouse.click(5, 300); pg.keyboard.press('Space'); pg.wait_for_timeout(400)
    if not pg.evaluate("CONTI.pl().dock"): fail('%s: 접힌 채 Space 로 재생했는데 독이 안 펼쳐짐' % label)
    # 펼친 동안에는 곡 메모 줄을 접는다 (작은 폰에서 영상·조작 단추 자리)
    if pg.locator('#ws>.pnote').is_visible(): fail('%s: 독을 펼쳤는데 곡 메모 줄이 그대로' % label)
    pg.click('#ws .mdexp'); pg.wait_for_timeout(300)
    # 곡 메모 줄 — 누르면 다 보인다
    h0 = pg.evaluate("document.querySelector('#ws>.pnote').getBoundingClientRect().height")
    pg.click('#ws>.pnote'); pg.wait_for_timeout(200)
    h1 = pg.evaluate("[document.querySelector('#ws>.pnote').getBoundingClientRect().height,document.querySelector('#ws>.pnote').scrollHeight,document.querySelector('#ws>.pnote').classList.contains('open')]")
    if not h1[2] or h1[0] + 1 < h1[1]: fail('%s: 곡 메모를 눌러도 다 안 보임 %s' % (label, h1))
    pg.click('#ws>.pnote')
    # 같은 예배 안에서 곡을 넘겨도 펼친 독은 펼친 채
    pg.click('#ws .mdexp'); pg.wait_for_timeout(300)
    pg.evaluate("CONTI.go('play/%s/1')" % sid); pg.wait_for_selector('#ws.nomedia', timeout=10000); pg.wait_for_timeout(300)
    pg.evaluate("CONTI.go('play/%s/0')" % sid); pg.wait_for_selector('#ws .media', timeout=10000); pg.wait_for_timeout(500)
    if not pg.evaluate("!!document.querySelector('#ws .media.open')&&document.getElementById('ws').classList.contains('dockopen')"): fail('%s: 곡을 넘기고 돌아오자 펼친 독이 접힘' % label)
    print('%s: 가운데 미디어 이름·다음 메모 · 접힌 채 재생/Space → 펼침 · 돌 때 접으면 멈춤 · 곡 메모 펼치기 · 곡을 넘겨도 펼친 채 ok' % label)
    ctx.close()

def open_pview(pg):
    pg.click('.top [data-act="pview"]'); pg.wait_for_selector('#pvs [data-vs]'); pg.wait_for_timeout(350)

def part_c(br, sid, state, errs, B):
    ctx, pg = new_page(br, {'width': 390, 'height': 844}, state, errs)
    go_play(pg, sid)
    insets(pg, 47, 34)
    label = '%s C 390' % B
    # 안 읽은 노트 → 보기 설정 단추에 빨간 점
    pg.evaluate("(sid)=>{const s=CONTI.S.services.find(x=>x.id===sid);s.published.messageRev=(s.published.messageRev||0)+5;CONTI.S.readRev={};CONTI.render()}", sid)
    pg.wait_for_timeout(900)
    if not pg.evaluate(M)['pviewDot']: fail('%s: 안 읽은 예배 노트인데 보기 설정 단추에 점이 없음' % label)
    open_pview(pg)
    shot(pg, '%s_c_sheet' % B)
    r = pg.evaluate("""()=>{const sm=document.querySelector('#modal .sheetm');const R=sm.getBoundingClientRect();
      const bs=[...document.querySelectorAll('#pvs button')].map(b=>{const r=b.getBoundingClientRect();return {t:b.textContent.trim(),l:r.left,r:r.right,w:r.width,h:r.height}});
      return {sm:[R.top,R.bottom,sm.scrollHeight,sm.clientHeight],bs,sess:[...document.querySelectorAll('#pvs [data-vs]')].map(b=>b.dataset.vs),
        on:[...document.querySelectorAll('#pvs [data-vs].on')].map(b=>b.dataset.vs),tools:[...document.querySelectorAll('#pvs [data-vt]')].map(b=>b.dataset.vt),
        dot:!!document.querySelector('#pvs [data-vt="msg"].dot'),team:CONTI.S.team.sessions.filter(s=>s!=='인도자')}}""")
    if r['sess'] != r['team'] or r['on'] != ['건반']: fail('%s: 세션 단추가 팀 세션과 다르거나 내 세션이 안 골라짐 %s' % (label, r))
    if r['tools'][:3] != ['piano', 'metro', 'msg'] or not r['dot']: fail('%s: 도구(건반·메트로놈·예배 노트 + 점)가 없음 %s' % (label, r['tools']))
    if r['sm'][0] < 47 - 0.5 or r['sm'][1] > 844 + 0.5: fail('%s: 시트가 화면 밖 %s' % (label, r['sm']))
    for b in r['bs']:
        if b['l'] < -0.5 or b['r'] > 390.5 or b['w'] < 30 or b['h'] < 30: fail('%s: 시트 단추가 화면 밖이거나 작음 %s' % (label, b))
    # 세션 — 제자리에서 (영상·재생 시각·악보 스크롤 그대로)
    st0 = pg.evaluate("()=>{const y=document.getElementById('yt');y.__keep=1;CONTI.P.t=7.7;CONTI.P.playing=true;const s=document.getElementById('sheetwrap');s.scrollTop=500;return s.scrollTop}")
    pg.click('#pvs [data-vs="베이스"]'); pg.wait_for_timeout(500)
    n = pg.evaluate("""()=>({keep:(document.getElementById('yt')||{}).__keep||0,t:CONTI.P.t,playing:CONTI.P.playing,st:document.getElementById('sheetwrap').scrollTop,
      sess:CONTI.pl().session,on:[...document.querySelectorAll('#pvs [data-vs].on')].map(b=>b.dataset.vs),chip:(document.querySelector('#pvs [data-vf="session"]')||{}).textContent,
      panel:(document.querySelector('[data-act="psess"].on')||{}).dataset})""")
    if not n['keep'] or abs(n['t'] - 7.7) > 0.01 or not n['playing'] or abs(n['st'] - st0) > 2: fail('%s: 세션을 바꾸자 영상·재생·스크롤이 흔들림 %s (st0 %s)' % (label, n, st0))
    if n['sess'] != '베이스' or n['on'] != ['베이스'] or n['chip'] != '베이스 메모' or (n['panel'] or {}).get('s') != '베이스': fail('%s: 세션이 베이스로 안 바뀜 %s' % (label, n))
    pg.evaluate("()=>{CONTI.P.playing=false}")
    # 드럼 — 드럼 전용 영상이 미디어 칩에 붙는다
    pg.click('#pvs [data-vs="드럼"]'); pg.wait_for_timeout(400)
    if pg.evaluate("document.querySelectorAll('[data-act=\"msel\"]').length") != 2: fail('%s: 드럼으로 바꿨는데 드럼 영상 칩이 없음' % label)
    pg.click('#pvs [data-vs="건반"]'); pg.wait_for_timeout(400)
    # 메모 필터 — 인도자 메모를 끄면 악보의 메모 칩이 사라지고 옆 칸 칩도 같이
    if not pg.locator('#sheet .m:has-text("드럼 B 후반 Down")').count(): fail('%s: 준비: 악보에 인도자 메모 띠가 없음' % label)
    pg.click('#pvs [data-vf="leader"]'); pg.wait_for_timeout(350)
    f = pg.evaluate("()=>({f:CONTI.pl().f.leader,panel:document.querySelector('[data-act=\"pf\"][data-k=\"leader\"]').classList.contains('on'),on:document.querySelector('#pvs [data-vf=\"leader\"]').classList.contains('on'),m:document.querySelectorAll('#sheet .m').length})")
    if f['f'] or f['panel'] or f['on'] or pg.locator('#sheet .m:has-text("드럼 B 후반 Down")').count(): fail('%s: 인도자 메모를 꺼도 남음 %s' % (label, f))
    pg.click('#pvs [data-vf="leader"]'); pg.wait_for_timeout(350)
    if not pg.locator('#sheet .m:has-text("드럼 B 후반 Down")').count(): fail('%s: 인도자 메모를 다시 켜도 안 보임' % label)
    # 크기
    pg.click('#pvs [data-vz="1"]'); pg.wait_for_timeout(350)
    z = pg.evaluate("[CONTI.pl().zoom,document.querySelector('#pvs .pvzoom b').textContent]")
    if abs(z[0] - 1.1) > 0.001 or z[1] != '110%': fail('%s: 크기 + 가 안 됨 %s' % (label, z))
    pg.click('#pvs [data-vz="-1"]'); pg.wait_for_timeout(350)
    # 도구 — 메트로놈 · 건반 (시트가 닫히고 도구가 열린다)
    pg.click('#pvs [data-vt="metro"]'); pg.wait_for_selector('#sidetool.on #metBpm', timeout=5000); pg.wait_for_timeout(300)
    if pg.locator('#modal #pvs').count(): fail('%s: 메트로놈을 열었는데 보기 설정이 남음' % label)
    pg.click('[data-act="sidetool-close"]'); pg.wait_for_timeout(400)
    open_pview(pg); pg.click('#pvs [data-vt="piano"]'); pg.wait_for_selector('#sidetool.on #pkeys', timeout=5000); pg.wait_for_timeout(300)
    pg.click('[data-act="sidetool-close"]'); pg.wait_for_timeout(400)
    # 예배 노트 — 읽으면 점이 사라진다
    open_pview(pg); pg.click('#pvs [data-vt="msg"]'); pg.wait_for_selector('#msgOk', timeout=5000); pg.click('#msgOk'); pg.wait_for_timeout(500)
    if pg.evaluate(M)['pviewDot']: fail('%s: 노트를 읽었는데 보기 설정 점이 남음' % label)
    # 반 줄 ↔ 원본 줄 (이 기기에 기억 — 앱을 다시 켜도)
    open_pview(pg)
    pg.click('#pvs [data-vh="0"]'); pg.wait_for_timeout(400)
    o = pg.evaluate("[document.querySelectorAll('#sheet .slice.half').length,localStorage.getItem('conti-half'),document.querySelector('#pvs [data-vh=\"0\"]').classList.contains('on')]")
    if o[0] or o[1] != '0' or not o[2]: fail('%s: 원본 줄로 바꿨는데 반 줄이 남거나 기억 안 됨 %s' % (label, o))
    pg.click('#pvs [data-close]'); pg.wait_for_timeout(500)
    st2 = ctx.storage_state(); ctx.close()
    ctx, pg = new_page(br, {'width': 390, 'height': 844}, st2, errs)   # 앱을 다시 켠 것처럼 (이 기기 설정만 이어진다)
    go_play(pg, sid, half=False); pg.wait_for_timeout(1500)
    if pg.locator('#sheet .slice.half').count() or pg.evaluate("CONTI.pl().half"): fail('%s: 다시 켜자 원본 줄 설정이 풀림' % label)
    open_pview(pg)
    if not pg.evaluate("document.querySelector('#pvs [data-vh=\"0\"]').classList.contains('on')"): fail('%s: 다시 켠 뒤 보기 설정에 원본 줄이 안 골라짐' % label)
    pg.click('#pvs [data-vh="1"]'); pg.wait_for_function("document.querySelectorAll('#sheet .slice.half').length>=8", timeout=10000)
    if pg.evaluate("localStorage.getItem('conti-half')") != '1': fail('%s: 반 줄로 되돌린 것이 기억 안 됨' % label)
    print('%s: 보기 설정 — 세션 제자리(영상·시각·스크롤 그대로)·메모 필터·크기·건반·메트로놈·노트(점)·반 줄/원본(다시 켜도) · 단추 화면 안 ok' % label)
    ctx.close()

def part_h(br, sid, state, errs, B):
    ctx, pg = new_page(br, {'width': 390, 'height': 844}, state, errs)
    go_play(pg, sid)
    label = '%s H' % B
    blob = pg.evaluate("(sid)=>{const s=CONTI.S.services.find(x=>x.id===sid);return s.published.items[0].pieces[0].blob}", sid)
    # 앞에 오래된 악보 7장이 있다고 치고, 지금 악보를 다시 읽게 한다 → 픽셀은 최근 HALF_KEEP(6)장만
    pg.evaluate("""(b)=>{const M=CONTI.HALF.img;const keep=[...M.entries()].filter(([k])=>k!==b);M.clear();
      for(let i=0;i<7;i++)M.set('old'+i,{W:1,H:1,dark:new Uint8Array(1),rowDark:new Uint16Array(1),plans:{}});keep.forEach(([k,v])=>M.set(k,v));
      window.dispatchEvent(new Event('resize'))}""", blob)
    pg.wait_for_function("document.querySelectorAll('#sheet .slice.half').length>=8", timeout=10000); pg.wait_for_timeout(500)
    k = pg.evaluate("(b)=>{const v=[...CONTI.HALF.img.entries()];return {dark:v.filter(([k,x])=>x.dark).length,cur:!!(CONTI.HALF.img.get(b)||{}).dark,old0:!!CONTI.HALF.img.get('old0').dark,n:v.length}}", blob)
    if k['dark'] > 6 or not k['cur'] or k['old0']: fail('%s: 반 줄 픽셀을 최근 6장만 들고 있지 않음 %s' % (label, k))
    # 픽셀을 버린 악보도 찾은 결과(plans)로 그대로 나뉜다
    pg.evaluate("(b)=>{CONTI.HALF.img.get(b).dark=null;window.dispatchEvent(new Event('resize'))}", blob); pg.wait_for_timeout(400)
    if pg.locator('#sheet .slice.half').count() < 8: fail('%s: 픽셀을 버린 뒤 다시 그리자 반 줄이 사라짐' % label)
    # 못 읽은 악보는 나누지 않는다
    pg.evaluate("(b)=>{CONTI.HALF.img.set(b,{fail:true});window.dispatchEvent(new Event('resize'))}", blob); pg.wait_for_timeout(400)
    if pg.locator('#sheet .slice.half').count(): fail('%s: 못 읽은 악보인데 반 줄이 있음' % label)
    print('%s: 반 줄 픽셀 최근 6장만(%s) · 버린 뒤에도 결과로 그대로 · 못 읽으면 원본 줄 ok' % (label, k))
    ctx.close()

def part_w(br, sid, state, errs, B):
    for (w, h), (sat, sab), adh in [((844, 390), (0, 21), 50), ((820, 1180), (24, 20), 90), ((1180, 820), (24, 20), 90), ((1024, 1366), (24, 20), 90)]:
        ctx, pg = new_page(br, {'width': w, 'height': h}, state, errs)
        go_play(pg, sid, half=False); pg.wait_for_timeout(1200)
        insets(pg, sat, sab); banner(pg, adh)
        label = '%s W %dx%d' % (B, w, h)
        m = pg.evaluate(M)
        check_frame(m, label)
        if m['pv'] or m['form'] or m['note'] or m['half'] or m['pview'] or m['hiddenTools'] or m['mini'] or m['exp']:
            fail('%s: 넓은·가로 화면에 폰 배치(송폼 줄·반 줄·보기 설정·독)가 섞임 %s' % (label, {k: m[k] for k in ['pv', 'form', 'note', 'pview', 'hiddenTools', 'mini', 'exp']}))
        for k in ['play', 'b5', 'f5', 'tnote']:
            if not m[k] or m[k]['b'] > m['limit'] + 1 or m[k]['t'] < 0: fail('%s: %s 가 화면 밖·배너 밑 %s' % (label, k, m[k]))
        if not m['vid'] or m['vid']['h'] < 72: fail('%s: 영상이 안 보임 %s' % (label, m['vid']))
        if not pg.locator('.top [data-act="metro"]').is_visible() or not pg.locator('.top [data-act="piano"]').is_visible(): fail('%s: 상단 건반·메트로놈이 안 보임' % label)
        shot(pg, '%s_w_%dx%d' % (B, w, h))
        print('%s: 예전 배치 그대로 — 반 줄·송폼 줄·독 없음 · 상단 도구 · 재생·±5·여기에 메모 배너 위 ok' % label)
        ctx.close()
    # 폰을 돌리면: 세로(반 줄·독) ↔ 가로(원본 줄·예전 칸)
    ctx, pg = new_page(br, {'width': 390, 'height': 844}, state, errs)
    go_play(pg, sid)
    pg.set_viewport_size({'width': 844, 'height': 390}); pg.wait_for_timeout(700)
    m = pg.evaluate(M)
    if m['pv'] or m['half'] or m['form']: fail('%s W 돌리기: 가로로 돌렸는데 반 줄·송폼 줄이 남음' % B)
    if not m['vid'] or m['vid']['h'] < 72: fail('%s W 돌리기: 가로에서 영상이 안 보임 %s' % (B, m['vid']))
    pg.set_viewport_size({'width': 390, 'height': 844}); pg.wait_for_function("document.querySelectorAll('#sheet .slice.half').length>=8", timeout=10000); pg.wait_for_timeout(500)
    check_collapsed(pg.evaluate(M), '%s W 다시 세로' % B)
    # 가로에서 영상을 틀어 둔 채 세로로 돌리면 독이 펼쳐져 영상이 보인다
    pg.set_viewport_size({'width': 844, 'height': 390}); pg.wait_for_timeout(500)
    pg.evaluate("CONTI.P.playing=true"); pg.set_viewport_size({'width': 390, 'height': 844}); pg.wait_for_timeout(600)
    if not pg.evaluate("CONTI.pl().dock"): fail('%s W 돌리기: 영상이 도는 채 세로로 돌렸는데 독이 접혀 영상이 숨음' % B)
    pg.evaluate("CONTI.P.playing=false")
    print('%s W 돌리기: 세로 ↔ 가로 배치가 따라감 · 틀어 둔 채 세로면 독이 펼쳐짐 ok' % B)
    ctx.close()

def part_e(br, sid, state, errs, B):
    # 폰 세로는 악보 칸이 화면 왼쪽 끝부터 시작한다 — 가장자리에서 오른쪽으로 쓸면 뒤로 (확대해서 옆으로 넘길 악보면 그쪽 몫)
    if B != 'chromium': return   # 터치 흉내(CDP)는 크로미움만
    ctx, pg = new_page(br, {'width': 390, 'height': 844}, state, errs)
    go_play(pg, sid)
    cdp = ctx.new_cdp_session(pg)
    def swipe(x0, y0, x1, y1, steps=10):
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x0, 'y': y0}]})
        for i in range(1, steps + 1):
            cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x0 + (x1 - x0) * i / steps, 'y': y0 + (y1 - y0) * i / steps}]}); pg.wait_for_timeout(16)
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
    label = '%s E 390' % B
    y = pg.evaluate("(()=>{const r=document.getElementById('sheetwrap').getBoundingClientRect();return r.top+r.height/2})()")
    if pg.evaluate("document.elementFromPoint(6,%f).closest('#sheetwrap')!==null" % y) is not True: fail('%s 준비: 왼쪽 끝이 악보 칸이 아님' % label)
    pg.evaluate("CONTI.setZoom(1.6)"); pg.wait_for_timeout(400)
    swipe(6, y, 260, y + 4); pg.wait_for_timeout(900)
    if '#/play/' not in pg.evaluate('location.hash'): fail('%s: 확대한 악보(옆으로 넘김)인데 가장자리 쓸기가 뒤로 감' % label)
    pg.evaluate("CONTI.setZoom(1)"); pg.wait_for_timeout(400)
    swipe(6, y, 260, y + 4); pg.wait_for_timeout(900)
    if '#/view/' not in pg.evaluate('location.hash'): fail('%s: 악보 위 왼쪽 가장자리에서 쓸었는데 뒤로 안 감 %s' % (label, pg.evaluate('location.hash')))
    print('%s: 악보 위 가장자리 쓸기 → 뒤로 · 확대한 악보는 옆으로 넘김 ok' % label)
    ctx.close()

def run():
    with sync_playwright() as p:
        errs = []
        only = [x for x in os.environ.get('PART', '').split(',') if x]
        # 악보 넣기(그림 처리)는 크로미움에서 — 헤드리스 웹킷은 악보 사진을 못 읽는다. 로그인 상태만 넘겨 받는다
        br = p.chromium.launch(); sid, state = seed(br, errs); br.close()
        for B in [x for x in os.environ.get('BROWSERS', 'webkit,chromium').split(',') if x]:
            try: br = getattr(p, B).launch()
            except Exception as e: fail('%s 를 못 띄움: %s' % (B, str(e).splitlines()[0][:120])); continue
            for f in (part_a, part_b, part_c, part_h, part_w, part_e):
                if not only or f.__name__[5:] in only: f(br, sid, state, errs, B)
            br.close()
        bad = [e for e in errs if 'ResizeObserver' not in e]
        if bad: fail('페이지 오류: %s' % bad[:3])
    if FAILS: print('FAILS %d' % len(FAILS)); sys.exit(1)
    print('OK test_practice_redesign')

run()
