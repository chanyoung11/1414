// 비밀번호 해시: Node 내장 scrypt. 저장 형식 "scrypt$N$salt$hash" (base64url)
import crypto from 'node:crypto';

const N = 16384, r = 8, p = 1, KEYLEN = 32;

export function hashPassword(pw) {
  const salt = crypto.randomBytes(16);
  const key = crypto.scryptSync(pw, salt, KEYLEN, { N, r, p });
  return `scrypt$${N}$${salt.toString('base64url')}$${key.toString('base64url')}`;
}

export function verifyPassword(pw, stored) {
  try {
    const [algo, n, salt, hash] = String(stored).split('$');
    if (algo !== 'scrypt') return false;
    const want = Buffer.from(hash, 'base64url');
    const got = crypto.scryptSync(pw, Buffer.from(salt, 'base64url'), want.length, { N: +n, r, p });
    return got.length === want.length && crypto.timingSafeEqual(got, want);
  } catch { return false; }
}

export const USERNAME_RE = /^[a-z0-9][a-z0-9._-]{2,19}$/;   // 3~20자, 영문 소문자·숫자·._-
export const PASSWORD_MIN = 6;
