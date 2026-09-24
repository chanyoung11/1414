# 감사 fe-12: 가져오기·내보내기·켜기(부팅)·오프라인 삭제
#  - F30  가져온 파일의 타임라인 메모 시각(t)·레이어·키 이동에 글자를 넣어도 스크립트가 돌지 않는다 (저장된 옛 값도)
#         날짜로 못 바꾸는 메모 시각(at)이 메모 올리기 전체를 막지 않는다. 악보의 빠르기·줄 수·비용 칸('곡 정보' 창)도 같다
#  - F101 모양이 망가진 파일을 가져와도 앱이 백지가 되지 않는다 (이미 저장된 망가진 예배도 켤 때 고친다)
#  - F142 같은 이름·날짜 예배로 '합치기'를 골라도 남의 메모가 내 이름으로 들어오지 않는다
#  - F31  팀 기기의 인도자가 발행본이 든 파일을 가져오면 초안으로 들어와 다음 동기화에 사라지지 않는다.
#         팀 서버에 이미 같은(더 새) 콘티가 있고 가져온 뒤 손대지 않았으면 서버 것을 받는다 ('수정 중' 으로 옛 곡 목록에 굳지 않게)
#  - F99  내보내기 파일에 비공개 말씀 메모·보낸 사람 계정 id 가 담기지 않는다
#  - F102 오프라인(또는 서버 오류)에서 지운 예배는 다시 연결되면 서버에서도 지워진다
#  - F32  서버 확인이 끝나지 않아도(약한 와이파이) 받아 둔 팀 화면이 몇 초 안에 뜨고, 나중에 다시 붙는다.
#         켜는 중에는 다시 묻기가 겹치지 않는다(/me 두 번·'다시 연결됐어요'·늦은 '모름'이 연결을 덮기). 설정 받기가 걸려도 무대가 열린다
#  - F143 켤 때 /me 가 한 번 503 이어도 로그인 창이 뜨지 않는다. 계속 실패하면 오프라인으로 열고 나중에 붙는다.
#         나중에 다시 붙을 때도 /me 가 끝나기 전에는 연결됨으로 보지 않는다 (그 사이 로그인 창 · 실패 뒤 남는 로그인 창)
#  - F100 앱(NATIVE)에서 내보내기는 공유 시트로 넘기고, 끝까지 됐을 때만 '보냄' 이라고 알린다 (운영 서버로는 아무 요청도 안 나간다)
import os, sys, time, json, base64, zlib, struct, random
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
tag = str(int(time.time()))[-6:]
A = ('fe12a' + tag, 'secret1', '하은')
H = {'x-conti': '1'}
XSS = '"><img src=x onerror="window.__xss=(window.__xss||0)+1">'


def png(w=80, h=40):
    # 200바이트가 안 되는 파일은 앱이 '예전 404 흔적'으로 보고 버린다 → 잡음을 넣어 크게 만든다
    raw = b''.join(b'\x00' + bytes(random.randrange(256) for _ in range(w * 3)) for _ in range(h))
    ch = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + ch(b'IDAT', zlib.compress(raw)) + ch(b'IEND', b'')


PNG = base64.b64encode(png()).decode()


def fail(msg):
    print('FAIL:', msg); sys.exit(1)


def signup(pg, u):
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=8000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
    pg.check('#lgAgree')
    pg.fill('#lgName', u[2]); pg.fill('#lgUser', u[0]); pg.fill('#lgPass', u[1]); pg.click('[data-act="lg-submit"]')


def imp(pg, data, wait=1500):
    pg.evaluate("CONTI.importJSON(new Blob([%s],{type:'application/json'}))" % json.dumps(json.dumps(data, ensure_ascii=False)))
    pg.wait_for_timeout(wait)


def item(iid, title, **kw):
    it = {'id': iid, 'title': title, 'key': 'G', 'mod': '', 'form': '', 'songNote': '', 'pieces': [], 'media': [], 'notes': []}
    it.update(kw); return it


def svc_js(sid):
    return "CONTI.S.services.find(s=>s.id===%s)" % json.dumps(sid)


def home(pg):
    pg.evaluate("location.hash='#/home'"); pg.wait_for_selector('.hd', timeout=10000); pg.wait_for_timeout(300)


def sim_offline(pg, off):
    # 오프라인 흉내(NET.server=null) 동안은 서버 확인도 실패로 둔다. 안 그러면 앱의 다시 묻기(20초마다)가
    # 그 사이 몰래 다시 붙어서, 오프라인 삭제·가져오기가 온라인 길로 가 시험이 가끔 틀렸다
    if off:
        pg.route('**/api/health', lambda r: r.fulfill(status=503, body='{}', headers={'content-type': 'application/json'}))
        pg.evaluate("CONTI.NET.server=null;CONTI.render()")
    else:
        pg.unroute('**/api/health')


