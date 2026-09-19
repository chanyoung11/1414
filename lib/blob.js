// 악보·녹음 파일 저장소.
//
// 두 곳을 쓴다.
//   - Cloudflare R2 (S3 호환) — 지금 올리는 파일. 내려받기(egress)가 공짜라 악보를 자주 보는 우리 앱에 맞다
//   - Vercel Blob — 예전에 올린 파일. 읽기만 한다 (2026-09-19 무료 한도 초과로 멈춘 그 저장소)
// R2 환경변수 네 개가 모두 있으면 R2 로 쓰고, 없으면 예전처럼 Vercel Blob 으로 쓴다.
// 읽을 때는 주소를 보고 어느 쪽인지 가른다 — 옮기는 동안 둘이 섞여 있어도 된다.
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
export async function presignPut(pathname, contentType, minutes = 30) {
  const validUntil = Date.now() + minutes * 60 * 1000;
  if (LOCAL) return { url: localUrl(pathname), pathname, validUntil };
  if (R2) {
    const { PutObjectCommand } = await import('@aws-sdk/client-s3');
    const { getSignedUrl } = await import('@aws-sdk/s3-request-presigner');
    try {
      // 같은 파일을 다시 올릴 수 있어야 한다(초안 저장 뒤 발행, 복구용 강제 재업로드) → 이름을 그대로 쓴다
      const url = await getSignedUrl(await r2Client(),
        new PutObjectCommand({ Bucket: R2.bucket, Key: pathname, ContentType: contentType }), { expiresIn: minutes * 60 });
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
export async function delBlobs(urls) {
  if (!urls.length) return;
  if (LOCAL) {
    const fs = await import('node:fs/promises');
    for (const u of urls) {
      if (!isLocal(u)) continue;
      try { const f = await localPath(localKey(u)); await fs.unlink(f); await fs.unlink(f + '.type').catch(() => {}); } catch (e) {}
    }
    return;
  }
  const mine = urls.filter(isR2), theirs = urls.filter((u) => !isR2(u));
  if (mine.length) {
    try {
      const { DeleteObjectsCommand } = await import('@aws-sdk/client-s3');
      await (await r2Client()).send(new DeleteObjectsCommand({ Bucket: R2.bucket,
        Delete: { Objects: mine.map((u) => ({ Key: r2Key(u) })) } }));
    } catch (e) { console.error('r2 del', e.message); }
  }
  if (theirs.length) {
    try { const { del } = await import('@vercel/blob'); await del(theirs); }
    catch (e) { console.error('blob del', e.message); }
  }
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
