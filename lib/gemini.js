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
이미지의 악보를 읽고 JSON으로만 답하라.

규칙:
- 코드는 오선 위에 적힌 표기를 그대로 옮긴다 (예: G, D/F#, Em7, Csus4, A9/C#, Bb, G°). 임의로 바꾸거나 이명동음으로 고치지 말 것.
- 마디 단위로 나눈다. 한 마디에 코드가 둘이면 둘 다, 코드가 없으면 빈 배열(앞 마디 코드가 이어짐).
- 가사는 그 마디 아래의 한글 원문 그대로. 없으면 null.
- 섹션 이름은 악보의 리허설 마크(A, B, C, Intro, Interlude, Bridge, Outro, 후렴 등)를 따른다. 없으면 멜로디·가사 흐름으로 나누고 A, B, C… 로 붙인다.
- 반복 기호·1/2번 괄호·D.S.·Coda 는 form 에 풀어서 순서로 적는다.
- 키는 조표와 첫/마지막 코드로 판단한다. 단조면 m 을 붙인다.
- 이미지에 곡이 두 개 이상이면 songs 배열에 순서대로 넣는다 (좌우 또는 위아래로 붙은 스캔).
- 확신이 없는 코드는 그대로 적되 notes 에 어떤 마디가 애매했는지 남긴다.
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
    tempo: Number.isFinite(+s.tempo) && +s.tempo > 0 ? Math.round(+s.tempo) : null,
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
