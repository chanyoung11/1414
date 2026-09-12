# §5 합주 녹음: 직접 업로드(4.5MB 초과) · 카드 · 플레이어 · 메모(곡 태그) · 보관 잠금 · 알림
import os, sys, time, datetime
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
tag = str(int(time.time()))[-6:]
H = {'x-conti': '1'}

def fail(msg): print('FAIL:', msg); sys.exit(1)

def run():
    with sync_playwright() as p:
        b = p.chromium.launch(args=['--use-fake-ui-for-media-stream']); errs = []
        cL = b.new_context(viewport={'width': 1240, 'height': 950}); pl = cL.new_page()
        pl.on('pageerror', lambda e: errs.append('L:' + str(e))); pl.on('dialog', lambda d: d.accept())
        pl.goto(URL); pl.wait_for_selector('#lgUser', timeout=8000)
        pl.click('[data-act="lg-mode"][data-m="signup"]'); pl.wait_for_selector('#lgName')
        pl.fill('#lgName', '하은'); pl.fill('#lgUser', 'rl' + tag); pl.fill('#lgPass', 'secret1'); pl.click('[data-act="lg-submit"]')
        pl.wait_for_selector('#gtTeam', timeout=8000); pl.fill('#gtTeam', '녹음팀'); pl.click('[data-act="team-create"]'); pl.wait_for_selector('.shell[data-page]', timeout=8000)
        team = pl.evaluate('CONTI.S.team.id')
        link = pl.evaluate("location.origin+location.pathname+'#/join/'+CONTI.S.team.invite")

        cM = b.new_context(viewport={'width': 1240, 'height': 950}); pm = cM.new_page()
        pm.on('pageerror', lambda e: errs.append('M:' + str(e))); pm.on('dialog', lambda d: d.accept())
        pm.goto(link); pm.wait_for_selector('#lgUser', timeout=8000)
        pm.click('[data-act="lg-mode"][data-m="signup"]'); pm.wait_for_selector('#lgName')
        pm.fill('#lgName', '민수'); pm.fill('#lgUser', 'rm' + tag); pm.fill('#lgPass', 'secret1'); pm.click('[data-act="lg-submit"]')
        pm.wait_for_selector('#jnName', timeout=8000); pm.click('[data-act="team-join"]'); pm.wait_for_selector('.shell[data-page]', timeout=8000)

        # 예배 발행
        pl.click('[data-act="new-svc"]'); pl.wait_for_selector('[data-f="svc.name"]'); pl.fill('[data-f="svc.name"]', '녹음 예배')
        pl.click('[data-act="add-item"]'); pl.wait_for_selector('[data-f="item.title"]'); pl.fill('[data-f="item.title"]', '주 사랑합니다'); pl.wait_for_timeout(400)
        svc_id = pl.evaluate('CONTI.S.services[0].id'); item_id = pl.evaluate('CONTI.S.services[0].items[0].id')
        pl.click('[data-act="publish"]'); pl.wait_for_selector('#pubOnly'); pl.click('#pubOnly'); pl.wait_for_timeout(5000)

        # ---- 6MB 파일 직접 업로드 (서버리스 본문 한도 4.5MB 초과) ----
        pl.goto(URL + '#/view/' + svc_id); pl.wait_for_selector('[data-act="reh-add"]', timeout=15000)
        pl.click('[data-act="reh-add"]'); pl.wait_for_selector('#rhFile', state='attached', timeout=5000)
        big = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scratch-reh.m4a')
        with open(big, 'wb') as f: f.write(b'\0' * (6 * 1024 * 1024))
        pl.set_input_files('#rhFile', big); pl.wait_for_timeout(1500)
        pl.fill('#rhLabel', '9/6 합주')
        pl.click('#rhOk')
        pl.wait_for_selector('.rehrow', timeout=90000)
        os.remove(big)
        rs = cL.request.get(URL + 'api/rehearsals?team=%s&service=%s' % (team, svc_id)).json()
        if not rs['rehearsals']: fail('녹음이 등록되지 않음')
        r0 = rs['rehearsals'][0]
        if int(r0['sizeBytes']) != 6 * 1024 * 1024: fail('업로드 크기가 다름: %s' % r0['sizeBytes'])
        if r0['label'] != '9/6 합주': fail('이름이 다름: %s' % r0['label'])
        if not rs['urls'].get(r0['blobId']): fail('재생 URL 없음')
        print('direct upload ok:', int(r0['sizeBytes']) // 1024 // 1024, 'MB')

        # ---- 멤버에게 알림 ----
        ns = [n for n in cM.request.get(URL + 'api/notifications?team=' + team).json()['notifications'] if n['type'] == 'rehearsal.uploaded']
        if not ns: fail('rehearsal.uploaded 알림 없음')
        print('notify ok:', ns[0]['title'])

        # ---- 플레이어 + 곡 태그 메모 ----
        pl.click('.rehrow'); pl.wait_for_selector('#rhAudio', state='attached', timeout=10000)
        pl.click('#rhNote'); pl.wait_for_selector('#rnText', timeout=5000)
        pl.fill('#rnText', '3번 B 들어갈 때 반박 빠름')
        pl.select_option('#rnItem', item_id)
        pl.click('#rnOk'); pl.wait_for_timeout(1500)
        rs = cL.request.get(URL + 'api/rehearsals?team=%s&service=%s' % (team, svc_id)).json()
        notes = rs['rehearsals'][0]['notes']
        if not notes or notes[0]['itemId'] != item_id: fail('곡 태그 메모 저장 안 됨: %s' % notes)
        print('note ok:', notes[0]['text'])
        pl.keyboard.press('Escape'); pl.wait_for_timeout(300)

        # ---- 곡 카드 "지난 연습에서" ----
        pl.goto(URL + '#/home'); pl.wait_for_selector('.hd'); pl.goto(URL + '#/view/' + svc_id); pl.wait_for_selector('.rehrow', timeout=15000); pl.wait_for_timeout(800)
        if '지난 연습에서' not in pl.locator('#app').inner_text(): fail('곡 카드에 "지난 연습에서"가 없음')
        if '반박 빠름' not in pl.locator('.reheard').inner_text(): fail('곡 카드 메모 내용 없음')
        print('song card line ok')

        # ---- 멤버 화면: 전체 메모는 보이고 업로드 버튼은 권한대로 ----
        pm.goto(URL + '#/home'); pm.reload(); pm.wait_for_selector('.svcrow', timeout=15000)
        pm.goto(URL + '#/view/' + svc_id); pm.wait_for_selector('.rehrow', timeout=15000); pm.wait_for_timeout(500)
        if '9/6 합주' not in pm.locator('#app').inner_text(): fail('멤버에게 녹음 카드가 안 보임')
        if not pm.locator('[data-act="reh-add"]').count(): fail('기본 권한(전원)인데 멤버에게 올리기 버튼이 없음')
        # 권한을 인도자만으로 좁히면 사라짐
        cL.request.patch(URL + 'api/teams/%s/settings' % team, headers=H, data={'rehearsalUploadRole': 'leader'})
        pm.reload(); pm.wait_for_selector('.rehrow', timeout=15000); pm.wait_for_timeout(800)
        if pm.locator('[data-act="reh-add"]').count(): fail('권한을 좁혔는데 멤버에게 올리기 버튼이 남음')
        rr = cM.request.post(URL + 'api/rehearsals/upload-url', headers=H, data={'teamId': team, 'size': 1000, 'mime': 'audio/mp4'})
        if rr.status != 403: fail('서버가 권한을 막지 않음: %s' % rr.status)
        print('upload permission ok')

        # ---- 보관 잠금 · 삭제 ----
        pl.reload(); pl.wait_for_selector('[data-act="reh-menu"]', timeout=15000)
        pl.click('[data-act="reh-menu"]'); pl.wait_for_selector('#rmKeep', timeout=5000)
        pl.click('#rmKeep'); pl.wait_for_timeout(1500)
        rs = cL.request.get(URL + 'api/rehearsals?team=%s&service=%s' % (team, svc_id)).json()
        if not rs['rehearsals'][0]['keep'] or rs['rehearsals'][0]['expiresAt']: fail('보관 잠금이 안 됨: %s' % rs['rehearsals'][0])
        print('keep lock ok')
        d = cL.request.delete(URL + 'api/rehearsals/%s?team=%s' % (r0['id'], team), headers=H)
        if d.status != 200: fail('삭제 실패: ' + d.text()[:120])
        if cL.request.get(URL + 'api/rehearsals?team=%s&service=%s' % (team, svc_id)).json()['rehearsals']: fail('삭제 후에도 남음')
        print('delete ok')

        print('errors:', errs)
        if errs: fail('page errors')
        b.close()
    print('REHEARSAL TEST OK')

if __name__ == '__main__':
    run()
