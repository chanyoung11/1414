# 개발 요청 2: C 세션별 미디어 · B 예배 노트 · A 코드 인식·전조 (온라인, GOOGLE_VISION_KEY=mock 권장)
import os, sys, time
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET = os.environ.get('CONTI_SHEET') or os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
tag = str(int(time.time()))[-6:]
LEADER = ('lead' + tag, 'secret1', '하은'); DRUM = ('mem' + tag, 'secret1', '민수'); KEYS = ('key' + tag, 'secret1', '지은')

def fail(msg): print('FAIL:', msg); sys.exit(1)

def signup(pg, user):
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=8000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
    pg.fill('#lgName', user[2]); pg.fill('#lgUser', user[0]); pg.fill('#lgPass', user[1]); pg.click('[data-act="lg-submit"]')

def join(ctx, user, link, session):
    pm = ctx.new_page(); pm.goto(link); pm.wait_for_selector('#lgUser', timeout=8000)
    pm.click('[data-act="lg-mode"][data-m="signup"]'); pm.wait_for_selector('#lgName'); pm.fill('#lgName', user[2]); pm.fill('#lgUser', user[0]); pm.fill('#lgPass', user[1]); pm.click('[data-act="lg-submit"]')
    pm.wait_for_selector('#jnName', timeout=8000); pm.click('#gtSess .q:has-text("%s")' % session); pm.click('[data-act="team-join"]'); pm.wait_for_selector('.hd [data-act="team"]', timeout=8000)
    return pm

