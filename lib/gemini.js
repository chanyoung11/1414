// Gemini 멀티모달 OMR — 악보 이미지 한 장을 보내 "코드 차트" 구조(제목·키·박자·섹션·마디별 코드·가사)를 받는다.
// 음표 단위 채보가 아니라 찬양팀이 실제로 쓰는 리드시트 정보를 뽑는 것이 목표.
// GEMINI_API_KEY 없으면 null(미연결). 'mock' 이면 테스트용 가짜 결과. 모델은 GEMINI_MODEL (기본 gemini-3.6-flash).
// 키는 서버 환경변수로만 쓰고 클라이언트에 절대 내려보내지 않는다.
// 과금: Gemini API는 Google Cloud 결제가 아니라 AI Studio 선불 크레딧(https://aistudio.google.com/billing)으로 빠져나간다.

const BASE = 'https://generativelanguage.googleapis.com/v1beta';

export function geminiConfigured() {
  return !!process.env.GEMINI_API_KEY;
}
export function geminiModel() {
  return process.env.GEMINI_MODEL || 'gemini-3.6-flash';
}

// 표준 단가 (USD / 1M 토큰, 2026-09 기준 텍스트·이미지 입력). 2027-01-01부터 3.6~3.8 Flash는 두 배로 오름.
export const PRICE = {
  'gemini-3.8-flash': { input: 0.75, output: 3.75 },
  'gemini-3.7-flash': { input: 0.75, output: 3.75 },
  'gemini-3.6-flash': { input: 0.75, output: 3.75 },
  'gemini-3.5-flash': { input: 1.50, output: 9.00 },
  'gemini-3.5-flash-lite': { input: 0.30, output: 2.50 },
  'gemini-3.1-flash-lite': { input: 0.25, output: 1.50 },
  'gemini-3.1-pro-preview': { input: 2.00, output: 12.00 },
  'gemini-2.5-flash': { input: 0.30, output: 2.50 },
  'gemini-2.5-flash-lite': { input: 0.10, output: 0.40 },
};
export function estimateUSD(model, usage) {
  const p = PRICE[model] || PRICE['gemini-3.6-flash'];
  return (usage.input || 0) * p.input / 1e6 + ((usage.output || 0) + (usage.thinking || 0)) * p.output / 1e6;
}

// 응답 스키마 (Gemini responseSchema = OpenAPI 부분집합, 타입은 대문자)
const BAR = {
  type: 'OBJECT',
  properties: {
    chords: { type: 'ARRAY', items: { type: 'STRING' }, description: '이 마디의 코드들, 왼쪽부터. 없으면 빈 배열. 예: ["G", "D/F#"]' },
    lyric: { type: 'STRING', nullable: true, description: '이 마디 아래 가사(있으면). 원문 그대로.' },
  },
  required: ['chords'],
};
const SECTION = {
  type: 'OBJECT',
  properties: {
    name: { type: 'STRING', description: '섹션 이름. 악보에 표기된 대로(Intro, A, B, C, Bridge, Interlude, Outro, 1절, 후렴 등). 표기가 없으면 A, B 순서로.' },
    repeat: { type: 'INTEGER', nullable: true, description: '반복 횟수 표기(x2 등)가 있으면 그 수' },
    bars: { type: 'ARRAY', items: BAR },
  },
  required: ['name', 'bars'],
};
const SONG = {
  type: 'OBJECT',
  properties: {
    title: { type: 'STRING', description: '곡 제목. 없으면 빈 문자열' },
    subtitle: { type: 'STRING', nullable: true, description: '부제·원곡명·작곡가 등 제목 아래 작은 글씨' },
    key: { type: 'STRING', description: '조표/코드로 판단한 키. 예: G, Bb, F#m, Em. 모르면 빈 문자열' },
    timeSignature: { type: 'STRING', description: '박자. 예: 4/4, 6/8. 모르면 빈 문자열' },
    tempo: { type: 'INTEGER', nullable: true, description: 'BPM 표기가 있으면 숫자' },
    sections: { type: 'ARRAY', items: SECTION },
    form: { type: 'STRING', description: '연주 순서를 한 줄로. 반복 기호(D.S., 반복표, 1·2번 괄호)를 풀어서. 예: Intro – A – A – B – Int – B – B – Outro' },
    confidence: { type: 'NUMBER', description: '0~1. 코드·구조를 얼마나 확신하는지' },
    notes: { type: 'STRING', nullable: true, description: '읽기 어려웠던 부분, 애매한 코드, 특이 지시(rit., 전조 등)' },
  },
  required: ['title', 'key', 'timeSignature', 'sections', 'form', 'confidence'],
};
const SCHEMA = {
  type: 'OBJECT',
  properties: {
    songs: { type: 'ARRAY', items: SONG, description: '이미지에 곡이 여러 개면 순서대로 각각' },
  },
  required: ['songs'],
};

