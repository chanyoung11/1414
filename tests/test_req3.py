# 개선안 묶음: 발행 충돌 · 카포 · 복구 코드 · 모바일 더보기 · 초안 동기화(두 기기) · 곡 안 전조 마커
import os, sys, time
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
tag = str(int(time.time()))[-6:]
LEADER = ('lead' + tag, 'secret1', '하은')

def fail(msg): print('FAIL:', msg); sys.exit(1)

def login(pg, user, mode='login'):
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=8000)
    if mode == 'signup':
        pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.fill('#lgName', user[2])
    pg.fill('#lgUser', user[0]); pg.fill('#lgPass', user[1]); pg.click('[data-act="lg-submit"]')

def run():
    with sync_playwright() as p:
        b = p.chromium.launch(); errs = []
        # ---- 기기 A (인도자): 팀 → 예배 → 악보 ----
        cA = b.new_context(viewport={'width': 1180, 'height': 820}); A = cA.new_page(); A.on('pageerror', lambda e: errs.append('A:' + str(e)))
        login(A, LEADER, 'signup'); A.wait_for_selector('#gtTeam', timeout=8000); A.fill('#gtTeam', '개선팀'); A.click('[data-act="team-create"]'); A.wait_for_selector('.hd [data-act="team"]', timeout=8000)
        team = A.evaluate("CONTI.S.team.id")
        A.click('[data-act="new-svc"]'); A.wait_for_selector('[data-f="svc.name"]'); A.fill('[data-f="svc.name"]', '개선 예배')
        A.click('[data-act="add-item"]'); A.wait_for_selector('[data-f="item.title"]'); A.fill('[data-f="item.title"]', '우리 주 하나님'); A.fill('[data-f="item.key"]', 'A')
        A.set_input_files('#pieceFile', [SHEET])
        ocr = cA.request.get(URL + 'api/ocr').json()
        if ocr.get('available'):
            A.wait_for_function("(()=>{const p=CONTI.S.services[0].items[0].pieces[0];return p&&p.ocr==='done'})()", timeout=30000)
        else:
            A.wait_for_timeout(3000)
        svc_id = A.evaluate("CONTI.S.services[0].id")
        # 마커 하나 찍고 "여기부터 전조 +2"
        A.click('#sheet .slice', position={'x': 200, 'y': 160}); A.wait_for_selector('#modal [data-l]'); A.click('#modal [data-l]'); A.wait_for_timeout(400)
        A.click('#sheet [data-marker]'); A.wait_for_selector('#modal [data-ks="2"]'); A.click('#modal [data-ks="2"]'); A.wait_for_timeout(500)
        ks = A.evaluate("CONTI.S.services[0].items[0].pieces[0].markers[0].keyShift")
        if ks != 2: fail('전조 마커 keyShift 저장 안 됨: %s' % ks)
        A.keyboard.press('Escape')
        if ocr.get('available'):
            # 악보 키 = 연주 키(A) 로 확정 → 마커 위 코드는 빨간 글씨 없음, 마커 아래 코드는 +2
            A.click('.chordbar [data-act="sheet-key"]'); A.wait_for_selector('#modal [data-k="A"]'); A.click('#modal [data-k="A"]'); A.wait_for_timeout(500)
            info = A.evaluate("(()=>{const it=CONTI.S.services[0].items[0];const p=it.pieces[0];const my=p.markers[0].y;const above=p.chords.filter(c=>c.y<my).length;const below=p.chords.filter(c=>c.y>=my).length;return {above,below,red:document.querySelectorAll('#sheet .chd').length}})()")
            print('keyShift render:', info)
            if info['red'] != info['below'] or info['below'] == 0: fail('전조 마커 아래 코드만 빨간 글씨여야 함: %s' % info)
        # 발행 (v1)
        A.click('[data-act="publish"]'); A.wait_for_selector('#pubOnly'); A.click('#pubOnly'); A.wait_for_timeout(6000)
        print('A published v1')

        # ---- 기기 B (같은 인도자, 다른 브라우저): 초안이 서버에서 내려오는지 ----
        cB = b.new_context(viewport={'width': 1180, 'height': 820}); B = cB.new_page(); B.on('pageerror', lambda e: errs.append('B:' + str(e)))
        login(B, LEADER); B.wait_for_selector('.svcrow', timeout=15000)
        B.goto(URL + '#/edit/' + svc_id); B.wait_for_selector('[data-f="item.title"]', timeout=15000)
        if B.evaluate("CONTI.S.services[0].items[0].title") != '우리 주 하나님': fail('기기 B에 예배가 안 내려옴')
        # B 에서 편집 → 초안 서버 저장 (2.5초 디바운스)
        B.fill('[data-f="item.title"]', '우리 주 하나님 (B에서 수정)'); B.wait_for_timeout(4000)
        r = cB.request.get(URL + 'api/services/' + svc_id + '/draft?team=' + team).json()
        if not r.get('doc') or '(B에서 수정)' not in r['doc']['items'][0]['title']: fail('B 초안이 서버에 없음: %s' % str(r)[:200])
        print('B draft pushed')
        # A 가 편집기를 다시 열면 "더 새로운 초안" 확인 → 수락
        A.once('dialog', lambda d: d.accept())
        A.goto(URL + '#/home'); A.wait_for_selector('.hd'); A.goto(URL + '#/edit/' + svc_id); A.wait_for_timeout(2500)
        if '(B에서 수정)' not in A.evaluate("CONTI.S.services[0].items[0].title"): fail('A 가 B 초안을 못 가져옴: ' + A.evaluate("CONTI.S.services[0].items[0].title"))
        print('A pulled draft')

        # ---- 발행 충돌: B 가 v2 발행 → A 도 v2 발행 시도 → 거부 + 롤백 ----
        B.click('[data-act="publish"]'); B.wait_for_selector('#pubOnly'); B.click('#pubOnly'); B.wait_for_timeout(5000)
        A.once('dialog', lambda d: d.accept())
        A.fill('[data-f="svc.notice"]', 'A 공지'); A.wait_for_timeout(300)
        A.click('[data-act="publish"]'); A.wait_for_selector('#pubOnly'); A.click('#pubOnly'); A.wait_for_timeout(5000)
        ver = cA.request.get(URL + 'api/services?team=' + team).json()['services'][0]['version']
        if ver != 2: fail('서버 버전이 2가 아님: %s' % ver)
        print('publish conflict handled, server v%s' % ver)

        # ---- 카포: 설정에서 2 → 연습 화면 빨간 코드 ----
        if ocr.get('available'):
            A.goto(URL + '#/home'); A.wait_for_selector('.hd'); A.click('.hd [data-act="settings"]'); A.wait_for_selector('#sCapo'); A.fill('#sCapo', '2'); A.click('#sOk'); A.wait_for_timeout(1000)
            if A.evaluate("CONTI.S.team.me.capo") != 2: fail('카포 저장 안 됨')
            A.goto(URL + '#/play/' + svc_id + '/0'); A.wait_for_selector('#sheet', timeout=15000); A.wait_for_timeout(1500)
            # 악보 키 = 연주 키, 카포 2 → 마커 위 코드는 -2 로 빨간 글씨, 마커 아래는 전조 +2 와 상쇄돼 0 → 없음
            got = A.evaluate("(()=>{const p=CONTI.S.services[0].published.items[0].pieces[0];const my=p.markers[0].y;return {red:document.querySelectorAll('#sheet .chd').length,above:p.chords.filter(c=>c.y<my).length,first:(document.querySelector('#sheet .chd')||{}).textContent}})()")
            print('capo render:', got)
            if got['red'] != got['above'] or got['above'] == 0: fail('카포 적용 이상: %s' % got)
            print('capo ok')

        # ---- 복구 코드 ----
        A.goto(URL + '#/home'); A.wait_for_selector('.hd'); A.click('.hd [data-act="settings"]'); A.wait_for_selector('#sRc'); A.click('#sRc'); A.wait_for_selector('.linkbox')
        code = A.locator('.linkbox').inner_text().strip(); A.click('#rcClose')
        A.evaluate("fetch('/api/auth/logout',{method:'POST',headers:{'x-conti':'1'}})"); A.wait_for_timeout(500); A.reload(); A.wait_for_selector('#lgUser', timeout=8000)
        A.click('[data-act="lg-mode"][data-m="recover"]'); A.wait_for_selector('#rcCode'); A.fill('#lgUser', LEADER[0]); A.fill('#rcCode', code); A.fill('#lgPass', 'newpass1'); A.click('[data-act="rc-submit"]')
        A.wait_for_selector('.hd', timeout=8000)
        if A.evaluate("(CONTI.NET.user||{}).username") != LEADER[0]: fail('복구 코드 로그인 실패')
        print('recovery ok')

        # ---- 두 곡 나란히 스캔 → 두 곡으로 분리 ----
        TWO = os.path.join(ROOT, 'docs', 'sample_two_pages.jpg')
        if os.path.exists(TWO):
            A.goto(URL + '#/home'); A.wait_for_selector('.hd'); A.click('[data-act="new-svc"]'); A.wait_for_selector('[data-f="svc.name"]'); A.fill('[data-f="svc.name"]', '분리 테스트')
            A.click('[data-act="add-item"]'); A.wait_for_selector('[data-f="item.title"]'); A.set_input_files('#pieceFile', [TWO])
            A.wait_for_function("(()=>{const s=CONTI.S.services.find(x=>x.name==='분리 테스트');const its=s?s.items:[];return its.length>=2&&its.every(it=>it.pieces.length&&it.pieces.every(p=>p.ocr&&p.ocr!=='pending'))})()", timeout=120000)
            two = A.evaluate("CONTI.S.services.find(x=>x.name==='분리 테스트').items.map(it=>({title:it.title,key:it.key,n:it.pieces[0].chords.length}))")
            print('split:', two)
            if len(two) != 2: fail('두 곡으로 나뉘지 않음: %s' % two)
            if ocr.get('available') and not (two[0]['n'] and two[1]['n']): fail('나뉜 곡의 코드가 비어 있음: %s' % two)
            print('two-page split ok')
        STACK = os.path.join(ROOT, 'docs', 'sample_stacked.jpg')
        if os.path.exists(STACK):
            A.goto(URL + '#/home'); A.wait_for_selector('.hd'); A.click('[data-act="new-svc"]'); A.wait_for_selector('[data-f="svc.name"]'); A.fill('[data-f="svc.name"]', '세로 분리')
            A.click('[data-act="add-item"]'); A.wait_for_selector('[data-f="item.title"]'); A.set_input_files('#pieceFile', [STACK])
            A.wait_for_function("(()=>{const s=CONTI.S.services.find(x=>x.name==='세로 분리');const its=s?s.items:[];return its.length>=2&&its.every(it=>it.pieces.length&&it.pieces.every(p=>p.ocr&&p.ocr!=='pending'))})()", timeout=120000)
            st = A.evaluate("CONTI.S.services.find(x=>x.name==='세로 분리').items.map(it=>({title:it.title,key:it.key,n:it.pieces[0].chords.length,h:it.pieces[0].h}))")
            print('stacked split:', st)
            if len(st) != 2: fail('위아래 두 곡이 나뉘지 않음: %s' % st)
            print('stacked split ok')

        # ---- 모바일 더보기 메뉴 ----
        cM = b.new_context(viewport={'width': 390, 'height': 844}); M = cM.new_page(); login(M, (LEADER[0], 'newpass1', LEADER[2])); M.wait_for_selector('.hd', timeout=8000)
        if M.locator('[data-act="sync"]').first.is_visible(): fail('모바일에서 보조 버튼이 그대로 보임')
        M.click('[data-act="home-more"]'); M.wait_for_selector('#modal [data-m="export"]'); print('mobile more-menu ok')
        print('errors:', errs)
        if errs: fail('page errors')
        b.close()
    print('REQ3 TEST OK')

if __name__ == '__main__':
    run()
