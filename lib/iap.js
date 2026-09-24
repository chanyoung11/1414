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

// 구독을 살리는 사건과 끊는 사건. 그 밖(TEST, TRANSFER 등)은 무시한다.
// RevenueCat 사건의 뜻을 그대로 따른다:
//  - SUBSCRIPTION_PAUSED 는 '다음 갱신부터 멈춤' 예약이다. 이번 기간은 이미 냈으니 끊지 않는다 (끝나면 EXPIRATION 이 온다)
//  - 환불은 REFUND 라는 사건이 따로 없다. CANCELLATION 에 cancel_reason=CUSTOMER_SUPPORT 로 오고, 바로 끊는다.
//    (환불 없이 고객센터에서 해지만 했으면 만료 시각이 아직 남아 있다 → 기간 끝까지 둔다)
//    그냥 해지(UNSUBSCRIBE 등)는 기간 끝까지 쓰고 EXPIRATION 때 끊는다
//  - PRODUCT_CHANGE 의 product_id 는 옛 상품, new_product_id 가 새 상품이다. 올리는 변경만 바로 반영하고
//    내리는 변경은 다음 갱신(RENEWAL 의 product_id 가 새 상품)에 반영된다
const GRANT = new Set(['INITIAL_PURCHASE', 'RENEWAL', 'UNCANCELLATION', 'SUBSCRIPTION_EXTENDED', 'REFUND_REVERSED']);
const REVOKE = new Set(['EXPIRATION']);
const ONE_TIME = new Set(['NON_RENEWING_PURCHASE']);
const RANK = { pro: 1, plus: 2 };

// 웹훅 본문을 우리가 할 일로 바꾼다. DB 는 건드리지 않는다 (시험하기 쉽게)
export function planFromEvent(ev) {
  const type = String(ev && ev.type || '');
  const product = String(ev && (ev.product_id || ev.product_identifier) || '');
  const appUserId = String(ev && ev.app_user_id || '');
  // 같은 사건을 다시 보내도(응답이 늦으면 RevenueCat 이 재시도한다) 한 번만 더하려고 사건 id 를 넘긴다
  const eventId = String(ev && ev.id || '').slice(0, 200);
  // 어느 팀 몫인지: 앱은 사기 직전에 사용자 속성 teamId 를 남긴다 (Purchases.setAttributes({ teamId })).
  // 한 사람이 여러 팀의 인도자·결제 담당일 수 있어서다. 없으면 서버가 산 사람의 팀에서 고른다
  const attrs = (ev && typeof ev.subscriber_attributes === 'object' && ev.subscriber_attributes) || {};
  const teamId = String((attrs.teamId && attrs.teamId.value) || '').slice(0, 64);
  if (!appUserId) return { kind: 'ignore', why: '사용자를 알 수 없음' };

  if (ONE_TIME.has(type) && PRODUCT_CREDITS[product])
    return { kind: 'credits', appUserId, omr: PRODUCT_CREDITS[product], product, eventId, teamId, pick: 'new' };

  // 만료 시각은 RevenueCat 이 알려 준다. 없으면 상품 기간으로 계산한다
  const untilOf = (map) => (ev.expiration_at_ms ? new Date(+ev.expiration_at_ms)
    : new Date(Date.now() + map.months * 30 * 86400000));
  if (type === 'PRODUCT_CHANGE') {
    const next = String(ev.new_product_id || '');
    const to = PRODUCT_PLAN[next], from = PRODUCT_PLAN[product];
    if (!to) return { kind: 'ignore', why: '모르는 상품: ' + next };
    if (from && RANK[to.plan] <= RANK[from.plan]) return { kind: 'ignore', why: '내리는 변경은 다음 갱신 때 반영' };
    return { kind: 'grant', appUserId, plan: to.plan, until: untilOf(to), product: next };
  }
  const map = PRODUCT_PLAN[product];
  if (GRANT.has(type)) {
    if (!map) return { kind: 'ignore', why: '모르는 상품: ' + product };
    // 팀을 새로 고를 수 있는 것은 새로 산 것(INITIAL_PURCHASE)과 갱신(끊겼다 다시 산 것도 RENEWAL 로 온다)뿐이다.
    // 나머지(해지 취소·연장·환불 되돌림)와 변경·만료·환불은 이 구독이 이미 적힌 팀에만 반영한다
    const pick = type === 'INITIAL_PURCHASE' ? 'new' : type === 'RENEWAL' ? 'renew' : '';
    return { kind: 'grant', appUserId, plan: map.plan, until: untilOf(map), product, teamId, pick };
  }
  // 환불이면 만료 시각이 환불한 때(지금)로 온다. 만료가 아직 멀면 고객센터 해지일 뿐이니 기간 끝(EXPIRATION)까지 둔다
  const refund = type === 'CANCELLATION' && String(ev.cancel_reason || '') === 'CUSTOMER_SUPPORT'
    && !(+ev.expiration_at_ms > Date.now() + 60000);
  if (REVOKE.has(type) || refund) {
    // 크레딧 팩(소모품)의 환불·만료로 구독 플랜을 끊지 않는다
    if (PRODUCT_CREDITS[product]) return { kind: 'ignore', why: '크레딧 팩은 플랜과 무관' };
    return { kind: 'revoke', appUserId, product };
  }
  return { kind: 'ignore', why: '다루지 않는 사건: ' + type };
}
