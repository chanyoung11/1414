# 약관·개인정보처리방침·가입 동의 (출시 필수)
import os, sys, time
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
H = {'x-conti': '1'}
def fail(m): print('FAIL:', m); sys.exit(1)

def run():
    tag = str(int(time.time()))[-6:]
    with sync_playwright() as p:
        b = p.chromium.launch(); c = b.new_context(viewport={'width':1180,'height':900}); pg = c.new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())

        # ---- 로그인 없이도 볼 수 있다 ----
        pg.goto(URL + '#/legal/privacy'); pg.wait_for_selector('.legal', timeout=10000); pg.wait_for_timeout(500)
        t = pg.locator('.legal').inner_text()
        for must in ['바디페인팅','469-06-03606','chanyoung07119@gmail.com','국외','Google','Vercel','Neon','계정을 지우면']:
            if must not in t: fail('개인정보처리방침에 "%s" 없음' % must)
        if '주민등록번호를 받지 않습니다' not in t: fail('주민번호 비수집 문구 없음')
        print('개인정보처리방침 ok (로그인 없이 열림)')
        pg.screenshot(path=os.path.join(ROOT,'tests','t_legal_privacy.png'))

        pg.click('[data-act="legal"][data-k="terms"]'); pg.wait_for_timeout(700)
        t2 = pg.locator('.legal').inner_text()
        for must in ['제1조','저작권','무료','탈퇴','바디페인팅']:
            if must not in t2: fail('이용약관에 "%s" 없음' % must)
        print('이용약관 ok')
        pg.screenshot(path=os.path.join(ROOT,'tests','t_legal_terms.png'))

        # ---- 가입 화면에 동의가 있고, 없으면 가입이 막힌다 ----
        pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=8000)
        pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
        if not pg.locator('#lgAgree').count(): fail('가입 화면에 동의 체크가 없음')
        if pg.locator('#lgAgree').is_checked(): fail('동의가 기본으로 체크돼 있음 (사전 동의 금지)')
        pg.fill('#lgName','하은'); pg.fill('#lgUser','lg'+tag); pg.fill('#lgPass','secret1')
        pg.click('[data-act="lg-submit"]'); pg.wait_for_timeout(900)
        if pg.locator('#gtTeam').count(): fail('동의 없이 가입됨')
        if '동의' not in pg.locator('#lgErr').inner_text(): fail('동의 안내가 안 뜸: ' + pg.locator('#lgErr').inner_text())
        print('동의 없이 가입 막힘 ok')

        # 로그인 화면에서 약관을 열어도 입력이 남는다
        pg.click('.agree a[data-k="terms"]'); pg.wait_for_selector('.legal', timeout=8000); pg.wait_for_timeout(500)
        pg.click('[data-act="legal-back"]'); pg.wait_for_selector('#lgUser', timeout=8000); pg.wait_for_timeout(500)
        if pg.evaluate("(document.querySelector('#lgUser')||{}).value") != 'lg'+tag: fail('약관 보고 오니 아이디가 날아감')
        print('약관 보고 와도 입력 유지 ok')

        # ---- 동의하면 가입되고, 서버에 동의 시각이 남는다 ----
        pg.fill('#lgName','하은'); pg.fill('#lgPass','secret1'); pg.check('#lgAgree')
        pg.click('[data-act="lg-submit"]'); pg.wait_for_selector('#gtTeam', timeout=10000)
        print('동의 후 가입 ok')
        n = os.popen("""cd %s && DATABASE_URL="postgres://postgres:pg@localhost:54329/postgres" node -e '
          import("pg").then(async ({default:pg})=>{const c=new pg.Client({connectionString:process.env.DATABASE_URL});
          await c.connect();const r=await c.query("select agreed_at is not null a, agreed_ver v from users where username=$1",["lg%s"]);
          console.log(r.rows[0]?(r.rows[0].a?"yes:"+r.rows[0].v:"no"):"nouser");await c.end()})' 2>/dev/null""" % (ROOT, tag)).read().strip()
        if not n.startswith('yes:'): fail('서버에 동의 기록이 없음: %s' % n)
        print('서버 동의 기록 ok:', n)

        # ---- 설정 앱 탭에 약관·사업자 정보 ----
        pg.fill('#gtTeam','약관팀'); pg.click('[data-act="team-create"]'); pg.wait_for_selector('.shell[data-page]', timeout=10000)
        pg.goto(URL + '#/settings'); pg.wait_for_selector('.setpane', timeout=8000)
        pg.click('[data-act="set-tab"][data-t="app"]'); pg.wait_for_timeout(600)
        st = pg.locator('.setpane').inner_text()
        if '469-06-03606' not in st: fail('설정에 사업자 정보가 없음')
        if '개인정보처리방침' not in st: fail('설정에 방침 링크가 없음')
        print('설정 약관·사업자 정보 ok')

        # ---- 약관 전에 가입한 사람에게 한 번 동의를 받는다 ----
        os.system("""cd %s && DATABASE_URL="postgres://postgres:pg@localhost:54329/postgres" node -e '
          import("pg").then(async ({default:pg})=>{const c=new pg.Client({connectionString:process.env.DATABASE_URL});
          await c.connect();await c.query("update users set agreed_at=null, agreed_ver=null where username=$1",["lg%s"]);
          await c.end()})' >/dev/null 2>&1""" % (ROOT, tag))
        pg.goto(URL + '#/home'); pg.reload(); pg.wait_for_selector('.shell[data-page]', timeout=10000); pg.wait_for_timeout(2500)
        if not pg.locator('#agChk').count(): fail('옛 사용자에게 재동의를 안 물음')
        pg.click('#agOk'); pg.wait_for_timeout(500)
        if '체크' not in pg.locator('#agErr').inner_text(): fail('체크 없이 동의가 통과됨')
        pg.check('#agChk'); pg.click('#agOk'); pg.wait_for_timeout(1200)
        if pg.locator('#agChk').count(): fail('동의했는데 창이 안 닫힘')
        got = os.popen("""cd %s && DATABASE_URL="postgres://postgres:pg@localhost:54329/postgres" node -e '
          import("pg").then(async ({default:pg})=>{const c=new pg.Client({connectionString:process.env.DATABASE_URL});
          await c.connect();const r=await c.query("select agreed_ver v from users where username=$1",["lg%s"]);
          console.log((r.rows[0]||{}).v||"none");await c.end()})' 2>/dev/null""" % (ROOT, tag)).read().strip()
        ver = pg.evaluate("CONTI.NET.user && CONTI.NET.user.legalVer")
        if got != ver: fail('재동의가 서버에 안 남음: %s (시행일 %s)' % (got, ver))
        print('옛 사용자 재동의 ok:', got)

        if errs: fail('JS 오류: %s' % errs[:3])
        print('errors:', errs)
        print('PASS test_legal')
        b.close()
run()
