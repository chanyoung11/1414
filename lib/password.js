// 비밀번호 해시: Node 내장 scrypt. 저장 형식 "scrypt$N$salt$hash" (base64url)
import crypto from 'node:crypto';
import os from 'node:os';
import { promisify } from 'node:util';

const N = 16384, r = 8, p = 1, KEYLEN = 32;
// scryptSync 는 한 번에 수십 ms 동안 이벤트 루프를 세운다. Cloud Run 은 한 프로세스가 요청 80개를 같이 받으니
// 로그인·가입이 몰리면 다른 요청이 전부 기다렸다 → 스레드 풀에서 도는 비동기 scrypt 를 쓴다.
// 이름에 Async 를 붙여 둔다. await 를 빠뜨리면 Promise 가 참으로 읽혀 !verify… 검사가 그냥 통과해 버린다
const scryptRaw = promisify(crypto.scrypt);

// 스레드 풀(기본 4개)은 API 응답 gzip·DNS 조회(Neon·R2 새 연결)·파일 읽기도 같이 쓴다. 해시를 그냥 다 걸면
// 가입 64개가 풀을 다 차지해, 1KB 넘는 응답(/api/me·곡 목록…)의 gzip 이 해시 줄 맨 뒤에서 0.4~0.5초를 기다렸다
// (Cloud Run 1 vCPU 에 80개면 2초 가까이 — 이벤트 루프가 서던 것이 풀 대기로 옮겨 갔을 뿐이었다).
// 동시에 도는 해시를 1~2개로 묶어 풀에 늘 빈 스레드를 남긴다. 해시는 CPU 만 쓰니 코어보다 많이 돌려 봐야 빨라지지도 않는다
const MAX_RUN = Math.max(1, Math.min(2, (os.availableParallelism ? os.availableParallelism() : os.cpus().length) - 1));
let running = 0;
const waiting = [];
async function scrypt(...a) {
  if (running < MAX_RUN) running++;
  else await new Promise((res) => waiting.push(res));   // 끝난 쪽이 자리를 그대로 넘겨준다 (running 은 그대로)
  try { return await scryptRaw(...a); }
  finally { const next = waiting.shift(); if (next) next(); else running--; }
}

export async function hashPasswordAsync(pw) {
  const salt = crypto.randomBytes(16);
  const key = await scrypt(pw, salt, KEYLEN, { N, r, p });
  return `scrypt$${N}$${salt.toString('base64url')}$${key.toString('base64url')}`;
}

export async function verifyPasswordAsync(pw, stored) {
  try {
    const [algo, n, salt, hash] = String(stored).split('$');
    if (algo !== 'scrypt') return false;
    const want = Buffer.from(hash, 'base64url');
    if (!want.length) return false;
    const got = await scrypt(pw, Buffer.from(salt, 'base64url'), want.length, { N: +n, r, p });
    return got.length === want.length && crypto.timingSafeEqual(got, want);
  } catch { return false; }
}

export const USERNAME_RE = /^[a-z0-9][a-z0-9._-]{2,19}$/;   // 3~20자, 영문 소문자·숫자·._-
export const PASSWORD_MIN = 6;
