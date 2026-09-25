# 운영 점검 desk-2 — 편집기: 마커 바로 위(또는 바로 아래)에 절단선이 있으면 마커를 눌러도 아무 일도 안 일어남
#   절단선(.cutline, z-index 4, 위아래 ±12px 잡는 자리)이 마커(.mkabs, z-index 3)를 덮어,
#   메모 도구로 누르면 메모 창이, 마커 도구로 누르면 마커 메뉴가 안 열렸다.
#   autoCut 은 탭한 곳 위 가장 가까운 여백(코드 줄과 오선 사이의 얇은 틈)에 절단선을 놓아 흔하고,
#   화면이 좁을수록(배율이 작을수록) 더 잘 겹친다.
# 되짚기: 절단선은 마커 도구에서만 끌 수 있는데 다른 도구에서도 탭을 가로채, 코드 도구로 절단선 옆 코드 상자를
#   누르면 '코드 고치기'가 아니라 그 자리에 새 코드 추가 창이 떴다.
# 지켜야 하는 것: 마커 도구에서 마커 밖 절단선은 여전히 끌어 옮길 수 있다.
import os, sys, time
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
tag = str(int(time.time()))[-6:]
def fail(m): print('FAIL:', m); sys.exit(1)

def signup(pg, user, name):
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=10000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
    pg.check('#lgAgree')
    pg.fill('#lgName', name); pg.fill('#lgUser', user); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam', timeout=10000); pg.fill('#gtTeam', '절단선팀'); pg.click('[data-act="team-create"]')
    pg.wait_for_selector('.shell[data-page]', timeout=10000); pg.wait_for_timeout(800)
    for _ in range(3):
        if pg.locator('#modal .ov').count(): pg.keyboard.press('Escape'); pg.wait_for_timeout(300)

def close_modal(pg):
    for _ in range(3):
        if not pg.evaluate("!!document.querySelector('#modal').firstChild"): return
        pg.keyboard.press('Escape'); pg.wait_for_timeout(300)
    fail('창이 안 닫힘')

def tool(pg, t):
    pg.click('[data-act="tool"][data-t="%s"]' % t); pg.wait_for_timeout(400)

# 마커 가운데를 가장 위에서 받는 것이 그 마커인지 (절단선이 덮으면 DIV.cutline). 화면 밖이면 먼저 가운데로 굴린다
HIT = """(mid)=>{const m=document.querySelector('#sheet .mkabs[data-marker="'+mid+'"]');if(!m)return null;
 m.scrollIntoView({block:'center',inline:'center'});const r=m.getBoundingClientRect();
 const cx=r.x+r.width/2,cy=r.y+r.height/2;const t=document.elementFromPoint(cx,cy);
 return {id:mid,cx,cy,top:t?(t.tagName+'.'+t.className):null,ok:!!(t&&t.closest('[data-marker]')===m)}}"""
MIDS = ('mA', 'mB', 'mC', 'mD')

def marker_center(pg, mid):
    pg.evaluate(HIT, mid); pg.wait_for_timeout(150)
    h = pg.evaluate(HIT, mid)
    if not h: fail('마커 %s 가 안 그려짐' % mid)
    return h

def covered(pg):
    return [h for h in (marker_center(pg, m) for m in MIDS) if not h['ok']]

