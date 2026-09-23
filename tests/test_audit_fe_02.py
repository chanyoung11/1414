# 감사 fe-02 회귀: 재구성 악보(붙임줄 · 코드 표기 · 조옮김 이름) · 합주 녹음 플레이어 · 편성 표
import os, sys, time
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
tag = str(int(time.time()))[-6:]
H = {'x-conti': '1'}
def fail(m): print('FAIL:', m); sys.exit(1)

def signup(b, name, user, link=None, viewport=None):
  c = b.new_context(viewport=viewport or {'width': 1400, 'height': 1000}); pg = c.new_page()
  pg.on('dialog', lambda d: d.accept())
  pg.goto(link or URL); pg.wait_for_selector('#lgUser', timeout=8000)
  pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
  pg.fill('#lgName', name); pg.fill('#lgUser', user); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')
  return c, pg

def svg_texts(pg):
  return pg.evaluate("[...document.querySelectorAll('#osmd svg text')].map(t=>t.textContent)")

# ---------------------------------------------------------------- 악보
CHORDS = ['G2', 'Cadd9', 'E7sus4', 'Asus', 'Am7(b5)', 'E7(b9)', 'E7#9', 'Fmaj9', 'Am(maj7)', 'Cdim7', 'C-7', 'Cm11', 'D6/9', 'N.C.', 'C6', 'G(후렴)']
SCORE = {
  'title': '감사 악보', 'key': 'G', 'time': '4/4',
  'measures': [
    # G06: 2분음표 A4 를 다음 마디 온음표 A4 에 잇는다 (마디를 넘는 붙임줄) + 같은 마디 안 붙임줄
    {'c': [{'b': 0, 't': 'G'}], 'n': [{'p': 'B4', 'd': 2}, {'p': 'A4', 'd': 2, 'tie': True}]},
    {'c': [], 'n': [{'p': 'A4', 'd': 1}]},
    {'c': [], 'n': [{'p': 'D5', 'd': 2, 'tie': True}, {'p': 'D5', 'd': 2}]},
  ] + [{'c': [{'b': 0, 't': t}], 'n': [{'p': 'G4', 'd': 1}]} for t in CHORDS],
}

