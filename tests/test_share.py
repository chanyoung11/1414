# 곡 공유 코드 (명세 A.7): 파일은 안 나가고, 다른 팀이 코드로 받으면 곡·편곡·고정 메모·유튜브가 생긴다.
# 짧은 코드는 회수·기한·횟수가 있고, 자립형은 서버 없이 글자 안에 다 들어 있다.
import os, sys, time
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
tag = str(int(time.time()))[-6:]
H = {'x-conti': '1'}
def fail(m): print('FAIL:', m); sys.exit(1)

def team_of(b, user, tname):
    c = b.new_context(viewport={'width': 1300, 'height': 950}); pg = c.new_page()
    pg.on('dialog', lambda d: d.accept())
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=8000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
    pg.fill('#lgName', '하은'); pg.fill('#lgUser', user); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam', timeout=8000); pg.fill('#gtTeam', tname); pg.click('[data-act="team-create"]')
    pg.wait_for_selector('.shell[data-page]', timeout=8000)
    return c, pg, pg.evaluate('CONTI.S.team.id')

def run():
  with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    cA, A, tA = team_of(b, 'sa' + tag, '보내는팀')
    cB, B, tB = team_of(b, 'sb' + tag, '받는팀')
    A.on('pageerror', lambda e: errs.append('A:' + str(e))); B.on('pageerror', lambda e: errs.append('B:' + str(e)))

    # 보내는 팀: 곡 + 유튜브 + 고정 메모 + (안 나가야 할) 악보 조각
    r = cA.request.post(URL + 'api/songs', headers=H, data={
      'teamId': tA, 'title': '오 신령한 주', 'artist': '마커스', 'key': 'G', 'tempo': '보통',
      'tags': ['경배'], 'form': 'Intro – A – B', 'songNote': '밝게',
      'media': [{'id': 'm1', 'type': 'youtube', 'url': 'https://youtu.be/abc12345', 'name': '원곡', 'start': 12, 'end': 200, 'sessions': []}],
      'pieces': [{'id': 'p1', 'blob': 'zz', 'w': 800, 'h': 1000, 'markers': [], 'hls': [], 'chords': []}]}).json()
    sid = r['song']['id']; aid = r['song']['arrangements'][0]['id']
    cA.request.post(URL + 'api/arrangements/%s/notes' % aid, headers=H,
                    data={'teamId': tA, 'markerLabel': 'B', 'layer': 'all', 'text': 'Key up 직전 한 박 쉬고'})
    A.evaluate("CONTI.S.songsAt='';CONTI.pullSongs(true)"); A.wait_for_timeout(1500)

    # ---- 미리보기: 파일은 안 나간다 ----
    pre = cA.request.get(URL + 'api/songs/%s/share-preview?team=%s' % (sid, tA)).json()
    if pre['left']['pieces'] != 1: fail('악보 장수를 못 셈: %s' % pre['left'])
    if 'pieces' in pre['song']['arr']: fail('미리보기에 악보가 들어감')
    if len(pre['song']['arr']['notes']) != 1: fail('고정 메모가 안 담김: %s' % pre['song']['arr'])
    print('preview ok: 담김 %d메모/%d링크 · 빠짐 악보%d장' % (len(pre['song']['arr']['notes']), len(pre['song']['arr']['media']), pre['left']['pieces']))

    # ---- 짧은 코드 만들기 (UI) ----
    A.goto(URL + '#/library/' + sid); A.wait_for_selector('.acard', timeout=10000); A.wait_for_timeout(500)
    A.click('[data-act="song-more"]'); A.wait_for_selector('#smShare', timeout=5000)
    A.click('#smShare'); A.wait_for_selector('#shOk', timeout=6000)
    txt = A.locator('#modal').inner_text()
    if '악보 사진 1장' not in txt: fail('"담기지 않는 것"에 악보가 안 보임')
    A.click('[data-sd="7"]'); A.wait_for_timeout(200); A.click('#shOk'); A.wait_for_timeout(2500)
    code = A.locator('#modal .linkbox').inner_text().strip()
    if not code.startswith('1414-') or len(code) != 11: fail('짧은 코드 모양이 이상함: %r' % code)
    print('short code ok:', code)
    A.click('[data-close="1"]')

    # ---- 받는 팀: 코드로 받기 ----
    B.goto(URL + '#/library'); B.wait_for_selector('.libpage', timeout=10000); B.wait_for_timeout(600)
    B.click('[data-act="lib-receive"]'); B.wait_for_selector('#shIn', timeout=5000)
    B.fill('#shIn', '[1414] 이 곡 좋아요 %s 받아보세요' % code); B.click('#shGo'); B.wait_for_selector('#shTake', timeout=8000)
    pv = B.locator('#modal').inner_text()
    if '오 신령한 주' not in pv or '보내는팀' not in pv: fail('미리보기 내용 이상:\n' + pv[:300])
    if '악보는 안 들어와요' not in pv: fail('파일이 안 온다는 안내가 없음')
    B.click('#shTake'); B.wait_for_timeout(3000)
    got = cB.request.get(URL + 'api/songs?team=' + tB).json()['songs']
    if len(got) != 1 or got[0]['title'] != '오 신령한 주': fail('곡이 안 담김: %s' % got)
    ga = got[0]['arrangements'][0]
    if ga['form'] != 'Intro – A – B': fail('송폼이 안 옴: %r' % ga['form'])
    if len(ga['media']) != 1 or ga['media'][0]['start'] != 12: fail('유튜브 구간이 안 옴: %s' % ga['media'])
    if ga['pieces']: fail('악보가 따라옴 — 파일은 안 나가야 한다')
    if len(ga.get('notes') or []) != 1: fail('고정 메모가 안 옴: %s' % ga.get('notes'))
    print('take ok:', got[0]['title'], '· 링크', len(ga['media']), '· 고정메모', len(ga['notes']))

    # ---- 한 팀만 쓰는 코드는 두 번 못 쓴다 ----
    r2 = cA.request.post(URL + 'api/share', headers=H, data={'teamId': tA, 'songId': sid, 'days': 7, 'maxUses': 1}).json()
    once = r2['code']
    if cB.request.post(URL + 'api/share/%s/take' % once, headers=H, data={'teamId': tB}).status != 200: fail('1회용 코드 첫 사용 실패')
    st = cB.request.post(URL + 'api/share/%s/take' % once, headers=H, data={'teamId': tB}).status
    if st == 200: fail('1회용 코드가 두 번 쓰임')
    print('one-shot share ok')

    # ---- 회수 ----
    r3 = cA.request.post(URL + 'api/share', headers=H, data={'teamId': tA, 'songId': sid}).json()['code']
    cA.request.delete(URL + 'api/share/%s?team=%s' % (r3, tA), headers=H)
    if cB.request.get(URL + 'api/share/' + r3).status == 200: fail('회수한 코드가 열림')
    print('revoke ok')

    # ---- 자립형 코드: 서버 없이 ----
    A.goto(URL + '#/library/' + sid); A.wait_for_selector('.acard', timeout=10000); A.wait_for_timeout(500)
    A.click('[data-act="song-more"]'); A.wait_for_selector('#smShare', timeout=5000)
    A.click('#smShare'); A.wait_for_selector('#shOk', timeout=6000)
    A.click('[data-sf="1"]'); A.wait_for_timeout(300); A.click('#shOk'); A.wait_for_timeout(2000)
    self_code = A.locator('#modal .linkbox').inner_text().strip()
    if not self_code.startswith('1414:') or len(self_code) < 60: fail('자립형 코드 모양이 이상함: %r' % self_code[:40])
    A.click('[data-close="1"]')
    B.goto(URL + '#/library'); B.wait_for_selector('.libpage', timeout=10000); B.wait_for_timeout(600)
    B.click('[data-act="lib-receive"]'); B.wait_for_selector('#shIn', timeout=5000)
    B.fill('#shIn', self_code); B.click('#shGo'); B.wait_for_selector('#shTake', timeout=8000)
    B.click('#shTake'); B.wait_for_timeout(3000)
    n = len(cB.request.get(URL + 'api/songs?team=' + tB).json()['songs'])
    if n != 3: fail('자립형으로 담긴 뒤 곡 수가 3이 아님: %d' % n)
    print('self-contained code ok (%d자)' % len(self_code))

    if errs: fail('페이지 오류:\n' + '\n'.join(errs[:6]))
    print('PASS test_share')
    b.close()

run()
