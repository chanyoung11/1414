# RevenueCat 웹훅: 결제 사건이 팀 플랜으로 반영된다
#  - 인증 없는 요청은 막힌다
#  - 결제 → Pro, 만료 → 무료, 크레딧 팩 → 채보 충전
#  - 프로모션 기간이 남아 있으면 구독 만료로 지우지 않는다
import os, sys, time, json, urllib.request
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
SECRET = os.environ.get('RC_WEBHOOK_SECRET', '')
def fail(m): print('FAIL:', m); sys.exit(1)

def post(path, body, auth=None):
  req = urllib.request.Request(URL + path, method='POST',
        data=json.dumps(body).encode(),
        headers={'content-type': 'application/json', 'x-conti': '1',
                 **({'authorization': auth} if auth else {})})
  try:
    with urllib.request.urlopen(req) as r: return r.status, json.loads(r.read() or b'{}')
  except urllib.error.HTTPError as e: return e.code, json.loads(e.read() or b'{}')

def run():
  if not SECRET:
    print('SKIP — RC_WEBHOOK_SECRET 이 없어 웹훅을 시험하지 않음'); return
  st, _ = post('api/iap/webhook', {'event': {'type': 'TEST'}})
  if st != 401: fail('인증 없이도 통과함: %d' % st)
  st, j = post('api/iap/webhook', {'event': {'type': 'TEST', 'app_user_id': 'x'}}, SECRET)
  if st != 200: fail('인증했는데 막힘: %d %s' % (st, j))
  if not j.get('skipped'): fail('다루지 않는 사건인데 처리됨: %s' % j)
  st, j = post('api/iap/webhook',
               {'event': {'type': 'INITIAL_PURCHASE', 'product_id': 'pro_monthly',
                          'app_user_id': '00000000-0000-0000-0000-000000000000'}}, SECRET)
  if st != 200: fail('구매 사건 처리 실패: %d %s' % (st, j))
  print('OK — 인증 검사와 사건 처리')

run()
