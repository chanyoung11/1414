// Gemini OMR 로컬 테스트
// 사용:
//   node scripts/omr-test.mjs docs/sample_sheet.jpg            # 악보 한 장 → 코드 차트 JSON + 토큰/비용
//   node scripts/omr-test.mjs --models                         # 이 키로 쓸 수 있는 모델 목록 (무료)
//   GEMINI_MODEL=gemini-2.5-flash-lite node scripts/omr-test.mjs docs/sample_sheet.jpg
//   GEMINI_API_KEY=mock node scripts/omr-test.mjs docs/sample_sheet.jpg   # 키 없이 배관만 확인
// .env.local 이 있으면 자동으로 읽는다 (이미 셸에 있는 값은 덮지 않음).
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
loadEnv(path.join(root, '.env.local'));
const { transcribeSheet, listModels, geminiConfigured, geminiModel, estimateUSD, PRICE } = await import(path.join(root, 'lib', 'gemini.js'));

const args = process.argv.slice(2);
if (!geminiConfigured()) { console.error('GEMINI_API_KEY 가 없어요 (.env.local 또는 환경변수). 배관만 보려면 GEMINI_API_KEY=mock'); process.exit(1); }

if (args.includes('--models')) {
  const ms = await listModels();
  console.log(`모델 ${ms.length}개 (generateContent 지원):`);
  for (const m of ms) console.log(`  ${m.name.padEnd(36)} ${m.displayName || ''}  (입력 한도 ${m.inputLimit || '?'})`);
  process.exit(0);
}

const file = args.find((a) => !a.startsWith('--'));
if (!file) { console.error('악보 이미지 경로를 주세요'); process.exit(1); }
const abs = path.resolve(file);
const buf = fs.readFileSync(abs);
const ext = path.extname(abs).toLowerCase();
const mime = ext === '.png' ? 'image/png' : ext === '.webp' ? 'image/webp' : 'image/jpeg';
console.log(`파일 ${path.basename(abs)} (${(buf.length / 1024).toFixed(0)} KB, ${mime}) → 모델 ${geminiModel()}`);

const t0 = Date.now();
let res;
try { res = await transcribeSheet({ b64: buf.toString('base64'), mime }); }
catch (e) { console.error('실패:', e.status || '', e.code || '', e.message); process.exit(2); }
const ms = Date.now() - t0;

// 요약
console.log(`\n걸린 시간 ${(ms / 1000).toFixed(1)}s · 토큰 입력 ${res.usage.input} / 출력 ${res.usage.output}${res.usage.thinking ? ' / 생각 ' + res.usage.thinking : ''} · 곡 ${res.songs.length}개${res.finishReason && res.finishReason !== 'STOP' ? ' · finish=' + res.finishReason : ''}`);
// 근사 비용 (lib/gemini.js PRICE 표준 단가 기준)
const usd = estimateUSD(res.model, res.usage);
const known = PRICE[res.model] ? '' : ' · 이 모델 단가는 표에 없어 3.6 Flash 단가로 계산';
console.log(`근사 비용 $${usd.toFixed(5)} (≈ ${(usd * 1400).toFixed(1)}원)${known}`);

for (const [i, s] of res.songs.entries()) {
  console.log(`\n── 곡 ${i + 1}: ${s.title || '(제목 없음)'}${s.subtitle ? ' — ' + s.subtitle : ''}`);
  console.log(`   키 ${s.key || '?'} · 박자 ${s.timeSignature || '?'}${s.tempo ? ' · ' + s.tempo + 'bpm' : ''} · 확신 ${(s.confidence * 100).toFixed(0)}%`);
  console.log(`   폼: ${s.form}`);
  for (const sec of s.sections) {
    const bars = sec.bars.map((b) => '| ' + (b.chords.join(' ') || '·')).join(' ') + ' |';
    console.log(`   [${sec.name}${sec.repeat ? ' x' + sec.repeat : ''}] ${bars}`);
    const lyr = sec.bars.map((b) => b.lyric).filter(Boolean).join(' / ');
    if (lyr) console.log(`      ${lyr}`);
  }
  if (s.notes) console.log(`   메모: ${s.notes}`);
}

if (args.includes('--json')) console.log('\n' + JSON.stringify(res.songs, null, 2));
const out = path.join(root, 'scratch-omr.json');
fs.writeFileSync(out, JSON.stringify({ file: path.basename(abs), model: res.model, usage: res.usage, songs: res.songs }, null, 2));
console.log(`\n전체 결과 저장: ${path.relative(root, out)}`);

function loadEnv(p) {
  if (!fs.existsSync(p)) return;
  for (const line of fs.readFileSync(p, 'utf8').split('\n')) {
    const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/); if (!m) continue;
    let v = m[2]; if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) v = v.slice(1, -1);
    if (process.env[m[1]] == null) process.env[m[1]] = v;
  }
}
