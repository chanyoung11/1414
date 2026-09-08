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
// 브라우저가 Blob 스토어로 바로 올릴 수 있는 서명 URL (서버리스 본문 한도 4.5MB를 우회)
export async function presignPut(pathname, contentType, minutes = 30) {
  const { issueSignedToken, presignUrl } = await import('@vercel/blob');
  const validUntil = Date.now() + minutes * 60 * 1000;
  // 같은 파일을 다시 올릴 수 있어야 한다(초안 저장 뒤 발행, 복구용 강제 재업로드)
  const opts = { pathname, validUntil, access: ACCESS, contentType, addRandomSuffix: false, allowOverwrite: true };
  const tok = await issueSignedToken({ operations: ['put'], ...opts });
  const p = await presignUrl(tok, { operation: 'put', ...opts });
  return { url: p.presignedUrl || p.url, pathname, validUntil };
}
// 올라온 파일 확인 (크기·타입). 없으면 null
export async function headBlob(pathname) {
  const { head } = await import('@vercel/blob');
  try { const h = await head(pathname); return { url: h.url, pathname: h.pathname, size: h.size, contentType: h.contentType }; }
  catch (e) { return null; }
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
