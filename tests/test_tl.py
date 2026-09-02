from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':1180,'height':820}); errs=[]
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto('http://localhost:8765/'); pg.wait_for_timeout(400)
    pg.fill('#sName','하은'); pg.click('#sOk'); pg.wait_for_timeout(200)
    pg.click('[data-act="new-svc"]'); pg.wait_for_timeout(300); pg.fill('[data-f="svc.name"]','테스트 예배'); pg.click('[data-act="add-item"]'); pg.wait_for_timeout(300)
    pg.fill('[data-f="item.title"]','주 사랑합니다'); pg.fill('[data-f="item.form"]','1414 – AAB – (Key up)CDD')
    pg.fill('#ytUrl','https://www.youtube.com/watch?v=dQw4w9WgXcQ'); pg.click('[data-act="add-yt"]'); pg.wait_for_timeout(300)
    box=pg.locator('.tlEdit').first
    box.locator('[data-tl="t"]').fill('1:23'); box.locator('[data-tl="s"]').select_option('드럼'); box.locator('[data-tl="text"]').fill('필 그대로 카피'); pg.click('[data-act="add-tnote"]'); pg.wait_for_timeout(300)
    box=pg.locator('.tlEdit').first
    box.locator('[data-tl="t"]').fill('2:10'); box.locator('[data-tl="text"]').fill('Key up 전 패드 빼기'); pg.click('[data-act="add-tnote"]'); pg.wait_for_timeout(300)
    print('tl rows:', pg.locator('.tlEdit .row.small').count())
    pg.screenshot(path='t_tl_editor.png')
    pg.click('[data-act="publish"]'); pg.wait_for_timeout(200)
    with pg.expect_download(): pg.click('#pubOk')
    pg.wait_for_timeout(300); pg.click('[data-act="view-svc"]'); pg.wait_for_timeout(500)
    print('viewer tl:', pg.locator('.tl[data-act="ytopen"]').count())
    with pg.expect_popup() as pop: pg.locator('.tl[data-act="ytopen"]').first.click()
    print('popup url:', pop.value.url)
    pg.click('[data-act="play"]'); pg.wait_for_timeout(3200)
    print('hint:', pg.locator('#ytHint').inner_text()[:40]); print('play tl:', pg.locator('#tlist .tl').count())
    # 메모 탭: 임베드가 막힌 환경(오류 153)에선 유튜브가 새 창으로 열리고, 임베드가 되는 환경에선 플레이어 안에서 그 시각으로 이동
    if '오류 153' in pg.locator('#ytHint').inner_text():
        with pg.expect_popup() as pop2: pg.locator('#tlist .tl').nth(0).click()
        print('seek popup:', pop2.value.url)
    else:
        row=pg.locator('#tlist .tl').nth(0); want=row.locator('.t').inner_text().strip(); row.click(); pg.wait_for_timeout(300)
        cur=pg.locator('#tCur').inner_text().strip(); print('seek in-player:', want, '->', cur); assert cur==want, (want, cur)
    pg.click('[data-act="tnote"]'); pg.wait_for_timeout(300); pg.fill('#cTime','3:05'); pg.fill('#cText','Down 구간'); pg.click('#cSave'); pg.wait_for_timeout(400)
    print('play tl after manual:', pg.locator('#tlist .tl').count(), [t.strip()[:5] for t in pg.locator('#tlist .tl .t').all_inner_texts()])
    pg.screenshot(path='t_tl_play.png'); print('errors:', errs); b.close()
