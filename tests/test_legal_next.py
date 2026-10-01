# 약관·개인정보처리방침 개정 (2026-10-09 시행) — 지금 판 / 개정안 / 이전 판, 홈 알림, 계정 삭제 안내, 사업자 정보
#  - 시행일(LEGAL_NEXT_AT) 전: 지금 판(방침 2026-09-24 · 약관 2026-09-27) + '개정 예정' 띠 → 개정안(#/legal/privacy/next) · 바뀌는 점(#/legal/changes)
#  - 시행일(한국 시각)부터: 개정판이 저절로 지금 판 · 옛 판은 '이전 판'(#/legal/privacy/prev)
#  - 날짜는 window.CONTI_LEGAL_TODAY 로 정해 본다 (진짜 오늘이 언제든 같은 결과). 한국 시각 경계는 Playwright 시계로 따로 본다
#  - 홈 알림: 로그인한 사람에게 한 장, 닫으면 다시 안 뜸(계정마다), 시행일 7일 뒤에는 없음
#  - 계정 삭제 안내: 로그인 없이 열리고, 구독 해지 문단·30일 팀·소셜 계정 확인·메모 처리·결제 기록이 지금 동작대로
#  - 사업자 정보: 호스팅 서비스 제공자 줄 · 통신판매업 번호가 비면 줄을 숨김 · 로그인 화면 아래와 설정에 한 줄
#  - 앱(iOS 흉내)에서 보는 약관·방침에 '웹에서 코드를 넣는다'는 말이 없다 (App Store 3.1.1 — 앱에서 코드 칸을 일부러 뺐다)
#  CONTI_URL=http://localhost:9210/ CONTI_DB=postgres://... python tests/test_legal_next.py
import os, sys, re, time, json, subprocess
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
SRV = urlparse(URL)
DB = os.environ.get('CONTI_DB') or os.environ.get('DATABASE_URL') or 'postgres://postgres:pg@localhost:54329/postgres'
H = {'x-conti': '1'}
NEXT = '2026-10-09'
def fail(m): print('FAIL:', m); sys.exit(1)

def db(sql, params=()):
  js = """import('pg').then(async ({default:pg})=>{const c=new pg.Client({connectionString:process.env.DB});await c.connect();
    const r=await c.query(process.env.SQL, JSON.parse(process.env.PARAMS));console.log(JSON.stringify(r.rows));await c.end()})
    .catch(e=>{console.log(JSON.stringify({error:e.message}));process.exit(1)})"""
  out = subprocess.run(['node', '-e', js], cwd=ROOT, capture_output=True, text=True, env={**os.environ, 'DB': DB, 'SQL': sql, 'PARAMS': json.dumps(list(params))})
  if out.returncode != 0: fail('DB 실패 (CONTI_DB 확인): %s %s' % (out.stdout[-200:], out.stderr[-200:]))
  return json.loads(out.stdout.strip().splitlines()[-1])

# '웹에서 코드를 넣는다' 같은 말 — 앱에 보이면 App Store 3.1.1 (앱 밖 구매·잠금 해제 유도)과 부딪힌다
WEB_CODE = re.compile(r'(웹|lets1414\.com|브라우저)[^.。\n]{0,24}(프로모션 )?코드|코드[^.。\n]{0,16}(웹|lets1414\.com)에서')

def legal(pg, path, day=None):
  if day is not None: pg.evaluate("(d)=>{window.CONTI_LEGAL_TODAY=d}", day)
  # 같은 주소면 hashchange 가 없어 다시 그리지 않는다 → 날짜만 바꿔 볼 때는 직접 다시 그린다
  pg.evaluate("(h)=>{if(location.hash.replace(/^#\\/?/,'')===h.replace(/^#\\/?/,''))CONTI.render();else location.hash=h}", path); pg.wait_for_timeout(250)
  pg.wait_for_selector('.legal', timeout=10000)
  return {'text': pg.locator('.legal').inner_text(), 'at': pg.get_attribute('.legal', 'data-at'), 'doc': pg.get_attribute('.legal', 'data-doc'),
          'banner': pg.get_attribute('#legalBanner', 'data-state') if pg.locator('#legalBanner').count() else None,
          'title': pg.locator('header h1, .hd h1').first.inner_text() if pg.locator('header h1, .hd h1').count() else ''}

