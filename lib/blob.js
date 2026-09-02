// Vercel Blob 업로드. BLOB_READ_WRITE_TOKEN 필요.
export async function putBlob(pathname, body, contentType) {
  const { put } = await import('@vercel/blob');
  const r = await put(pathname, body, { access: 'public', addRandomSuffix: true, contentType: contentType || 'application/octet-stream' });
  return r.url;
}
export async function delBlobs(urls) {
  if (!urls.length) return;
  const { del } = await import('@vercel/blob');
  try { await del(urls); } catch (e) { console.error('blob del', e.message); }
}
