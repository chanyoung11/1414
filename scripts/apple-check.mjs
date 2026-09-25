// 애플 토큰 되돌리기(lib/apple.js) 설정 확인 — 진짜 애플에 한 번 묻는다. 배포 전·키를 바꾼 뒤에 사람이 돌린다.
//
// 운영 키로 client_secret 을 만들어 아무 사용자의 것도 아닌 가짜 토큰을 /auth/revoke 로 보낸다.
// 애플은 client_secret 이 맞으면 없는 토큰에도 200(RFC 7009), 키·키 id·팀 id·client_id 가 안 맞으면 400 invalid_client 를 준다.
// 사용자 계정에는 아무 일도 없다. 앱(번들 id)과 웹(Services ID) 둘 다 본다.
//   set -a; . ./.env.cloudrun; set +a; node scripts/apple-check.mjs
import { appleRevokeConfigured, revokeAppleToken, appleBase } from '../lib/apple.js';

if (!appleRevokeConfigured()) {
  console.log('BAD APPLE_SIGNIN_KEY · APPLE_SIGNIN_KEY_ID · APPLE_SIGNIN_TEAM_ID 중 빠진 것이 있어요 (애플 토큰을 받지도 되돌리지도 않는다)');
  process.exit(1);
}
const clients = [['앱(번들 id)', process.env.APNS_BUNDLE_ID || 'com.lets1414.app'], ['웹(Services ID)', process.env.APPLE_SERVICE_ID]];
let bad = 0;
for (const [label, id] of clients) {
  if (!id) { console.log(`--  ${label}: 설정 없음 (건너뜀)`); continue; }
  const r = await revokeAppleToken({ token: 'apple-check-not-a-real-token', clientId: id });
  if (r.ok) console.log(`ok  ${label} ${id}: 애플이 client_secret 을 받았어요`);
  else { bad++; console.log(`BAD ${label} ${id}: ${r.error}` + (/invalid_client/.test(r.error || '') ? ' — 키가 이 client_id(주 App ID·Services ID)에 묶였는지, 키 id·팀 id 를 보세요' : '')); }
}
console.log(`(애플 주소 ${appleBase()})`);
process.exit(bad ? 1 : 0);
