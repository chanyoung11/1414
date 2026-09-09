# 라이브러리 A부: 곡·편곡 모델 · 검색(초성/가사/아티스트) · 곡 상세 4탭 · 예배에 넣기 · 사용 이력 · 합치기
import os, sys, time
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
tag = str(int(time.time()))[-6:]
def fail(m): print('FAIL:', m); sys.exit(1)

def run():
  with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    c = b.new_context(viewport={'width': 1300, 'height': 1000}); pg = c.new_page()
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=8000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
    pg.fill('#lgName', '하은'); pg.fill('#lgUser', 'lb' + tag); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam', timeout=8000); pg.fill('#gtTeam', '라이브러리팀'); pg.click('[data-act="team-create"]')
    pg.wait_for_selector('.hd [data-act="team"]', timeout=8000)
    team = pg.evaluate('CONTI.S.team.id')

    # ---- 곡 세 개 만들기 (서버 API 로 바로) ----
    songs = [
      {'title': '오 신령한 주', 'artist': '마커스', 'key': 'G', 'tempo': '보통', 'tags': ['경배'], 'firstLine': '성령과 피로써', 'form': 'Intro – A – B'},
      {'title': '주 은혜임을', 'artist': '어노인팅', 'key': 'A', 'tempo': '느림', 'tags': ['적용']},
      {'title': '나 어느 곳에 있든지', 'key': 'D', 'tempo': '빠름', 'tags': ['찬양']},
    ]
    ids = []
    for sdef in songs:
      r = c.request.post(URL + 'api/songs', headers={'x-conti': '1'}, data={**sdef, 'teamId': team}).json()
      ids.append(r['song']['id'])
    pg.goto(URL + '#/library'); pg.wait_for_selector('.libpage', timeout=10000); pg.wait_for_timeout(800)
    if pg.locator('.songrow').count() != 3: fail('곡 3개가 안 보임: %d' % pg.locator('.songrow').count())
    print('library home ok: 3곡')

    # ---- 검색: 초성 · 가사 · 아티스트 ----
    def search(qq):
      pg.fill('#libQ', qq); pg.wait_for_timeout(400)
      return [x.strip().split('\n')[0] for x in pg.locator('.songrow').all_inner_texts()]
    r1 = search('ㅇㅅㄹ')
    if not r1 or '오 신령한 주' not in r1[0]: fail('초성 검색 실패: %s' % r1)
    r2 = search('성령')
    if not r2 or '오 신령한 주' not in r2[0]: fail('가사 검색 실패: %s' % r2)
    if '가사' not in pg.locator('.songrow').first.inner_text(): fail('어디서 걸렸는지 안 보임')
    r3 = search('어노인팅')
    if not r3 or '주 은혜임을' not in r3[0]: fail('아티스트 검색 실패: %s' % r3)
    if '아티스트' not in pg.locator('.songrow').first.inner_text(): fail('아티스트 표시 없음')
    print('search ok: 초성·가사·아티스트')
    pg.fill('#libQ', ''); pg.wait_for_timeout(400)

    # ---- 필터: 키 · 템포 ----
    pg.click('[data-lf="key"][data-v="A"]'); pg.wait_for_timeout(400)
    if pg.locator('.songrow').count() != 1: fail('키 필터 실패: %d' % pg.locator('.songrow').count())
    pg.click('[data-lf="key"][data-v="A"]'); pg.wait_for_timeout(300)
    pg.click('[data-lf="tempo"][data-v="빠름"]'); pg.wait_for_timeout(400)
    if pg.locator('.songrow').count() != 1: fail('템포 필터 실패')
    pg.click('[data-lf="tempo"][data-v="빠름"]'); pg.wait_for_timeout(300)
    print('filters ok')

    # ---- 곡 상세: 편곡 추가(다른 키로) ----
    pg.goto(URL + '#/library/' + ids[0]); pg.wait_for_selector('.acard', timeout=10000)
    pg.evaluate("window.prompt=()=>'A'")
    pg.click('[data-act="song-clone"]'); pg.wait_for_timeout(2000)
    if pg.locator('.acard').count() != 2: fail('편곡이 2개가 안 됨: %d' % pg.locator('.acard').count())
    arrs = pg.evaluate("CONTI.S.songs.find(s=>s.id==='%s').arrangements.map(a=>[a.name,a.key,a.isDefault])" % ids[0])
    print('arrangements ok:', arrs)

    # ---- 예배에 넣기 ----
    pg.click('[data-arradd]'); pg.wait_for_selector('#atsGo', timeout=6000)
    pg.click('[data-ats="new"]'); pg.wait_for_selector('#atsName', timeout=5000)
    pg.fill('#atsName', '라이브 예배'); pg.click('#atsGo')
    pg.wait_for_selector('[data-f="item.title"]', timeout=10000); pg.wait_for_timeout(600)
    it = pg.evaluate("(()=>{const s=CONTI.S.services[0];return {n:s.items.length,title:s.items[0].title,songId:s.items[0].songId,arrId:!!s.items[0].arrId,key:s.items[0].key,form:s.items[0].form}})()")
    if it['n'] != 1 or it['songId'] != ids[0]: fail('예배에 곡이 안 들어감: %s' % it)
    if not it['form']: fail('편곡의 송폼이 안 따라옴: %s' % it)
    print('add to service ok:', it)

    # ---- 발행 → 사용 이력 ----
    svc = pg.evaluate('CONTI.S.services[0].id')
    pg.click('[data-act="publish"]'); pg.wait_for_selector('#pubOnly', timeout=6000); pg.click('#pubOnly'); pg.wait_for_timeout(4000)
    pg.goto(URL + '#/library/' + ids[0]); pg.wait_for_selector('.acard', timeout=10000); pg.wait_for_timeout(800)
    pg.click('[data-tab="hist"]'); pg.wait_for_timeout(600)
    body = pg.locator('.libpage').inner_text()
    if '라이브 예배' not in body: fail('사용 이력에 예배가 없음:\n' + body[:400])
    if '1회' not in body: fail('부른 횟수가 안 맞음:\n' + body[:300])
    print('usage history ok')

    # ---- 고정 메모 ----
    arr0 = pg.evaluate("CONTI.S.songs.find(s=>s.id==='%s').arrangements[0].id" % ids[0])
    c.request.post(URL + 'api/arrangements/%s/notes' % arr0, headers={'x-conti': '1'},
                   data={'teamId': team, 'markerLabel': 'C', 'layer': 'all', 'text': 'Key up 직전 한 박 쉬고'})
    pg.evaluate("CONTI.LIB.detail=null"); pg.reload(); pg.wait_for_selector('.libpage', timeout=10000); pg.wait_for_timeout(1200)
    pg.click('[data-tab="notes"]'); pg.wait_for_timeout(500)
    if 'Key up' not in pg.locator('.libpage').inner_text(): fail('고정 메모가 안 보임')
    print('fixed note ok')

    # ---- 합치기 ----
    c.request.post(URL + 'api/songs', headers={'x-conti': '1'}, data={'teamId': team, 'title': '오 신령한 주', 'key': 'C'})
    pg.goto(URL + '#/library'); pg.wait_for_selector('.libpage', timeout=10000); pg.wait_for_timeout(1500)
    if not pg.locator('[data-act="lib-merge"]').count(): fail('정리 카드가 안 뜸')
    pg.click('[data-act="lib-merge"]'); pg.wait_for_selector('[data-domerge]', timeout=6000)
    pg.click('[data-domerge="0"]'); pg.wait_for_timeout(2500)
    n = pg.evaluate("CONTI.S.songs.filter(s=>!s.archived).length")
    if n != 3: fail('합친 뒤 곡 수가 3이 아님: %d' % n)
    print('merge ok')

    if errs: fail('페이지 오류:\n' + '\n'.join(errs[:6]))
    pg.goto(URL + '#/library'); pg.wait_for_timeout(1200)
    pg.screenshot(path=os.path.join(os.path.dirname(os.path.abspath(__file__)), 't_library.png'), full_page=True)
    print('PASS test_library2')
    b.close()

run()