const PROMPT = `너는 한국 교회 찬양팀의 악보(리드시트: 멜로디 오선 + 코드 + 한글 가사)를 읽어 코드 차트로 옮기는 전문가다.
이미지의 악보를 읽고 JSON으로만 답하라. 아래 규칙은 순서대로 우선한다.

[1] 코드는 "적힌 글자 그대로" 옮긴다. 이것이 가장 중요하다.
- 절대 다른 키로 바꾸지 않는다. 이명동음으로 고쳐 적지 않는다.
  악보에 Fb 라고 적혀 있으면 Fb 다. E 로 바꾸지 말 것. Cb/Eb 는 Cb/Eb 다. B/D# 로 바꾸지 말 것.
- 곡 중간에 조표가 바뀌어(전조) 낯선 이름(Fb, Cb, Abm7, Gb…)이 나와도 그대로 옮긴다.
  "읽기 쉬운 키로 정리"하는 것은 오답이다.
- 괄호·위첨자도 유지한다: A9/C#, D(sus4), E(sus4), G°, Am7(b5).

[2] 마디는 악보에 그려진 것만 담는다. 반복해서 늘리지 않는다.
- sections[].bars 에는 악보에 실제로 그려진 마디만 순서대로 넣는다.
- 반복 기호(:‖), 1·2번 괄호, D.S., Coda 때문에 같은 마디를 두 번 적지 말 것.
  반복은 sections 를 복제하지 말고 form 문자열에만 순서로 적는다.
- 1·2번 괄호가 있으면 그 마디의 lyric 앞에 "1." "2." 를 붙여 구분한다.
- 한 마디에 코드가 둘이면 둘 다, 코드가 없으면 빈 배열(앞 마디가 이어짐).

[3] 섹션 이름은 정해진 방식으로만 붙인다.
- 악보에 리허설 마크(A, B, C… 또는 Intro/Interlude/Bridge/Ending)가 인쇄돼 있으면 그것을 그대로 쓴다.
- 인쇄된 마크가 없으면 나오는 순서대로 Intro, A, B, C, D … 만 쓴다.
  "Verse", "Chorus", "후렴", "Bridge 1", "Key Change" 같은 이름을 지어내지 않는다.
- 전조된 구간도 같은 규칙을 따르고, 이름 뒤에 조를 덧붙이지 않는다.

[4] 가사는 그 마디 아래에 인쇄된 한글 그대로. 음절 사이의 붙임줄(-)도 살린다. 없으면 null.

[5] 나머지
- key 는 첫 조표와 시작·끝 코드로 판단한다. 단조면 m 을 붙인다. 곡 중간 전조는 key 에 반영하지 않는다.
- form 은 연주 순서를 한 줄로. 반복을 풀어서 적는다. 예: Intro – A – A – B – C – C – B'
- 이미지에 곡이 두 개 이상이면 songs 배열에 순서대로 넣는다 (좌우 또는 위아래로 붙은 스캔).
- 애매했던 마디는 notes 에 "몇 번째 섹션 몇 마디"로 남긴다.
- 악보가 아니거나 읽을 수 없으면 songs 를 빈 배열로.`;