def run():
  tag = str(int(time.time()))[-6:]
  with sync_playwright() as p:
    b = p.chromium.launch(); errs = []

    # ================= 1) 시행일 전 (2026-10-02) — 로그인 없이 =================
    c = b.new_context(viewport={'width': 1180, 'height': 900})
    c.add_init_script("window.CONTI_LEGAL_TODAY='2026-10-02'")
    pg = c.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(URL + '#/legal/privacy'); pg.wait_for_selector('.legal', timeout=10000); pg.wait_for_timeout(400)
    if pg.evaluate("CONTI.legal.next") != NEXT: fail('개정 시행일 상수가 %s 가 아님: %s' % (NEXT, pg.evaluate("CONTI.legal.next")))
    if pg.evaluate("CONTI.legal.live()"): fail('10-02 인데 개정판이 지금 판으로 보임')
    cur = legal(pg, '#/legal/privacy')
    if cur['at'] != '2026-09-24': fail('시행 전 방침이 지금 판(2026-09-24)이 아님: %s' % cur['at'])
    if cur['banner'] != 'soon' or '개정 예정' not in cur['text'] or NEXT not in cur['text']: fail('지금 판에 개정 예정 띠가 없음: %s' % cur['banner'])
    if 'RevenueCat' in cur['text']: fail('시행 전인데 지금 판에 개정 내용(RevenueCat)이 들어감')
    if '시행일: 2026-09-24' not in cur['text']: fail('지금 판 시행일이 바뀜')
    if not pg.locator('#legalBanner [data-act="legal"][data-k="changes"]').count(): fail('띠에 바뀌는 점 단추가 없음')
    print('시행 전 지금 판(09-24) + 개정 예정 띠 ok')
    pg.click('#legalBanner [data-v="next"]'); pg.wait_for_timeout(500)
    if pg.evaluate("location.hash") != '#legal/privacy/next': fail('개정안 보기가 개정안 주소로 안 감: %s' % pg.evaluate("location.hash"))
    nx = {'text': pg.locator('.legal').inner_text(), 'at': pg.get_attribute('.legal', 'data-at'), 'banner': pg.get_attribute('#legalBanner', 'data-state')}
    if nx['at'] != NEXT or nx['banner'] != 'draft' or '개정안' not in nx['text']: fail('개정안 화면이 아님: %s %s' % (nx['at'], nx['banner']))
    t = nx['text']
    for must in ['RevenueCat, Inc.', 'compliance@revenuecat.com', 'privacyquestions@cloudflare.com', 'privacy@databricks.com', 'googlekrsupport@google.com',
                 '아시아·태평양', '싱가포르', 'Google Cloud Run', 'Neon', '암호화된 통신', '받는 곳의 보유 기간',
                 '처리하는 정보는 다음과 같습니다', '구글·Apple 로그인', '접속·보안', '팀 관리 기록', '결제 수단 정보는 받지 않습니다',
                 '회사 서버에는 저장하지 않습니다', "'나만 보기' 메모는 모두 지웁니다", '지워진 사용자', '90일', '30일이 지나면 지웁니다',
                 '스토어 영수증을 따로 보관하지 않으며', '파기 절차와 방법', '쿠키', '제3자 제공', '앱 접근 권한', '선택 권한', '10일 안에', '위임장',
                 '대표자 박찬영', '1833-6972', '118', '1301', '182', '같거나 그 이상의 수준', '학습', '변경 이력', '2026-09-15', '제정', '2026-09-17',
                 '웹 게시 2026-09-25', '호스팅 서비스 제공자', 'Google LLC (Google Cloud)', '주민등록번호를 받지 않습니다', '바디페인팅', '469-06-03606',
                 '계정을 지우면', '설정 › 개인정보 보호 및 보안 › 추적']:
      if must not in t: fail('개정 방침에 "%s" 없음' % must)
    if '실제로 저장하는 것은 다음이 전부' in t: fail('개정 방침에 "다음이 전부" 단정이 남음')
    if '5년' in t: fail('개정 방침에 사실과 다른 결제 5년 보관이 있음')
    if '통신판매업' in t: fail('신고번호가 비었는데 통신판매업 줄이 보임')
    cols = pg.locator('#xferTab thead th').count(); rows = pg.locator('#xferTab tbody tr').count()
    if cols != 6 or rows != 7: fail('국외 이전 표가 여섯 칸·일곱 줄이 아님: %d칸 %d줄' % (cols, rows))
    print('개정안 방침: RevenueCat·여섯 칸 표(연락처·나라·방법·보유 기간)·처리 항목·보유 기간·파기·쿠키·권한·권리·구제 기관·변경 이력 ok')
    pg.screenshot(path=os.path.join(ROOT, 'tests', 't_legal_next_privacy.png'), full_page=False)

    # 이용약관 개정안
    tv = legal(pg, '#/legal/terms/next')
    if tv['at'] != NEXT or tv['banner'] != 'draft': fail('약관 개정안이 아님: %s %s' % (tv['at'], tv['banner']))
    t = tv['text']
    for must in ['제2조의2 (약관의 게시와 변경)', '시행 7일 전부터', '구글·Apple 계정으로 가입', 'AI 결과는 틀리거나 빠진 부분이 있을 수 있습니다',
                 '연습 녹음', '곡 코드', '무료 체험을 받은 적 없는 계정으로 팀을 만들면', '7일 동안 Pro 플랜을 무료로 체험', '자동으로 결제되지 않습니다',
                 '자동 갱신되는 구독', '24시간 전까지 해지하지 않으면', 'Google Play 구독은', '다음 결제일 전까지 해지하지 않으면',
                 '이미 결제한 기간의 요금은 자동으로 돌아가지 않습니다', '남은 기간은 없어지고', '한 팀에 한 번만', '이어 붙습니다', '스토어 구독으로 유료인 팀에는 쓸 수 없습니다',
                 '무료 플랜으로 돌아갑니다', '제5조의2 (청약철회와 환불)', '7일 안에', '3개월 안', 'reportaproblem.apple.com', '저작권법 제103조',
                 '음란물', '구독 중이라면', '자동으로 해지되지 않습니다', "'나만 보기'로 쓴 메모", '고의 또는 과실 없이', '변경 이력', '2026-09-27', '제정',
                 '제1조', '저작권', '탈퇴', '바디페인팅', '호스팅 서비스 제공자']:
      if must not in t: fail('개정 약관에 "%s" 없음' % must)
    if '외부 서비스 장애' in t: fail('개정 약관에 외부 서비스 장애 일괄 면책이 남음')
    if '처음 팀을 만들면' in t: fail('개정 약관에 틀린 체험 조건("처음 팀을 만들면")이 남음')
    if WEB_CODE.search(t): fail('약관에 웹에서 코드를 넣으라는 말이 있음: %s' % WEB_CODE.search(t).group(0))
    tc = legal(pg, '#/legal/terms')
    if tc['at'] != '2026-09-27' or '시행일: 2026-09-27' not in tc['text'] or tc['banner'] != 'soon': fail('시행 전 약관 지금 판이 아님: %s %s' % (tc['at'], tc['banner']))
    print('개정안 약관: 제2조의2·가입·AI·체험·구독(애플/구글)·해지·코드·제5조의2·저작권 신고·유해물·탈퇴·면책 ok · 지금 판은 09-27 그대로')

    # 바뀌는 점
    ch = legal(pg, '#/legal/changes')
    if ch['doc'] != 'changes' or '바뀌는 점' not in ch['text'] or '10월 9일' not in ch['text']: fail('바뀌는 점 페이지가 아님')
    for must in ['RevenueCat', '제5조의2', '변경 이력 — 개인정보처리방침', '변경 이력 — 이용약관', '계정을 지워 이용을 끝낼 수 있습니다']:
      if must not in ch['text']: fail('바뀌는 점에 "%s" 없음' % must)
    if not pg.locator('.legal [data-act="legal"][data-k="privacy"][data-v="next"]').count(): fail('바뀌는 점에 개정 방침 단추가 없음')
    print('바뀌는 점 페이지 ok')
    c.close()

    # ================= 2) 시행일부터 — 개정판이 지금 판, 옛 판은 이전 판 =================
    c = b.new_context(viewport={'width': 1180, 'height': 900})
    c.add_init_script("window.CONTI_LEGAL_TODAY='%s'" % NEXT)
    pg = c.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(URL + '#/legal/privacy'); pg.wait_for_selector('.legal', timeout=10000); pg.wait_for_timeout(300)
    lv = legal(pg, '#/legal/privacy')
    if lv['at'] != NEXT or lv['banner'] != 'new' or 'RevenueCat' not in lv['text']: fail('시행일인데 개정판이 지금 판이 아님: %s %s' % (lv['at'], lv['banner']))
    if '(지금 판)' not in lv['text']: fail('변경 이력에 지금 판 표시가 없음')
    pv = legal(pg, '#/legal/privacy/prev')
    if pv['at'] != '2026-09-24' or pv['banner'] != 'prev' or '이전 판' not in pv['text'] or '(이전 판)' not in pv['title']: fail('이전 판이 안 보임: %s %s %s' % (pv['at'], pv['banner'], pv['title']))
    if 'RevenueCat' in pv['text']: fail('이전 판에 개정 내용이 섞임')
    tl = legal(pg, '#/legal/terms')
    if tl['at'] != NEXT or '제5조의2' not in tl['text']: fail('시행일인데 약관 개정판이 지금 판이 아님')
    tp = legal(pg, '#/legal/terms/prev')
    if tp['at'] != '2026-09-27' or tp['banner'] != 'prev': fail('약관 이전 판이 안 보임')
    # 이력에서 이전 판으로 가는 단추
    legal(pg, '#/legal/privacy')
    if not pg.locator('.lhist [data-v="prev"]').count(): fail('시행 뒤 변경 이력에 이전 판 보기 단추가 없음')
    # 시행 30일 뒤에는 '바뀌었습니다' 띠를 내린다 (이력에서는 그대로 이전 판을 볼 수 있다)
    late = legal(pg, '#/legal/privacy', '2026-11-20')
    if late['banner'] is not None or late['at'] != NEXT: fail('시행 한참 뒤에도 띠가 남음: %s' % late['banner'])
    print('시행일부터 개정판 = 지금 판 · 옛 판 = 이전 판 · 30일 뒤 띠 내림 ok')
    c.close()

    # ================= 3) 한국 시각 경계 =================
    c = b.new_context(); pg = c.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(URL + '#/legal/privacy'); pg.wait_for_selector('.legal', timeout=10000)
    k = pg.evaluate("[CONTI.legal.kst(Date.UTC(2026,9,8,14,59,59)),CONTI.legal.kst(Date.UTC(2026,9,8,15,0,0))]")
    if k != ['2026-10-08', '2026-10-09']: fail('한국 시각 날짜 계산이 틀림: %s' % k)
    c.close()
    for when, want in (('2026-10-08T14:59:00Z', '2026-09-24'), ('2026-10-08T15:00:30Z', NEXT)):
      c = b.new_context(); pg = c.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
      pg.clock.set_fixed_time(when)
      pg.goto(URL + '#/legal/privacy'); pg.wait_for_selector('.legal', timeout=10000); pg.wait_for_timeout(300)
      got = pg.get_attribute('.legal', 'data-at')
      if got != want: fail('%s(UTC) 에 보이는 방침이 %s 가 아님: %s' % (when, want, got))
      c.close()
    print('한국 시각 10-09 00:00 경계로 판이 바뀜 ok')

    # ================= 4) 계정 삭제 안내 (로그인 없이 · 지금 동작) =================
    c = b.new_context(viewport={'width': 390, 'height': 844}); pg = c.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(URL + '#/legal/delete'); pg.wait_for_selector('.legal', timeout=10000); pg.wait_for_timeout(300)
    t = pg.locator('.legal').inner_text()
    for must in ['구독 중이라면 먼저 해지하세요', '자동으로 해지되지 않습니다', 'apps.apple.com/account/subscriptions', 'play.google.com/store/account/subscriptions',
                 '비밀번호로 한 번 더 확인', '그 계정으로 한 번 더 로그인', 'Apple 로만 가입한 계정은 웹이나 아이폰에서',
                 '나 혼자만 있는 팀', '바로 지웁니다', '다른 팀원이 모두 비활성인 팀', '30일 뒤', '(일부 팀은 30일 뒤 지워집니다)',
                 "예배 메모, '나만 보기'로 쓴 메모", '지워진 사용자', 'RevenueCat', '결제와 사람의 연결을 끊습니다', '7일 안에', '호스팅 서비스 제공자']:
      if must not in t: fail('계정 삭제 안내에 "%s" 없음' % must)
    for bad in ['5년', '아이디와 비밀번호를 한 번 더 입력', '내가 유일한 인도자였다면', '내가 쓴 메모·개인 설정']:
      if bad in t: fail('계정 삭제 안내에 옛 문구 "%s" 가 남음' % bad)
    if WEB_CODE.search(t): fail('삭제 안내에 웹 코드 안내가 있음')
    if pg.evaluate("document.documentElement.scrollWidth>innerWidth+1"): fail('폰 너비에서 삭제 안내가 옆으로 넘침')
    pg.screenshot(path=os.path.join(ROOT, 'tests', 't_legal_delete.png'), full_page=True)
    # 폰 너비에서 여섯 칸 표가 넘치지 않고 칸 이름이 붙는다
    pg.evaluate("()=>{window.CONTI_LEGAL_TODAY='2026-10-02';location.hash='#/legal/privacy/next'}"); pg.wait_for_selector('#xferTab', timeout=8000); pg.wait_for_timeout(300)
    if pg.evaluate("document.documentElement.scrollWidth>innerWidth+1"): fail('폰 너비에서 국외 이전 표가 옆으로 넘침')
    lab = pg.evaluate("getComputedStyle(document.querySelector('#xferTab td[data-l]'),'::before').content")
    if '나라' not in (lab or ''): fail('폰에서 국외 이전 표 칸 이름이 안 붙음: %s' % lab)
    pg.screenshot(path=os.path.join(ROOT, 'tests', 't_legal_next_phone.png'), full_page=False)
    print('계정 삭제 안내(구독 해지·소셜 확인·30일 팀·메모·결제 연결) · 폰 너비 표 ok')
    c.close()

    # ================= 5) 로그인 화면·설정의 사업자 정보, 홈 알림 =================
    c = b.new_context(viewport={'width': 1180, 'height': 900})
    c.add_init_script("window.CONTI_LEGAL_TODAY='2026-10-02'")
    pg = c.new_page(); pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=10000); pg.wait_for_timeout(300)
    bl = pg.locator('#bizLine').inner_text() if pg.locator('#bizLine').count() else ''
    for must in ['바디페인팅', '대표 박찬영', '사업자등록번호 469-06-03606', '충청남도 천안시', '010-2445-0711', 'chanyoung07119@gmail.com', '호스팅 서비스 제공자 Google LLC (Google Cloud)']:
      if must not in bl: fail('로그인 화면 사업자 정보에 "%s" 없음: %s' % (must, bl))
    if '통신판매업' in bl: fail('신고번호가 비었는데 로그인 화면에 통신판매업이 보임')
    if pg.locator('#legalNotice').count(): fail('로그인하지 않았는데 개정 알림이 보임')
    print('로그인 화면 아래 사업자 정보 한 줄 ok')

    u = 'ln' + tag
    r = c.request.post(URL + 'api/auth/signup', headers=H, data={'username': u, 'password': 'secret1', 'name': '하은'})
    if not r.ok: fail('가입 실패: %s' % r.text()[:200])
    uid = r.json()['user']['id']
    r = c.request.post(URL + 'api/teams', headers=H, data={'name': '개정팀', 'myName': '하은', 'session': '인도자'})
    if not r.ok: fail('팀 만들기 실패: %s' % r.text()[:200])
    pg.goto(URL + '#/home'); pg.reload(); pg.wait_for_selector('.shell[data-page]', timeout=15000); pg.wait_for_timeout(1200)
    if not pg.locator('#legalNotice').count(): fail('로그인한 사람 홈에 개정 알림이 없음')
    nt = pg.locator('#legalNotice').inner_text()
    if '개인정보처리방침·이용약관이 10월 9일부터 바뀌어요' not in nt or '바뀌는 점 보기' not in nt: fail('개정 알림 문구가 다름: %s' % nt)
    if WEB_CODE.search(nt): fail('개정 알림에 웹 코드 안내가 있음')
    pg.screenshot(path=os.path.join(ROOT, 'tests', 't_legal_notice.png'))
    pg.click('#legalNotice [data-act="legal-notice-off"]'); pg.wait_for_timeout(500)
    if pg.locator('#legalNotice').count(): fail('닫았는데 개정 알림이 남음')
    pg.reload(); pg.wait_for_selector('.shell[data-page]', timeout=15000); pg.wait_for_timeout(1200)
    if pg.locator('#legalNotice').count(): fail('닫은 개정 알림이 다시 켜니 또 뜸')
    print('홈 개정 알림: 보임 · 닫기 · 다시 켜도 안 뜸 ok')
    # 이 기기에 다른 계정으로 들어오면 그 계정에는 뜬다 (닫기는 계정마다) → '바뀌는 점 보기'를 누르면 바뀌는 점으로 가고 다시 안 뜬다
    pg.evaluate("(k)=>localStorage.removeItem(k)", 'conti-legal-notice:%s:%s' % (NEXT, uid))
    pg.evaluate("()=>{CONTI.render()}"); pg.wait_for_timeout(500)
    if not pg.locator('#legalNotice').count(): fail('기억을 지웠는데 개정 알림이 안 뜸 (계정마다 기억하는 열쇠가 다름)')
    pg.click('#legalNotice [data-act="legal-notice-go"]'); pg.wait_for_timeout(600)
    if pg.evaluate("location.hash") != '#legal/changes' or '바뀌는 점' not in pg.locator('.legal').inner_text(): fail('바뀌는 점 보기가 바뀌는 점으로 안 감: %s' % pg.evaluate("location.hash"))
    pg.click('[data-act="legal-back"]'); pg.wait_for_timeout(600)
    if pg.locator('#legalNotice').count(): fail('바뀌는 점을 본 뒤에도 개정 알림이 남음')
    # 시행일 7일 뒤까지는 '바뀌었어요', 그 뒤에는 없음
    # (닫은 것은 이번 실행 동안 메모리에도 남으므로 다시 켠다)
    pg.evaluate("(k)=>localStorage.removeItem(k)", 'conti-legal-notice:%s:%s' % (NEXT, uid))
    pg.goto(URL + '#/home'); pg.reload(); pg.wait_for_selector('.shell[data-page]', timeout=15000); pg.wait_for_timeout(800)
    pg.evaluate("()=>{window.CONTI_LEGAL_TODAY='2026-10-16';CONTI.render()}"); pg.wait_for_timeout(600)
    lt = pg.locator('#legalNotice').inner_text() if pg.locator('#legalNotice').count() else ''
    if '10월 9일부터 바뀌었어요' not in lt: fail('시행 7일 뒤(10-16)에 바뀌었어요 알림이 안 보임: %s' % lt)
    pg.evaluate("()=>{window.CONTI_LEGAL_TODAY='2026-10-17';CONTI.render()}"); pg.wait_for_timeout(500)
    if pg.locator('#legalNotice').count(): fail('시행 8일 뒤에도 개정 알림이 남음')
    print('바뀌는 점 보기 → 바뀌는 점 · 시행 7일 뒤까지만 ok')

    # 설정 → 앱 의 사업자 정보 한 줄
    pg.evaluate("()=>{window.CONTI_LEGAL_TODAY='2026-10-02';location.hash='#/settings'}"); pg.wait_for_selector('.setpane', timeout=8000)
    pg.click('[data-act="set-tab"][data-t="app"]'); pg.wait_for_timeout(500)
    sb = pg.locator('#sBiz').inner_text() if pg.locator('#sBiz').count() else ''
    for must in ['바디페인팅', '대표 박찬영', '469-06-03606', '충청남도 천안시', '010-2445-0711', 'chanyoung07119@gmail.com', 'Google LLC (Google Cloud)']:
      if must not in sb: fail('설정 사업자 정보에 "%s" 없음: %s' % (must, sb))
    print('설정 → 앱 사업자 정보 한 줄 ok')

    # 약관 동의 창 문구 (item 19) — 동의 기록을 지우면 다시 묻는다
    db('update users set agreed_at=null, agreed_ver=null where id=$1', [uid])
    pg.goto(URL + '#/home'); pg.reload(); pg.wait_for_selector('#agChk', timeout=15000); pg.wait_for_timeout(300)
    mt = pg.locator('#modal').inner_text()
    if '이용약관과 개인정보처리방침을 확인하고 동의해 주세요' not in mt or '계속 쓰시려면' in mt: fail('동의 창 문구가 바뀌지 않음: %s' % mt[:200])
    pg.check('#agChk'); pg.click('#agOk'); pg.wait_for_timeout(800)
    print('동의 창 문구 ok')
    c.close()

    # ================= 6) 앱(iOS 흉내)에서 보는 문서 — 웹 코드 안내 없음 =================
    c = b.new_context(viewport={'width': 390, 'height': 844}, service_workers='block')
    def handler(route):
      u = urlparse(route.request.url)
      if u.scheme == 'https' and u.hostname == 'localhost' and u.port is None:
        try: return route.fulfill(response=route.fetch(url='%s://%s/%s' % (SRV.scheme, SRV.netloc, u.path.lstrip('/')) + ('?' + u.query if u.query else '')))
        except Exception:
          try: return route.abort()
          except Exception: return
      if u.hostname == SRV.hostname and u.port == SRV.port: return route.continue_()
      return route.abort()
    c.route('**/*', handler)
    c.add_init_script("""window.CONTI_LEGAL_TODAY='2026-10-02';window.Capacitor={getPlatform:()=>'ios',isNativePlatform:()=>true,isPluginAvailable:()=>false,
      Plugins:{App:{addListener:()=>Promise.resolve({remove(){}}),getLaunchUrl:()=>Promise.resolve(undefined),exitApp(){},getInfo:()=>Promise.resolve({})},SplashScreen:{hide:()=>Promise.resolve()}}};""")
    pg = c.new_page(); pg.on('pageerror', lambda e: errs.append('app: %s' % e))
    pg.goto('https://localhost/#/legal/terms/next'); pg.wait_for_selector('.legal', timeout=15000); pg.wait_for_timeout(400)
    if not pg.evaluate("/^(capacitor|ionic):/.test(location.protocol)||(location.hostname==='localhost'&&!location.port&&location.protocol==='https:')"): fail('앱 흉내가 안 됨')
    for path in ('#/legal/terms/next', '#/legal/privacy/next', '#/legal/terms', '#/legal/privacy', '#/legal/changes', '#/legal/delete'):
      t = legal(pg, path)['text']
      m = WEB_CODE.search(t)
      if m: fail('앱에서 %s 에 웹 코드 안내가 있음: %s' % (path, m.group(0)))
    if pg.evaluate("document.documentElement.scrollWidth>innerWidth+1"): fail('앱 폰 화면에서 문서가 옆으로 넘침')
    print('앱(iOS)에서 보는 약관·방침·바뀌는 점·삭제 안내에 웹 코드 안내 없음 ok')
    c.close()

    if errs: fail('JS 오류: %s' % errs[:3])
    print('PASS test_legal_next')
    b.close()
run()
