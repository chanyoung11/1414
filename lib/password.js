// 비밀번호 해시: Node 내장 scrypt. 저장 형식 "scrypt$N$salt$hash" (base64url)
import crypto from 'node:crypto';
import { promisify } from 'node:util';

const N = 16384, r = 8, p = 1, KEYLEN = 32;
// scryptSync 는 한 번에 수십 ms 동안 이벤트 루프를 세운다. Cloud Run 은 한 프로세스가 요청 80개를 같이 받으니
// 로그인·가입이 몰리면 다른 요청이 전부 기다렸다 → 스레드 풀에서 도는 비동기 scrypt 를 쓴다.
// 이름에 Async 를 붙여 둔다. await 를 빠뜨리면 Promise 가 참으로 읽혀 !verify… 검사가 그냥 통과해 버린다
const scrypt = promisify(crypto.scrypt);

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