// image: { b64, mime } , opts: { model?, thinking? }
// → { songs: [...], model, usage: { input, output, total }, raw }
export async function transcribeSheet(image, opts = {}) {
  const key = process.env.GEMINI_API_KEY;
  if (!key) return null;
  const model = opts.model || geminiModel();
  if (key === 'mock') return { songs: [mockSong()], model: 'mock', usage: { input: 0, output: 0, total: 0 } };

  const generationConfig = { responseMimeType: 'application/json', responseSchema: SCHEMA, temperature: 0.1 };
  // 생각(thinking) 조절: 숫자면 2.5 계열의 thinkingBudget, 문자열(minimal|low|medium|high)이면 3.x 계열의 thinkingLevel
  // 기본 'low': 샘플 악보 비교(2026-09-08)에서 기본 생각(약 2,800토큰)은 낯선 이명동음(Fb, Cb)을 멋대로 "고쳐" 전조 구간 코드 5개를 틀렸고,
  // low 는 코드 오류 0·비용 1/4·속도 3.5배였다. 끄기(0)는 3.x 모델이 거부한다.
  const thinking = opts.thinking != null ? opts.thinking : (process.env.GEMINI_THINKING != null && process.env.GEMINI_THINKING !== '' ? process.env.GEMINI_THINKING : 'low');
  if (thinking != null) {
    if (/^\d+$/.test(String(thinking))) generationConfig.thinkingConfig = { thinkingBudget: +thinking };
    else if (/^(minimal|low|medium|high)$/i.test(String(thinking))) generationConfig.thinkingConfig = { thinkingLevel: String(thinking).toUpperCase() };
  }

  const body = {
    contents: [{ role: 'user', parts: [{ text: PROMPT }, { inline_data: { mime_type: image.mime || 'image/jpeg', data: image.b64 } }] }],
    generationConfig,
  };
  const r = await fetch(`${BASE}/models/${encodeURIComponent(model)}:generateContent?key=${encodeURIComponent(key)}`, {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) {
    const msg = (j.error && j.error.message) || ('Gemini ' + r.status);
    const err = new Error(msg); err.status = r.status; err.code = j.error && j.error.status; throw err;
  }
  const cand = (j.candidates || [])[0];
  const text = cand && cand.content && cand.content.parts ? cand.content.parts.map((p) => p.text || '').join('') : '';
  let parsed;
  try { parsed = JSON.parse(text); } catch (e) {
    const err = new Error('Gemini 응답이 JSON이 아니에요: ' + text.slice(0, 200)); err.code = 'bad_json'; throw err;
  }
  const u = j.usageMetadata || {};
  return {
    songs: normalize(parsed.songs),
    model,
    finishReason: cand && cand.finishReason,
    usage: { input: u.promptTokenCount || 0, output: u.candidatesTokenCount || 0, thinking: u.thoughtsTokenCount || 0, total: u.totalTokenCount || 0 },
  };
}

/* ---------- 악보 재구성 (사진 → 악보 데이터) ---------- */
// 짧은 JSON 으로 받는다. MusicXML 로 받으면 같은 내용에 48배를 쓰게 된다.
const NOTE_S = { type: 'OBJECT', properties: {
  p: { type: 'STRING', nullable: true, description: '음이름+옥타브 (A4, Bb3, F#5). 쉼표는 null' },
  d: { type: 'INTEGER', description: '1=온음표 2=2분 4=4분 8=8분 16=16분 32=32분' },
  dot: { type: 'BOOLEAN', nullable: true }, tie: { type: 'BOOLEAN', nullable: true },
  l: { type: 'ARRAY', items: { type: 'STRING' }, nullable: true, description: '절별 가사 음절. 이어지는 음절은 끝에 - 를 붙임' },
}, required: ['p', 'd'] };
const MEASURE_S = { type: 'OBJECT', properties: {
  c: { type: 'ARRAY', nullable: true, items: { type: 'OBJECT', properties: { b: { type: 'NUMBER', description: '마디 안 시작 박 (0 부터)' }, t: { type: 'STRING' } }, required: ['b', 't'] } },
  n: { type: 'ARRAY', items: NOTE_S },
  rs: { type: 'BOOLEAN', nullable: true, description: '도돌이표 시작' }, re: { type: 'BOOLEAN', nullable: true, description: '도돌이표 끝' },
  end: { type: 'INTEGER', nullable: true, description: '1·2번 괄호' },
  key: { type: 'STRING', nullable: true, description: '이 마디부터 조가 바뀌면 새 조' },
}, required: ['n'] };
const SCORE_S = { type: 'OBJECT', properties: { songs: { type: 'ARRAY', items: { type: 'OBJECT', properties: {
  title: { type: 'STRING' }, composer: { type: 'STRING', nullable: true }, key: { type: 'STRING' }, time: { type: 'STRING' },
  tempo: { type: 'INTEGER', nullable: true }, verses: { type: 'INTEGER' }, pickup: { type: 'BOOLEAN', nullable: true, description: '첫 마디가 못갖춘마디면 true' },
  form: { type: 'STRING', nullable: true, description: '연주 순서 한 줄' }, measures: { type: 'ARRAY', items: MEASURE_S },
  confidence: { type: 'NUMBER' }, notes: { type: 'STRING', nullable: true },
}, required: ['title', 'key', 'time', 'verses', 'measures', 'confidence'] } } }, required: ['songs'] };

const SCORE_PROMPT = `이 악보 사진을 읽어 JSON 으로 옮겨라.

[0] 사진에 보이는 마디를 처음부터 끝까지 하나도 빠뜨리지 않는다.
 오선이 여러 줄이면 모든 줄을 읽는다. 중간에 끊지 말 것.
 사진에 오선이 한 줄뿐이면 그 줄의 마디만 적는다. 없는 마디를 지어내지 말 것.

[1] 코드는 인쇄된 글자 그대로. 이것이 가장 중요하다.
 악보에 Fb 면 Fb 다. E 나 Db 로 바꾸면 오답이다. Cb/Eb 는 Cb/Eb 다.
 곡 중간에 조가 바뀌어 Fb, Cb, Abm7, Gb 같은 낯선 이름이 나와도 그대로 옮긴다.
 A9/C#, D(sus4), G° 처럼 괄호·기호도 그대로.

[2] 음표는 마디마다 길이 합이 박자와 정확히 맞아야 한다.
 4/4 면 한 마디의 (4/d, 점음표는 1.5배) 합이 정확히 4 박이다. 안 맞으면 다시 세어라.
 쉼표도 음표처럼 넣는다 (p 를 null 로).
 첫 마디가 못갖춘마디(앞꾸밈)면 pickup 을 true 로 하고 그 마디만 짧아도 된다.

[3] 마디는 악보에 그려진 것만. 도돌이표로 반복되는 마디를 두 번 적지 말 것.
 도돌이표는 rs/re, 1·2번 괄호는 end 로 표시한다.

[4] 가사는 음표 하나에 음절 하나씩 l 에 넣는다.
 한 음표 아래 1절·2절이 두 줄로 적혀 있으면 l:["1절음절","2절음절"] 로 넣고 verses 를 2 로.
 여러 음표에 걸치는 음절은 첫 음표에만 넣고 끝에 - 를 붙인다. 가사가 없는 음표는 l 을 생략.

[5] 조가 바뀌는 마디에 key 를 적는다. 곡 전체 key 는 첫 조표 기준.

[6] 옥타브는 높은음자리표(사진의 오선) 기준으로 적는다.
 오선 첫째 줄(아래)이 E4, 셋째 줄 가운데가 B4, 다섯째 줄(위)이 F5 다.
 오선 아래 첫 덧줄이 C4(가온다). 보통 찬양 멜로디는 C4~A5 안에 들어온다.
 한 옥타브 아래로 적는 실수를 하지 말 것.`;

async function callGemini(parts, generationConfig, model) {
  const key = process.env.GEMINI_API_KEY;
  const r = await fetch(`${BASE}/models/${encodeURIComponent(model)}:generateContent?key=${encodeURIComponent(key)}`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ contents: [{ role: 'user', parts }], generationConfig }),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) { const e = new Error((j.error && j.error.message) || ('Gemini ' + r.status)); e.status = r.status; e.code = j.error && j.error.status; throw e; }
  const cand = (j.candidates || [])[0];
  const text = cand && cand.content && cand.content.parts ? cand.content.parts.map((p) => p.text || '').join('') : '';
  const u = j.usageMetadata || {};
  return { text, finishReason: cand && cand.finishReason, usage: { input: u.promptTokenCount || 0, output: u.candidatesTokenCount || 0, thinking: u.thoughtsTokenCount || 0 } };
}

