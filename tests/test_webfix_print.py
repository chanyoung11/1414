# 인쇄: 악보 사진도 코드 차트도 없는 곡(제목·키·송폼만)
# 조판이 그런 곡을 통째로 건너뛰는데 앞 곡 바닥글은 '다음 N. 그 곡'을 가리켜, 종이에 없는 곡을 넘겨 찾게 했다 (desk-3).
# 바닥글을 인쇄된 다음 곡으로 돌리면 예배 순서와 어긋나니(그 곡도 부른다) 머리(번호·제목·키·송폼)만이라도 한 장 담는다.
#   CONTI_URL=http://localhost:9103/ .venv/bin/python tests/test_webfix_print.py
import os, re, sys, time
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
def fail(m): print('FAIL:', m); sys.exit(1)

# 쪽마다: 머리 번호·제목, 바닥글 '다음' 글, 악보·차트·'악보 없음' 여부
PAGES_JS = """(()=>[...document.querySelectorAll('#printArea .ppage')].map(pp=>({
  heads:[...pp.querySelectorAll('.songhead')].map(h=>({n:+(h.querySelector('.num')||{}).textContent,
    title:(h.querySelector('.title')||{}).textContent||'',key:(h.querySelector('.key')||{}).textContent||''})),
  text:pp.innerText,
  nx:(pp.querySelector('.pfoot2 .nx')||{}).textContent||'',
  slice:!!pp.querySelector('.pslice'),chart:!!pp.querySelector('.pchart'),
  body:!!pp.querySelector('.pslice,.pcover,.psum,.pchart,.songhead')})))()"""

def preview(pg):
    pg.click('#pvGo'); pg.wait_for_selector('#printArea.pv .ppage', timeout=10000); pg.wait_for_timeout(700)
    return pg.evaluate(PAGES_JS)

def check_next_chain(pages, label):
    # 바닥글이 '다음 N. 제목' 이라 하면 바로 다음 쪽이 그 곡 머리로 시작해야 한다 (넘기면 그 곡)
    for i, p in enumerate(pages):
        if not p['nx']: continue
        m = re.match(r'다음 (\d+)\. (.+?) / ', p['nx'])
        if not m: fail('%s: 바닥글 꼴이 이상함: %r' % (label, p['nx']))
        n, title = int(m.group(1)), m.group(2)
        if i + 1 >= len(pages): fail('%s: 마지막 쪽 바닥글이 종이에 없는 곡을 가리킴: %r' % (label, p['nx']))
        nh = pages[i + 1]['heads']
        if not nh or nh[0]['n'] != n or nh[0]['title'] != title:
            fail('%s: %d쪽 바닥글 %r 인데 다음 쪽 머리는 %r' % (label, i + 1, p['nx'], nh))