def score_checks(b):
  c, pg = signup(b, '하은', 'fa' + tag)
  errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
  pg.wait_for_selector('#gtTeam', timeout=8000); pg.fill('#gtTeam', '감사악보'); pg.click('[data-act="team-create"]'); pg.wait_for_selector('.shell[data-page]', timeout=8000)
  pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]'); pg.fill('[data-f="svc.name"]', '악보 예배')
  pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]'); pg.fill('[data-f="item.title"]', '감사 악보'); pg.wait_for_timeout(400)
  svc = pg.evaluate('CONTI.S.services[0].id'); item = pg.evaluate('CONTI.S.services[0].items[0].id')
  pg.evaluate("(sc)=>{const it=CONTI.S.services[0].items[0];it.score=sc;CONTI.save()}", SCORE)
  pg.goto(URL + '#/score/%s/%s' % (svc, item)); pg.wait_for_selector('#osmd svg', timeout=25000); pg.wait_for_timeout(1500)

  # ---- G06: 붙임줄이 실제로 그려진다 (시작만 적으면 OSMD 가 버렸다) ----
  ties = pg.evaluate("document.querySelectorAll('#osmd svg .vf-stavetie').length")
  if ties < 2: fail('G06 붙임줄이 안 그려짐: %d개' % ties)
  xml = pg.evaluate("CONTI.scoreToMusicXML(CONTI.S.services[0].items[0].score)")
  if xml.count('<tied type="stop"/>') != 2 or xml.count('<tied type="start"/>') != 2: fail('G06 MusicXML 에 붙임줄 짝이 없음')
  # 높이가 다른 음으로는 잇지 않는다 (끝이 없는 시작을 내보내지 않게)
  x2 = pg.evaluate("CONTI.scoreToMusicXML({key:'C',time:'4/4',measures:[{n:[{p:'B4',d:2,tie:true},{p:'C5',d:2}]}]})")
  if '<tie ' in x2: fail('G06 다른 음 사이에 붙임줄 시작이 남음')
  # 서버 쪽 MusicXML(/score/musicxml)도 같은 짝
  sx = pg.evaluate("""async(sc)=>{const r=await fetch('/api/score/musicxml',{method:'POST',headers:{'x-conti':'1','content-type':'application/json'},body:JSON.stringify({teamId:CONTI.S.team.id,score:sc})});return (await r.json()).xml}""", SCORE)
  if sx.count('<tied type="stop"/>') != 2: fail('G06 서버 MusicXML 에 붙임줄 끝이 없음')
  print('ties ok:', ties)

  # ---- G05: 코드가 적힌 그대로 보인다 (C-7 → C, Am7(b5) → Am7, D6/9 · N.C. 사라짐 이던 것) ----
  t = svg_texts(pg)
  for want in CHORDS:
    if want not in t: fail('G05 코드 %r 가 악보에 없음: %s' % (want, [x for x in t if not x.isdigit()]))
  # 전조하면 코드도 같이 옮겨지고, 못 읽는 코드('G(후렴)')는 근음만 옮겨진 척하지 않는다
  pg.click('[data-act="score-tr"][data-d="1"]'); pg.wait_for_timeout(300)
  pg.click('[data-act="score-tr"][data-d="1"]'); pg.wait_for_selector('#osmd svg', timeout=20000); pg.wait_for_timeout(1500)
  t2 = svg_texts(pg)
  for want in ['E6/9', 'N.C.', 'Bm7(b5)', 'F#7sus4', 'D-7', 'A2', 'Dadd9', 'G(후렴)']:
    if want not in t2: fail('G05 +2 에서 %r 없음: %s' % (want, [x for x in t2 if not x.isdigit()]))
  pg.click('[data-act="score-tr"][data-d="0"]'); pg.wait_for_timeout(1200)
  print('chords ok')

  # ---- G13 · G25 · G26: 조옮김 이름 ----
  r = pg.evaluate("""()=>{const T=CONTI.transposeScore,X=CONTI.scoreToMusicXML;
    const one=(key,semis,ns,cs)=>{const sc=T({key,time:'4/4',measures:[{c:(cs||[]).map(t=>({b:0,t})),n:(ns||[]).map(p=>({p,d:4}))}]},semis);
      return {key:sc.key,fifths:+(X(sc).match(/<fifths>(-?\\d+)/)||[])[1],n:sc.measures[0].n.map(n=>n.p),c:sc.measures[0].c.map(c=>c.t)}};
    const mod={key:'G',time:'4/4',measures:[{c:[{b:0,t:'G'}],n:[{p:'G4',d:1}]},{key:'Ab',c:[{b:0,t:'Ab'},{b:2,t:'Db/F'}],n:[{p:'Ab4',d:4},{p:'C5',d:4},{p:'Eb5',d:2}]}]};
    const up=T(mod,2),dn=T(mod,-2);
    const bad={key:'C',time:'4/4',measures:[{c:[],n:[{p:'Bb',d:4},{p:'c5',d:4},{p:'H4',d:4},{p:'Bb4',d:4}]}]};
    return {am4:one('Am',4,['A4','C5','E5'],['Am','E7/G#']),bm2:one('Bm',2),em3:one('Em',-3),amm1:one('Am',-1,['A4','C5','E5']),
      f1:one('F',1,['Bb4','F4']),e2:one('E',2,['D#4']),em2:one('Em',-2,['D#5'],['B7/D#']),
      dbm:+X({key:'Dbm',measures:[{n:[]}]}).match(/<fifths>(-?\\d+)/)[1],
      up:[up.measures[1].key,up.measures[1].n.map(n=>n.p),up.measures[1].c.map(c=>c.t)],
      dn:[dn.key,dn.measures[1].key,dn.measures[1].n.map(n=>n.p),dn.measures[1].c.map(c=>c.t)],
      bad:[2,-1].map(s=>T(bad,s).measures[0].n.map(n=>n.p)),badOct:[2,-1].map(s=>(X(T(bad,s)).match(/<octave>(-?\\d+)/g)||[]).join())}}""")
  if (r['am4']['key'], r['am4']['fifths']) != ('C#m', 4): fail('G13 Am+4 가 C#m(#4) 가 아님: %s' % r['am4'])
  if r['am4']['n'] != ['C#5', 'E5', 'G#5'] or r['am4']['c'] != ['C#m', 'G#7/B#']: fail('G13 Am+4 음이름: %s' % r['am4'])
  if r['bm2']['key'] != 'C#m' or r['em3']['key'] != 'C#m': fail('G13 Bm+2 / Em-3: %s %s' % (r['bm2'], r['em3']))
  if (r['amm1']['key'], r['amm1']['fifths'], r['amm1']['n']) != ('G#m', 5, ['G#4', 'B4', 'D#5']): fail('G13 Am-1: %s' % r['amm1'])
  if (r['f1']['key'], r['f1']['n']) != ('Gb', ['Cb5', 'Gb4']): fail('G13 Gb 장조의 시는 Cb: %s' % r['f1'])
  if (r['e2']['key'], r['e2']['n']) != ('F#', ['E#4']): fail('G13 F# 장조의 파는 E#: %s' % r['e2'])
  if (r['em2']['key'], r['em2']['n'], r['em2']['c']) != ('Dm', ['C#5'], ['A7/C#']): fail('G13 Dm 이끎음은 C#: %s' % r['em2'])
  if r['dbm'] != 4: fail('G13 Dbm 조표가 %s' % r['dbm'])
  if r['up'] != ['Bb', ['Bb4', 'D5', 'F5'], ['Bb', 'Eb/G']]: fail('G25 G→Ab 곡 +2 의 바뀐 조 부분: %s' % r['up'])
  if r['dn'] != ['F', 'Gb', ['Gb4', 'Bb4', 'Db5'], ['Gb', 'Cb/Eb']]: fail('G25 G→Ab 곡 -2: %s' % r['dn'])
  if r['bad'] != [['Bb', 'c5', 'H4', 'C5'], ['Bb', 'c5', 'H4', 'A4']] or '-' in ''.join(r['badOct']): fail('G26 못 읽는 음이 옮기면 음표가 됨: %s %s' % (r['bad'], r['badOct']))
  print('transpose names ok')

  # ---- G26: 마디 고치기에서 음이름 받기 ----
  pg.click('[data-act="score-edit"]'); pg.wait_for_timeout(1200)
  box = pg.evaluate("()=>{const o=CONTI.SC.osmd;const m=o.GraphicSheet.MeasureList[0][0];const bb=m.PositionAndShape;return {x:bb.AbsolutePosition.x*CONTI.SC.k,y:bb.AbsolutePosition.y*CONTI.SC.k,w:bb.Size.width*CONTI.SC.k,h:bb.Size.height*CONTI.SC.k}}")
  host = pg.locator('#osmd svg').bounding_box()
  pg.mouse.click(host['x'] + box['x'] + box['w']/2, host['y'] + box['y'] + box['h']/2)
  pg.wait_for_selector('[data-np="0"]', timeout=6000)
  pg.fill('[data-np="0"]', 'bb4'); pg.wait_for_timeout(100)
  if pg.evaluate("CONTI.S.services[0].items[0].score.measures[0].n[0].p") != 'Bb4': fail('G26 소문자 음이름을 고쳐 받지 않음')
  if 'bad' in (pg.get_attribute('[data-np="0"]', 'class') or ''): fail('G26 맞는 음이름이 빨갛게 표시됨')
  pg.fill('[data-np="0"]', 'Bb'); pg.wait_for_timeout(100)
  if 'bad' not in (pg.get_attribute('[data-np="0"]', 'class') or ''): fail('G26 못 읽는 음이름이 표시되지 않음')
  pg.fill('[data-np="0"]', 'B4'); pg.click('[data-close="1"]'); pg.wait_for_timeout(800)
  print('pitch input ok')
  if errs: fail('악보 페이지 오류: %s' % errs[:3])
  c.close()

def run():
  with sync_playwright() as p:
    b = p.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'])
    score_checks(b)
    b.close()
  print('OK test_audit_fe_02')

run()
