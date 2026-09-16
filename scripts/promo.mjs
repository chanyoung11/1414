// 프로모션 코드 만들기·보기
//   node scripts/promo.mjs new --plan pro --days 30 --uses 1 --note "카톡 홍보"
//   node scripts/promo.mjs new --code WELCOME --days 30 --uses 100
//   node scripts/promo.mjs list
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
for (const line of (fs.existsSync(path.join(root, '.env.local')) ? fs.readFileSync(path.join(root, '.env.local'), 'utf8').split('\n') : [])) {
  const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)$/); if (m && !process.env[m[1]]) process.env[m[1]] = m[2].replace(/^["']|["']$/g, '');
}
const { q } = await import(path.join(root, 'lib', 'db.js'));
const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const cmd = process.argv[2] || 'list';

// 헷갈리는 글자(0/O, 1/I)는 뺀다
const gen = (n = 8) => Array.from(crypto.randomBytes(n)).map((b) => 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'[b % 32]).join('');

if (cmd === 'new') {
  const code = (arg('code') || gen()).toUpperCase();
  const plan = arg('plan', 'pro'), days = +arg('days', 30), uses = +arg('uses', 1), note = arg('note', '');
  if (!['pro', 'plus'].includes(plan)) { console.error('plan 은 pro 또는 plus'); process.exit(1); }
  await q('insert into promo_codes(code, plan, days, max_uses, note) values($1,$2,$3,$4,$5)', [code, plan, days, uses, note]);
  console.log(`만들었습니다 — ${code}  (${plan} ${days}일 · ${uses}회 · ${note})`);
} else {
  const rows = await q('select code, plan, days, used, max_uses, note, created_at from promo_codes order by created_at desc limit 50');
  if (!rows.length) console.log('(코드 없음)');
  rows.forEach((r) => console.log(`${r.code.padEnd(10)} ${r.plan.padEnd(5)} ${String(r.days).padStart(3)}일  ${r.used}/${r.max_uses}  ${r.note || ''}`));
}
process.exit(0);
