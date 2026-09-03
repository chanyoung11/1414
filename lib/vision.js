// Google Cloud Vision OCR — 악보의 코드 띠 이미지(여러 장)를 보내 단어와 위치를 받는다.
// GOOGLE_VISION_KEY 가 없으면 null 반환(미연결). 'mock' 이면 테스트용 가짜 결과.

export function visionConfigured() {
  return !!process.env.GOOGLE_VISION_KEY;
}

// images: [{ b64, mime, w, h }] → [{ tokens: [{ text, x, y, w, h, conf }] }]
export async function ocrBands(images) {
  const key = process.env.GOOGLE_VISION_KEY;
  if (!key) return null;
  if (key === 'mock') return images.map((im, i) => mockBand(im, i));
  const body = {
    requests: images.map((im) => ({
      image: { content: im.b64 },
      features: [{ type: 'DOCUMENT_TEXT_DETECTION' }],
      imageContext: { languageHints: im.kind === 'title' ? ['ko', 'en'] : ['en'] },
    })),
  };
  const r = await fetch('https://vision.googleapis.com/v1/images:annotate?key=' + encodeURIComponent(key), {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error((j.error && j.error.message) || ('Vision ' + r.status));
  return (j.responses || []).map((res) => ({ tokens: tokensOf(res) }));
}

// Vision 응답 → 같은 줄에서 붙어 있는 단어를 하나의 토큰으로 합침 ("A" "/" "C#" → "A/C#")
function tokensOf(res) {
  const out = [];
  const pages = (res.fullTextAnnotation && res.fullTextAnnotation.pages) || [];
  for (const page of pages) for (const block of page.blocks || []) for (const para of block.paragraphs || []) {
    let cur = null;
    for (const word of para.words || []) {
      const text = (word.symbols || []).map((s) => s.text).join('');
      const box = bbox(word.boundingBox);
      if (!text.trim() || !box) continue;
      const conf = Math.round((word.confidence || 0) * 100);
      const brk = (word.symbols || []).some((s) => s.property && s.property.detectedBreak && /SPACE|EOL|LINE/.test(s.property.detectedBreak.type || ''));
      if (cur && box.x - (cur.x + cur.w) < cur.h * 0.35 && Math.abs(box.y - cur.y) < cur.h * 0.8) {
        cur.text += text; cur.w = box.x + box.w - cur.x; cur.h = Math.max(cur.h, box.h); cur.y = Math.min(cur.y, box.y); cur.conf = Math.min(cur.conf, conf);
      } else { if (cur) out.push(cur); cur = { text, ...box, conf }; }
      if (brk) { out.push(cur); cur = null; }
    }
    if (cur) out.push(cur);
  }
  return out;
}
function bbox(b) {
  const v = (b && b.vertices) || [];
  if (v.length < 4) return null;
  const xs = v.map((p) => p.x || 0), ys = v.map((p) => p.y || 0);
  const x = Math.min(...xs), y = Math.min(...ys);
  return { x, y, w: Math.max(...xs) - x, h: Math.max(...ys) - y };
}

// 테스트용: 띠 폭을 따라 코드 몇 개를 흩뿌린다 (첫 띠는 G 계열, 나머지는 C 계열)
function mockBand(im, i) {
  if (im.kind === 'title') { const h = Math.round((im.h || 80) * 0.5); return { tokens: [{ text: '우리', x: 300, y: 10, w: h * 2, h, conf: 95 }, { text: '주', x: 300 + h * 2.4, y: 10, w: h, h, conf: 95 }, { text: '하나님', x: 300 + h * 3.8, y: 10, w: h * 3, h, conf: 95 }, { text: '작사 심형진', x: 700, y: 10 + h * 1.6, w: h * 2, h: Math.round(h * 0.4), conf: 90 }] }; }
  const sets = [['G', 'Bm7', 'A9/C#', 'C', 'G/B'], ['C', 'G/B', 'C', 'D(sus4)', 'D'], ['G', 'Bm7', 'A9/C#', 'C', 'A9/C#'], ['C', 'G°/B', 'C/E', 'D', 'G']];
  const list = sets[i % sets.length];
  const h = Math.round((im.h || 60) * 0.45), y = Math.round((im.h || 60) * 0.25);
  return { tokens: list.map((text, k) => ({ text, x: Math.round(((im.w || 800) / list.length) * k + 20), y, w: Math.round(h * 0.6 * text.length), h, conf: 95 })) };
}
