// 안전한 Blob 정리: DB(blobs 테이블)가 참조하는 파일은 절대 지우지 않고, 어디에도 없는 고아 파일만 지운다.
// 사용:  node scripts/blob-gc.mjs             → 목록만 보여줌 (기본이 dry-run)
//        node scripts/blob-gc.mjs --delete    → 실제 삭제. 아래 안전장치를 모두 통과해야만 지운다
// 안전장치 (2026-09-06 전체 삭제 사고 재발 방지):
//   1) DB와 스토어가 같은 환경이어야 한다 — DATABASE_URL 호스트에 BLOB_GC_DB_HOST(기본 'neon.tech')가 들어 있어야 함.
//      로컬 Docker DB + 운영 토큰 조합이면 운영 파일 전부가 고아로 보이므로 여기서 멈춘다.
//   2) 참조된 파일이 0개면 중단 (DB를 잘못 가리키고 있다는 신호)
//   3) 고아 비율이 50%를 넘으면 --force 없이는 중단
//   4) 최근 24시간 안에 올라온 파일은 건드리지 않는다 (DB 스냅샷 뒤에 올라온 파일을 지우는 경합 방지)
import pg from 'pg';
import { list, del } from '@vercel/blob';

const args = process.argv.slice(2);
const doDelete = args.includes('--delete');
const force = args.includes('--force');
const url = process.env.DATABASE_URL || process.env.POSTGRES_URL;
if (!url || !process.env.BLOB_READ_WRITE_TOKEN) { console.error('DATABASE_URL, BLOB_READ_WRITE_TOKEN 필요'); process.exit(1); }
const needHost = process.env.BLOB_GC_DB_HOST || 'neon.tech';
const host = (() => { try { return new URL(url).host; } catch { return ''; } })();
if (!host.includes(needHost)) { console.error(`중단: DATABASE_URL 호스트(${host || '?'})가 '${needHost}'가 아니에요. 스토어와 다른 DB를 보고 있을 가능성이 큽니다. 의도한 것이면 BLOB_GC_DB_HOST=${host || '<host>'} 로 명시하세요.`); process.exit(2); }

const c = new pg.Client({ connectionString: url, ssl: /neon\.tech|sslmode=require/.test(url) ? { rejectUnauthorized: false } : undefined });
await c.connect();
const rows = (await c.query('select url, pathname from blobs')).rows;
await c.end();
const keepUrl = new Set(rows.map((r) => r.url));
const keepPath = new Set(rows.map((r) => r.pathname).filter(Boolean));

const RECENT_MS = 24 * 3600 * 1000;
let cursor, kept = 0, recent = 0, total = 0; const orphans = [];
do {
  const page = await list({ cursor, limit: 1000 });
  cursor = page.cursor;
  for (const b of page.blobs) {
    total++;
    if (keepUrl.has(b.url) || keepPath.has(b.pathname)) { kept++; continue; }
    if (b.uploadedAt && Date.now() - new Date(b.uploadedAt).getTime() < RECENT_MS) { recent++; continue; }
    orphans.push(b);
  }
} while (cursor);
const missing = rows.filter((r) => r.url && !r.url.startsWith('mock:')).length - kept;
console.log(`스토어 파일 ${total}개 · DB 참조 ${rows.length}건 · 참조돼 유지 ${kept} · 최근 24시간 내라 보류 ${recent} · 고아(삭제 대상) ${orphans.length}${missing > 0 ? ` · DB에는 있는데 스토어에 없는 파일 ${missing}개(복구 필요)` : ''}`);
for (const b of orphans.slice(0, 20)) console.log('  고아:', b.pathname, Math.round(b.size / 1024) + 'KB', b.uploadedAt);
if (orphans.length > 20) console.log(`  … 외 ${orphans.length - 20}개`);

if (!orphans.length) { console.log('지울 파일이 없어요'); process.exit(0); }
if (!doDelete) { console.log('(dry-run: 실제로 지우려면 --delete)'); process.exit(0); }
if (kept === 0) { console.error('중단: 참조된 파일이 하나도 없어요. DB를 잘못 보고 있을 가능성이 큽니다'); process.exit(3); }
if (orphans.length / total > 0.5 && !force) { console.error(`중단: 고아 비율이 ${Math.round(orphans.length / total * 100)}%예요. 정말 맞으면 --force 를 붙이세요`); process.exit(4); }
await del(orphans.map((b) => b.url));
console.log(`고아 파일 ${orphans.length}개 삭제 완료`);
