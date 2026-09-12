# 재구성 악보: 채보 데이터 → OSMD 오선 그리기 · 조옮김 · 마디 편집 · MusicXML 내보내기
import os, sys, time
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
tag = str(int(time.time()))[-6:]
def fail(m): print('FAIL:', m); sys.exit(1)

# 8마디, 1·2번 괄호, 도돌이표, 2절 가사, 중간 조 바뀜
SCORE = {
  'at': 1, 'model': 'test', 'lines': 2, 'cost': 24,
  'title': '주 은혜임을', 'composer': '홍길동', 'key': 'G', 'time': '4/4', 'tempo': 72, 'verses': 2, 'pickup': False,
  'measures': [
    {'c': [{'b': 0, 't': 'G'}], 'n': [{'p':'D4','d':4,'l':['주','내']},{'p':'G4','d':4,'l':['은','평']},{'p':'B4','d':2,'l':['혜','생']}], 'rs': True},
    {'c': [{'b': 0, 't': 'Bm7'}, {'b': 2, 't': 'Em'}], 'n': [{'p':'A4','d':8},{'p':'B4','d':8},{'p':'D5','d':4},{'p':None,'d':2}]},
    {'c': [{'b': 0, 't': 'C'}], 'n': [{'p':'C5','d':4,'dot':True},{'p':'B4','d':8},{'p':'A4','d':2,'tie':True}]},
    {'c': [{'b': 0, 't': 'D/F#'}], 'n': [{'p':'A4','d':1}], 'end': 1, 're': True},
    {'c': [{'b': 0, 't': 'G'}], 'n': [{'p':'G4','d':1}], 'end': 2},
    {'c': [{'b': 0, 't': 'Cb'}], 'n': [{'p':'Eb5','d':2},{'p':'Db5','d':2}], 'key': 'Cb'},
    {'c': [{'b': 0, 't': 'Fb'}], 'n': [{'p':'Cb5','d':4},{'p':'Bb4','d':4},{'p':'Ab4','d':2}]},
    {'c': [], 'n': [{'p':'Cb5','d':1}]},
  ],
}