def run():
    tag = str(int(time.time()))[-6:]
    with sync_playwright() as p:
        b = p.chromium.launch(); c = b.new_context(viewport={'width':1400,'height':950}); pg = c.new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
        pg.goto(URL); pg.wait_for_selector('#lgUser')
        pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
        pg.check('#lgAgree')
        pg.fill('#lgName','하은'); pg.fill('#lgUser','wp'+tag); pg.fill('#lgPass','secret1'); pg.click('[data-act="lg-submit"]')
        pg.wait_for_selector('#gtTeam'); pg.fill('#gtTeam','인쇄팀'); pg.click('#gtSess .q:has-text("건반")'); pg.click('[data-act="team-create"]')
        pg.wait_for_selector('.shell[data-page]', timeout=10000)

        pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
        pg.fill('[data-f="svc.name"]','9/28 주일 1부')
        pg.click('[data-act="add-item"]'); pg.wait_for_timeout(400)
        pg.fill('[data-f="item.title"]','악보 있는 첫 곡'); pg.fill('[data-f="item.key"]','G')
        pg.fill('[data-f="item.form"]','Int – A – B'); pg.wait_for_timeout(300)
        pg.set_input_files('#pieceFile', [SHEET])
        pg.wait_for_function("(()=>{const p=(CONTI.S.services[0].items[0].pieces||[])[0];return p&&p.w>0})()", timeout=90000)
        pg.wait_for_timeout(1200)
        # 2·3번은 악보 사진도 차트도 없는 곡(송폼만 · 제목만), 4번은 1번 악보를 같이 쓰는 곡
        pg.evaluate("""(()=>{const s=CONTI.S.services[0];const p0=s.items[0].pieces[0];
          s.items.push({id:'wfxfo2',title:'송폼만 있는 곡',key:'D',mod:'',form:'A – B – C – B',pieces:[],media:[],notes:[]});
          s.items.push({id:'wfxfo3',title:'제목만 있는 곡',key:'E',mod:'',form:'',pieces:[],media:[],notes:[]});
          s.items.push({id:'wfxsc4',title:'악보 있는 끝 곡',key:'A',mod:'',form:'A – B',
            pieces:[{...JSON.parse(JSON.stringify(p0)),id:'wfxpc4'}],media:[],notes:[]});
          CONTI.save()})()""")
        pg.wait_for_timeout(400)
        sid = pg.evaluate("CONTI.S.services[0].id")
        pg.goto(URL + '#/view/' + sid); pg.wait_for_selector('[data-act="print"]', timeout=10000); pg.wait_for_timeout(1200)

        # ---- 합주·무대용 (기본: 곡별 악보 + 다음 곡 표시) ----
        pg.click('[data-act="print"]'); pg.wait_for_selector('#pvGo', timeout=8000)
        pg.click('[data-po="mode"][data-v="stage"]'); pg.wait_for_timeout(300)
        pages = preview(pg)
        heads = [h for p in pages for h in p['heads']]
        titles = [h['title'] for h in heads]
        print('합주용 %d장 · 머리: %s' % (len(pages), titles))
        for t in ('악보 있는 첫 곡','송폼만 있는 곡','제목만 있는 곡','악보 있는 끝 곡'):
            if t not in titles: fail('인쇄에서 빠진 곡: %s (머리 %s)' % (t, titles))
        if [h['n'] for h in heads if h['title'] in ('송폼만 있는 곡','제목만 있는 곡')] != [2, 3]:
            fail('악보 없는 곡 번호가 예배 순서와 다름: %r' % heads)
        fo = next(p for p in pages if any(h['title']=='송폼만 있는 곡' for h in p['heads']))
        if 'A – B – C – B' not in fo['text'] or not any(h['key']=='D' for h in fo['heads']):
            fail('송폼만 있는 곡 쪽에 키·송폼이 없음: %r' % fo['text'][:200])
        if fo['slice'] or fo['chart']: fail('악보 없는 곡 쪽에 악보·차트가 그려짐')
        if '악보 없음' not in fo['text']: fail('악보 없는 곡 쪽에 "악보 없음" 표시가 없음: %r' % fo['text'][:200])
        print('악보 없는 곡도 머리(번호·제목·키·송폼) 한 장 ok')
        check_next_chain(pages, '합주용')
        if not any('다음 2. 송폼만 있는 곡' in p['nx'] for p in pages): fail('1번 바닥글이 2번을 가리키지 않음')
        print('바닥글 "다음" 이 늘 바로 다음 쪽 곡 ok')
        if any(not p['body'] for p in pages): fail('내용 없는 빈 쪽이 있음')
        over = pg.evaluate("""(()=>{const bad=[];document.querySelectorAll('.ppage').forEach((pp,i)=>{
           const pr=pp.getBoundingClientRect();
           pp.querySelectorAll('.blk,.pstrip').forEach(b=>{const r=b.getBoundingClientRect();
             if(r.right>pr.right+0.6||r.left<pr.left-0.6||r.bottom>pr.bottom+0.6)bad.push(i+':'+(b.className||''))})});
           return bad})()""")
        if over: fail('페이지 밖으로 나간 블록: %s' % over[:6])
        print('빈 쪽·넘침 없음 ok')

        # ---- 범위: 악보 없는 곡 하나만 → '인쇄할 것이 없어요' 대신 그 곡 한 장 ----
        pg.click('[data-pv="opt"]'); pg.wait_for_selector('#pvGo', timeout=8000)
        pg.click('[data-po="only"][data-v="wfxfo2"]'); pg.wait_for_timeout(300)
        pg.click('#pvGo'); pg.wait_for_timeout(900)
        toast = pg.evaluate("(document.querySelector('#toast.show')||{}).textContent||''")
        if '인쇄할 것이 없어요' in toast: fail('곡별 악보를 켰는데 "인쇄할 것이 없어요": ' + toast)
        one = pg.evaluate(PAGES_JS)
        if len(one) != 1 or [h['title'] for h in one[0]['heads']] != ['송폼만 있는 곡'] or one[0]['nx']:
            fail('범위 한 곡(악보 없음) 미리보기가 이상함: %r' % one)
        print('범위 = 악보 없는 곡 하나 → 그 곡 한 장 ok')

        # ---- 보관·전달용 (표지 + 곡별, 다음 곡 표시 없음) ----
        pg.click('[data-pv="opt"]'); pg.wait_for_selector('#pvGo', timeout=8000)
        pg.click('[data-po="only"][data-v=""]'); pg.wait_for_timeout(200)
        pg.click('[data-po="mode"][data-v="archive"]'); pg.wait_for_timeout(300)
        ap = preview(pg)
        at = [h['title'] for p in ap for h in p['heads']]
        if not pg.locator('.ppage .pcover').count(): fail('보관용인데 표지가 없음')
        for t in ('송폼만 있는 곡','제목만 있는 곡'):
            if t not in at: fail('보관용에서 빠진 곡: %s (%s)' % (t, at))
        if any(p['nx'] for p in ap): fail('보관용(다음 곡 표시 끔)인데 바닥글에 다음 곡')
        print('보관용 %d장 ok' % len(ap))

        pg.click('[data-pv="close"]'); pg.wait_for_timeout(300)
        if errs: fail('JS 오류: %s' % errs[:3])
        b.close()
    print('OK test_webfix_print')

run()
