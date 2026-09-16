// 코드 인식 정확도 측정: docs/sample_sheet.jpg 를 정답지와 견준다.
//   node scripts/ocr-bench.mjs            → Gemini
//   node scripts/ocr-bench.mjs vision     → Google Vision (GOOGLE_VISION_KEY 필요)
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ocrChordsGemini } from '../lib/gemini.js';
import { ocrBands } from '../lib/vision.js';

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const TRUTH = JSON.parse(fs.readFileSync(process.env.TRUTH || path.join(ROOT, 'docs', 'sample_sheet.truth.json'), 'utf8'));
const want = TRUTH.systems.flat();

const norm = (t) => String(t || '').replace(/♯/g, '#').replace(/♭/g, 'b').replace(/\s+/g, '')
  .replace(/[（(]\s*/g, '(').replace(/\s*[）)]/g, ')').trim();

const img = fs.readFileSync(path.join(ROOT, TRUTH.file));
const b64 = img.toString('base64');
const mode = process.argv[2] === 'vision' ? 'vision' : 'gemini';

// 통째로 한 장 보낸다 (Gemini 는 전체 맥락이 있을수록 잘 읽는다)
const one = [{ b64, mime: 'image/jpeg', w: TRUTH.w || 2120, h: TRUTH.h || 3163 }];
let tokens = [];
let usage = null;
if (mode === 'gemini') {
  const r = await ocrChordsGemini(one, { thinking: process.env.THINK || 'LOW' });
  if (!r) { console.error('GEMINI_API_KEY 가 없습니다'); process.exit(1); }
  tokens = r.bands.flatMap((b) => b.tokens); usage = r.usage;
  if (r.bands.some((b) => b.err)) console.error('오류:', r.bands.map((b) => b.err).filter(Boolean));
} else {
  const r = await ocrBands(one);
  if (!r) { console.error('GOOGLE_VISION_KEY 가 없습니다'); process.exit(1); }
  tokens = r.flatMap((b) => b.tokens);
}
// 읽은 순서대로 (위→아래, 왼→오른쪽)
const got = tokens.slice().sort((a, b) => (a.y - b.y) || (a.x - b.x)).map((t) => norm(t.text));

// 코드처럼 보이는 것만 남긴다 (Vision 은 가사·번호까지 뱉는다)
const CHORD_RE = /^[A-G](#|b)?(m|maj|min|dim|aug|sus|add|°|ø)?[0-9()susadimaugMj#b+°ø\/A-G-]*$/;
const gotC = got.filter((t) => CHORD_RE.test(t) && t.length <= 12);

// 순서를 지키며 맞춘 개수 (LCS)
function lcs(a, b) {
  const m = a.length, n = b.length; const d = Array.from({ length: m + 1 }, () => new Int32Array(n + 1));
  for (let i = 1; i <= m; i++) for (let j = 1; j <= n; j++)
    d[i][j] = a[i - 1] === b[j - 1] ? d[i - 1][j - 1] + 1 : Math.max(d[i - 1][j], d[i][j - 1]);
  return d[m][n];
}
const hit = lcs(want.map(norm), gotC);
const pct = (x, y) => (y ? Math.round(x / y * 1000) / 10 : 0);
console.log(`[${mode}] 정답 ${want.length}개 · 읽은 것 ${got.length}개 (코드꼴 ${gotC.length}개)`);
console.log(`맞음 ${hit}  ·  재현율 ${pct(hit, want.length)}%  ·  정밀도 ${pct(hit, gotC.length)}%`);
if (usage) console.log('토큰:', usage);
// 틀린 것 보기
const wc = {}, gc = {};
want.forEach((t) => { wc[norm(t)] = (wc[norm(t)] || 0) + 1; });
gotC.forEach((t) => { gc[t] = (gc[t] || 0) + 1; });
const miss = Object.entries(wc).filter(([k, v]) => (gc[k] || 0) < v).map(([k, v]) => `${k}×${v - (gc[k] || 0)}`);
const extra = Object.entries(gc).filter(([k, v]) => (wc[k] || 0) < v).map(([k, v]) => `${k}×${v - (wc[k] || 0)}`);
if (miss.length) console.log('놓침 :', miss.join(' '));
if (extra.length) console.log('잘못 :', extra.join(' '));
if (process.env.DUMP) console.log('읽은 순서:', gotC.join(' '));
