# 죽은 버튼 찾기: 화면마다 보이는 버튼을 하나씩 눌러 아무 변화(라우트·모달·DOM·토스트)도 없으면 보고한다.
#   .venv/bin/python scripts/deadclick.py [URL]
import sys, time, os, subprocess
from playwright.sync_api import sync_playwright
URL=sys.argv[1] if len(sys.argv)>1 else 'http://localhost:8766/'
SKIP={'lg-submit','logout','del-svc','account-delete','team-leave','publish','lslots','lclear','lnotify','ldefault','repub','pick-all'}   # 파괴적이거나 서버 쓰는 것
def snap(pg):
  return pg.evaluate("""()=>({h:location.hash,modal:!!document.querySelector('#modal>*'),n:document.body.innerHTML.length,
    toast:[...document.querySelectorAll('.toast')].some(t=>getComputedStyle(t).opacity!=='0'),noti:!!document.querySelector('.ddnoti,.dd')})""")
def run():
  tag=str(int(time.time()))[-6:]
  with sync_playwright() as p:
    b=p.chromium.launch(); c=b.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True); pg=c.new_page(); pg.on('dialog',lambda d:d.dismiss())
    errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)[:140]))
    pg.goto(URL); pg.wait_for_selector('#lgUser')
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
    pg.fill('#lgName','점검'); pg.fill('#lgUser','dc'+tag); pg.fill('#lgPass','secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam'); pg.fill('#gtTeam','점검팀'); pg.click('#gtSess .q:has-text("건반")'); pg.click('[data-act="team-create"]')
    pg.wait_for_selector('.shell[data-page]',timeout=10000); pg.wait_for_timeout(800)
    # 곡 하나 있는 예배 하나
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]',timeout=8000)
    pg.fill('[data-f="svc.name"]','점검 예배'); pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]'); pg.fill('[data-f="item.title"]','곡'); pg.wait_for_timeout(600)
    sid=pg.evaluate("CONTI.S.services[0].id")
    dead=[]; tried=0
    for name,route in [('홈','#/home'),('콘티','#/view/'+sid),('연습','#/play/'+sid),('편집','#/edit/'+sid),('일정','#/cal'),('편성','#/sched'),('라이브러리','#/library'),('알림','#/inbox'),('설정','#/settings'),('팀','#/team'),('말씀','#/word')]:
      pg.evaluate("(h)=>{location.hash=h}",route); pg.wait_for_timeout(900)
      if pg.locator('#modal>*').count(): pg.keyboard.press('Escape'); pg.evaluate("CONTI.closeModal&&CONTI.closeModal()"); pg.wait_for_timeout(200)
      keys=pg.evaluate("""()=>[...document.querySelectorAll('#app [data-act], #app button, .bnav [data-act]')].filter(e=>{const r=e.getBoundingClientRect();return r.width>4&&r.height>4&&!e.disabled&&!e.closest('#modal')})
        .map(e=>e.dataset.act||('btn:'+(e.id||e.textContent.trim().slice(0,12))))""")
      seen=set()
      for k in keys:
        if k in seen or k.replace('btn:','') in SKIP or k in SKIP: continue
        seen.add(k); tried+=1
        pg.evaluate("(h)=>{if(location.hash!==h)location.hash=h}",route); pg.wait_for_timeout(300)
        if pg.locator('#modal>*').count(): pg.evaluate("document.querySelector('#modal').innerHTML=''")
        sel=('#app [data-act="%s"], .bnav [data-act="%s"]'%(k,k)) if not k.startswith('btn:') else None
        before=snap(pg)
        try:
          if sel: pg.locator(sel).first.click(timeout=2000)
          else: pg.locator('#app button').filter(has_text=k[4:]).first.click(timeout=2000)
        except Exception as e: continue
        pg.wait_for_timeout(450)
        after=snap(pg)
        if before==after: dead.append((name,k))
    print('눌러본 버튼 %d개'%tried)
    print('죽은 버튼 %d개:'%len(dead)); [print('  ',n,k) for n,k in dead]
    print('콘솔 오류:',errs[:5])
    b.close()
run()
