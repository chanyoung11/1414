// 인앱결제 (RevenueCat 웹훅).
// 애플·구글의 영수증 검증·갱신·환불은 RevenueCat 이 처리하고, 결과만 우리 서버로 온다.
// 우리가 하는 일은 "이 사용자의 팀을 어떤 플랜으로 언제까지 둘 것인가" 뿐이다.
//
// 필요한 환경변수:
//   RC_WEBHOOK_SECRET  웹훅 Authorization 헤더와 대조할 값 (RevenueCat 대시보드에서 지정)
//
// 상품 id → 플랜. 스토어에 등록한 id 와 같아야 한다
export const PRODUCT_PLAN = {
  pro_monthly: { plan: 'pro', months: 1 },
  pro_yearly: { plan: 'pro', months: 12 },
  plus_monthly: { plan: 'plus', months: 1 },
  plus_yearly: { plan: 'plus', months: 12 },
};
// 크레딧 팩(채보 충전). 소모품이라 갱신이 없다
export const PRODUCT_CREDITS = {
  credits_30: 30,
  credits_100: 100,
};

export const rcConfigured = () => !!process.env.RC_WEBHOOK_SECRET;

// RevenueCat 은 대시보드에서 정한 값을 Authorization 헤더에 그대로 넣어 보낸다
export function rcAuthOk(req) {
  const want = process.env.RC_WEBHOOK_SECRET || '';
  if (!want) return false;
  const got = String(req.headers.authorization || '');
  if (got.length !== want.length) return false;
  let diff = 0;
  for (let i = 0; i < want.length; i++) diff |= got.charCodeAt(i) ^ want.charCodeAt(i);
  return diff === 0;
}

// 구독을 살리는 사건과 끊는 사건. 그 밖(TEST, TRANSFER 등)은 무시한다
const GRANT = new Set(['INITIAL_PURCHASE', 'RENEWAL', 'UNCANCELLATION', 'PRODUCT_CHANGE', 'SUBSCRIPTION_EXTENDED']);
const REVOKE = new Set(['EXPIRATION', 'REFUND', 'SUBSCRIPTION_PAUSED']);
const ONE_TIME = new Set(['NON_RENEWING_PURCHASE']);

// 웹훅 본문을 우리가 할 일로 바꾼다. DB 는 건드리지 않는다 (시험하기 쉽게)
export function planFromEvent(ev) {
  const type = String(ev && ev.type || '');
  const product = String(ev && (ev.product_id || ev.product_identifier) || '');
  const appUserId = String(ev && ev.app_user_id || '');
  if (!appUserId) return { kind: 'ignore', why: '사용자를 알 수 없음' };

  if (ONE_TIME.has(type) && PRODUCT_CREDITS[product])
    return { kind: 'credits', appUserId, omr: PRODUCT_CREDITS[product], product };

  const map = PRODUCT_PLAN[product];
  if (GRANT.has(type)) {
    if (!map) return { kind: 'ignore', why: '모르는 상품: ' + product };
    // 만료 시각은 RevenueCat 이 알려 준다. 없으면 상품 기간으로 계산한다
    const until = ev.expiration_at_ms ? new Date(+ev.expiration_at_ms)
      : new Date(Date.now() + map.months * 30 * 86400000);
    return { kind: 'grant', appUserId, plan: map.plan, until, product };
  }
  if (REVOKE.has(type)) return { kind: 'revoke', appUserId, product };
  return { kind: 'ignore', why: '다루지 않는 사건: ' + type };
}
