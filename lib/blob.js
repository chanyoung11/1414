// 악보·녹음 파일 저장소.
//
// 두 곳을 쓴다.
//   - Cloudflare R2 (S3 호환) — 지금 올리는 파일. 내려받기(egress)가 공짜라 악보를 자주 보는 우리 앱에 맞다
//   - Vercel Blob — 예전에 올린 파일. 읽기만 한다 (2026-09-19 무료 한도 초과로 멈춘 그 저장소)
// R2 환경변수 네 개가 모두 있으면 R2 로 쓰고, 없으면 예전처럼 Vercel Blob 으로 쓴다.
// 읽을 때는 주소를 보고 어느 쪽인지 가른다 — 옮기는 동안 둘이 섞여 있어도 된다.
import { q } from './db.js';

const ACCESS = process.env.BLOB_ACCESS === 'public' ? 'public' : 'private';
// 로컬 개발·테스트는 저장소를 아예 건드리지 않는다.
// (2026-09-19: 테스트가 운영 토큰으로 올려 쓰레기 파일 1,700개가 쌓였다)
const LOCAL = process.env.BLOB_LOCAL_DIR || null;
const LOCAL_BASE = (process.env.BLOB_LOCAL_BASE || `http://localhost:${process.env.PORT || 8766}`).replace(/\/+$/, '');
const localUrl = (key) => `${LOCAL_BASE}/localblob/${key}`;
const isLocal = (url) => !!LOCAL && String(url || '').startsWith(LOCAL_BASE + '/localblob/');
const localKey = (url) => decodeURIComponent(String(url).slice((LOCAL_BASE + '/localblob/').length));
async function localPath(key) {
  const path = await import('node:path');
  const f = path.join(LOCAL, key);
  if (!f.startsWith(path.resolve(LOCAL))) throw new Error('경로가 이상해요');
  return f;
}
const R2 = (process.env.R2_ENDPOINT && process.env.R2_ACCESS_KEY_ID && process.env.R2_SECRET_ACCESS_KEY && process.env.R2_BUCKET)
  ? { endpoint: process.env.R2_ENDPOINT.replace(/\/+$/, ''), bucket: process.env.R2_BUCKET,
      accessKeyId: process.env.R2_ACCESS_KEY_ID, secretAccessKey: process.env.R2_SECRET_ACCESS_KEY }
  : null;

export class BlobDownError extends Error {}
const asDown = (e) => {
  // 저장소가 멎었을 때(요금제·정지) 알아볼 수 있게 바꿔 던진다
  if (/suspend|store has been|not\s*active|billing/i.test(String(e && e.message))) return new BlobDownError('악보 저장소가 잠시 멈췄어요. 잠시 뒤에 다시 시도해 주세요');
  return e;
};

/* ---------------- Cloudflare R2 ---------------- */
const isR2 = (url) => !!R2 && String(url || '').startsWith(R2.endpoint + '/' + R2.bucket + '/');
const r2Url = (key) => `${R2.endpoint}/${R2.bucket}/${key}`;
const r2Key = (url) => decodeURIComponent(String(url).slice((R2.endpoint + '/' + R2.bucket + '/').length));
let _client = null;
async function r2Client() {
  if (_client) return _client;
  const { S3Client } = await import('@aws-sdk/client-s3');
  _client = new S3Client({ region: 'auto', endpoint: R2.endpoint,
    credentials: { accessKeyId: R2.accessKeyId, secretAccessKey: R2.secretAccessKey } });
  return _client;
}
// 같은 이름으로 다시 올려도 옛 파일을 덮지 않게 뒤에 짧은 무작위 글자를 붙인다 (Vercel Blob 과 같은 방식)
const withSuffix = (pathname) => {
  const rnd = Math.random().toString(36).slice(2, 10);
  const i = pathname.lastIndexOf('.');
  return i > 0 ? `${pathname.slice(0, i)}-${rnd}${pathname.slice(i)}` : `${pathname}-${rnd}`;
};

