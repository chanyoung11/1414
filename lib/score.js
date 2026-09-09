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
  const measures = (s.measures || []).map((m, i) => {
    const parts = [];
    const attrs = [];
    if (i === 0) {
      attrs.push(`<divisions>${DIVISIONS}</divisions>`,
        `<key><fifths>${FIFTHS[String(cur).replace(/m$/, '')] ?? 0}</fifths><mode>${/m$/.test(cur) ? 'minor' : 'major'}</mode></key>`,
        `<time><beats>${time[1]}</beats><beat-type>${time[2]}</beat-type></time>`,
        `<clef><sign>G</sign><line>2</line></clef>`);
    } else if (m.key && m.key !== cur) {
      cur = m.key;
      attrs.push(`<key><fifths>${FIFTHS[String(cur).replace(/m$/, '')] ?? 0}</fifths><mode>${/m$/.test(cur) ? 'minor' : 'major'}</mode></key>`);
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
      parts.push(`<note>${p ? `<pitch><step>${p.step}</step>${p.alter ? `<alter>${p.alter}</alter>` : ''}<octave>${p.octave}</octave></pitch>` : '<rest/>'}`
        + `<duration>${d}</duration>${n.tie ? '<tie type="start"/>' : ''}<voice>1</voice><type>${TYPE[n.d] || 'quarter'}</type>${n.dot ? '<dot/>' : ''}`
        + bs + (n.tie ? '<notations><tied type="start"/></notations>' : '') + lyr + `</note>`);
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