def run():
  with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    c = b.new_context(viewport={'width': 1400, 'height': 1000}); pg = c.new_page()
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=8000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
    pg.fill('#lgName', '하은'); pg.fill('#lgUser', 'sc'+tag); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam', timeout=8000); pg.fill('#gtTeam', '악보팀'); pg.click('[data-act="team-create"]'); pg.wait_for_selector('.shell[data-page]', timeout=8000)

    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]'); pg.fill('[data-f="svc.name"]', '악보 예배')
    pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]')
    pg.fill('[data-f="item.title"]', '주 은혜임을'); pg.fill('[data-f="item.key"]', 'G'); pg.wait_for_timeout(400)
    svc = pg.evaluate('CONTI.S.services[0].id'); item = pg.evaluate('CONTI.S.services[0].items[0].id')

    pg.evaluate("(sc)=>{const it=CONTI.S.services[0].items[0];it.score=sc;CONTI.save()}", SCORE)
    pg.goto(URL + '#/score/%s/%s' % (svc, item)); pg.wait_for_timeout(500)

    # ---- OSMD 가 실제 오선을 그렸는가 ----
    pg.wait_for_selector('#osmd svg', timeout=25000)
    pg.wait_for_timeout(1200)
    n_paths = pg.evaluate("document.querySelectorAll('#osmd svg path').length")
    if n_paths < 30: fail('오선/음표가 거의 안 그려짐: path %d개' % n_paths)

    svg = pg.evaluate("document.querySelector('#osmd svg').outerHTML")
    for want in ['주 은혜임을', 'Bm7', 'D/F#']:
      if want not in svg: fail('악보에 %r 이(가) 없음' % want)
    if '은' not in svg or '평' not in svg: fail('2절 가사가 안 그려짐')
    print('osmd ok: path', n_paths)

    # ---- 조옮김: G → A (+2) 이면 코드도 함께 ----
    pg.click('[data-act="score-tr"][data-d="1"]'); pg.wait_for_timeout(300)
    pg.click('[data-act="score-tr"][data-d="1"]'); pg.wait_for_selector('#osmd svg', timeout=20000); pg.wait_for_timeout(1200)
    svg2 = pg.evaluate("document.querySelector('#osmd svg').outerHTML")
    if 'C#m7' not in svg2: fail('Bm7 이 C#m7 로 안 옮겨짐')
    if 'E/G#' not in svg2: fail('슬래시 코드 전조 안 됨')
    if not pg.locator('.top .pill.key').first.inner_text().startswith('A'): fail('머리말 키가 A 가 아님')
    print('transpose ok')
    pg.click('[data-act="score-tr"][data-d="0"]'); pg.wait_for_timeout(1200)

    # ---- 마디 고치기: 코드·음표·가사 ----
    pg.click('[data-act="score-edit"]'); pg.wait_for_timeout(1200)
    ok = pg.evaluate("()=>{const o=CONTI.SC.osmd;if(!o)return null;const m=o.GraphicSheet.MeasureList[1][0];const bb=m.PositionAndShape;return {x:bb.AbsolutePosition.x*CONTI.SC.k,y:bb.AbsolutePosition.y*CONTI.SC.k,w:bb.Size.width*CONTI.SC.k,h:bb.Size.height*CONTI.SC.k}}")
    if not ok: fail('OSMD 마디 좌표를 못 읽음')
    host = pg.locator('#osmd svg').bounding_box()
    pg.mouse.click(host['x'] + ok['x'] + ok['w']/2, host['y'] + ok['y'] + ok['h']/2)
    pg.wait_for_selector('#mcAdd', timeout=6000)
    body = pg.locator('#modal').inner_text()
    if '2마디' not in body: fail('2마디 창이 안 뜸:\n' + body[:200])
    pg.fill('[data-ct="0"]', 'Bm'); pg.wait_for_timeout(200)
    pg.fill('[data-nl="0"][data-v="0"]', '테스트'); pg.wait_for_timeout(200)
    pg.click('[data-close="1"]'); pg.wait_for_timeout(1500)
    got = pg.evaluate("CONTI.S.services[0].items[0].score.measures[1].c[0].t")
    if got != 'Bm': fail('코드 수정이 저장 안 됨: %r' % got)
    lyr = pg.evaluate("CONTI.S.services[0].items[0].score.measures[1].n[0].l[0]")
    if lyr != '테스트': fail('가사 수정이 저장 안 됨: %r' % lyr)
    svg3 = pg.evaluate("document.querySelector('#osmd svg').outerHTML")
    if '테스트' not in svg3: fail('고친 가사가 악보에 안 나옴')
    print('edit ok')

    # ---- 마디 추가·삭제 ----
    before = pg.evaluate("CONTI.S.services[0].items[0].score.measures.length")
    pg.mouse.click(host['x'] + ok['x'] + ok['w']/2, host['y'] + ok['y'] + ok['h']/2)
    pg.wait_for_selector('#mIns2', timeout=6000); pg.click('#mIns2'); pg.wait_for_timeout(900)
    if pg.evaluate("CONTI.S.services[0].items[0].score.measures.length") != before+1: fail('마디 추가 안 됨')
    pg.click('#mDel'); pg.wait_for_timeout(900)
    if pg.evaluate("CONTI.S.services[0].items[0].score.measures.length") != before: fail('마디 삭제 안 됨')
    pg.click('[data-close="1"]'); pg.wait_for_timeout(400)
    print('measure add/del ok')

    # ---- MusicXML 내보내기 ----
    xml = pg.evaluate("()=>{const it=CONTI.S.services[0].items[0];return CONTI.scoreToMusicXML(it.score)}")
    for want in ['<score-partwise', '<repeat direction="forward"', '<ending number="1"', '<fifths>-7</fifths>', '<lyric number="2"', '<dot/>', '<tie type="start"/>', '<beam number="1">begin</beam>']:
      if want not in xml: fail('MusicXML 에 %r 이(가) 없음' % want)
    print('musicxml ok:', len(xml), 'bytes')

    # ---- 박자 검사 ----
    bad = pg.evaluate("CONTI.badMeasuresOf(CONTI.S.services[0].items[0].score)")
    if bad: fail('정상 악보인데 박자 오류로 잡힘: %s' % bad)
    print('measure check ok')

    # ---- 옥타브 보정: 한 옥타브 아래로 읽힌 줄을 되올린다 ----
    oc = pg.evaluate('''(()=>{
      const low={key:'A',time:'4/4',measures:[{n:[{p:'A3',d:4},{p:'C#4',d:4},{p:'E4',d:2}]}]};
      const ok ={key:'A',time:'4/4',measures:[{n:[{p:'A4',d:4},{p:'C#5',d:4},{p:'E5',d:2}]}]};
      const r1=CONTI.mergeScoreParts([low,low]);            // 둘 다 낮으면 통째로 올린다
      const r2=CONTI.mergeScoreParts([ok,low]);             // 한 줄만 낮으면 그 줄만 맞춘다
      const r3=CONTI.mergeScoreParts([ok,ok]);              // 정상은 건드리지 않는다
      return [r1.measures[0].n[0].p, r2.measures[1].n[0].p, r3.measures[0].n[0].p];
    })()''')
    if oc[0] != 'A4': fail('전체 옥타브 보정 실패: %s' % oc[0])
    if oc[1] != 'A4': fail('줄별 옥타브 보정 실패: %s' % oc[1])
    if oc[2] != 'A4': fail('정상 악보를 건드림: %s' % oc[2])
    print('octave fix ok')

    pg.screenshot(path=os.path.join(os.path.dirname(os.path.abspath(__file__)),'t_score.png'), full_page=True)
    if errs: fail('페이지 오류:\n' + '\n'.join(errs[:5]))
    print('PASS test_score')
    b.close()

run()