/* ---------------- 올리기 ---------------- */
export async function putBlob(pathname, body, contentType) {
  const type = contentType || 'application/octet-stream';
  if (LOCAL) {
    const fs = await import('node:fs/promises'); const path = await import('node:path');
    const key = withSuffix(pathname); const f = await localPath(key);
    await fs.mkdir(path.dirname(f), { recursive: true });
    await fs.writeFile(f, body);
    await fs.writeFile(f + '.type', type);
    return { url: localUrl(key), pathname: key };
  }
  if (R2) {
    const { PutObjectCommand } = await import('@aws-sdk/client-s3');
    const key = withSuffix(pathname);
    try {
      await (await r2Client()).send(new PutObjectCommand({ Bucket: R2.bucket, Key: key, Body: body, ContentType: type }));
      return { url: r2Url(key), pathname: key };
    } catch (e) { throw asDown(e); }
  }
  const { put } = await import('@vercel/blob');
  try {
    const r = await put(pathname, body, { access: ACCESS, addRandomSuffix: true, contentType: type });
    return { url: r.url, pathname: r.pathname };
  } catch (e) { throw asDown(e); }
}

// 브라우저가 저장소로 바로 올릴 수 있는 서명 URL (서버리스 본문 한도 4.5MB를 우회)
// size 를 서명에 넣어 알린 크기와 다른 파일은 저장소가 받지 않게 한다. 전에는 크기가 참고용일 뿐이라
// 한도를 넘는 파일도 올라갔고, 1KB 로 등록한 뒤 같은 URL 로 몇 GB 를 덮어쓸 수도 있었다.
// 받자마자 올리니 URL 은 10분만 산다. 등록까지 안 하고 버린 파일은 하루 뒤 크론이 치운다(blob_trash)
export async function presignPut(pathname, contentType, minutes = 10, size = 0) {
  const validUntil = Date.now() + minutes * 60 * 1000;
  // 로컬 개발 서버(scripts/dev.mjs)는 서명 대신 len 으로 같은 검사를 한다
  if (LOCAL) { await remember([localUrl(pathname)], PENDING_HOURS); return { url: localUrl(pathname) + (size ? `?len=${size}` : ''), pathname, validUntil }; }
  if (R2) {
    const { PutObjectCommand } = await import('@aws-sdk/client-s3');
    const { getSignedUrl } = await import('@aws-sdk/s3-request-presigner');
    try {
      // 같은 파일을 다시 올릴 수 있어야 한다(초안 저장 뒤 발행, 복구용 강제 재업로드) → 이름을 그대로 쓴다
      const url = await getSignedUrl(await r2Client(),
        new PutObjectCommand({ Bucket: R2.bucket, Key: pathname, ContentType: contentType, ...(size ? { ContentLength: size } : {}) }),
        { expiresIn: minutes * 60 });
      await remember([r2Url(pathname)], PENDING_HOURS);
      return { url, pathname, validUntil, publicUrl: r2Url(pathname) };
    } catch (e) { throw asDown(e); }
  }
  const { issueSignedToken, presignUrl } = await import('@vercel/blob');
  const opts = { pathname, validUntil, access: ACCESS, contentType, addRandomSuffix: false, allowOverwrite: true };
  try {
    const tok = await issueSignedToken({ operations: ['put'], ...opts });
    const p = await presignUrl(tok, { operation: 'put', ...opts });
    return { url: p.presignedUrl || p.url, pathname, validUntil };
  } catch (e) { throw asDown(e); }
}

/* ---------------- 지우기 ---------------- */
// 저장소에서 바로 지운다. 못 지운 주소를 돌려준다
// R2 의 DeleteObjects 는 한 번에 1,000개까지다. 전에는 전부 한 번에 보내서, 파일이 1,000개 넘는 팀을 지우면
// 요청이 통째로 거절되고 기록만 사라져 파일이 영영 남았다. 200 으로 와도 키마다 실패(Errors)가 있을 수 있다
async function removeNow(urls) {
  const failed = [];
  if (LOCAL) {
    const fs = await import('node:fs/promises');
    for (const u of urls) {
      if (!isLocal(u)) continue;
      try {
        const f = await localPath(localKey(u));
        await fs.unlink(f).catch((e) => { if (e.code !== 'ENOENT') throw e; });
        await fs.unlink(f + '.type').catch(() => {});
      } catch (e) { failed.push(u); }
    }
    return failed;
  }
  const mine = urls.filter(isR2), theirs = urls.filter((u) => !isR2(u));
  for (let i = 0; i < mine.length; i += 1000) {
    const chunk = mine.slice(i, i + 1000);
    try {
      const { DeleteObjectsCommand } = await import('@aws-sdk/client-s3');
      const r = await (await r2Client()).send(new DeleteObjectsCommand({ Bucket: R2.bucket,
        Delete: { Objects: chunk.map((u) => ({ Key: r2Key(u) })), Quiet: true } }));
      const bad = new Set((r.Errors || []).map((x) => x.Key));
      if (bad.size) console.error('r2 del', bad.size, (r.Errors[0].Code || '') + ' ' + (r.Errors[0].Message || ''));
      for (const u of chunk) if (bad.has(r2Key(u))) failed.push(u);
    } catch (e) { console.error('r2 del', e.message); failed.push(...chunk); }
  }
  for (let i = 0; i < theirs.length; i += 500) {
    const chunk = theirs.slice(i, i + 500);
    try { const { del } = await import('@vercel/blob'); await del(chunk); }
    catch (e) { console.error('blob del', e.message); failed.push(...chunk); }
  }
  return failed;
}