def run():
    with sync_playwright() as p:
        b = p.chromium.launch(); errs = []
        c1 = b.new_context(viewport={'width': 1180, 'height': 820}); pg = c1.new_page(); pg.on('pageerror', lambda e: errs.append('L:' + str(e)))
        signup(pg, LEADER); pg.wait_for_selector('#gtTeam', timeout=8000); pg.fill('#gtTeam', '요청2팀'); pg.click('[data-act="team-create"]'); pg.wait_for_selector('.hd [data-act="team"]', timeout=8000)
        pg.click('.hd [data-act="team"]'); pg.wait_for_selector('#tmLink'); link = pg.locator('#tmLink').inner_text().strip(); pg.keyboard.press('Escape')
        ocr = c1.request.get(URL + 'api/ocr').json(); print('ocr available:', ocr)

        # ---- 예배 + 곡 + 악보(코드 인식) ----
        pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]'); pg.fill('[data-f="svc.name"]', '요청2 예배')
        pg.fill('[data-f="svc.message"]', '이번 예배는 잔잔하게 시작합니다.\n\n둘째 곡 브레이크 확실히.')
        pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]'); pg.fill('[data-f="item.title"]', '우리 주 하나님'); pg.fill('[data-f="item.key"]', 'A')
        pg.set_input_files('#pieceFile', [SHEET])
        if ocr.get('available'):
            pg.wait_for_function("(()=>{const p=CONTI.S.services[0].items[0].pieces[0];return p&&p.ocr==='done'})()", timeout=30000)
            info = pg.evaluate("(()=>{const p=CONTI.S.services[0].items[0].pieces[0];return {n:(p.chords||[]).length,key:p.sheetKey}})()")
            print('chords:', info)
            if info['n'] < 5: fail('코드 인식 결과가 너무 적음')
            pg.wait_for_selector('.chordbar [data-act="sheet-key"]', timeout=8000)
            # 악보 키를 G로 확정 → 연주 키 A → +2, 빨간 코드가 옮겨져 있어야 함
            pg.click('.chordbar [data-act="sheet-key"]'); pg.wait_for_selector('#modal [data-k="G"]'); pg.click('#modal [data-k="G"]'); pg.wait_for_timeout(500)
            red = pg.evaluate("[...document.querySelectorAll('#sheet .chd')].map(e=>e.textContent)")
            want = pg.evaluate("(()=>{const it=CONTI.S.services[0].items[0];const p=it.pieces[0];const off=CONTI.chordOffset(it,p);return {off,list:p.chords.map(c=>CONTI.transposeChord(c.text,off,it.key)),orig:p.chords.slice(0,6).map(c=>c.text)}})()")
            print('orig:', want['orig'], '-> red:', red[:6], 'offset', want['off'])
            if want['off'] != 2 or not red or red != want['list']: fail('전조 결과 이상: %s vs %s' % (red[:6], want['list'][:6]))
            if not any('/' in x for x in want['orig'] + red): print('  (분수 코드 없음)')
            # 연주 키를 G로 → 전조량 0 → 빨간 글씨 없음
            pg.fill('[data-f="item.key"]', 'G'); pg.wait_for_timeout(500)
            if pg.locator('#sheet .chd').count() != 0: fail('전조량 0인데 빨간 글씨가 있음')
            pg.fill('[data-f="item.key"]', 'A'); pg.wait_for_timeout(400)
            # 코드 도구로 첫 코드 고치기
            pg.click('[data-act="tool"][data-t="chord"]'); pg.wait_for_selector('#sheet .chdbox'); pg.locator('#sheet .chdbox').first.click(); pg.wait_for_selector('#chText'); pg.fill('#chText', 'Em7'); pg.click('#chOk'); pg.wait_for_timeout(400)
            if pg.evaluate("CONTI.S.services[0].items[0].pieces[0].chords[0].text") != 'Em7': fail('코드 수정 미반영')
            pg.click('[data-act="tool"][data-t="marker"]')
            # 자동 채우기: 제목·키가 빈 곡에 악보를 넣으면 채워진다
            pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]'); pg.wait_for_timeout(300)
            pg.set_input_files('#pieceFile', [SHEET])
            pg.wait_for_function("(()=>{const it=CONTI.S.services[0].items[1];const p=it&&it.pieces[0];return p&&p.ocr==='done'})()", timeout=40000)
            auto = pg.evaluate("(()=>{const it=CONTI.S.services[0].items[1];return {title:it.title,key:it.key,mode:it.pieces[0].ocrMode,n:it.pieces[0].chords.length}})()")
            print('autofill:', auto)
            if not auto['title'] or not auto['key']: fail('제목/키 자동 채우기 실패: %s' % auto)
            if pg.locator('[data-f="item.title"]').input_value() != auto['title']: fail('제목 입력창 미갱신')
            pg.click('[data-act="del-item"]'); pg.wait_for_timeout(500)
            pg.locator('.list-item').first.click(); pg.wait_for_timeout(400)
        else:
            pg.wait_for_timeout(3000); print('OCR 미연결 → 인식 검사 건너뜀')
        # ---- 미디어: 전체 1개 + 드럼 전용 1개 ----
        pg.fill('#ytUrl', 'https://youtu.be/dQw4w9WgXcQ'); pg.click('[data-act="add-yt"]'); pg.wait_for_timeout(400)
        pg.click('#mdTarget [data-mdt="드럼"]'); pg.fill('#ytUrl', 'https://youtu.be/C7s2MeQ122M'); pg.click('[data-act="add-yt"]'); pg.wait_for_timeout(400)
        tags = pg.locator('[data-act="md-target"]').all_inner_texts(); print('media tags:', tags)
        if tags != ['전체', '드럼']: fail('미디어 대상 태그 이상: %s' % tags)
        svc_id = pg.evaluate("CONTI.S.services[0].id")
        pg.click('[data-act="publish"]'); pg.wait_for_selector('#pubOnly'); kk = pg.locator('#kk').input_value()
        if '잔잔하게' not in kk or '앱에서 전문 보기' not in kk or '브레이크' in kk: fail('카톡 텍스트에 첫 문단만 들어가야 함: ' + kk)
        pg.click('#pubOnly'); pg.wait_for_timeout(6000)
        print('published', svc_id)

        # ---- 드럼 멤버 ----
        c2 = b.new_context(viewport={'width': 430, 'height': 900}); pm = join(c2, DRUM, link, '드럼'); pm.on('pageerror', lambda e: errs.append('D:' + str(e)))
        pm.wait_for_selector('.svcrow', timeout=15000); pm.goto(URL + '#/view/' + svc_id); pm.wait_for_selector('#msgOk', timeout=15000)   # 예배 노트 첫 입장 바텀시트
        if '잔잔하게' not in pm.locator('#msgBody').inner_text(): fail('예배 노트 본문 없음')
        pm.click('#msgOk'); pm.wait_for_timeout(400)
        if pm.locator('[data-act="msg"].dot').count(): fail('읽은 뒤에도 빨간 점')
        pm.reload(); pm.wait_for_selector('[data-act="msg"]', timeout=15000); pm.wait_for_timeout(800)
        if pm.locator('#msgOk').count(): fail('읽었어요 뒤에도 자동으로 다시 뜸')
        drum_tags = [t for t in pm.locator('.card .tag').all_inner_texts() if t == '드럼']
        if len(drum_tags) != 1: fail('드럼 화면에 드럼 전용 미디어 태그가 없음')
        pm.goto(URL + '#/play/' + svc_id + '/0'); pm.wait_for_selector('[data-act="msel"]', timeout=15000)
        chips = pm.locator('[data-act="msel"]').all_inner_texts(); on = pm.locator('[data-act="msel"].on').inner_text()
        if len(chips) != 2 or '드럼' not in on: fail('드럼: 전용 미디어가 맨 앞·기본 선택이어야 함: %s / %s' % (chips, on))
        if ocr.get('available'):
            if pm.locator('#sheet .chd').count() < 5: fail('멤버 연습 화면에 빨간 코드 없음')
            pm.click('[data-act="pf"][data-k="chords"]'); pm.wait_for_timeout(300)
            if pm.locator('#sheet .chd').count() != 0: fail('전조 코드 토글 꺼도 남음')
        print('drum member ok')

        # ---- 건반 멤버: 드럼 전용은 안 보임 ----
        c3 = b.new_context(viewport={'width': 430, 'height': 900}); pk = join(c3, KEYS, link, '건반'); pk.on('pageerror', lambda e: errs.append('K:' + str(e)))
        pk.wait_for_selector('.svcrow', timeout=15000); pk.goto(URL + '#/view/' + svc_id); pk.wait_for_selector('#msgOk', timeout=15000); pk.click('#msgOk')
        if [t for t in pk.locator('.card .tag').all_inner_texts() if t == '드럼']: fail('건반 화면에 드럼 전용 미디어가 보임')
        pk.goto(URL + '#/play/' + svc_id + '/0'); pk.wait_for_selector('[data-act="msel"]', timeout=15000)
        if pk.locator('[data-act="msel"]').count() != 1: fail('건반: 미디어는 전체용 1개만 보여야 함')
        print('keys member ok')

        # ---- 글을 고쳐 재발행 → 드럼 멤버에 빨간 점 + 다시 한 번 ----
        pg.goto(URL + '#/edit/' + svc_id); pg.wait_for_selector('[data-f="svc.message"]'); pg.fill('[data-f="svc.message"]', '글을 고쳤습니다. 다시 읽어 주세요.'); pg.wait_for_timeout(300)
        pg.click('[data-act="publish"]'); pg.wait_for_selector('#pubOnly'); pg.click('#pubOnly'); pg.wait_for_timeout(4000)
        pm.goto(URL + '#/home'); pm.wait_for_selector('.hd'); pm.evaluate("CONTI.SYNC.pullServices().then(()=>CONTI.render())"); pm.wait_for_timeout(3000)
        pm.goto(URL + '#/view/' + svc_id); pm.wait_for_selector('#msgOk', timeout=15000)
        if '고쳤습니다' not in pm.locator('#msgBody').inner_text(): fail('새 글이 아님')
        print('message rev ok; errors:', errs)
        if errs: fail('page errors')
        b.close()
    print('REQ2 TEST OK')

if __name__ == '__main__':
    run()
