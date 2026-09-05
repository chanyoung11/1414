// 안전한 Blob 정리: DB의 services/drafts/blobs에서 참조되는 파일은 절대 지우지 않고,
// 그 어디에도 없는 고아 파일만 삭제한다. 사용: node scripts/blob-gc.mjs [--dry]
import pg from 'pg';
import { list, del } from '@vercel/blob';
const dry = process.argv.includes('--dry');
const url = process.env.DATABASE_URL || process.env.POSTGRES_URL;
if (!url || !process.env.BLOB_READ_WRITE_TOKEN) { console.error('DATABASE_URL, BLOB_READ_WRITE_TOKEN 필요'); process.exit(1); }
const c = new pg.Client({ connectionString: url, ssl: /neon\.tech|sslmode=require/.test(url) ? { rejectUnauthorized: false } : undefined });
await c.connect();
const rows = (await c.query('select url, pathname from blobs')).rows;
const keepUrl = new Set(rows.map(r => r.url));
const keepPath = new Set(rows.map(r => r.pathname).filter(Boolean));
await c.end();
let cursor, orphans = [], kept = 0;
do {
  const page = await list({ cursor, limit: 1000 });
  cursor = page.cursor;
  for (const b of page.blobs) {
    if (keepUrl.has(b.url) || keepPath.has(b.pathname)) { kept++; continue; }
    orphans.push(b.url);
  }
} while (cursor);
console.log(`참조됨(유지): ${kept} · 고아(삭제 대상): ${orphans.length}`);
if (orphans.length && !dry) { await del(orphans); console.log('고아 파일 삭제 완료'); }
else if (dry) console.log('(--dry: 삭제 안 함)');
