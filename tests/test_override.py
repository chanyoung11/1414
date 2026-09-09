# 참조와 덮어쓰기 (명세 A.1.2): 예배에서 고친 값은 라이브러리에 안 새고,
# 라이브러리에서 고친 값은 미발행 예배에 따라오며, "곡에 반영"·"되돌리기"가 된다
import os, sys, time
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
tag = str(int(time.time()))[-6:]
H = {'x-conti': '1'}
def fail(m): print('FAIL:', m); sys.exit(1)

def run():
  with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    c = b.new_context(viewport={'width': 1300, 'height': 950}); pg = c.new_page()
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=8000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
    pg.fill('#lgName', '하은'); pg.fill('#lgUser', 'ov' + tag); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam', timeout=8000); pg.fill('#gtTeam', '참조팀'); pg.click('[data-act="team-create"]')
    pg.wait_for_selector('.hd [data-act="team"]', timeout=8000)
    team = pg.evaluate('CONTI.S.team.id')

    r = c.request.post(URL + 'api/songs', headers=H, data={
      'teamId': team, 'title': '오 신령한 주', 'key': 'G', 'form': 'Intro – A – B', 'songNote': '밝게'}).json()
    sid = r['song']['id']; aid = r['song']['arrangements'][0]['id']
    pg.evaluate("CONTI.pullSongs(true)"); pg.wait_for_timeout(1500)

    # ---- 두 예배에 같은 편곡을 넣는다 ----
    for name in ['예배 하나', '예배 둘']:
      pg.goto(URL + '#/library/' + sid); pg.wait_for_selector('.acard', timeout=10000); pg.wait_for_timeout(400)
      pg.click('[data-arradd]'); pg.wait_for_selector('#atsGo', timeout=6000)
      pg.click('[data-ats="new"]'); pg.wait_for_selector('#atsName', timeout=5000)
      pg.fill('#atsName', name); pg.click('#atsGo'); pg.wait_for_selector('[data-f="item.title"]', timeout=10000); pg.wait_for_timeout(500)
    svcs = pg.evaluate("CONTI.S.services.map(s=>[s.id,s.name])")
    if len(svcs) != 2: fail('예배 2개가 안 생김: %s' % svcs)
    s1, s2 = svcs[1][0], svcs[0][0]
    print('two services ok')

    # ---- 예배 하나에서 키를 바꾼다 → 라이브러리·다른 예배는 그대로 ----
    pg.goto(URL + '#/edit/' + s1); pg.wait_for_selector('[data-f="item.key"]', timeout=10000); pg.wait_for_timeout(500)
    pg.fill('[data-f="item.key"]', 'A'); pg.wait_for_timeout(4500)
    if not pg.locator('.ovbar').count(): fail('"라이브러리 편곡과 다름" 줄이 안 뜸')
    if '키' not in pg.locator('.ovbar').inner_text(): fail('바뀐 항목이 안 보임: ' + pg.locator('.ovbar').inner_text())
    srv = c.request.get(URL + 'api/songs?team=' + team).json()['songs'][0]['arrangements'][0]
    if srv['key'] != 'G': fail('예배에서 바꾼 키가 라이브러리로 샘: %s' % srv['key'])
    k2 = pg.evaluate("CONTI.S.services.find(s=>s.id==='%s').items[0].key" % s2)
    if k2 != 'G': fail('다른 예배까지 바뀜: %s' % k2)
    print('override isolated ok')

    # ---- 라이브러리에서 송폼을 고치면 미발행 예배 둘 다 따라온다 (키는 예배 하나만 그대로 A) ----
    c.request.patch(URL + 'api/arrangements/' + aid, headers=H, data={'teamId': team, 'form': 'Intro – A – B – C'})
    pg.evaluate("CONTI.S.songsAt='';CONTI.pullSongs(true)"); pg.wait_for_timeout(2500)
    f1 = pg.evaluate("CONTI.S.services.find(s=>s.id==='%s').items[0].form" % s1)
    f2 = pg.evaluate("CONTI.S.services.find(s=>s.id==='%s').items[0].form" % s2)
    if f1 != 'Intro – A – B – C' or f2 != 'Intro – A – B – C': fail('라이브러리 수정이 안 따라옴: %r / %r' % (f1, f2))
    k1 = pg.evaluate("CONTI.S.services.find(s=>s.id==='%s').items[0].key" % s1)
    if k1 != 'A': fail('예배에서 고친 키가 덮여 버림: %s' % k1)
    print('library edit flows down ok')

    # ---- "곡에 반영" ----
    pg.goto(URL + '#/edit/' + s1); pg.wait_for_selector('.ovbar', timeout=10000); pg.wait_for_timeout(600)
    pg.click('[data-act="ov-apply"]'); pg.wait_for_timeout(2500)
    srv = c.request.get(URL + 'api/songs?team=' + team).json()['songs'][0]['arrangements'][0]
    if srv['key'] != 'A': fail('곡에 반영이 안 됨: %s' % srv['key'])
    if pg.locator('.ovbar').count(): fail('반영 뒤에도 "다름" 줄이 남음')
    pg.evaluate("CONTI.S.songsAt='';CONTI.pullSongs(true)"); pg.wait_for_timeout(2000)
    k2 = pg.evaluate("CONTI.S.services.find(s=>s.id==='%s').items[0].key" % s2)
    if k2 != 'A': fail('다른 미발행 예배에 반영이 안 옴: %s' % k2)
    print('apply-to-song ok')

    # ---- "되돌리기" ----
    pg.goto(URL + '#/edit/' + s2); pg.wait_for_selector('[data-f="item.songNote"]', timeout=10000); pg.wait_for_timeout(500)
    pg.fill('[data-f="item.songNote"]', '이 예배만 조용히'); pg.wait_for_timeout(4500)
    if not pg.locator('.ovbar').count(): fail('곡 메모 수정에 "다름" 줄이 안 뜸')
    pg.click('[data-act="ov-revert"]'); pg.wait_for_timeout(1500)
    note = pg.evaluate("CONTI.S.services.find(s=>s.id==='%s').items[0].songNote" % s2)
    if note != '밝게': fail('되돌리기가 안 됨: %r' % note)
    if pg.locator('.ovbar').count(): fail('되돌린 뒤에도 "다름" 줄이 남음')
    print('revert ok')

    # ---- 발행본은 합쳐진 값을 그대로 담고, 뒤에 편곡이 바뀌어도 그대로 ----
    pg.goto(URL + '#/edit/' + s1); pg.wait_for_selector('[data-act="publish"]', timeout=10000)
    pg.click('[data-act="publish"]'); pg.wait_for_selector('#pubOnly', timeout=6000); pg.click('#pubOnly'); pg.wait_for_timeout(4000)
    c.request.patch(URL + 'api/arrangements/' + aid, headers=H, data={'teamId': team, 'form': '바뀐 송폼'})
    pg.evaluate("CONTI.S.songsAt='';CONTI.pullSongs(true)"); pg.wait_for_timeout(2500)
    pub = pg.evaluate("CONTI.S.services.find(s=>s.id==='%s').published.items[0].form" % s1)
    if pub != 'Intro – A – B – C': fail('발행본이 나중 수정에 흔들림: %r' % pub)
    draft = pg.evaluate("CONTI.S.services.find(s=>s.id==='%s').items[0].form" % s1)
    if draft != '바뀐 송폼': fail('초안은 따라와야 함: %r' % draft)
    print('published snapshot frozen ok')

    # ---- 같은 제목의 곡이 두 번 만들어지지 않는다 (이행 전 콘티가 기기에 남아 있던 경우) ----
    n0 = pg.evaluate("CONTI.S.songs.filter(s=>!s.archived).length")
    pg.goto(URL + '#/edit/' + s2); pg.wait_for_selector('[data-f="item.title"]', timeout=10000); pg.wait_for_timeout(500)
    pg.evaluate("""(()=>{const sv=CONTI.S.services.find(x=>x.id===CONTI.route().a);
      const it=JSON.parse(JSON.stringify(sv.items[0]));it.id='dup1';delete it.songId;delete it.arrId;delete it.ov;delete it.bs;delete it.arrAt;
      sv.items.push(it);sv.editedAt=Date.now();CONTI.save()})()""")
    pg.wait_for_timeout(6000)   # 3초 디바운스 + 밀기
    n1 = pg.evaluate("CONTI.S.songs.filter(s=>!s.archived).length")
    if n1 != n0: fail('제목이 같은데 곡이 또 만들어짐: %d → %d' % (n0, n1))
    linked = pg.evaluate("CONTI.S.services.find(x=>x.id==='%s').items.find(i=>i.id==='dup1').arrId" % s2)
    if not linked: fail('있는 곡에 안 이어짐')
    print('no duplicate song ok')

    if errs: fail('페이지 오류:\n' + '\n'.join(errs[:6]))
    print('PASS test_override')
    b.close()

run()
