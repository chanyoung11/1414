# 메모 두 층 (명세 A.6): "이 곡에 항상"은 편곡에 붙어 다음 예배에도 따라오고,
# "이번 예배만"은 그 예배에만 남는다. 발행본은 발행 시점 고정 메모를 굳힌다
import os, sys, time
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
tag = str(int(time.time()))[-6:]
H = {'x-conti': '1'}
def fail(m): print('FAIL:', m); sys.exit(1)

def add_song_to_new_service(pg, sid, name):
    pg.goto(URL + '#/library/' + sid); pg.wait_for_selector('.acard', timeout=10000); pg.wait_for_timeout(400)
    pg.click('[data-arradd]'); pg.wait_for_selector('#atsGo', timeout=6000)
    pg.click('[data-ats="new"]'); pg.wait_for_selector('#atsName', timeout=5000)
    pg.fill('#atsName', name); pg.click('#atsGo')
    pg.wait_for_selector('[data-f="item.title"]', timeout=10000); pg.wait_for_timeout(600)
    return pg.evaluate("CONTI.route().a")

def run():
  with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    c = b.new_context(viewport={'width': 1300, 'height': 1000}); pg = c.new_page()
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=8000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
    pg.fill('#lgName', '하은'); pg.fill('#lgUser', 'fx' + tag); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam', timeout=8000); pg.fill('#gtTeam', '메모팀'); pg.click('[data-act="team-create"]')
    pg.wait_for_selector('.shell[data-page]', timeout=8000)
    team = pg.evaluate('CONTI.S.team.id')

    # 곡 하나 + 악보 한 장 + 마커 A
    r = c.request.post(URL + 'api/songs', headers=H, data={'teamId': team, 'title': '오 신령한 주', 'key': 'G', 'form': 'A – B'}).json()
    sid = r['song']['id']
    pg.evaluate("CONTI.pullSongs(true)"); pg.wait_for_timeout(1200)
    s1 = add_song_to_new_service(pg, sid, '예배 하나')
    pg.set_input_files('#pieceFile', [SHEET])
    pg.wait_for_function("(()=>{const p=(CONTI.S.services[0].items[0].pieces||[])[0];return p&&p.ocr&&p.ocr!=='pending'})()", timeout=90000)
    pg.wait_for_timeout(4500)   # pushSongs 디바운스(3초)로 악보가 편곡에 올라가게
    # 마커 A 를 찍는다 (좌표 대신 데이터로)
    pg.evaluate("""(()=>{const s=CONTI.S.services.find(x=>x.id===CONTI.route().a);const it=s.items[0];
      const p=it.pieces[0];p.markers=[{id:'mk1',label:'A',x:40,y:60,cut:120}];CONTI.save();CONTI.render()})()""")
    pg.wait_for_timeout(1500)

    # ---- "이 곡에 항상" 으로 메모 ----
    # 편집기에서는 "메모" 도구를 켜고 마커를 탭한다
    pg.click('[data-act="tool"][data-t="memo"]'); pg.wait_for_timeout(400)
    pg.click('.mkabs[data-marker="mk1"]'); pg.wait_for_selector('#cText', timeout=6000)
    if not pg.locator('#cWhen').count(): fail('"언제까지" 스위치가 없음')
    if not pg.locator('[data-w2="always"].on').count(): fail('인도자 기본이 "이 곡에 항상"이 아님')
    pg.fill('#cText', 'Key up 직전 한 박 쉬고'); pg.click('#cSave'); pg.wait_for_timeout(2500)
    fixed = c.request.get(URL + 'api/songs/%s?team=%s' % (sid, team)).json()['notes']
    if not fixed or fixed[0]['markerLabel'] != 'A': fail('편곡에 고정 메모가 안 붙음: %s' % fixed)
    if fixed[0]['layer'] != 'all': fail('인도자 메모가 all 이 아님: %s' % fixed[0])
    print('always-note saved ok')

    # ---- 같은 곡을 다른 예배에 넣으면 라벨이 같은 자리에 따라온다 ----
    pg.evaluate("CONTI.S.songsAt='';CONTI.pullSongs(true)"); pg.wait_for_timeout(2000)
    s2 = add_song_to_new_service(pg, sid, '예배 둘')
    pg.evaluate("""(()=>{const s=CONTI.S.services.find(x=>x.id===CONTI.route().a);const it=s.items[0];
      const p=it.pieces[0];if(p)p.markers=[{id:'mk9',label:'A',x:40,y:60,cut:120}];CONTI.save();CONTI.render()})()""")
    pg.wait_for_timeout(1500)
    body = pg.locator('#app').inner_text()
    if 'Key up' not in body: fail('다른 예배에 고정 메모가 안 따라옴:\n' + body[:400])
    if not pg.locator('.m.fixed').count(): fail('고정 메모가 구분되게 안 그려짐')
    print('always-note follows ok')

    # ---- "이번 예배만" 은 그 예배에만 ----
    pg.click('[data-act="tool"][data-t="memo"]'); pg.wait_for_timeout(400)
    pg.click("[data-marker=\"mk9\"]"); pg.wait_for_selector('#cText', timeout=6000)
    pg.click('[data-w2="once"]'); pg.fill('#cText', '여기만'); pg.click('#cSave'); pg.wait_for_timeout(1500)
    if '여기만' not in pg.locator('#app').inner_text(): fail('이번 예배만 메모가 안 보임')
    pg.goto(URL + '#/edit/' + s1); pg.wait_for_selector('.sheet', timeout=10000); pg.wait_for_timeout(1500)
    b1 = pg.locator('#app').inner_text()
    if '여기만' in b1: fail('이번 예배만 메모가 다른 예배로 샘')
    if 'Key up' not in b1:
        print('DEBUG', pg.evaluate("(()=>{const s=CONTI.S.services.find(x=>x.id==='%s');const it=s.items[0];const a=CONTI.arrOfItem(it);return {arrId:it.arrId,ov:it.ov,notes:a?(a.notes||[]).length:'no arr',markers:(it.pieces[0]||{}).markers,fx:CONTI.fixedNotesOf(it,'mk1',{mode:'edit'})}})()" % s1))
        fail('첫 예배에서 고정 메모가 사라짐')
    print('once-note isolated ok')

    # ---- 발행하면 그 시점 고정 메모가 굳는다 ----
    pg.click('[data-act="publish"]'); pg.wait_for_selector('#pubOnly', timeout=6000); pg.click('#pubOnly'); pg.wait_for_timeout(4000)
    nid = fixed[0]['id']; arr = fixed[0]['arrangementId']
    c.request.delete(URL + 'api/arrangements/%s/notes/%s?team=%s' % (arr, nid, team), headers=H)
    pg.evaluate("CONTI.S.songsAt='';CONTI.LIB.detail=null;CONTI.pullSongs(true)"); pg.wait_for_timeout(2000)
    pg.goto(URL + '#/view/' + s1); pg.wait_for_selector('.card', timeout=10000); pg.wait_for_timeout(1200)
    frozen = pg.evaluate("(CONTI.S.services.find(x=>x.id==='%s').published.items[0].fixedNotes||[]).length" % s1)
    if not frozen: fail('발행본에 고정 메모가 안 굳었음')
    print('published snapshot keeps fixed notes ok')

    if errs: fail('페이지 오류:\n' + '\n'.join(errs[:6]))
    print('PASS test_fixednote')
    b.close()

run()
