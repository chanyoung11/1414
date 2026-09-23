# 감사 fe-02 회귀: 재구성 악보(붙임줄 · 코드 표기 · 조옮김 이름) · 합주 녹음 플레이어 · 편성 표
import os, sys, time
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
tag = str(int(time.time()))[-6:]
H = {'x-conti': '1'}
def fail(m): print('FAIL:', m); sys.exit(1)

def signup(b, name, user, link=None, viewport=None):
  # 서비스 워커는 막는다: 개발 서버에서는 녹음 파일이 같은 도메인이라 워커가 캐시해 버려 page.route 가 못 본다 (운영 R2 는 다른 도메인)
  c = b.new_context(viewport=viewport or {'width': 1400, 'height': 1000}, service_workers='block'); pg = c.new_page()
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

# ---------------------------------------------------------------- 합주 녹음
def wav_file(sec=10):
  import wave, tempfile, struct, math
  f = tempfile.NamedTemporaryFile(suffix='.wav', delete=False); f.close()
  w = wave.open(f.name, 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
  w.writeframes(b''.join(struct.pack('<h', int(3000 * math.sin(i / 8000 * 2 * math.pi * 440))) for i in range(8000 * sec))); w.close()
  return f.name

# 로컬 파일 서버는 Range 를 모른다(R2 는 안다) → 자리 옮기기가 안 되므로 녹음 파일은 Range 로 대신 내준다
def serve_ranges(pg, path):
  data = open(path, 'rb').read()
  def h(route):
    rg = route.request.headers.get('range', '')
    if not rg.startswith('bytes='): return route.fulfill(status=200, body=data, headers={'content-type': 'audio/wav', 'accept-ranges': 'bytes'})
    a, _, z = rg[6:].partition('-'); a = int(a or 0); z = int(z) if z else len(data) - 1
    route.fulfill(status=206, body=data[a:z + 1], headers={'content-type': 'audio/wav', 'accept-ranges': 'bytes', 'content-range': 'bytes %d-%d/%d' % (a, z, len(data))})
  pg.route('**/localblob/**', h)

SPY = """()=>{if(window.__spy)return;window.__spy=1;window.__streams=[];const g=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
  navigator.mediaDevices.getUserMedia=async c=>{const s=await g(c);window.__streams.push(s);return s}}"""
LIVE = "window.__streams.some(s=>s.getTracks().some(t=>t.readyState==='live'))"

def reh_checks(b):
  cL, pl = signup(b, '하은', 'ra' + tag)
  errs = []; pl.on('pageerror', lambda e: errs.append('L:' + str(e)))
  pl.wait_for_selector('#gtTeam', timeout=8000); pl.fill('#gtTeam', '감사녹음'); pl.click('[data-act="team-create"]'); pl.wait_for_selector('.shell[data-page]', timeout=8000)
  team = pl.evaluate('CONTI.S.team.id'); link = pl.evaluate("location.origin+location.pathname+'#/join/'+CONTI.S.team.invite")
  cM, pm = signup(b, '민수', 'rb' + tag, link)
  pm.on('pageerror', lambda e: errs.append('M:' + str(e)))
  pm.wait_for_selector('#jnName', timeout=8000); pm.click('[data-act="team-join"]'); pm.wait_for_selector('.shell[data-page]', timeout=8000)
  pl.click('[data-act="new-svc"]'); pl.wait_for_selector('[data-f="svc.name"]'); pl.fill('[data-f="svc.name"]', '녹음 예배')
  pl.click('[data-act="add-item"]'); pl.wait_for_selector('[data-f="item.title"]'); pl.fill('[data-f="item.title"]', '주 사랑합니다'); pl.wait_for_timeout(400)
  svc_id = pl.evaluate('CONTI.S.services[0].id')
  pl.click('[data-act="publish"]'); pl.wait_for_selector('#pubOnly'); pl.click('#pubOnly'); pl.wait_for_timeout(4000)
  wav = wav_file(10)

  pl.goto(URL + '#/view/' + svc_id); pl.wait_for_selector('[data-act="reh-add"]', timeout=15000)
  pl.click('[data-act="reh-add"]'); pl.wait_for_selector('#rhFile', state='attached', timeout=5000)
  pl.set_input_files('#rhFile', wav); pl.wait_for_timeout(800); pl.fill('#rhLabel', '감사 합주'); pl.click('#rhOk')
  pl.wait_for_selector('.rehrow', timeout=30000); pl.wait_for_timeout(500)

  # ---- F64: 녹음 중에 Esc · 바깥 누르기로 닫아도 마이크가 꺼진다. 녹음은 남아 다시 열면 올릴 수 있다 ----
  pl.evaluate(SPY)
  for how in ('esc', 'outside'):
    pl.click('[data-act="reh-add"]'); pl.wait_for_selector('#rhRec', timeout=5000)
    pl.click('#rhRec'); pl.wait_for_function(LIVE, timeout=8000); pl.wait_for_timeout(1500)
    if how == 'esc': pl.keyboard.press('Escape')
    else: pl.mouse.click(5, 5)
    pl.wait_for_timeout(800)
    if pl.locator('#rhRec').count(): fail('F64 창이 안 닫힘 (%s)' % how)
    if pl.evaluate(LIVE): fail('F64 창을 닫았는데(%s) 마이크가 계속 녹음 중' % how)
    pl.click('[data-act="reh-add"]'); pl.wait_for_selector('#rhRec', timeout=5000); pl.wait_for_timeout(300)
    if '올리지 않은 녹음' not in pl.inner_text('#rhPick') or pl.is_disabled('#rhOk'): fail('F64 닫힌 녹음이 남지 않음 (%s): %s' % (how, pl.inner_text('#rhPick')))
    pl.click('[data-close="1"]'); pl.wait_for_timeout(300)
  print('recorder close ok')

  # ---- F128: 메모를 적고 돌아와도 보던 자리 ----
  serve_ranges(pl, wav)
  SEEKABLE = "document.querySelector('#rhAudio')&&document.querySelector('#rhAudio').seekable.length>0"
  pl.click('.rehrow'); pl.wait_for_function(SEEKABLE, timeout=10000)
  pl.evaluate("document.querySelector('#rhAudio').currentTime=4.2"); pl.wait_for_timeout(300)
  if abs(pl.evaluate("document.querySelector('#rhAudio').currentTime") - 4.2) > 0.1: fail('테스트 준비: 4.2초로 옮기지 못함')
  pl.click('#rhNote'); pl.wait_for_selector('#rnText', timeout=5000); pl.fill('#rnText', '여기 템포'); pl.click('#rnOk')
  pl.wait_for_function("document.querySelector('#rhAudio')&&document.querySelector('#rhAudio').readyState>=1", timeout=10000); pl.wait_for_timeout(400)
  t = pl.evaluate("document.querySelector('#rhAudio').currentTime")
  if abs(t - 4.2) > 0.6: fail('F128 메모 뒤 플레이어가 %.1f초 (4.2초여야)' % t)
  if '0:04' not in pl.inner_text('#rhT'): fail('F128 시간 표시가 보던 자리가 아님: %s' % pl.inner_text('#rhT'))
  pl.keyboard.press('Escape'); pl.wait_for_timeout(300)
  print('note keeps position ok: %.1f' % t)

  # ---- F65: 재생 주소가 1시간 지나면 새로 받는다 · 주소가 끊겨도 한 번 새로 받아 튼다 ----
  seen = []
  pl.on('request', lambda r: seen.append(r.url) if '/api/rehearsals?' in r.url else None)
  pl.evaluate("window.__d0=Date.now;Date.now=()=>window.__d0()+51*60e3")
  pl.click('.rehrow'); pl.wait_for_selector('#rhAudio', state='attached', timeout=10000); pl.wait_for_timeout(500)
  pl.evaluate("Date.now=window.__d0")
  if not seen: fail('F65 50분이 지났는데 재생 주소를 새로 받지 않음')
  pl.keyboard.press('Escape'); pl.wait_for_timeout(300)
  src = pl.evaluate("fetch('/api/rehearsals?team=%s&service=%s',{headers:{'x-conti':'1'}}).then(r=>r.json()).then(j=>Object.values(j.urls)[0])" % (team, svc_id))
  hits = []
  def once403(route):
    hits.append(1)
    if len(hits) == 1: route.fulfill(status=403, body='expired')
    else: route.fallback()
  pl.route(src.split('?')[0] + '*', once403)
  seen.clear(); pl.click('.rehrow')
  pl.wait_for_function("document.querySelector('#rhAudio')&&document.querySelector('#rhAudio').readyState>=1", timeout=10000)
  if len(hits) < 2 or not seen: fail('F65 끊긴 주소를 다시 받지 않음: hits=%d refetch=%d' % (len(hits), len(seen)))
  pl.unroute(src.split('?')[0] + '*'); pl.keyboard.press('Escape'); pl.wait_for_timeout(300)
  print('expired url refetch ok')

  # ---- G27: 인도자가 권한을 좁히면, 멤버가 올리기 창을 열 때 바로 알고 · 올리다 막히면 기기에 저장 ----
  pm.goto(URL + '#/view/' + svc_id); pm.wait_for_selector('[data-act="reh-add"]', timeout=15000)
  cL.request.patch(URL + 'api/teams/%s/settings' % team, headers=H, data={'rehearsalUploadRole': 'leader'})
  pm.click('[data-act="reh-add"]'); pm.wait_for_timeout(2000)
  if pm.locator('#rhRec').count(): fail('G27 권한이 없는데 녹음 창이 그대로 열려 있음')
  if pm.locator('[data-act="reh-add"]').count(): fail('G27 권한이 없는데 녹음 올리기 단추가 남음')
  cL.request.patch(URL + 'api/teams/%s/settings' % team, headers=H, data={'rehearsalUploadRole': 'member'})
  pm.reload(); pm.wait_for_selector('[data-act="reh-add"]', timeout=15000)
  pm.click('[data-act="reh-add"]'); pm.wait_for_selector('#rhFile', state='attached', timeout=5000); pm.wait_for_timeout(1200)
  pm.set_input_files('#rhFile', wav); pm.wait_for_timeout(800)
  cL.request.patch(URL + 'api/teams/%s/settings' % team, headers=H, data={'rehearsalUploadRole': 'leader'})
  pm.click('#rhOk'); pm.wait_for_selector('#rhSave', timeout=8000)
  if not pm.is_disabled('#rhOk'): fail('G27 권한이 없는데 올리기를 다시 누를 수 있음')
  with pm.expect_download(timeout=8000) as dl: pm.click('#rhSave')
  if not dl.value.suggested_filename.endswith('.wav'): fail('G27 저장 파일 이름: %s' % dl.value.suggested_filename)
  print('upload permission refresh ok:', dl.value.suggested_filename)
  os.remove(wav)
  if errs: fail('녹음 페이지 오류: %s' % errs[:3])
  cL.close(); cM.close()

def run(only=os.environ.get('ONLY', '')):
  with sync_playwright() as p:
    b = p.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'])
    if only in ('', 'score'): score_checks(b)
    if only in ('', 'reh'): reh_checks(b)
    b.close()
  print('OK test_audit_fe_02')

run()
