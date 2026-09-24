// 발행본·초안·편곡 문서에서 숫자·정해진 값이어야 하는 칸을 제 모양으로 맞춘다.
// 문서는 인도자가 보낸 JSON 이 그대로 저장되는데, 앱은 이 칸들을 화면에 그대로 끼워 넣는다
// (v${version} · ?t=${start} · ♩=${tempo} · data-start=${cut} · class="m ${layer}" …).
// 숫자 칸에 태그를 넣으면 그 팀원 앱에서 스크립트가 돈다. 새 앱은 화면에서도 막지만
// 이미 깔린 앱은 번들에 옛 화면이 들어 있어 서버가 주는 값을 믿는다 → 저장할 때·내려줄 때 거른다.
// 내려줄 때 거르면 이미 저장된 옛 문서도 같이 걸러진다.

const num = (v, d) => {
  const n = typeof v === 'number' ? v : (typeof v === 'string' && v.trim() !== '' ? Number(v) : NaN);
  return Number.isFinite(n) ? n : d;
};
const list = (v) => (Array.isArray(v) ? v : []);
const isObj = (v) => !!v && typeof v === 'object' && !Array.isArray(v);
// 예배 메모(leader·session·mine) + 편곡 고정 메모(all)
const LAYERS = ['leader', 'session', 'mine', 'all'];
// 앱의 OV_FIELDS 와 같다 — 예배에서 고친 편곡 칸
const OV_FIELDS = ['key', 'mod', 'form', 'songNote', 'pieces', 'media', 'chart', 'score'];

function safeNote(n) {
  if (!isObj(n)) return;
  if (n.t != null) n.t = num(n.t, 0);
  if (n.layer != null && !LAYERS.includes(n.layer)) n.layer = 'mine';
}

// 곡 하나. 예배의 곡과 편곡이 같은 모양이라 둘 다 이걸로 거른다
export function safeItem(it) {
  if (!isObj(it)) return it;
  for (const md of list(it.media)) {
    if (!isObj(md)) continue;
    if (md.start != null) md.start = num(md.start, 0);
    if (md.end != null) md.end = num(md.end, 0);
    list(md.notes).forEach(safeNote);
  }
  for (const p of list(it.pieces)) {
    for (const m of list(isObj(p) ? p.markers : null)) {
      if (!isObj(m)) continue;
      if (m.cut != null) m.cut = num(m.cut, null);
      if (m.keyShift != null) m.keyShift = num(m.keyShift, null);
    }
  }
  if (isObj(it.score)) {
    const sc = it.score;
    // 곡 정보 창이 빠르기·오선 줄 수·비용을 그대로 끼운다 (value="${tempo}" · 오선 ${lines}줄 · 약 ${cost}원)
    for (const k of ['tempo', 'lines', 'cost']) if (sc[k] != null) sc[k] = num(sc[k], null);
    // 박자는 '4/4' 꼴만 — AI 결과도 이렇게 맞춘다 (lib/gemini.js). 옛 앱은 마디 창에 박자를 그대로 끼운다
    if (sc.time != null && !/^\d+\/\d+$/.test(String(sc.time))) sc.time = '4/4';
  }
  list(it.notes).forEach(safeNote);
  list(it.fixedNotes).forEach(safeNote);
  if (isObj(it.ov)) for (const k of Object.keys(it.ov)) if (!OV_FIELDS.includes(k)) delete it.ov[k];
  return it;
}

// 예배 문서 (발행본·초안)
export function safeDoc(doc) {
  if (!isObj(doc)) return doc;
  if (doc.version != null) doc.version = num(doc.version, 0);
  list(doc.items).forEach(safeItem);
  return doc;
}
