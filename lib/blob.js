// Vercel Blob (비공개 스토어). BLOB_READ_WRITE_TOKEN 필요.
// 저장은 private, 읽기는 1시간짜리 서명 URL로만.
const ACCESS = process.env.BLOB_ACCESS === 'public' ? 'public' : 'private';
export async function putBlob(pathname, body, contentType) {
  const { put } = await import('@vercel/blob');
  const r = await put(pathname, body, { access: ACCESS, addRandomSuffix: true, contentType: contentType || 'application/octet-stream' });
  return { url: r.url, pathname: r.pathname };
}
export async function delBlobs(urls) {
  if (!urls.length) return;
  const { del } = await import('@vercel/blob');
  try { await del(urls); } catch (e) { console.error('blob del', e.message); }
}
// [{id, url, pathname}] → {id: 읽기 URL}. 비공개면 서명 URL(1시간), 공개면 그대로
export async function readUrls(rows) {
  const out = {};
  if (!rows.length) return out;
  if (ACCESS === 'public') { rows.forEach((r) => { out[r.id] = r.url; }); return out; }
  const { issueSignedToken, presignUrl } = await import('@vercel/blob');
  const validUntil = Date.now() + 60 * 60 * 1000;
  const tok = await issueSignedToken({ operations: ['get'], validUntil });
  for (const r of rows) {
    const pathname = r.pathname || new URL(r.url).pathname.replace(/^\//, '');
    try { const p = await presignUrl(tok, { operation: 'get', pathname, access: 'private', validUntil }); out[r.id] = p.presignedUrl || p.url; }
    catch (e) { console.error('presign', r.id, e.message); out[r.id] = r.url; }
  }
  return out;
}