// 저장소에서 못 지운 것은 blob_trash 에 적어 두고 크론이 다시 지운다. 부르는 쪽은 DB 행을 먼저 지우기도 하므로
// 여기서 놓치면 파일이 아무 기록 없이 영영 남는다
export async function delBlobs(urls) {
  if (!urls.length) return;
  const failed = await removeNow(urls);
  if (failed.length) await remember(failed, 0);
}

/* ---------------- 치울 목록 (blob_trash) ---------------- */
const PENDING_HOURS = 24, MAX_TRIES = 30;
// 적지 못해도 요청은 그대로 간다 (로그만 남긴다)
// hours > 0 은 직접 업로드용 예약: 같은 이름을 다시 받으면 기한을 다시 미룬다. 0 은 지우다 실패한 것
async function remember(urls, hours) {
  const list = [...new Set(urls)].filter((u) => /^https?:\/\//.test(u));   // 'mock:' 같은 가짜 주소는 지울 곳이 없다
  if (!list.length) return;
  try {
    await q(`insert into blob_trash(url, due_at) select u, now() + make_interval(hours => $2::int) from unnest($1::text[]) as u
             on conflict (url) do ${hours ? 'update set due_at = excluded.due_at, tries = 0' : 'nothing'}`, [list, hours]);
  } catch (e) { console.error('blob_trash', e.message); }
}
const keyOf = (u) => (isR2(u) ? r2Key(u) : isLocal(u) ? localKey(u) : null);
// 이 프로세스가 지울 수 있는 곳의 주소만 건드린다 (로컬 서버가 운영 주소를, 토큰 없이 Vercel 을 지우려 들지 않게)
const deletablePrefixes = () => (LOCAL ? [LOCAL_BASE + '/localblob/']
  : [R2 && `${R2.endpoint}/${R2.bucket}/`, process.env.BLOB_READ_WRITE_TOKEN && 'https://'].filter(Boolean));

// 크론(/cron/dates)이 하루 한 번 부른다. 기한이 지난 것을 지우되, blobs 가 가리키는 파일은 살아 있는 것이라
// 지우지 않고 목록에서만 뺀다 (같은 id 로 다시 올려 등록한 경우 — 직접 업로드는 이름이 같다)
export async function sweepBlobs(limit = 3000) {
  const pre = deletablePrefixes();
  const rows = await q(`select url from blob_trash where due_at <= now() and tries < $1
                          and exists (select 1 from unnest($3::text[]) p where starts_with(url, p))
                        order by due_at limit $2`, [MAX_TRIES, limit, pre]);
  const urls = rows.map((r) => r.url).filter((u) => pre.some((p) => u.startsWith(p)));
  if (!urls.length) return { deleted: 0, kept: 0, failed: 0 };
  const live = await q('select url, pathname from blobs where url = any($1::text[]) or pathname = any($2::text[])',
    [urls, urls.map(keyOf).filter(Boolean)]);
  const liveUrl = new Set(live.map((r) => r.url)), livePath = new Set(live.map((r) => r.pathname).filter(Boolean));
  const dead = urls.filter((u) => !liveUrl.has(u) && !livePath.has(keyOf(u)));
  const failed = new Set(await removeNow(dead));
  const done = urls.filter((u) => !failed.has(u));
  if (done.length) await q('delete from blob_trash where url = any($1::text[])', [done]);
  if (failed.size) await q(`update blob_trash set tries = tries + 1, due_at = now() + interval '1 day' where url = any($1::text[])`, [[...failed]]);
  return { deleted: dead.length - failed.size, kept: urls.length - dead.length, failed: failed.size };
}

/* ---------------- 확인 ---------------- */
// 올라온 파일 확인 (크기·타입). 없으면 null
export async function headBlob(pathname) {
  if (LOCAL) {
    try {
      const fs = await import('node:fs/promises'); const f = await localPath(pathname);
      const st = await fs.stat(f);
      const type = await fs.readFile(f + '.type', 'utf8').catch(() => 'application/octet-stream');
      return { url: localUrl(pathname), pathname, size: st.size, contentType: type };
    } catch (e) { return null; }
  }
  if (R2) {
    try {
      const { HeadObjectCommand } = await import('@aws-sdk/client-s3');
      const h = await (await r2Client()).send(new HeadObjectCommand({ Bucket: R2.bucket, Key: pathname }));
      return { url: r2Url(pathname), pathname, size: h.ContentLength, contentType: h.ContentType };
    } catch (e) { return null; }
  }
  const { head } = await import('@vercel/blob');
  try { const h = await head(pathname); return { url: h.url, pathname: h.pathname, size: h.size, contentType: h.contentType }; }
  catch (e) { return null; }
}

// 파일이 저장소에 실제로 있는지. 없으면 false (기록만 남은 경우)
export async function blobExists(row) {
  if (LOCAL) {
    try { const fs = await import('node:fs/promises'); await fs.stat(await localPath(row.pathname || localKey(row.url))); return true; }
    catch (e) { return false; }
  }
  if (isR2(row.url)) {
    try {
      const { HeadObjectCommand } = await import('@aws-sdk/client-s3');
      await (await r2Client()).send(new HeadObjectCommand({ Bucket: R2.bucket, Key: row.pathname || r2Key(row.url) }));
      return true;
    } catch (e) {
      if (/not\s*found|404|NoSuchKey/i.test(String(e && (e.name + e.message)))) return false;
      return true;
    }
  }
  try {
    const { head } = await import('@vercel/blob');
    await head(row.url);
    return true;
  } catch (e) {
    if (/not\s*found|404|does not exist/i.test(String(e && e.message))) return false;
    return true;   // 권한·네트워크 문제로는 지우지 않는다
  }
}

/* ---------------- 읽기 주소 ---------------- */
// [{id, url, pathname}] → {id: 읽기 URL}. 한 시간짜리 서명 URL.
// R2 것과 Vercel Blob 것이 섞여 있어도 각자 맞는 방식으로 만든다.
export async function readUrls(rows) {
  const out = {};
  if (!rows.length) return out;
  if (LOCAL) { rows.forEach((r) => { out[r.id] = r.url; }); return out; }
  if (ACCESS === 'public' && !R2) { rows.forEach((r) => { out[r.id] = r.url; }); return out; }
  const mine = rows.filter((r) => isR2(r.url)), theirs = rows.filter((r) => !isR2(r.url));

  if (mine.length) {
    try {
      const { GetObjectCommand } = await import('@aws-sdk/client-s3');
      const { getSignedUrl } = await import('@aws-sdk/s3-request-presigner');
      const c = await r2Client();
      await Promise.all(mine.map(async (r) => {
        const key = r.pathname || r2Key(r.url);
        try { out[r.id] = await getSignedUrl(c, new GetObjectCommand({ Bucket: R2.bucket, Key: key }), { expiresIn: 3600 }); }
        catch (e) { console.error('r2 presign', r.id, e.message); }
      }));
    } catch (e) { console.error('r2 presign all', e.message); }
  }

  if (theirs.length) {
    const { issueSignedToken, presignUrl } = await import('@vercel/blob');
    const validUntil = Date.now() + 60 * 60 * 1000;
    // 저장소가 멎어 있으면(요금제·정지) 여기서 던진다. 그때 콘티·곡 목록까지 같이 죽으면 안 된다.
    // 파일 주소만 비우고 나머지는 그대로 돌려준다 — 화면에는 '악보 파일이 없어요' 안내가 뜬다
    let tok = null;
    try { tok = await issueSignedToken({ operations: ['get'], validUntil }); }
    catch (e) { console.error('blob token', e.message); }
    if (tok) for (const r of theirs) {
      const pathname = r.pathname || new URL(r.url).pathname.replace(/^\//, '');
      try { const p = await presignUrl(tok, { operation: 'get', pathname, access: 'private', validUntil }); out[r.id] = p.presignedUrl || p.url; }
      catch (e) { console.error('presign', r.id, e.message); out[r.id] = r.url; }
    }
  }
  return out;
}
