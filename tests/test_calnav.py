# 일정·편성 달력이 이번 달 ~ +2개월에 갇혀 있던 것 (2026-09-19)
#  - 지난 달로 갈 수 있다 · 더 먼 미래도 볼 수 있다 · '이번 달'로 돌아온다
#  - 편성 탭도 같이 움직인다 · 지난 날짜는 눌러서 답할 수 없다
import os, sys, time, datetime
from playwright.sync_api import sync_playwright
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
def fail(m): print('FAIL:', m); sys.exit(1)

def mk(dt): return dt.strftime('%Y-%m-%d')
def mkey(dt): return dt.strftime('%Y-%m')
def addm(d, n):
  y, m = d.year, d.month + n
  y += (m - 1) // 12; m = (m - 1) % 12 + 1
  return datetime.date(y, m, 15)

def run():
  tag = str(int(time.time()))[-6:]
  today = datetime.date.today()
  past2 = addm(today, -2); fut4 = addm(today, 4); soon = addm(today, 1)
  with sync_playwright() as p:
    b = p.chromium.launch(); c = b.new_context(viewport={'width':1180,'height':820}); pg = c.new_page()
    errs = []; pg.on('pageerror', lambda e: errs.append(repr(e)[:200])); pg.on('dialog', lambda d: d.accept())
    pg.goto(URL); pg.wait_for_selector('#lgUser')
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
    pg.fill('#lgName','하은'); pg.fill('#lgUser','cn'+tag); pg.fill('#lgPass','secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam'); pg.fill('#gtTeam','달력팀'); pg.click('#gtSess .q:has-text("건반")'); pg.click('[data-act="team-create"]')
    pg.wait_for_selector('.shell[data-page]', timeout=10000)
    tid = pg.evaluate("CONTI.S.team.id")

    # 지난 달·다음 달·넉 달 뒤에 사역 날짜를 연다
    for d, label in [(past2,'지난'), (soon,'담달'), (fut4,'넉달')]:
      r = pg.evaluate("""async ([tid,date,label])=>{
        const res=await fetch('/api/teams/'+tid+'/dates',{method:'POST',headers:{'content-type':'application/json','x-conti':'1'},
          credentials:'include',body:JSON.stringify({date,label})});
        return res.status}""", [tid, mk(d), label])
      if r != 200: fail('날짜 만들기 실패 %s: %s' % (label, r))

    def labels():
      return pg.evaluate("()=>[...document.querySelectorAll('.calmo .cal-cell .lb')].map(e=>e.textContent.trim())")
    def head():
      return pg.evaluate("()=>[...document.querySelectorAll('.calmo .cal-hd b')].map(e=>e.textContent.trim())")

    # ---- 기본: 이번 달 ~ +2개월
    pg.goto(URL + '#/cal'); pg.wait_for_selector('.calmo', timeout=10000); pg.wait_for_timeout(900)
    base = head()
    if len(base) != 3: fail('달이 3개가 아님: %s' % base)
    if '담달' not in ''.join(labels()): fail('다음 달 예배가 안 보임: %s' % labels())
    if '지난' in ''.join(labels()): fail('기본 화면에 지난 달이 섞임: %s' % labels())
    print('기본 석 달 ok', base)

    # ---- 지난 달로 두 번
    for _ in range(2):
      pg.click('[data-act="sch-mv"][data-d="-1"]'); pg.wait_for_timeout(1200)
    got = head()
    if got == base: fail('이전 달로 안 감: %s' % got)
    if '지난' not in ''.join(labels()): fail('두 달 전 예배가 안 보임: %s / %s' % (got, labels()))
    print('지난 달 ok', got, labels())

    # 지난 날짜는 눌러서 답할 수 없다
    clickable = pg.evaluate("()=>[...document.querySelectorAll('.cal-cell.past[data-cal]')].length")
    if clickable: fail('지난 날짜가 아직 눌림: %d칸' % clickable)

    # ---- '이번 달'로 복귀
    pg.click('[data-act="sch-now"]'); pg.wait_for_timeout(1200)
    if head() != base: fail("'이번 달'로 안 돌아옴: %s → %s" % (base, head()))
    print('이번 달 복귀 ok')

    # ---- 먼 미래 (넉 달 뒤)
    for _ in range(3):
      pg.click('[data-act="sch-mv"][data-d="1"]'); pg.wait_for_timeout(1000)
    if '넉달' not in ''.join(labels()): fail('넉 달 뒤 예배가 안 보임: %s / %s' % (head(), labels()))
    print('먼 미래 ok', head())

    # ---- 편성 탭도 같이 움직인다
    pg.goto(URL + '#/sched/' + mkey(past2)); pg.wait_for_selector('.shell[data-page]', timeout=10000); pg.wait_for_timeout(1500)
    sub = pg.evaluate("()=>{const e=document.querySelector('.hd .date, .ttl .date, .hd .sub, .shell .sub');return e?e.textContent.trim():''}")
    cols = pg.evaluate("()=>[...document.querySelectorAll('.schtab .dcol')].map(e=>e.textContent.trim()).join(' ')")
    lst = pg.evaluate("()=>document.body.innerText")
    if '지난' not in (cols + lst): fail('편성 탭에서 지난 달이 안 보임: %s | %s' % (sub, cols[:120]))
    if not pg.locator('[data-act="sch-mv"]').count(): fail('편성 탭에 달 이동 단추가 없음')
    print('편성 탭 이동 ok')

    if errs: fail('콘솔 오류: %s' % errs[:3])
    b.close()
  print('OK — 달력 앞뒤 달 보기')
run()
