# 스토어 스크린샷을 배포본에서 심사 계정으로 찍는다.
#   .venv/bin/python scripts/store-shots.py
# 플레이(9:16 1080×1920 · 가로 1920×1080) / 애플 6.7" 1290×2796 · 6.5" 1284×2778 / 아이패드 2048×2732
import os, subprocess, sys
from playwright.sync_api import sync_playwright
URL='https://lets1414.com/'
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PW=subprocess.run(['security','find-generic-password','-a','1414-appreview','-w'],capture_output=True,text=True).stdout.strip()
SETS=[('store-play',405,720,2.667,720,405),('store',430,932,3,932,430),('store-65',428,926,3,926,428),('store-ipad',1024,1366,2,1366,1024)]
SHOTS=[('01_home','#/home'),('02_view','view'),('03_play','play'),('04_cal','#/cal'),('05_library','#/library'),('06_sched','#/sched'),('07_stage','stage')]
def settle(pg,ms=1600):
    pg.wait_for_timeout(ms)
    # 인도자의 글 팝업이 뜨면 '읽었어요'
    # 약관 재동의 팝업이 있으면 동의 (한 번 하면 서버에 남아 심사자도 안 본다)
    if pg.locator('#agChk').count():
        pg.check('#agChk'); pg.click('#modal .btn.pri'); pg.wait_for_timeout(1500)
    if pg.locator('#msgOk').count(): pg.click('#msgOk'); pg.wait_for_timeout(500)
    pg.evaluate("document.querySelectorAll('.toast').forEach(t=>t.remove())")
with sync_playwright() as p:
    b=p.chromium.launch()
    for folder,w,h,dsf,lw,lh in SETS:
        out=os.path.join(ROOT,'docs',folder); os.makedirs(out,exist_ok=True)
        for old in os.listdir(out):   # 예전 캡처는 지운다
            if old.endswith('.png'): os.remove(os.path.join(out,old))
        c=b.new_context(viewport={'width':w,'height':h},device_scale_factor=dsf,is_mobile=w<800,has_touch=True)
        pg=c.new_page(); pg.on('dialog',lambda d:d.accept())
        pg.goto(URL); pg.wait_for_selector('#lgUser',timeout=20000)
        pg.fill('#lgUser','appreview'); pg.fill('#lgPass',PW); pg.click('[data-act="lg-submit"]')
        pg.wait_for_selector('.shell[data-page]',timeout=25000); settle(pg,2500)
        sid=pg.evaluate("(()=>{const s=CONTI.S.services.filter(x=>x.published);return (s[0]||CONTI.S.services[0]).id})()")
        for name,route in SHOTS:
            if route=='stage':
                pg.set_viewport_size({'width':lw,'height':lh})
                pg.goto(URL+'#/view/'+sid); settle(pg,1500)
                pg.click('[data-act="play"][data-stage="1"]'); pg.wait_for_selector('#stageWrap .stgpage',timeout=15000); pg.wait_for_timeout(1500)
            elif route=='view': pg.goto(URL+'#/view/'+sid); settle(pg,2000)
            elif route=='play': pg.goto(URL+'#/play/'+sid); settle(pg,2500)
            else: pg.goto(URL+route); settle(pg)
            pg.screenshot(path=os.path.join(out,name+'.png'))
            if route=='stage': pg.keyboard.press('Escape'); pg.set_viewport_size({'width':w,'height':h})
        c.close(); print(folder,'ok')
    b.close()
