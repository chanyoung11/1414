# 코드 차트: 채보 결과 표시 · 전조·카포 반영 · 코드 수정 · 연습 화면 전환 · 라이브러리 저장
import os, sys, time, json
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
tag = str(int(time.time()))[-6:]

def fail(msg): print('FAIL:', msg); sys.exit(1)

# 채보 결과를 흉내 낸 차트 (악보 키 G)
CHART = {
    'at': 1, 'model': 'test', 'title': '테스트 곡', 'key': 'G', 'timeSignature': '4/4', 'tempo': 72,
    'form': 'Intro – A – B', 'notes': None,
    'sections': [
        {'name': 'Intro', 'repeat': None, 'bars': [
            {'chords': ['G'], 'lyric': None}, {'chords': ['Bm7'], 'lyric': None},
            {'chords': ['C', 'D'], 'lyric': None}, {'chords': [], 'lyric': None}]},
        {'name': 'A', 'repeat': 2, 'bars': [
            {'chords': ['G'], 'lyric': '우리 주'}, {'chords': ['D/F#'], 'lyric': '하나님'}]},
    ],
}

def run():
    with sync_playwright() as p:
        b = p.chromium.launch(); errs = []
        c = b.new_context(viewport={'width': 1300, 'height': 950}); pg = c.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
        pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=8000)
        pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
        pg.fill('#lgName', '하은'); pg.fill('#lgUser', 'ct' + tag); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')
        pg.wait_for_selector('#gtTeam', timeout=8000); pg.fill('#gtTeam', '차트팀'); pg.click('[data-act="team-create"]'); pg.wait_for_selector('.hd [data-act="team"]', timeout=8000)

        pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]'); pg.fill('[data-f="svc.name"]', '차트 예배')
        pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]')
        pg.fill('[data-f="item.title"]', '테스트 곡'); pg.fill('[data-f="item.key"]', 'A'); pg.wait_for_timeout(400)
        svc_id = pg.evaluate('CONTI.S.services[0].id')

        # 채보 결과를 곡에 넣고 다시 그림
        pg.evaluate("(ch)=>{const it=CONTI.S.services[0].items[0];it.chart=ch;CONTI.save();CONTI.render()}", CHART)
        pg.wait_for_selector('.chart', timeout=10000)

        # ---- 전조: 악보 G → 연주 A 이면 +2 ----
        head = pg.locator('.chart .chd').first.inner_text()
        if '+2' not in head: fail('전조 표시가 없음: ' + head)
        if '악보 G → 연주 A' not in head: fail('키 안내가 없음: ' + head)
        chords = pg.locator('.chart .cch').first.inner_text()
        if chords.strip() != 'A': fail('G 가 A 로 안 옮겨짐: %r' % chords)
        # 슬래시 코드도 옮겨지는지 (D/F# +2 → E/G#)
        allc = pg.locator('.chart').first.inner_text()
        if 'E/G#' not in allc: fail('슬래시 코드 전조 안 됨:\n' + allc)
        if 'x2' not in allc: fail('반복 표시가 없음')
        if '우리 주' not in allc: fail('가사가 안 보임')
        print('transpose ok:', chords.strip(), '/ E/G#')

        # ---- 코드 수정: 저장은 악보 키 기준 ----
        pg.locator('[data-cc="0.1.0"]').click(); pg.wait_for_selector('#ccIn', timeout=5000)
        if pg.locator('#ccIn').input_value() != 'Bm7': fail('수정창에 원래 코드가 안 뜸: %s' % pg.locator('#ccIn').input_value())
        prev = pg.locator('#ccPrev').inner_text()
        if prev != 'C#m7': fail('미리보기 전조가 틀림: %s' % prev)
        pg.fill('#ccIn', 'Em7'); pg.click('#ccOk'); pg.wait_for_timeout(800)
        saved = pg.evaluate("CONTI.S.services[0].items[0].chart.sections[0].bars[1].chords[0]")
        if saved != 'Em7': fail('악보 키 기준으로 저장 안 됨: %s' % saved)
        shown = pg.locator('[data-cc="0.1.0"]').inner_text()
        if shown != 'F#m7': fail('수정 후 표시가 전조 반영 안 됨: %s' % shown)
        print('edit ok: Em7 저장 →', shown, '표시')

        # ---- 라이브러리에 차트가 따라감 ----
        lib = pg.evaluate("(CONTI.S.library[0]||{}).chart ? CONTI.S.library[0].chart.sections.length : 0")
        if lib != 2: fail('라이브러리에 차트가 안 들어감: %s' % lib)
        print('library ok')

        # ---- 발행 후 연습 화면에서 차트 탭 ----
        pg.click('[data-act="publish"]'); pg.wait_for_selector('#pubOnly'); pg.click('#pubOnly'); pg.wait_for_timeout(5000)
        pg.goto(URL + '#/play/' + svc_id + '/0'); pg.wait_for_selector('[data-act="chart-tab"]', timeout=15000)
        pg.click('[data-act="chart-tab"]'); pg.wait_for_selector('#chartpanel .chart', timeout=10000)
        ptxt = pg.locator('#chartpanel').inner_text()
        if 'F#m7' not in ptxt: fail('연습 화면 차트에 수정이 반영 안 됨')
        print('play chart ok')

        # ---- 카포 2: 연주 A 기준으로 두 반음 내려 보임 ----
        pg.goto(URL + '#/home'); pg.wait_for_selector('.hd'); pg.click('.hd [data-act="settings"]'); pg.wait_for_selector('#sCapo')
        pg.fill('#sCapo', '2'); pg.click('#sOk'); pg.wait_for_timeout(1500)
        pg.goto(URL + '#/play/' + svc_id + '/0'); pg.wait_for_selector('#chartpanel .chart', timeout=15000); pg.wait_for_timeout(500)
        cap = pg.locator('#chartpanel .cch').first.inner_text().strip()
        if cap != 'G': fail('카포 2 인데 첫 코드가 G 가 아님: %s' % cap)
        if '카포 2' not in pg.locator('#chartpanel .chd').inner_text(): fail('카포 표시가 없음')
        print('capo ok:', cap)

        # ---- 콘티 보기에서 접힌 차트 ----
        pg.goto(URL + '#/view/' + svc_id); pg.wait_for_selector('.cwrap', timeout=15000); pg.wait_for_timeout(2500)
        if '코드 차트 보기' not in pg.locator('.cwrap').inner_text(): fail('콘티 보기에 차트 토글이 없음')
        pg.locator('.cwrap').first.evaluate("d=>{d.open=true}"); pg.wait_for_timeout(600)
        if 'G' not in pg.locator('.cwrap .cch').first.inner_text(): fail('펼친 차트가 비어 있음')
        print('viewer chart ok')

        # ---- 차트 지우기 ----
        pg.goto(URL + '#/edit/' + svc_id); pg.wait_for_selector('[data-act="chart-del"]', timeout=15000)
        pg.locator('[data-act="chart-del"]').first.dispatch_event('click'); pg.wait_for_timeout(1000)
        if pg.evaluate("!!CONTI.S.services[0].items[0].chart"): fail('차트가 안 지워짐')
        if pg.locator('.chart').count(): fail('지운 뒤에도 차트가 보임')
        print('delete ok')

        print('errors:', errs)
        if errs: fail('page errors')
        b.close()
    print('CHART TEST OK')

if __name__ == '__main__':
    run()