// 사진 → 악보. 박자가 안 맞는 마디는 그 마디만 다시 물어 고친다 (한 번)
export async function transcribeScore(image, opts = {}) {
  const key = process.env.GEMINI_API_KEY;
  if (!key) return null;
  const model = opts.model || geminiModel();
  if (key === 'mock') return { songs: [mockScore()], model: 'mock', usage: { input: 0, output: 0, total: 0 }, badMeasures: [] };
  const img = { inline_data: { mime_type: image.mime || 'image/jpeg', data: image.b64 } };
  const cfg = { temperature: 0.1, responseMimeType: 'application/json', responseSchema: SCORE_S, maxOutputTokens: 32768,
    thinkingConfig: { thinkingLevel: (opts.thinking || 'LOW').toUpperCase() } };
  const first = await callGemini([{ text: SCORE_PROMPT }, img], cfg, model);
  let parsed;
  try { parsed = JSON.parse(first.text); } catch (e) { const err = new Error('악보를 옮기다 응답이 끊겼어요. 다시 시도해 주세요'); err.code = 'bad_json'; throw err; }
  const songs = normalizeScores(parsed.songs);
  const usage = { ...first.usage };
  // 박자 검증 → 어긋난 마디만 다시
  const { checkMeasures, durTicks: durTicks0, measureTicks: measureTicks0 } = await import('./score.js');
  let badTotal = [];
  for (const [si, s] of songs.entries()) {
    let bad = checkMeasures(s).filter((b) => !(b.measure === 1 && s.pickup));
    if (bad.length && opts.repair !== false) {
      // 한 번에 몰아 물으면 답이 길어져 잘린다. 8마디씩 끊어 묻는다
      const fixCfg = { temperature: 0.1, responseMimeType: 'application/json', maxOutputTokens: 16384,
        thinkingConfig: { thinkingLevel: 'LOW' },
        responseSchema: { type: 'OBJECT', properties: { fixes: { type: 'ARRAY', items: { type: 'OBJECT', properties: { measure: { type: 'INTEGER' }, n: { type: 'ARRAY', items: NOTE_S } }, required: ['measure', 'n'] } } }, required: ['fixes'] } };
      for (let k = 0; k < Math.min(bad.length, 24); k += 8) {
        try {
          const ask = bad.slice(k, k + 8).map((b) => ({ measure: b.measure, n: s.measures[b.measure - 1].n }));
          const msg = `아래는 방금 이 악보에서 옮긴 마디들인데, 음표 길이의 합이 ${s.time} 박자와 맞지 않는다.
사진에서 해당 마디를 다시 보고 음표와 쉼표를 정확히 세어 고쳐라. 가사(l)는 그대로 유지한다.
한 마디의 합은 정확히 ${(String(s.time).split('/')[0] || 4)} 박이어야 한다 (4/d, 점음표는 1.5배).
곡: ${s.title} / 조 ${s.key} / 박자 ${s.time}
고칠 마디: ${JSON.stringify(ask)}`;
          const fix = await callGemini([{ text: msg }, img], fixCfg, model);
          usage.output += fix.usage.output; usage.thinking += fix.usage.thinking; usage.input += fix.usage.input;
          const fj = JSON.parse(fix.text);
          for (const f of (fj.fixes || [])) {
            const idx = (+f.measure || 0) - 1;
            const m0 = s.measures[idx];
            if (!m0 || !Array.isArray(f.n) || !f.n.length) continue;
            const fixed = cleanNotes(f.n);
            // 고친 쪽이 박자에 더 안 맞으면 버린다. 안 그러면 더 나빠질 수 있다
            const sum = (arr) => arr.reduce((a, n) => a + durTicks0(n), 0);
            const want = measureTicks0(s.time);
            if (Math.abs(sum(fixed) - want) >= Math.abs(sum(m0.n || []) - want)) continue;
            // 가사는 원래 것을 지킨다 (모델이 자주 빠뜨린다)
            const old = m0.n || [];
            s.measures[idx].n = fixed.map((n, i) => (old[i] && old[i].l && !n.l ? { ...n, l: old[i].l } : n));
          }
        } catch (e) { console.error('score repair', e.message); }
      }
      bad = checkMeasures(s).filter((b) => !(b.measure === 1 && s.pickup));
    }
    badTotal = badTotal.concat(bad.map((b) => ({ song: si, ...b })));
  }
  usage.total = usage.input + usage.output + usage.thinking;
  return { songs, model, usage, badMeasures: badTotal, finishReason: first.finishReason };
}
const cleanNotes = (arr) => (Array.isArray(arr) ? arr : []).slice(0, 64).map((n) => ({
  p: n && n.p ? String(n.p).trim() : null,
  d: [1, 2, 4, 8, 16, 32].includes(+n.d) ? +n.d : 4,
  ...(n && n.dot ? { dot: true } : {}), ...(n && n.tie ? { tie: true } : {}),
  ...(n && Array.isArray(n.l) && n.l.length ? { l: n.l.slice(0, 4).map((x) => String(x).slice(0, 12)) } : {}),
}));
function normalizeScores(songs) {
  return (Array.isArray(songs) ? songs : []).slice(0, 4).map((s) => ({
    title: str(s.title), composer: s.composer ? str(s.composer) : null,
    key: str(s.key).replace(/\s/g, '') || 'C', time: /^\d+\/\d+$/.test(str(s.time)) ? str(s.time) : '4/4',
    tempo: Number.isFinite(+s.tempo) && +s.tempo >= 20 && +s.tempo <= 400 ? Math.round(+s.tempo) : null,
    verses: Math.max(1, Math.min(6, Math.round(+s.verses) || 1)), pickup: !!s.pickup,
    form: s.form ? str(s.form) : '', confidence: Math.max(0, Math.min(1, +s.confidence || 0)),
    notes: s.notes ? str(s.notes) : null,
    measures: (Array.isArray(s.measures) ? s.measures : []).slice(0, 400).map((m) => ({
      ...(Array.isArray(m.c) && m.c.length ? { c: m.c.slice(0, 8).map((c) => ({ b: +c.b || 0, t: str(c.t).replace(/\s/g, '').slice(0, 16) })).filter((c) => c.t) } : {}),
      n: cleanNotes(m.n),
      ...(m.rs ? { rs: true } : {}), ...(m.re ? { re: true } : {}),
      ...(m.end ? { end: Math.max(1, Math.min(4, Math.round(+m.end))) } : {}),
      ...(m.key ? { key: str(m.key).replace(/\s/g, '').slice(0, 6) } : {}),
    })),
  })).filter((s) => s.measures.length);
}
function mockScore() {
  return { title: '우리 주 하나님', composer: null, key: 'A', time: '4/4', tempo: 70, verses: 2, pickup: false,
    form: 'Intro – A – B', confidence: 0.9, notes: 'mock',
    measures: [
      { c: [{ b: 0, t: 'A' }], n: [{ p: 'A4', d: 4, l: ['우', '재'] }, { p: 'B4', d: 4, l: ['리', '하'] }, { p: 'C#5', d: 2, l: ['주', '실'] }] },
      { c: [{ b: 0, t: 'Bm7' }, { b: 2, t: 'A9/C#' }], n: [{ p: 'B4', d: 4 }, { p: 'A4', d: 4 }, { p: null, d: 2 }], re: true },
    ] };
}

