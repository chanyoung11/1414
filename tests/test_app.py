import json, os, sys
from playwright.sync_api import sync_playwright
URL='http://localhost:8765/'
def run():
  with sync_playwright() as p:
    b=p.chromium.launch(); ctx=b.new_context(viewport={'width':1180,'height':820}, accept_downloads=True); pg=ctx.new_page()
    errs=[]; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append('console:'+m.text) if m.type=='error' else None)
    pg.goto(URL); pg.wait_for_timeout(600)
    # settings modal
    pg.fill('#sName','하은'); pg.click('#sSess .q:has-text("건반")'); pg.click('#sOk'); pg.wait_for_timeout(300)
    pg.screenshot(path='t_home.png')
    pg.click('[data-act="new-svc"]'); pg.wait_for_timeout(400)
    pg.fill('[data-f="svc.name"]','11/21 LIKE MT 저녁집회'); pg.fill('[data-f="svc.notice"]','연습 토 14:00 본당 · 편성: 드럼 ○○')
    pg.click('[data-act="add-item"]'); pg.wait_for_timeout(300)
    pg.fill('[data-f="item.title"]','우리 주 하나님'); pg.fill('[data-f="item.key"]','A'); pg.fill('[data-f="item.mod"]','')
    pg.fill('[data-f="item.form"]','1414 – AAB – Int(2(G D-A)) – AABB – (Key up)CDD(Brk)D – E반복 – E – F반복'); pg.wait_for_timeout(200)
    assert pg.locator('.list-item .grow').first.inner_text().strip()=='우리 주 하나님', 'list row title not live-updated'; assert pg.locator('.list-item .num').first.inner_text().strip()=='1', 'num badge overwritten'
    print('chips:', pg.locator('#formchips .chip').count())
    pg.set_input_files('#pieceFile', ['docs/sample_sheet.jpg']); pg.wait_for_timeout(2500)
    st=pg.evaluate("()=>JSON.parse(JSON.stringify(window.CONTI.S))")
    it=st['services'][0]['items'][0]; print('pieces:', len(it['pieces']), 'gaps:', len(it['pieces'][0]['gaps']), it['pieces'][0]['w'], it['pieces'][0]['h'])
    pg.screenshot(path='t_editor1.png')
    # place marker A near top-left of first system: click slice at (30px, y ~ 8% of height)
    sl=pg.locator('.slice').first; box=sl.bounding_box(); print('slice box', box)
    pg.mouse.click(box['x']+40, box['y']+box['height']*0.09); pg.wait_for_timeout(300)
    pg.click('#modal [data-l="A"]'); pg.wait_for_timeout(300)
    pg.mouse.click(box['x']+40, box['y']+box['height']*0.31); pg.wait_for_timeout(300)
    pg.click('#modal [data-l="B"]'); pg.wait_for_timeout(300)
    pg.mouse.click(box['x']+40, box['y']+box['height']*0.62); pg.wait_for_timeout(300)
    pg.click('#modal [data-l="C"]'); pg.wait_for_timeout(300)
    st=pg.evaluate("()=>JSON.parse(JSON.stringify(window.CONTI.S))")
    mks=st['services'][0]['items'][0]['pieces'][0]['markers']; print('markers:', [(m['label'],m['y'],m['cut']) for m in mks])
    # highlight tool: drag
    pg.click('[data-act="tool"][data-t="hl"]'); pg.wait_for_timeout(200)
    sl=pg.locator('.slice').first; box=sl.bounding_box()
    pg.mouse.move(box['x']+box['width']*0.55, box['y']+box['height']*0.33); pg.mouse.down(); pg.mouse.move(box['x']+box['width']*0.9, box['y']+box['height']*0.38, steps=5); pg.mouse.up(); pg.wait_for_timeout(300)
    # memo tool: click marker B
    pg.click('[data-act="tool"][data-t="memo"]'); pg.wait_for_timeout(200)
    pg.locator("span.mk[data-marker]:has-text(\"B\")").first.click(); pg.wait_for_timeout(300)
    pg.click('#modal [data-p="Down"]'); pg.fill('#cText','후반 Down, 드럼 하프타임'); pg.click('#modal [data-s="드럼"]'); pg.click('#cSave'); pg.wait_for_timeout(400)
    pg.locator("span.mk[data-marker]:has-text(\"C\")").first.click(); pg.wait_for_timeout(300)
    pg.fill('#cText','Key up 직전 한 박 쉬고'); pg.click('#cSave'); pg.wait_for_timeout(400)
    # youtube
    pg.fill('#ytUrl','https://youtu.be/dQw4w9WgXcQ?t=42'); pg.click('[data-act="add-yt"]'); pg.wait_for_timeout(300)
    pg.screenshot(path='t_editor2.png', full_page=False)
    # library check
    st=pg.evaluate("()=>JSON.parse(JSON.stringify(window.CONTI.S))"); print('library:', [l['title'] for l in st['library']], 'notes:', len(st['services'][0]['items'][0]['notes']))
    # second song from library
    pg.click('[data-act="add-lib"]'); pg.wait_for_timeout(300); pg.click('#modal [data-lib]'); pg.wait_for_timeout(500)
    st=pg.evaluate("()=>JSON.parse(JSON.stringify(window.CONTI.S))"); print('items:', [i['title'] for i in st['services'][0]['items']])
    # publish
    pg.click('[data-act="publish"]'); pg.wait_for_timeout(300); print('kakao:\n', pg.input_value('#kk'))
    with pg.expect_download() as dl: pg.click('#pubOk')
    d=dl.value; path='/private/tmp/claude-501/-Users-chanyoung/b4bb55f2-67e5-4915-ac80-9a56a36b2106/scratchpad/export.json'; d.save_as(path); print('download', d.suggested_filename, os.path.getsize(path)//1024,'KB'); pg.wait_for_timeout(500)
    # view
    pg.click('[data-act="view-svc"]'); pg.wait_for_timeout(600); pg.screenshot(path='t_view.png')
    # play
    pg.click('[data-act="play"]'); pg.wait_for_timeout(800); pg.screenshot(path='t_play.png')
    print('strips in play:', pg.locator('#sheet .strip').count(), 'markers:', pg.locator('#sheet [data-marker]').count())
    # member memo via strip +
    pg.locator('#sheet [data-act="memo"]').first.click(); pg.wait_for_timeout(300); pg.fill('#cText','왼손 옥타브'); pg.click('#cSave'); pg.wait_for_timeout(400)
    print('strips after mine:', pg.locator('#sheet .strip').count())
    pg.click('[data-act="stage"]'); pg.wait_for_timeout(300); pg.screenshot(path='t_stage.png')
    print('errors:', errs)
    # fresh context import as member
    ctx2=b.new_context(viewport={'width':1180,'height':820}); pg2=ctx2.new_page(); e2=[]; pg2.on('pageerror', lambda e: e2.append(str(e)))
    pg2.goto(URL); pg2.wait_for_timeout(500); pg2.fill('#sName','민수'); pg2.click('#sSess .q:has-text("드럼")'); pg2.click('#sRole [data-r="member"]'); pg2.click('#sOk'); pg2.wait_for_timeout(300)
    pg2.on('filechooser', lambda fc: fc.set_files(path))
    pg2.click('[data-act="import"]'); pg2.wait_for_timeout(1500)
    pg2.screenshot(path='t_member_home.png')
    pg2.click('[data-act="view-svc"]'); pg2.wait_for_timeout(700); pg2.screenshot(path='t_member_view.png')
    pg2.click('[data-act="play"]'); pg2.wait_for_timeout(800); pg2.screenshot(path='t_member_play.png')
    print('member strips:', pg2.locator('#sheet .strip').count(), 'errors2:', e2)
    b.close()
run()