def run():
    with sync_playwright() as p:
        b = p.chromium.launch(); errs = []
        ctx = b.new_context(viewport={'width': 1180, 'height': 820}, service_workers='block')
        pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
        dialogs = []
        pg.on('dialog', lambda d: (dialogs.append(d.message), d.accept()))
        signup(pg, A); pg.wait_for_selector('#gtTeam', timeout=8000)
        pg.fill('#gtTeam', 'fe12팀'); pg.click('[data-act="team-create"]'); pg.wait_for_selector('.shell[data-page]', timeout=20000)
        team = pg.evaluate('CONTI.S.team.id')
        if not pg.evaluate('CONTI.NET.server===true'): fail('온라인이 아님')

        # ---------- F30: 가져온 파일로 스크립트 실행 ----------
        sid = 'x30' + tag; mid = 'md30' + tag; blob = 'bl30' + tag
        evil = {'app': 'conti', 'v': 1, 'at': int(time.time() * 1000), 'services': [{
            'id': sid, 'name': 'XSS 예배', 'date': '2026-11-01', 'notice': '', 'version': 0, 'published': None,
            'items': [item('it30' + tag, '곡', pieces=[{'id': 'pc30' + tag, 'blob': blob, 'w': 800, 'h': 400,
                    'markers': [{'id': 'mk30' + tag, 'label': 'A', 'x': 10, 'y': 50, 'keyShift': XSS, 'cut': None}], 'hls': [], 'chords': []}],
                notes=[{'id': 'nl30' + tag, 'marker': 'mk30' + tag, 'layer': XSS, 'text': '레이어', 'author': '인도자'}],
                media=[{'id': mid, 'type': 'youtube', 'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ', 'start': XSS, 'notes': [
                    {'id': 'nt30' + tag, 't': XSS, 'layer': 'leader', 'text': '시각', 'author': '인도자'},
                    {'id': 'nb30' + tag, 't': 5, 'layer': 'leader', 'text': '먼 미래', 'author': '인도자', 'at': 1e20}]}])]}],
            'library': [], 'blobs': {blob: {'type': 'image/png', 'b64': PNG}}}
        imp(pg, evil)
        got = pg.evaluate("(()=>{const s=%s;const it=s.items[0];return {t:it.media[0].notes.map(n=>n.t===undefined?null:n.t),at:it.media[0].notes.map(n=>n.at===undefined?null:n.at),layers:it.notes.map(n=>n.layer),ks:it.pieces[0].markers[0].keyShift===undefined,start:it.media[0].start}})()" % svc_js(sid))
        if got['t'] != [None, 5] or got['at'] != [None, None]: fail('숫자 칸이 정리되지 않음: %s' % got)
        if got['layers'] != [] or not got['ks'] or got['start'] != 0: fail('레이어·키 이동·구간이 정리되지 않음: %s' % got)
        pg.evaluate("location.hash='#/play/%s/0'" % sid); pg.wait_for_timeout(3500)
        pg.evaluate("location.hash='#/edit/%s'" % sid); pg.wait_for_timeout(2500)
        if pg.evaluate('window.__xss||0'): fail('가져온 파일로 스크립트가 실행됨')
        # 날짜로 못 바꾸는 at 이 빠졌으니 메모 올리기가 통과해 서버에 들어간다
        notes = ctx.request.get(URL + 'api/notes?team=%s&service=%s' % (team, sid)).json()['notes']
        if 'nb30' + tag not in [n['id'] for n in notes]: fail('메모가 서버에 올라가지 않음 (at 이 올리기를 막음): %s' % notes)
        # 예전 버전이 이미 저장해 둔 나쁜 값도 화면에서 스크립트가 되지 않는다 (그리는 쪽에서 막음)
        pg.evaluate("location.hash='#/home'"); pg.wait_for_timeout(500)
        pg.evaluate("CONTI.SYNC.pushNotes=async()=>true;CONTI.SYNC.pullNotes=async()=>{}")   # 서버 메모로 덮이지 않게 (그리기만 본다)
        pg.evaluate("(()=>{const it=%s.items[0];it.media[0].notes.push({id:'raw30',t:%s,layer:'leader',text:'옛 값'});it.notes.push({id:'raw31',marker:it.pieces[0].markers[0].id,layer:%s,text:'옛 레이어'});it.pieces[0].markers[0].keyShift=%s;CONTI.save()})()" % (svc_js(sid), json.dumps(XSS), json.dumps(XSS), json.dumps(XSS)))
        pg.evaluate("location.hash='#/edit/%s'" % sid); pg.wait_for_timeout(2000)
        if pg.locator('.ksb').count() < 1: fail('키 이동 표시가 그려지지 않아 확인할 수 없음')
        if pg.locator('.m', has_text='옛 레이어').count() < 1: fail('옛 레이어 메모가 그려지지 않아 확인할 수 없음')
        if pg.evaluate('window.__xss||0'): fail('저장돼 있던 옛 값으로 편집 화면에서 스크립트가 실행됨')
        pg.evaluate("location.hash='#/play/%s/0'" % sid); pg.wait_for_timeout(3000)
        if pg.locator('#tlist .tl', has_text='옛 값').count() < 1: fail('옛 타임라인 메모가 그려지지 않아 확인할 수 없음')
        if pg.evaluate('window.__xss||0'): fail('저장돼 있던 옛 값으로 스크립트가 실행됨')
        print('F30 ok')
        pg.evaluate("location.hash='#/home'"); pg.reload(); pg.wait_for_selector('.hd', timeout=20000)   # 막아 둔 메모 동기화를 되돌린다

        # ---------- F30(악보): 악보의 빠르기·줄 수·비용 칸으로도 스크립트가 돌지 않는다 ----------
        s30 = 'sc30' + tag; i30 = 'si30' + tag
        score = {'measures': [{'c': [{'t': 'C', 'b': 0}], 'n': [{'p': 'C4', 'd': 16}]}, 'x'], 'title': '악보', 'key': 'C', 'time': '4/4',
                 'tempo': XSS, 'lines': XSS, 'cost': XSS, 'verses': XSS, 'model': 'gem'}
        imp(pg, {'app': 'conti', 'services': [{'id': s30, 'name': '악보 예배', 'date': '2026-11-01', 'version': 0, 'published': None,
                 'items': [item(i30, '악보곡', score=score)]}], 'library': [dict(item('lb30' + tag, '라이브러리 악보곡'), score=score)]})
        sc = pg.evaluate("(()=>{const a=%s.items[0].score,b=CONTI.S.library.find(x=>x.id===%s).score;return [a,b].map(s=>[s.tempo,s.lines,s.cost,s.verses,s.measures.length])})()" % (svc_js(s30), json.dumps('lb30' + tag)))
        if sc != [[None, None, None, None, 1]] * 2: fail('악보 숫자 칸·마디가 정리되지 않음: %s' % sc)
        def score_info():
            pg.evaluate("location.hash='#/score/%s/%s'" % (s30, i30)); pg.wait_for_selector('[data-act="score-info"]', timeout=10000)
            pg.click('[data-act="score-info"]'); pg.wait_for_selector('#siTempo', timeout=5000); pg.wait_for_timeout(300)
        score_info()
        if pg.evaluate('window.__xss||0'): fail('가져온 악보 칸으로 스크립트가 실행됨')
        pg.keyboard.press('Escape'); pg.evaluate("location.hash='#/home'"); pg.wait_for_timeout(300)
        # 서버·예전 버전이 남긴 값이어도 창에서 글자로만 보인다
        pg.evaluate("(()=>{const s=%s.items[0].score;s.tempo=%s;s.lines=%s;s.cost=%s;CONTI.save()})()" % (svc_js(s30), json.dumps(XSS), json.dumps(XSS), json.dumps(XSS)))
        score_info()
        if pg.evaluate('window.__xss||0'): fail('저장돼 있던 악보 칸으로 스크립트가 실행됨')
        if pg.evaluate("document.getElementById('siTempo').value") != XSS: fail('빠르기 칸이 글자 그대로 보이지 않음')
        pg.keyboard.press('Escape'); pg.evaluate("location.hash='#/home'"); pg.wait_for_timeout(300)
        # 제대로 된 악보는 그대로
        pg.evaluate("(()=>{const s=%s.items[0].score;s.tempo=72;s.lines=3;s.cost=41;CONTI.save()})()" % svc_js(s30))
        score_info()
        info = pg.evaluate("[document.getElementById('siTempo').value,document.querySelector('#modal').textContent]")
        if info[0] != '72' or '오선 3줄' not in info[1] or '약 41원' not in info[1]: fail('악보 정보가 제대로 안 보임: %s' % info)
        pg.keyboard.press('Escape')
        print('F30 score ok')

        # ---------- F101: 망가진 파일 · 이미 저장된 망가진 예배 ----------
        home(pg)
        imp(pg, {'app': 'conti', 'services': [{'id': 'bad101' + tag, 'name': '망가진 예배', 'date': '2026-10-01'}, 5, None,
                                             {'name': '이상한 예배', 'date': '2026-10-02', 'items': 'x', 'published': 'y'}], 'library': 'z', 'blobs': 'q'})
        if errs: fail('망가진 파일로 오류: %s' % errs)
        if pg.locator('.hd').count() == 0: fail('망가진 파일을 가져온 뒤 홈이 그려지지 않음')
        shapes = pg.evaluate("CONTI.S.services.filter(s=>/망가진|이상한/.test(s.name)).map(s=>[Array.isArray(s.items),s.published,typeof s.id])")
        if shapes != [[True, None, 'string'], [True, None, 'string']]: fail('가져온 예배 모양이 정리되지 않음: %s' % shapes)
        pg.evaluate("CONTI.S.services.push({id:'raw101',name:'옛 망가진 예배',date:'2026-10-03'});CONTI.save()"); pg.wait_for_timeout(800)
        n_dialog = len(dialogs)
        pg.reload(); pg.wait_for_selector('.hd', timeout=20000); pg.wait_for_timeout(800)
        if len(dialogs) != n_dialog: fail('켤 때 경고창이 뜸: %s' % dialogs[n_dialog:])
        if errs: fail('저장된 망가진 예배로 켤 때 오류: %s' % errs)
        if '옛 망가진 예배' not in pg.locator('#app').inner_text(): fail('저장된 망가진 예배가 목록에 안 보임')
        print('F101 ok')

        # ---------- F142: 합치기 길에서도 남의 메모는 거른다 ----------
        home(pg)
        twin = 'tw142' + tag
        pg.evaluate("CONTI.S.services.push({id:%s,name:'합칠 예배',date:'2026-10-04',notice:'',version:0,items:[{id:'ti1'+%s,title:'곡1',key:'G',mod:'',form:'',songNote:'',pieces:[],media:[],notes:[]}],published:null});CONTI.save()" % (json.dumps(twin), json.dumps(tag)))
        mine = [{'id': 'no142' + tag, 'marker': 'm1', 'layer': 'mine', 'author': '남', 'text': '남의 개인 메모'},
                {'id': 'ns142' + tag, 'marker': 'm1', 'layer': 'session', 'session': '드럼', 'author': '남', 'text': '남의 세션 메모'},
                {'id': 'nl142' + tag, 'marker': 'm1', 'layer': 'leader', 'author': '인도자', 'text': '인도자 메모'}]
        imp(pg, {'app': 'conti', 'services': [{'id': 'in142' + tag, 'name': '합칠 예배', 'date': '2026-10-04', 'version': 0, 'published': None,
            'items': [item('ti2' + tag, '곡2', notes=mine, media=[{'id': 'mm142' + tag, 'type': 'youtube', 'url': 'https://youtu.be/dQw4w9WgXcQ',
                'notes': [{'id': 'nm142' + tag, 't': 3, 'layer': 'mine', 'author': '남', 'text': '남의 타임라인'}]}])]}], 'library': []})
        merged = pg.evaluate("(()=>{const s=%s;const it=s.items.find(i=>i.title==='곡2');return it?{notes:it.notes.map(n=>n.text),media:it.media[0].notes.map(n=>n.text)}:null})()" % svc_js(twin))
        if not merged: fail('합치기가 안 됨')
        if merged['notes'] != ['인도자 메모'] or merged['media'] != []: fail('합치기 길로 남의 메모가 들어옴: %s' % merged)
        if pg.evaluate("!!%s" % svc_js('in142' + tag)): fail('합쳤는데 따로도 추가됨')
        print('F142 ok')

        # ---------- F31: 발행본이 든 파일 → 초안으로, 동기화 뒤에도 남는다 ----------
        home(pg)
        ps = 'pub31' + tag
        dialogs.clear()
        imp(pg, {'app': 'conti', 'at': int(time.time() * 1000), 'services': [{'id': ps, 'name': '다른 팀 예배', 'date': '2026-10-11', 'version': 3, 'editedAt': 1, 'draftPushedAt': 1, 'pubPending': True,
            'items': [item('it31' + tag, '파일 곡')], 'published': {'version': 3, 'at': 1, 'name': '다른 팀 예배', 'date': '2026-10-11', 'items': [item('it31' + tag, '파일 곡')], 'changes': []}}], 'library': []}, wait=800)
        toast = pg.evaluate("(document.getElementById('toast')||{}).textContent||''")
        if '초안' not in toast: fail('초안으로 들어왔다는 안내가 없음: %s' % toast)
        st = pg.evaluate("(()=>{const s=%s;return s&&{pub:s.published,pp:!!s.pubPending,dp:s.draftPushedAt||0,ed:s.editedAt}})()" % svc_js(ps))
        if not st or st['pub'] is not None or st['pp'] or st['dp'] or st['ed'] < 1000: fail('초안으로 들어오지 않음: %s' % st)
        pg.evaluate("CONTI.SYNC.pullServices().then(()=>CONTI.render())"); pg.wait_for_timeout(2500)
        home(pg)
        if not pg.evaluate("!!%s" % svc_js(ps)): fail('가져온 예배가 다음 동기화에서 사라짐')
        # 편집을 열면 초안이 서버에 올라가 다른 기기에서도 이어진다
        pg.evaluate("location.hash='#/edit/%s'" % ps); pg.wait_for_selector('[data-f="svc.name"]', timeout=10000)
        pg.fill('[data-f="svc.name"]', '다른 팀 예배 (가져옴)'); pg.wait_for_timeout(4000)
        drafts = [d['id'] for d in ctx.request.get(URL + 'api/services?team=' + team).json()['drafts']]
        if ps not in drafts: fail('가져온 초안이 서버에 올라가지 않음: %s' % drafts)
        print('F31 ok')

        # ---------- F31(같은 팀): 오프라인에서 가져온 파일의 콘티가 팀 서버에 이미 있으면(더 새 버전) 그것을 받는다 ----------
        # 초안을 올리기 전에 목록부터 받아도, 손대지 않은 가져오기를 '고친 것'으로 쳐서 옛 곡 목록으로 굳지 않는다
        home(pg)
        def pub_srv(sid2, v, titles):
            r = ctx.request.put(URL + 'api/services/' + sid2, headers=H, data={'teamId': team, 'doc': {'id': sid2, 'name': '같은 팀 예배 ' + sid2[:4], 'date': '2026-10-12', 'version': v,
                                'items': [item('s%d' % i + sid2, t) for i, t in enumerate(titles)], 'changes': []}})
            if r.status != 200: fail('서버 발행 실패: %s' % r.text()[:200])
        def file_v1(sid2):
            its = [item('s0' + sid2, '곡1')]
            nm = '같은 팀 예배 ' + sid2[:4]   # 이름·날짜가 같으면 '합칠까요' 로 간다 — 따로 들어오게 이름을 다르게
            return {'app': 'conti', 'at': int(time.time() * 1000), 'library': [], 'services': [{'id': sid2, 'name': nm, 'date': '2026-10-12', 'version': 1,
                    'items': its, 'published': {'version': 1, 'at': 1, 'name': nm, 'date': '2026-10-12', 'items': its, 'changes': []}}]}
        same, kept = 'same31' + tag, 'kept31' + tag
        sim_offline(pg, True); pg.wait_for_timeout(300)   # 이 기기는 아직 받지 않았다 (오프라인)
        for s2 in (same, kept): pub_srv(s2, 1, ['곡1'])
        imp(pg, file_v1(same), wait=500); imp(pg, file_v1(kept), wait=500)
        # 두 번째 것은 가져온 뒤 오프라인에서 고쳤다 → 그것은 진짜 '수정 중' 으로 지킨다
        pg.evaluate("(()=>{const s=%s;s.name='고친 예배';s.editedAt=Date.now()+5;CONTI.save()})()" % svc_js(kept))
        for s2 in (same, kept): pub_srv(s2, 2, ['곡1', '곡2'])   # 다른 인도자가 v2 발행
        sim_offline(pg, False)
        pg.evaluate("CONTI.NET.server=true;CONTI.SYNC.pullServices().then(()=>CONTI.render())"); pg.wait_for_timeout(2500)
        st = pg.evaluate("[%s,%s].map(s=>s&&{v:s.version,pv:s.published&&s.published.version,items:s.items.map(i=>i.title),name:s.name,ff:'fromFile' in s})" % (svc_js(same), svc_js(kept)))
        if st[0] != {'v': 2, 'pv': 2, 'items': ['곡1', '곡2'], 'name': '같은 팀 예배 same', 'ff': False}: fail('손대지 않은 가져오기가 서버 발행본으로 바뀌지 않음: %s' % st[0])
        if not st[1] or st[1]['name'] != '고친 예배' or st[1]['pv'] != 2 or st[1]['v'] != 3: fail('가져온 뒤 고친 것은 지켜야 함: %s' % st[1])
        print('F31 same-team ok')

        # ---------- F99: 내보내기에 비공개 말씀 메모가 담기지 않는다 ----------
        home(pg)
        w_priv = {'passage': '요 3:16', 'title': '사랑', 'line': '한 줄', 'memo': '인도자만 볼 비공개 메모', 'memoPublic': False, 'from': {'type': 'pastor', 'memberId': 'uid-secret', 'name': '목사님'}}
        w_pub = dict(w_priv, memo='공개 메모', memoPublic=True)
        pg.evaluate("(()=>{const s=%s;s.word=%s;s.published={version:1,at:1,name:s.name,date:s.date,word:%s,items:JSON.parse(JSON.stringify(s.items)),changes:[]};const t=%s;t.word=%s;CONTI.save()})()"
                    % (svc_js(ps), json.dumps(w_priv), json.dumps(w_priv), svc_js(twin), json.dumps(w_pub)))
        with pg.expect_download(timeout=15000) as dl:
            pg.click('[data-act="export"]')
        path = dl.value.path(); data = json.load(open(path, encoding='utf-8'))
        raw = open(path, encoding='utf-8').read()
        if '인도자만 볼 비공개 메모' in raw: fail('비공개 말씀 메모가 내보내기 파일에 들어감')
        if 'uid-secret' in raw: fail('보낸 사람 계정 id 가 내보내기 파일에 들어감')
        ex = {s['id']: s for s in data['services']}
        if ex[ps]['word']['memo'] != '' or ex[ps]['published']['word']['memo'] != '' or ex[ps]['word']['passage'] != '요 3:16': fail('말씀이 이상하게 나감: %s' % ex[ps]['word'])
        if ex[twin]['word']['memo'] != '공개 메모': fail('공개 메모까지 빠짐: %s' % ex[twin]['word'])
        if pg.evaluate("%s.word.memo" % svc_js(ps)) != '인도자만 볼 비공개 메모': fail('내보내기가 이 기기의 말씀까지 바꿈')
        print('F99 ok')

        # ---------- F102: 오프라인에서 지운 예배는 다시 연결되면 서버에서도 지운다 ----------
        home(pg)
        def publish_on_server(sid2, name):
            r = ctx.request.put(URL + 'api/services/' + sid2, headers=H, data={'teamId': team, 'doc': {'id': sid2, 'name': name, 'date': '2026-10-18', 'version': 1, 'items': [item('it' + sid2, '곡')], 'changes': []}})
            if r.status != 200: fail('서버 발행 실패: %s' % r.text()[:200])
        d1, d2 = 'del1' + tag, 'del2' + tag
        publish_on_server(d1, '오프라인 삭제'); publish_on_server(d2, '서버 오류 삭제')
        pg.evaluate("CONTI.SYNC.pullServices().then(()=>CONTI.render())"); pg.wait_for_timeout(2500); home(pg)
        if not pg.evaluate("!!%s&&!!%s" % (svc_js(d1), svc_js(d2))): fail('서버 발행본을 받지 못함')
        sim_offline(pg, True); pg.wait_for_timeout(500)
        pg.click('[data-act="del-svc"][data-id="%s"]' % d1); pg.wait_for_timeout(800)
        if pg.evaluate("(CONTI.S.delPending||[]).includes(%s)" % json.dumps(d1)) is not True: fail('오프라인 삭제가 대기열에 없음')
        sim_offline(pg, False)
        pg.evaluate("CONTI.NET.server=true;CONTI.render()"); pg.wait_for_timeout(500)
        # 서버 오류(5xx) 한 번 → 대기열, 다음 동기화 때 다시
        state = {'n': 0}
        def flaky(route):
            if route.request.method == 'DELETE' and state['n'] == 0:
                state['n'] += 1; route.fulfill(status=503, body='{"error":"x","message":"잠깐 오류"}', headers={'content-type': 'application/json'})
            else: route.continue_()
        m2 = lambda u: ('/api/services/' + d2) in u
        pg.route(m2, flaky)
        pg.click('[data-act="del-svc"][data-id="%s"]' % d2); pg.wait_for_timeout(1200)
        if state['n'] != 1: fail('삭제 요청이 가로채지지 않음')
        if pg.evaluate("(CONTI.S.delPending||[]).includes(%s)" % json.dumps(d2)) is not True: fail('서버 오류 삭제가 대기열에 없음')
        on_server = [s['id'] for s in ctx.request.get(URL + 'api/services?team=' + team).json()['services']]
        if d1 not in on_server or d2 not in on_server: fail('아직 지우기 전인데 서버에 없음')
        pg.evaluate("CONTI.SYNC.pullServices()"); pg.wait_for_timeout(2500)
        on_server = [s['id'] for s in ctx.request.get(URL + 'api/services?team=' + team).json()['services']]
        if d1 in on_server or d2 in on_server: fail('다시 연결됐는데 서버에서 안 지워짐: %s' % on_server)
        if pg.evaluate("(CONTI.S.delPending||[]).length"): fail('지운 뒤에도 대기열이 남음')
        pg.unroute(m2)
        print('F102 ok')

        # ---------- F32: 서버 확인이 끝나지 않아도 받아 둔 팀 화면이 뜬다 ----------
        home(pg)
        hung = []
        pg.route('**/api/health', lambda route: hung.append(route))   # 응답이 오지 않는다 (교회 와이파이)
        t0 = time.time(); pg.reload()
        try: pg.wait_for_selector('.hd', timeout=6000)
        except Exception: fail('서버 확인이 걸려 있는 동안 화면이 비어 있음 (%.1fs)' % (time.time() - t0))
        took = time.time() - t0
        if took > 5: fail('화면이 너무 늦게 뜸: %.1fs' % took)
        if '다른 팀 예배' not in pg.locator('#app').inner_text(): fail('받아 둔 예배가 안 보임')
        pg.wait_for_function('window.CONTI&&CONTI.NET.server===null', timeout=15000)   # 시간 초과로 오프라인
        if not hung: fail('서버 확인 요청이 가로채지지 않음')
        for r in hung:
            try: r.abort()
            except Exception: pass
        pg.unroute('**/api/health')
        pg.evaluate("window.dispatchEvent(new Event('online'))")
        pg.wait_for_function('window.CONTI&&CONTI.NET.server===true&&!!CONTI.NET.user', timeout=15000)
        if pg.locator('#lgUser').count(): fail('다시 붙었는데 로그인 창이 뜸')
        print('F32 ok (첫 화면 %.1fs)' % took)

        # ---------- F143: /me 한 번 503 → 로그인 창 없이 이어짐 ----------
        state = {'n': 0}
        def once503(route):
            state['n'] += 1
            if state['n'] == 1: route.fulfill(status=503, body='{"error":"x","message":"잠깐 오류"}', headers={'content-type': 'application/json'})
            else: route.continue_()
        pg.route('**/api/me', once503)
        pg.reload(); pg.wait_for_timeout(4000)
        if state['n'] < 2: fail('/me 를 다시 부르지 않음 (%d)' % state['n'])
        if pg.locator('#lgUser').count(): fail('/me 503 한 번에 로그인 창이 뜸')
        if not pg.evaluate('CONTI.NET.server===true&&!!CONTI.NET.user'): fail('다시 불러서 로그인 상태가 되지 않음')
        pg.unroute('**/api/me')
        # 계속 503 → 오프라인으로 받아 둔 것을 보여 주고, 나아지면 붙는다
        pg.route('**/api/me', lambda route: route.fulfill(status=503, body='{"error":"x","message":"오류"}', headers={'content-type': 'application/json'}))
        pg.reload(); pg.wait_for_selector('.hd', timeout=15000); pg.wait_for_timeout(3000)
        if pg.locator('#lgUser').count(): fail('/me 가 계속 503 일 때 로그인 창이 뜸')
        if not pg.evaluate('CONTI.NET.server===null'): fail('/me 가 계속 실패하는데 오프라인으로 두지 않음')
        pg.unroute('**/api/me')
        pg.evaluate("window.dispatchEvent(new Event('online'))")
        pg.wait_for_function('window.CONTI&&CONTI.NET.server===true&&!!CONTI.NET.user', timeout=15000)
        print('F143 ok')

        # ---------- F143(다시 붙기): 오프라인에서 다시 붙는 동안 /me 가 느리거나 실패해도 로그인 창이 뜨지 않는다 ----------
        mode = {'m': '503', 'held': []}
        def me_route(route):
            if mode['m'] == '503': route.fulfill(status=503, body='{"error":"x","message":"오류"}', headers={'content-type': 'application/json'})
            else: mode['held'].append(route)
        pg.route('**/api/me', me_route)
        pg.reload(); pg.wait_for_selector('.hd', timeout=15000); pg.wait_for_timeout(3500)
        if not pg.evaluate('CONTI.NET.server===null'): fail('/me 503 으로 오프라인이 되지 않음')
        mode['m'] = 'hold'
        pg.evaluate("window.dispatchEvent(new Event('online'))"); pg.wait_for_timeout(1500)
        if not mode['held']: fail('다시 붙기가 /me 를 부르지 않음')
        pg.evaluate("location.hash='#/library'"); pg.wait_for_timeout(800)   # /me 를 기다리는 사이 화면을 그린다
        if pg.locator('#lgUser').count(): fail('다시 붙는 중 /me 를 기다리는 사이 로그인 창이 뜸')
        if pg.evaluate('CONTI.NET.server') is not None: fail('/me 가 끝나기 전에 연결됨으로 봄')
        mode['m'] = '503'
        for r in mode['held']:
            try: r.fulfill(status=503, body='{"error":"x","message":"오류"}', headers={'content-type': 'application/json'})
            except Exception: pass
        pg.wait_for_timeout(1000)
        if pg.locator('#lgUser').count() or not pg.evaluate('CONTI.NET.server===null'): fail('다시 붙기의 /me 503 뒤 로그인 창 또는 연결 상태가 남음')
        pg.unroute('**/api/me')
        pg.evaluate("window.dispatchEvent(new Event('online'))")
        pg.wait_for_function('CONTI.NET.server===true&&!!CONTI.NET.user', timeout=15000)
        if pg.locator('#lgUser').count(): fail('붙은 뒤 로그인 창이 뜸')
        print('F143 reconnect ok')

        # ---------- F32/F143(켜는 중): 켜기가 서버 확인·/me 를 기다리는 동안 다시 묻기가 겹치지 않는다 ----------
        pg.evaluate("location.hash='#/home'"); pg.wait_for_timeout(300)
        cnt = {'me': 0, 'held': []}
        def slow_me(route):
            cnt['me'] += 1
            if cnt['me'] == 1: cnt['held'].append(route)
            else: route.continue_()
        pg.route('**/api/me', slow_me)
        pg.reload(); pg.wait_for_timeout(700)
        pg.evaluate("document.dispatchEvent(new Event('visibilitychange'));window.dispatchEvent(new Event('online'))"); pg.wait_for_timeout(1800)
        if cnt['me'] != 1: fail('켜는 중 화면 복귀로 /me 를 또 부름 (%d번)' % cnt['me'])
        if pg.locator('#lgUser').count(): fail('켜는 중 로그인 창이 뜸')
        for r in cnt['held']:
            try: r.continue_()
            except Exception: pass
        pg.wait_for_function('window.CONTI&&CONTI.NET.server===true&&!!CONTI.NET.user', timeout=15000); pg.wait_for_timeout(500)
        if '다시 연결됐어요' in pg.evaluate("(document.getElementById('toast')||{}).textContent||''"): fail('그냥 느리게 켜졌는데 다시 연결됐다고 알림')
        if cnt['me'] != 1: fail('켜기가 끝난 뒤에도 /me 를 또 부름 (%d번)' % cnt['me'])
        pg.unroute('**/api/me')
        # 켜기의 서버 확인이 걸려 있는 동안 화면 복귀 → 켜기가 끝나며 방금 붙은 연결을 '모름'으로 덮지 않는다 (켜기가 오프라인으로 끝나면 곧 다시 붙는다)
        hold = {'h': [], 'n': 0, 'me': 0}
        def hang_first_health(route):
            hold['n'] += 1
            if hold['n'] == 1: hold['h'].append(route)
            else: route.continue_()
        def count_me(route):
            hold['me'] += 1; route.continue_()
        pg.route('**/api/health', hang_first_health); pg.route('**/api/me', count_me)
        pg.reload(); pg.wait_for_timeout(1000)
        pg.evaluate("document.dispatchEvent(new Event('visibilitychange'))"); pg.wait_for_timeout(1500)
        if hold['me']: fail('켜기가 서버 확인을 기다리는 동안 다시 묻기가 따로 붙음')
        pg.wait_for_function('window.CONTI&&CONTI.NET.server===null', timeout=12000)   # 켜기의 서버 확인 시간 초과
        t0 = time.time()
        pg.wait_for_function('CONTI.NET.server===true&&!!CONTI.NET.user', timeout=15000)
        if time.time() - t0 > 9: fail('켜기가 오프라인으로 끝난 뒤 늦게 붙음: %.1fs' % (time.time() - t0))
        for r in hold['h']:
            try: r.abort()
            except Exception: pass
        pg.unroute('**/api/health'); pg.unroute('**/api/me')
        print('F32 boot/recheck ok')

        # ---------- F32(무대): 설정 받기가 끝나지 않아도 무대 모드가 열린다 ----------
        st32 = 'st32' + tag
        pg.evaluate("CONTI.S.services.push({id:%s,name:'무대 예배',date:'2026-10-11',notice:'',version:0,items:[{id:'st1'+%s,title:'곡1',key:'G',mod:'',form:'',songNote:'',pieces:[],media:[],notes:[]}],published:null});CONTI.save();CONTI.PREFS.data=null" % (json.dumps(st32), json.dumps(tag)))
        held = []
        pg.route('**/api/me/prefs', lambda route: held.append(route))
        pg.evaluate("location.hash='#/play/%s/0'" % st32); pg.wait_for_timeout(1500)
        t0 = time.time(); pg.evaluate("(()=>{CONTI.stageOpen(%s,0)})()" % svc_js(st32))
        try: pg.wait_for_selector('#stageWrap', timeout=6000)
        except Exception: fail('설정 받기가 걸려 있는 동안 무대 모드가 열리지 않음')
        if not held: fail('설정 받기 요청이 가로채지지 않음')
        pg.evaluate("CONTI.stageExit()"); pg.wait_for_timeout(300)
        for r in held:
            try: r.abort()
            except Exception: pass
        pg.unroute('**/api/me/prefs')
        print('F32 stage ok (%.1fs)' % (time.time() - t0))

        if errs: fail('page errors: %s' % errs)

        # ---------- F32(서비스 워커): 페이지 요청이 안 끝나도 캐시해 둔 화면으로 연다 ----------
        sctx = b.new_context(viewport={'width': 1180, 'height': 820})
        spg = sctx.new_page()
        spg.goto(URL); spg.wait_for_selector('#lgUser', timeout=10000)
        spg.wait_for_function("navigator.serviceWorker&&navigator.serviceWorker.controller", timeout=15000)
        spg.wait_for_timeout(1000)
        page_hung = []
        root = URL.rstrip('/') + '/'
        sctx.route(lambda u: u.split('#')[0] in (root, root + 'index.html'), lambda route: page_hung.append(route))
        t0 = time.time(); spg.goto(URL, wait_until='commit', timeout=15000)
        try: spg.wait_for_selector('#lgUser', timeout=9000)
        except Exception: fail('페이지 요청이 걸려 있는 동안 캐시로 열리지 않음')
        took = time.time() - t0
        if not page_hung: print('  (이 Playwright 는 서비스 워커의 요청을 가로채지 못해 건너뜀)')
        elif took > 7: fail('캐시로 너무 늦게 열림: %.1fs' % took)
        else: print('  서비스 워커 캐시로 %.1fs 에 열림' % took)
        for r in page_hung:
            try: r.abort()
            except Exception: pass
        sctx.close()

        # ---------- F100: 앱(NATIVE)에서 내보내기 → 공유 시트 ----------
        # https://localhost (주소에 포트가 없음) 로 열면 앱으로 본다. 앱은 운영 서버를 부르므로 그쪽 요청은 전부 막는다
        nctx = b.new_context(viewport={'width': 1180, 'height': 820}, service_workers='block')
        leaked = []
        def gate(route):
            u = route.request.url
            if u.startswith('https://localhost/'):
                r = route.fetch(url=URL + u[len('https://localhost/'):]); route.fulfill(response=r)
            elif u.startswith(URL): route.continue_()
            else: leaked.append(u); route.abort()
        nctx.route('**/*', gate)
        nctx.add_init_script("""
          window.__chunks=[];window.__shared=null;window.__shareMode='ok';
          window.Capacitor={Plugins:{
            Printer:{saveFile:async o=>{window.__chunks.push(o);return {uri:'file:///data/cache/exports/'+encodeURIComponent(o.name)}}},
            Share:{share:async o=>{if(window.__shareMode==='cancel')throw new Error('Share canceled');window.__shared=o;return {activityType:'x'}}}}};
          Object.defineProperty(Navigator.prototype,'canShare',{value:undefined,configurable:true});
        """)
        npg = nctx.new_page(); nerrs = []; npg.on('pageerror', lambda e: nerrs.append(str(e))); npg.on('dialog', lambda d: d.accept())
        npg.goto('https://localhost/#/home'); npg.wait_for_function('window.CONTI&&CONTI.S', timeout=20000)
        if not npg.evaluate("location.protocol==='https:'&&!location.port"): fail('앱 주소로 열리지 않음')
        npg.evaluate("CONTI.S.team.me.name='하은';CONTI.S.services.push({id:'nat'+%s,name:'앱 예배 😀',date:'2026-10-25',notice:'😀'.repeat(300000),version:0,items:[],published:null});CONTI.save();location.hash='#/home';CONTI.render()" % json.dumps(tag))
        npg.wait_for_selector('[data-act="export"]', timeout=10000)
        npg.click('[data-act="export"]'); npg.wait_for_function('!!window.__shared', timeout=15000); npg.wait_for_timeout(300)
        chunks = npg.evaluate('window.__chunks.map(c=>({n:c.name,a:c.append,l:c.data.length}))')
        whole = npg.evaluate("window.__chunks.map(c=>c.data).join('')")
        if len(chunks) < 2 or chunks[0]['a'] or not all(c['a'] for c in chunks[1:]): fail('큰 파일을 나눠 쓰지 않음: %s' % chunks)
        # 조각마다 따로 브리지를 건너므로(JSON) 이모지 반쪽으로 끝나면 깨진다
        if not npg.evaluate("window.__chunks.every(c=>{const x=c.data.charCodeAt(c.data.length-1),y=c.data.charCodeAt(0);return !(x>=0xd800&&x<=0xdbff)&&!(y>=0xdc00&&y<=0xdfff)})"): fail('이모지 반쪽에서 잘림')
        try: back = json.loads(whole)
        except Exception as e: fail('나눠 쓴 조각을 이으면 원래 파일이 아님: %s' % e)
        if not any(s['id'] == 'nat' + tag for s in back['services']): fail('내보낸 파일에 예배가 없음')
        shared = npg.evaluate('window.__shared')
        if not shared['files'] or not shared['files'][0].startswith('file:///'): fail('공유 시트에 파일이 안 넘어감: %s' % shared)
        t1 = npg.evaluate("(document.getElementById('toast')||{}).textContent||''")
        if '파일 보냄' not in t1: fail('공유를 마쳤는데 알림이 없음: %s' % t1)
        # 공유를 닫으면(취소) '보냄' 이라고 하지 않는다
        npg.evaluate("window.__shareMode='cancel';window.__shared=null;document.getElementById('toast').textContent=''")
        npg.click('[data-act="export"]'); npg.wait_for_timeout(2500)
        t2 = npg.evaluate("(document.getElementById('toast')||{}).textContent||''")
        if '보냄' in t2 or '저장' in t2: fail('공유를 취소했는데 보냈다고 알림: %s' % t2)
        # iOS 웹뷰: 웹 공유. 준비가 길어 손길이 만료되면 '보내기'를 한 번 더 누른다
        npg.evaluate("""(()=>{window.__ws=[];let n=0;
          Object.defineProperty(Navigator.prototype,'canShare',{value:function(d){return !!(d&&d.files&&d.files.length)},configurable:true,writable:true});
          Object.defineProperty(Navigator.prototype,'share',{value:function(o){n++;if(n===1){const e=new Error('gesture');e.name='NotAllowedError';return Promise.reject(e)}window.__ws.push(o.files[0].name);return Promise.resolve()},configurable:true,writable:true});
          window.__chunks=[];document.getElementById('toast').textContent=''})()""")
        npg.click('[data-act="export"]'); npg.wait_for_selector('#sfGo', timeout=10000)
        npg.click('#sfGo'); npg.wait_for_timeout(800)
        if not npg.evaluate('window.__ws.length'): fail('다시 눌렀는데 웹 공유가 안 됨')
        t3 = npg.evaluate("(document.getElementById('toast')||{}).textContent||''")
        if '파일 보냄' not in t3: fail('웹 공유를 마쳤는데 알림이 없음: %s' % t3)
        if npg.evaluate('window.__chunks.length'): fail('웹 공유가 되는데 앱 플러그인으로도 씀')
        print('  (밖으로 나가는 요청은 모두 막음: %d건, 운영 서버 %d건)' % (len(leaked), len([u for u in leaked if 'lets1414.com' in u])))
        if nerrs: fail('앱 모드 page errors: %s' % nerrs)
        print('F100 ok')
        b.close()
    print('AUDIT FE-12 TEST OK')


if __name__ == '__main__':
    run()
