// 악보 데이터 모델과 MusicXML 변환.
// AI 에게는 짧은 JSON 으로 받고(값이 싸다), 그리기·내보내기는 MusicXML 로 바꾼다(표준이라 어디서든 열린다).
//
// 모델:
// { title, composer, key:'A', time:'4/4', tempo:70, verses:2,
//   measures:[ { c:[{b:0,t:'Bm7'}], n:[{p:'A4',d:8,dot,tie,l:['우','재']}],
//               rs:true, re:true, end:1, key:'Cb' } ] }
//   p: 'A4' 음이름+옥타브, 쉼표는 null.  d: 1=온,2=2분,4=4분,8=8분,16=16분,32.
//   dot: 점음표, tie: 다음 음표와 붙임줄, l: 절별 가사 음절(없으면 생략)
//   c: 마디 안 코드 [{b: 시작 박, t: 표기}]
//   rs/re: 도돌이표 시작·끝, end: 1·2번 괄호, key: 이 마디부터 조 바뀜

export const DUR = [1, 2, 4, 8, 16, 32];
const TYPE = { 1: 'whole', 2: 'half', 4: 'quarter', 8: 'eighth', 16: '16th', 32: '32nd' };
const STEP_ALTER = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
const FIFTHS = { C: 0, G: 1, D: 2, A: 3, E: 4, B: 5, 'F#': 6, 'C#': 7, F: -1, Bb: -2, Eb: -3, Ab: -4, Db: -5, Gb: -6, Cb: -7 };
// 단조는 나란한장조의 조표를 쓴다 (Am 은 0개, A장조의 3개가 아니다)
const MINOR_FIFTHS = { A: 0, E: 1, B: 2, 'F#': 3, 'C#': 4, 'G#': 5, 'D#': 6, 'A#': 7, D: -1, G: -2, C: -3, F: -4, Bb: -5, Eb: -6, Ab: -7 };
const fifthsOf = (key) => {
  const k = String(key || 'C').trim();
  const minor = /m$/.test(k) && !/^[A-G](#|b)?maj/i.test(k);
  const root = k.replace(/m$/, '');
  const T = minor ? MINOR_FIFTHS : FIFTHS;
  if (T[root] != null) return T[root];
  // 표에 없는 이름(Dbm·Fb·A#)은 같은 소리의 다른 이름으로 찾는다 (예전에는 0 → 조표 없음)
  const pc = pcOf(root);
  const same = Object.keys(T).filter((x) => pcOf(x) === pc).sort((a, b) => Math.abs(T[a]) - Math.abs(T[b]));
  return pc != null && same.length ? T[same[0]] : 0;
};
const pcOf = (name) => { const m = String(name || '').match(/^([A-G])(#|b)?$/); return m ? (STEP_ALTER[m[1]] + (m[2] === '#' ? 1 : m[2] === 'b' ? -1 : 0) + 12) % 12 : null; };
const esc = (s) => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

// 'A4' 'Bb3' 'F#5' → {step:'A', alter:0, octave:4}
export function parsePitch(p) {
  const m = String(p || '').match(/^([A-G])(#{1,2}|b{1,2}|)(-?\d)$/);
  if (!m) return null;
  const alter = m[2].startsWith('#') ? m[2].length : m[2].startsWith('b') ? -m[2].length : 0;
  return { step: m[1], alter, octave: +m[3] };
}
export const midiOf = (p) => { const x = parsePitch(p); return x ? (x.octave + 1) * 12 + STEP_ALTER[x.step] + x.alter : null; };

// divisions=24 면 온음표 96, 3연음(8분음표 1/3)까지 정수로 떨어진다
export const DIVISIONS = 24;
export const durTicks = (n) => { const base = (DIVISIONS * 4) / (n.d || 4); return n.dot ? base * 1.5 : base; };
export const measureTicks = (time) => {
  const m = String(time || '4/4').match(/^(\d+)\/(\d+)$/);
  const beats = m ? +m[1] : 4, bt = m ? +m[2] : 4;
  return (DIVISIONS * 4 * beats) / bt;
};

// 마디마다 음표 길이 합이 박자와 맞는지. 어긋난 마디 번호와 차이를 돌려준다
export function checkMeasures(score) {
  const want = measureTicks(score.time);
  const bad = [];
  (score.measures || []).forEach((m, i) => {
    const got = (m.n || []).reduce((a, n) => a + durTicks(n), 0);
    if (got !== want) bad.push({ measure: i + 1, got, want });
  });
  return bad;
}

/* ---------- AI 가 옮긴 악보 검사: 말이 안 되는 결과를 그리지 않는다 ----------
   실사용 제보 "아예 말 안 되게 엉터리로 그려 준다" (2026-09-30). 재현해 보니 AI 는 틀릴 때도 확신 0.9 로
   그럴듯한 JSON 을 낸다: 오선이 반쯤 잘린 조각에서 없는 음표를 지어내고(F#5 G#5 …), 박자표가 안 보이는 12/8 줄을
   4/4 로 짐작해 음 길이·높이를 4/4 에 맞게 지어냈다 (박자 합은 맞아서 '박자 확인' 표시도 안 떴다).
   그래서 (1) 박자는 인쇄된 것·앞 줄에서 알려 준 것·음 길이 합으로 다시 정하고 (2) 음 높이·음 길이·되풀이·박자 합이
   말이 안 되면 한 번 다시 묻고, 그래도 안 되면 그리지 않고 까닭을 알린다 */
const TIME_RE = /^(\d{1,2})\/(1|2|4|8|16)$/;
export const validTime = (t) => { const m = String(t || '').trim().match(TIME_RE); return m && +m[1] >= 1 && +m[1] <= 16 ? `${+m[1]}/${m[2]}` : ''; };
// 음이름 정리: ♯♭·소문자·공백·쉼표 표기를 고친다. 못 읽는 것은 그대로 둔다 (검사에서 센다)
export function normPitch(p) {
  if (p == null) return null;
  let s = String(p).trim().replace(/♯/g, '#').replace(/♭/g, 'b').replace(/\s+/g, '');
  if (!s || /^(r|rest|x|-|none|null|쉼표)$/i.test(s)) return null;
  return s[0].toUpperCase() + s.slice(1);
}
const sumOf = (m) => (m.n || []).reduce((a, n) => a + durTicks(n), 0);
// 박자에 맞는 마디의 비율 (못갖춘 첫마디는 빼고 센다)
export function timeFit(score, time) {
  const want = measureTicks(time);
  const ms = (score.measures || []).filter((m, i) => !(i === 0 && score.pickup) && (m.n || []).length);
  if (!ms.length) return 0;
  return ms.filter((m) => sumOf(m) === want).length / ms.length;
}
// 음 길이 합으로 박자를 짐작한다 (가장 흔한 합). 점음표가 많으면 겹박자(6/8·12/8)
export function inferTime(score) {
  const ms = (score.measures || []).filter((m, i) => !(i === 0 && score.pickup) && (m.n || []).length);
  if (!ms.length) return '';
  const cnt = new Map();
  ms.forEach((m) => { const t = sumOf(m); cnt.set(t, (cnt.get(t) || 0) + 1); });
  const [top, n] = [...cnt.entries()].sort((a, b) => b[1] - a[1])[0];
  if (n < Math.max(1, ms.length * 0.5)) return '';
  const notes = ms.flatMap((m) => m.n || []);
  const compound = notes.filter((x) => x.dot).length >= notes.length * 0.25;
  const q = DIVISIONS;   // 4분음표 한 개
  return ({ [2 * q]: '2/4', [3 * q]: compound ? '6/8' : '3/4', [4 * q]: '4/4', [5 * q]: '5/4', [6 * q]: compound ? '12/8' : '6/4',
    [1.5 * q]: '3/8', [4.5 * q]: '9/8' })[top] || '';
}
// 박자 정하기. AI 가 적은 것(인쇄된 박자표)과 앞 줄에서 알려 준 것(hint)이 있으면 그것을 따른다 — 음 길이 합이 거기에 안 맞으면
// 박자를 바꿔 맞춰 줄 게 아니라 음표를 잘못 읽은 것이다 (12/8 이라고 적고 음표는 6/8 토막으로 낸 답을 6/8 로 '살려' 주면 안 된다).
// 둘이 다르면 마디가 더 많이 맞는 쪽 + timeConflict (한 번 다시 묻는다). 둘 다 없을 때만 음 길이 합으로 짐작하고, 그것도 안 되면 4/4
export function resolveTime(score, hint) {
  const printed = validTime(score.time), told = validTime(hint && hint.time);
  let pick;
  if (printed && told && printed !== told) {
    const a = timeFit(score, printed), b = timeFit(score, told);
    pick = a > b ? { t: printed, from: 'printed', fit: a, conflict: true } : { t: told, from: 'hint', fit: b, conflict: true };
  } else if (printed || told) {
    const t = printed || told;
    pick = { t, from: printed ? 'printed' : 'hint', fit: timeFit(score, t), conflict: false };
  } else {
    const inf = inferTime(score);
    pick = inf ? { t: inf, from: 'inferred', fit: timeFit(score, inf), conflict: false } : { t: '4/4', from: 'default', fit: timeFit(score, '4/4'), conflict: false };
  }
  score.time = pick.t;
  return { time: pick.t, from: pick.from, fit: pick.fit, conflict: pick.conflict };
}
const KO_REASON = {
  empty: '오선에서 음표를 찾지 못했어요',
  unreadable: '악보가 잘렸거나 흐려서 음표가 안 보여요',
  pitch: '음 이름을 알아볼 수 없어요',
  range: '음 높이가 멜로디로는 말이 안 돼요',
  duration: '음 길이를 알아볼 수 없어요',
  density: '한 마디에 음표가 너무 많아요',
  loop: '같은 마디만 되풀이돼요',
  rhythm: '마디마다 박자가 맞지 않아요',
  time: '박자표가 앞 줄과 달라요',
};
export const reasonKo = (rs) => [...new Set(rs || [])].map((r) => KO_REASON[r] || r).join(' · ');
// 한 조각(보통 오선 한 줄)에서 옮긴 악보가 말이 되는지.
// hard: 그리면 안 되는 것 (다시 물어도 안 되면 거절) · soft: 다시 물어볼 만한 것 (그래도 그리기는 한다)
// opts.final: 박자 고치기까지 끝난 뒤 — 이때 박자 합이 절반 넘게 틀리면 hard (그 전에는 거의 다 틀릴 때만 soft, 고치기가 먼저다)
export function scoreSanity(score, opts = {}) {
  const hard = [], soft = [];
  const ms = score && Array.isArray(score.measures) ? score.measures : [];
  const notes = ms.flatMap((m) => m.n || []);
  const sounding = notes.filter((n) => n.p);
  const st = (score && score._stats) || {};
  if (score && score.problem && !sounding.length) hard.push('unreadable');
  else if (!ms.length || (!sounding.length && !ms.some((m) => (m.c || []).length))) hard.push('empty');
  if (sounding.length) {
    const mids = sounding.map((n) => midiOf(n.p));
    const bad = mids.filter((x) => x == null).length;
    if (bad > Math.max(1, sounding.length * 0.1)) hard.push('pitch');
    const ok = mids.filter((x) => x != null).sort((a, b) => a - b);
    if (ok.length) {
      // 높은음자리표 멜로디는 한 줄에 한 옥타브 반 남짓. 한 옥타브 틀린 것은 앱이 바로잡으니 넉넉히 본다
      const out = ok.filter((x) => x < 40 || x > 96).length;
      const lo = ok[Math.floor(ok.length * 0.05)], hi = ok[Math.max(0, Math.ceil(ok.length * 0.95) - 1)];
      if (out > Math.max(1, ok.length * 0.1) || hi - lo > 31) hard.push('range');
    }
  }
  if ((st.badDur || 0) > Math.max(1, notes.length * 0.1)) hard.push('duration');
  if (ms.some((m) => (m.n || []).length > 32)) hard.push('density');
  // 같은 마디 되풀이 (AI 가 고장 나면 같은 것을 끝없이 낸다)
  let run = 1, best = 1;
  for (let i = 1; i < ms.length; i++) {
    const a = JSON.stringify([ms[i].n, ms[i].c || []]), b = JSON.stringify([ms[i - 1].n, ms[i - 1].c || []]);
    run = a === b && (ms[i].n || []).length ? run + 1 : 1; best = Math.max(best, run);
  }
  if (best >= 8) hard.push('loop');
  if (score && score._timeConflict) soft.push('time');
  // 박자 합: 고치기 전에는 거의 모든 마디가 안 맞을 때만 (마디를 잘못 나눈 것이라 마디별 고치기로는 안 된다 → 처음부터 다시),
  // 고치기까지 끝난 뒤에는 절반 넘게 안 맞으면 그리지 않는다
  const want = measureTicks(score && score.time);
  const counted = ms.filter((m, i) => !(i === 0 && score.pickup) && (m.n || []).length);
  const badN = counted.filter((m) => sumOf(m) !== want).length;
  const badRatio = counted.length ? badN / counted.length : 0;
  if (opts.final) { if (badN >= 2 && badRatio > 0.5) hard.push('rhythm'); }
  else if (badN >= 2 && badRatio >= 0.75) soft.push('rhythm');
  return { ok: !hard.length, hard, soft, badRatio, message: reasonKo(hard.length ? hard : soft) };
}

// 악보 전체를 반음 단위로 옮긴다 (코드 표기도 같이). 조표는 목표 키로 다시 적는다
const SHARP = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
const FLAT = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B'];
const useFlat = (key) => /b/.test(String(key || '')) || ['F', 'Dm', 'Gm', 'Cm', 'Fm', 'Bbm', 'Ebm'].includes(String(key || ''));
export function transposeScore(score, semis) {
  if (!semis) return score;
  const key2 = spellKey(score.key, semis);
  const flat = useFlat(key2);
  const spell = (mid) => (flat ? FLAT : SHARP)[((mid % 12) + 12) % 12] + (Math.floor(mid / 12) - 1);
  const out = { ...score, key: key2, measures: (score.measures || []).map((m) => ({
    ...m,
    key: m.key ? spellKey(m.key, semis) : m.key,
    c: (m.c || []).map((c) => ({ ...c, t: transposeChordText(c.t, semis, key2) })),
    n: (m.n || []).map((n) => (n.p ? { ...n, p: spell(midiOf(n.p) + semis) } : n)),
  })) };
  return out;
}
export function spellKey(key, semis) {
  const m = String(key || 'C').match(/^([A-G])(#|b)?(m)?$/);
  if (!m) return key;
  const root = STEP_ALTER[m[1]] + (m[2] === '#' ? 1 : m[2] === 'b' ? -1 : 0);
  const to = ((root + semis) % 12 + 12) % 12;
  // 조표가 적은 쪽 이름을 고른다
  const cand = [SHARP[to], FLAT[to]].filter((x, i, a) => a.indexOf(x) === i);
  const pick = cand.sort((a, b) => Math.abs(FIFTHS[a] ?? 9) - Math.abs(FIFTHS[b] ?? 9))[0];
  return pick + (m[3] || '');
}
export function transposeChordText(text, semis, key) {
  const m = String(text || '').match(/^([A-G])(#|b)?([^/]*)(?:\/([A-G])(#|b)?)?$/);
  if (!m) return text;
  const flat = useFlat(key);
  const sp = (st, ac) => { const v = ((STEP_ALTER[st] + (ac === '#' ? 1 : ac === 'b' ? -1 : 0) + semis) % 12 + 12) % 12; return (flat ? FLAT : SHARP)[v]; };
  return sp(m[1], m[2]) + (m[3] || '') + (m[4] ? '/' + sp(m[4], m[5]) : '');
}

// 코드 표기 → MusicXML harmony (kind 는 대표적인 것만, 나머지는 other + text 로 원문 보존)
const KIND = [[/^maj7|^M7|^Δ/, 'major-seventh'], [/^m7b5|^ø/, 'half-diminished'], [/^m(?:in)?7/, 'minor-seventh'],
  [/^m(?:in)?9/, 'minor-ninth'], [/^m(?:in)?6/, 'minor-sixth'], [/^m(?:in)?\b|^m(?!aj)/, 'minor'],
  [/^dim|^°|^o\b/, 'diminished'], [/^aug|^\+/, 'augmented'], [/^sus2/, 'suspended-second'], [/^sus4|^\(sus4\)/, 'suspended-fourth'],
  [/^9/, 'dominant-ninth'], [/^11/, 'dominant-11th'], [/^13/, 'dominant-13th'], [/^7/, 'dominant'], [/^6/, 'major-sixth'], [/^$/, 'major']];
function harmonyXML(text) {
  const m = String(text || '').match(/^([A-G])(#|b)?([^/]*)(?:\/([A-G])(#|b)?)?$/);
  if (!m) return '';
  const suffix = (m[3] || '').trim();
  const kind = (KIND.find(([re]) => re.test(suffix)) || [null, 'other'])[1];
  const alter = (a) => (a === '#' ? '<root-alter>1</root-alter>' : a === 'b' ? '<root-alter>-1</root-alter>' : '');
  const balter = (a) => (a === '#' ? '<bass-alter>1</bass-alter>' : a === 'b' ? '<bass-alter>-1</bass-alter>' : '');
  return `<harmony print-frame="no"><root><root-step>${m[1]}</root-step>${alter(m[2])}</root>`
    + `<kind text="${esc(suffix)}">${kind}</kind>`
    + (m[4] ? `<bass><bass-step>${m[4]}</bass-step>${balter(m[5])}</bass>` : '')
    + `</harmony>`;
}


// 8분음표 이하를 박 단위로 묶어 꼬리표(beam)를 만든다. 없으면 음표마다 깃발이 달려 손으로 그린 악보와 달라 보인다
function beamsOf(notes, unit) {
  const lvl = (n) => (n && n.p && n.d >= 8 ? Math.round(Math.log2(n.d / 4)) : 0);
  const pos = []; let t = 0;
  (notes || []).forEach((n) => { pos.push(t); t += durTicks(n); });
  const groups = []; let cur = [], curBeat = -1;
  (notes || []).forEach((n, i) => {
    const b = Math.floor(pos[i] / unit), e = Math.floor((pos[i] + durTicks(n) - 1) / unit);
    const ok = lvl(n) > 0 && b === e;
    if (!ok || b !== curBeat) { if (cur.length > 1) groups.push(cur); cur = []; }
    if (ok) { cur.push(i); curBeat = b; } else curBeat = -1;
  });
  if (cur.length > 1) groups.push(cur);
  const out = {};
  groups.forEach((g) => g.forEach((idx, j) => {
    const L = lvl(notes[idx]); const arr = [];
    const prev = j > 0 ? lvl(notes[g[j - 1]]) : 0, next = j < g.length - 1 ? lvl(notes[g[j + 1]]) : 0;
    for (let k = 1; k <= L; k++) {
      const p = prev >= k, q = next >= k;
      arr.push(p && q ? 'continue' : p ? 'end' : q ? 'begin' : (j > 0 ? 'backward hook' : 'forward hook'));
    }
    out[idx] = arr;
  }));
  return out;
}
export const beamUnit = (time) => {
  const m = String(time || '4/4').match(/^(\d+)\/(\d+)$/);
  const beats = m ? +m[1] : 4, bt = m ? +m[2] : 4;
  return (beats % 3 === 0 && bt === 8) ? (DIVISIONS * 4 / 8) * 3 : (DIVISIONS * 4) / bt;
};

// 모델 → MusicXML (Verovio·뮤즈스코어·시벨리우스가 읽는 표준)
export function toMusicXML(score) {
  const s = score || {};
  const time = String(s.time || '4/4').match(/^(\d+)\/(\d+)$/) || [null, '4', '4'];
  const verses = Math.max(1, +s.verses || 1);
  let cur = s.key || 'C';
  // 붙임줄은 시작과 끝이 짝이어야 한다 — 시작만 적으면 여는 프로그램이 버린다.
  // 다음 음표(다음 마디 첫 음 포함)가 같은 높이일 때만 잇고, 그 음표에 끝(stop)을 적는다
  const seq = [];
  (s.measures || []).forEach((m, i) => (m.n || []).forEach((n, ni) => seq.push([i + ':' + ni, midiOf(n.p), n.tie])));
  const tieS = new Set(), tieE = new Set();
  seq.forEach(([k, mid, tie], j) => { const nx = seq[j + 1]; if (tie && mid != null && nx && nx[1] === mid) { tieS.add(k); tieE.add(nx[0]); } });
  const measures = (s.measures || []).map((m, i) => {
    const parts = [];
    const attrs = [];
    if (i === 0) {
      attrs.push(`<divisions>${DIVISIONS}</divisions>`,
        `<key><fifths>${fifthsOf(cur)}</fifths><mode>${/m$/.test(cur) ? 'minor' : 'major'}</mode></key>`,
        `<time><beats>${time[1]}</beats><beat-type>${time[2]}</beat-type></time>`,
        `<clef><sign>G</sign><line>2</line></clef>`);
    } else if (m.key && m.key !== cur) {
      cur = m.key;
      attrs.push(`<key><fifths>${fifthsOf(cur)}</fifths><mode>${/m$/.test(cur) ? 'minor' : 'major'}</mode></key>`);
    }
    if (attrs.length) parts.push(`<attributes>${attrs.join('')}</attributes>`);
    if (m.rs) parts.push('<barline location="left"><bar-style>heavy-light</bar-style><repeat direction="forward"/></barline>');
    if (m.end) parts.push(`<barline location="left"><ending number="${m.end}" type="start"/></barline>`);
    if (i === 0 && s.tempo) parts.push(`<direction placement="above"><direction-type><metronome><beat-unit>quarter</beat-unit><per-minute>${+s.tempo}</per-minute></metronome></direction-type><sound tempo="${+s.tempo}"/></direction>`);
    let tick = 0;
    const chords = (m.c || []).slice().sort((a, b) => (+a.b || 0) - (+b.b || 0));
    let ci = 0;
    const bm = beamsOf(m.n || [], beamUnit(s.time));
    let ni = -1;
    for (const n of (m.n || [])) {
      ni++;
      const beatNow = tick / DIVISIONS * (+time[2] / 4);
      while (ci < chords.length && (+chords[ci].b || 0) <= beatNow + 1e-6) { parts.push(harmonyXML(chords[ci].t)); ci++; }
      const d = durTicks(n);
      const p = n.p ? parsePitch(n.p) : null;
      const lyr = (Array.isArray(n.l) ? n.l : n.l ? [n.l] : []).map((t, vi) => t
        ? `<lyric number="${vi + 1}"><syllabic>${/-$/.test(t) ? 'begin' : 'single'}</syllabic><text>${esc(String(t).replace(/-$/, ''))}</text></lyric>` : '').join('');
      const bs = (bm[ni] || []).map((v, k) => (v ? `<beam number="${k + 1}">${v}</beam>` : '')).join('');
      const te = tieE.has(i + ':' + ni), ts = tieS.has(i + ':' + ni);
      parts.push(`<note>${p ? `<pitch><step>${p.step}</step>${p.alter ? `<alter>${p.alter}</alter>` : ''}<octave>${p.octave}</octave></pitch>` : '<rest/>'}`
        + `<duration>${d}</duration>${te ? '<tie type="stop"/>' : ''}${ts ? '<tie type="start"/>' : ''}<voice>1</voice><type>${TYPE[n.d] || 'quarter'}</type>${n.dot ? '<dot/>' : ''}`
        + bs + (te || ts ? `<notations>${te ? '<tied type="stop"/>' : ''}${ts ? '<tied type="start"/>' : ''}</notations>` : '') + lyr + `</note>`);
      tick += d;
    }
    while (ci < chords.length) { parts.push(harmonyXML(chords[ci].t)); ci++; }
    if (m.end) parts.push(`<barline location="right"><ending number="${m.end}" type="${m.re ? 'stop' : 'discontinue'}"/>${m.re ? '<bar-style>light-heavy</bar-style><repeat direction="backward"/>' : ''}</barline>`);
    else if (m.re) parts.push('<barline location="right"><bar-style>light-heavy</bar-style><repeat direction="backward"/></barline>');
    return `<measure number="${i + 1}">${parts.join('')}</measure>`;
  });
  return `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="3.1">
<work><work-title>${esc(s.title || '')}</work-title></work>
${s.composer ? `<identification><creator type="composer">${esc(s.composer)}</creator></identification>` : ''}
<part-list><score-part id="P1"><part-name>${esc(s.partName || 'Melody')}</part-name></score-part></part-list>
<part id="P1">${measures.join('')}</part>
</score-partwise>`;
}