// 사용 가능한 모델 목록 (무료 호출) — 키 진단용
export async function listModels() {
  const key = process.env.GEMINI_API_KEY;
  if (!key || key === 'mock') return [];
  const r = await fetch(`${BASE}/models?key=${encodeURIComponent(key)}&pageSize=100`);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) { const err = new Error((j.error && j.error.message) || ('Gemini ' + r.status)); err.status = r.status; throw err; }
  return (j.models || []).filter((m) => (m.supportedGenerationMethods || []).includes('generateContent')).map((m) => ({ name: m.name.replace(/^models\//, ''), displayName: m.displayName, inputLimit: m.inputTokenLimit }));
}

// 응답 정리: 문자열 트림, 코드 배열 보정, 빈 섹션 제거
function normalize(songs) {
  return (Array.isArray(songs) ? songs : []).map((s) => ({
    title: str(s.title), subtitle: s.subtitle == null ? null : str(s.subtitle),
    key: str(s.key).replace(/\s+/g, ''), timeSignature: str(s.timeSignature).replace(/\s+/g, ''),
    tempo: Number.isFinite(+s.tempo) && +s.tempo >= 20 && +s.tempo <= 400 ? Math.round(+s.tempo) : null,
    sections: (Array.isArray(s.sections) ? s.sections : []).map((sec) => ({
      name: str(sec.name) || '?', repeat: Number.isFinite(+sec.repeat) && +sec.repeat > 1 ? Math.round(+sec.repeat) : null,
      bars: (Array.isArray(sec.bars) ? sec.bars : []).map((b) => ({
        chords: (Array.isArray(b.chords) ? b.chords : []).map((c) => str(c).replace(/\s+/g, '')).filter(Boolean),
        lyric: b.lyric == null ? null : str(b.lyric) || null,
      })),
    })).filter((sec) => sec.bars.length),
    form: str(s.form), confidence: Math.max(0, Math.min(1, +s.confidence || 0)),
    notes: s.notes == null ? null : str(s.notes) || null,
  }));
}
const str = (v) => (v == null ? '' : String(v)).trim();

// 차트 → 앱의 곡 폼 문자열 (예: "Intro – A – A – B – Int(2) – B – Outro") 로 쓰기 좋게 섹션 순서만 돌려줌
export function chartToForm(song) {
  return song && song.form ? song.form : (song && song.sections ? song.sections.map((s) => s.name).join(' – ') : '');
}

function mockSong() {
  return {
    title: '우리 주 하나님', subtitle: null, key: 'G', timeSignature: '4/4', tempo: 72,
    sections: [
      { name: 'Intro', repeat: null, bars: [{ chords: ['G'], lyric: null }, { chords: ['Bm7'], lyric: null }, { chords: ['A9/C#'], lyric: null }, { chords: ['C', 'G/B'], lyric: null }] },
      { name: 'A', repeat: null, bars: [{ chords: ['G'], lyric: '우리 주 하나님' }, { chords: ['Bm7'], lyric: '온 땅의 주인' }, { chords: ['C'], lyric: '높이 계신 주' }, { chords: ['D'], lyric: '경배합니다' }] },
      { name: 'B', repeat: 2, bars: [{ chords: ['C'], lyric: '주의 이름' }, { chords: ['G/B'], lyric: '높이세' }, { chords: ['C'], lyric: '주의 이름' }, { chords: ['D(sus4)', 'D'], lyric: '높이세' }] },
    ],
    form: 'Intro – A – B – B – Outro', confidence: 0.9, notes: 'mock',
  };
}