def run():
    with sync_playwright() as p:
        b = p.chromium.launch(); errs = []
        c = b.new_context(viewport={'width': 1366, 'height': 900}); pg = c.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
        signup(pg, 'wfe' + tag, '인도')
        pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
        pg.fill('[data-f="svc.name"]', '절단선 예배'); pg.wait_for_timeout(300)
        pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]')
        pg.fill('[data-f="item.title"]', '절단선곡'); pg.fill('[data-f="item.key"]', 'G'); pg.wait_for_timeout(300)
        pg.set_input_files('#pieceFile', [SHEET])
        pg.wait_for_function("(()=>{const it=CONTI.S.services[0].items[0];const p=it&&(it.pieces||[])[0];return p&&p.w>0})()", timeout=60000)
        pg.wait_for_selector('#sheet .slice', timeout=10000); pg.wait_for_timeout(600)

        # 마커를 데이터로 놓는다 (화면 배율로 몇 px 떨어졌는지 정해 둠)
        #   A: 자기 절단선이 가운데 4px 위 (autoCut 이 코드 줄-오선 틈을 고른 모양)
        #   B: 절단선이 80px 위 — 원래도 되던 것
        #   C: 다른 마커(D)의 절단선이 가운데 5px 아래
        #   코드 ch1: B 의 절단선 위, 마커와 떨어진 오른쪽
        def place():
            pg.evaluate("""()=>{const it=CONTI.S.services[0].items[0];const p=it.pieces[0];
              const s=+document.querySelector('#sheet .slice').dataset.s;const px=v=>Math.round(v/s);
              const y1=Math.round(p.h*0.2),y2=Math.round(p.h*0.45),y3=Math.round(p.h*0.7);
              const x=Math.round(p.w*0.3);
              p.markers=[{id:'mA',label:'A',x,y:y1,cut:y1-px(4)},
                         {id:'mB',label:'B',x,y:y2,cut:y2-px(80)},
                         {id:'mC',label:'C',x,y:y3,cut:y3-px(80)},
                         {id:'mD',label:'D',x,y:y3+px(60),cut:y3+px(5)}];
              p.chords=[{id:'ch1',text:'G',x:Math.round(p.w*0.7),y:y2-px(80)-15,w:40,h:30,conf:100,fixed:true}];
              CONTI.save();CONTI.render()}""")
            pg.wait_for_selector('#sheet .mkabs[data-marker="mD"]', timeout=8000); pg.wait_for_timeout(500)
        place()
        if pg.locator('#sheet .cutline').count() != 4: fail('절단선 네 개가 안 그려짐: %d' % pg.locator('#sheet .cutline').count())

        # ---- 메모 도구: 네 마커 모두 가운데를 누르면 메모 창 ----
        tool(pg, 'memo')
        bad = covered(pg)
        if bad: fail('메모 도구에서 마커 가운데를 절단선이 덮음: %s' % bad)
        for mid in ('mA', 'mC', 'mB'):
            h = marker_center(pg, mid)
            pg.mouse.click(h['cx'], h['cy']); pg.wait_for_timeout(700)
            if not pg.locator('#cText').count(): fail('메모 도구로 마커 %s 를 눌러도 메모 창이 안 열림' % mid)
            close_modal(pg)
        print('메모 도구 마커 탭 ok')

        # ---- 마커 도구: 가운데를 누르면 마커 메뉴 (절단선 끌기로 잡히지 않음) ----
        tool(pg, 'marker')
        bad = covered(pg)
        if bad: fail('마커 도구에서 마커 가운데를 절단선이 덮음: %s' % bad)
        cuts0 = pg.evaluate("CONTI.S.services[0].items[0].pieces[0].markers.map(m=>m.cut)")
        for mid, lab in (('mA', 'A'), ('mC', 'C')):
            h = marker_center(pg, mid)
            pg.mouse.click(h['cx'], h['cy']); pg.wait_for_timeout(700)
            if not pg.locator('#mmMemo').count(): fail('마커 도구로 마커 %s 를 눌러도 마커 메뉴가 안 열림' % lab)
            if ('마커 ' + lab) not in pg.locator('#modal').inner_text(): fail('다른 마커의 메뉴가 열림 (%s)' % lab)
            close_modal(pg)
        if pg.evaluate("CONTI.S.services[0].items[0].pieces[0].markers.map(m=>m.cut)") != cuts0:
            fail('마커를 눌렀는데 절단선이 움직임')
        print('마커 도구 마커 탭 ok')

        # ---- 마커 도구: 마커에서 떨어진 곳의 절단선은 여전히 끌린다 ----
        pg.evaluate("document.querySelector('#sheet .cutline[data-cut=\"mA\"]').scrollIntoView({block:'center'})"); pg.wait_for_timeout(200)
        r = pg.evaluate("""()=>{const e=document.querySelector('#sheet .cutline[data-cut="mA"]');const b=e.getBoundingClientRect();
          return {x:b.x+b.width*0.75,y:b.y}}""")
        before = pg.evaluate("CONTI.S.services[0].items[0].pieces[0].markers.find(m=>m.id==='mA').cut")
        pg.mouse.move(r['x'], r['y']); pg.mouse.down(); pg.mouse.move(r['x'], r['y'] - 10, steps=3); pg.mouse.move(r['x'], r['y'] - 24, steps=3); pg.mouse.up()
        pg.wait_for_timeout(600)
        after = pg.evaluate("CONTI.S.services[0].items[0].pieces[0].markers.find(m=>m.id==='mA').cut")
        if not (after < before - 5): fail('마커 도구에서 절단선이 안 끌림: %s → %s' % (before, after))
        if pg.locator('#modal .ov').count(): fail('절단선을 끌었는데 창이 열림')
        print('절단선 끌기 ok', before, '→', after)

        # ---- 다른 도구에서는 절단선이 탭을 가로채지 않는다 (코드 도구: 절단선 위 코드 상자 = 코드 고치기) ----
        place()
        tool(pg, 'chord')
        pg.evaluate("document.querySelector('#sheet .chdbox[data-chord=\"ch1\"]').scrollIntoView({block:'center'})"); pg.wait_for_timeout(200)
        h = pg.evaluate("""()=>{const e=document.querySelector('#sheet .chdbox[data-chord="ch1"]');const b=e.getBoundingClientRect();
          const cx=b.x+b.width/2,cy=b.y+b.height/2;const t=document.elementFromPoint(cx,cy);return {cx,cy,top:t?(t.tagName+'.'+t.className):null}}""")
        pg.mouse.click(h['cx'], h['cy']); pg.wait_for_timeout(600)
        if not pg.locator('#chText').count(): fail('코드 도구로 코드 상자를 눌러도 창이 안 열림')
        if not pg.locator('#chDel').count(): fail('절단선 옆 코드 상자를 눌렀는데 코드 고치기가 아니라 새 코드 추가가 뜸 (맨 위: %s)' % h['top'])
        close_modal(pg)
        if pg.evaluate("CONTI.S.services[0].items[0].pieces[0].chords.length") != 1: fail('코드가 새로 생김')
        print('코드 도구 절단선 옆 코드 ok')

        # ---- 폰 폭: 배율이 작아 틈이 더 잘 겹친다 ----
        pg.set_viewport_size({'width': 390, 'height': 844}); pg.wait_for_timeout(300)
        pg.evaluate("CONTI.render()"); pg.wait_for_selector('#sheet .mkabs', timeout=8000); pg.wait_for_timeout(600)
        tool(pg, 'memo')
        bad = covered(pg)
        if bad: fail('폰 폭 메모 도구에서 마커를 절단선이 덮음: %s' % bad)
        h = marker_center(pg, 'mA')
        pg.mouse.click(h['cx'], h['cy']); pg.wait_for_timeout(700)
        if not pg.locator('#cText').count(): fail('폰 폭에서 메모 도구로 마커 A 를 눌러도 메모 창이 안 열림')
        close_modal(pg)
        print('폰 폭 마커 탭 ok')

        if errs: fail('페이지 오류:\n' + '\n'.join(errs[:6]))
        b.close()
    print('OK test_webfix_editor')

run()
