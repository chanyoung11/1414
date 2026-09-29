// Gemini 멀티모달 OMR — 악보 이미지 한 장을 보내 "코드 차트" 구조(제목·키·박자·섹션·마디별 코드·가사)를 받는다.
// 음표 단위 채보가 아니라 찬양팀이 실제로 쓰는 리드시트 정보를 뽑는 것이 목표.
// GEMINI_API_KEY 없으면 null(미연결). 'mock' 이면 테스트용 가짜 결과. 모델은 GEMINI_MODEL (기본 gemini-3.6-flash).
// 키는 서버 환경변수로만 쓰고 클라이언트에 절대 내려보내지 않는다.
// 과금: Gemini API는 Google Cloud 결제가 아니라 AI Studio 선불 크레딧(https://aistudio.google.com/billing)으로 빠져나간다.

import { checkMeasures, durTicks, measureTicks, normPitch, resolveTime, scoreSanity, reasonKo, validTime } from './score.js';

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
- 악보가 아니거나 읽을 수 없으면 songs 를 빈 배열로. 잘리거나 흐려서 안 보이는 코드·가사를 지어내지 않는다.`;

// image: { b64, mime } , opts: { model?, thinking?, retry?, reserve?, release? }
// → { songs: [...], model, usage: { input, output, thinking, total }, calls }
// 말이 안 되는 결과(코드가 아닌 글자를 코드로 · 끝없는 되풀이 · 빈 결과)는 한 번 다시 묻고(reserve 로 하루 한도 자리를 잡은 뒤),
// 그래도 안 되면 code 'nonsense' 로 던진다 — 라우트가 이번 달 채보 횟수를 돌려주고 까닭을 알린다
export async function transcribeSheet(image, opts = {}) {
  const key = process.env.GEMINI_API_KEY;
  if (!key) return null;
  const model = opts.model || geminiModel();
  // 가짜 엔진의 실패: 'MockFail'(base64 TW9ja0ZhaWw)로 시작하는 이미지. 실패하면 크레딧을 돌려주는지 시험한다
  if (key === 'mock' && String(image.b64 || '').startsWith('TW9ja0ZhaWw')) throw new Error('mock failure');
  if (key === 'mock') return { songs: [mockSong()], model: 'mock', usage: { input: 0, output: 0, total: 0 } };

  // 답 길이에 끝을 둔다. 없으면 모델 최대치까지 생성·과금될 수 있다 (코드 차트는 보통 수천 토큰)
  const generationConfig = { responseMimeType: 'application/json', responseSchema: SCHEMA, temperature: 0.1, maxOutputTokens: 32768 };
  // 생각(thinking) 조절: 숫자면 2.5 계열의 thinkingBudget, 문자열(minimal|low|medium|high)이면 3.x 계열의 thinkingLevel
  // 기본 'low': 샘플 악보 비교(2026-09-08)에서 기본 생각(약 2,800토큰)은 낯선 이명동음(Fb, Cb)을 멋대로 "고쳐" 전조 구간 코드 5개를 틀렸고,
  // low 는 코드 오류 0·비용 1/4·속도 3.5배였다. 끄기(0)는 3.x 모델이 거부한다.
  const thinking = opts.thinking != null ? opts.thinking : (process.env.GEMINI_THINKING != null && process.env.GEMINI_THINKING !== '' ? process.env.GEMINI_THINKING : 'low');
  if (thinking != null) {
    if (/^\d+$/.test(String(thinking))) generationConfig.thinkingConfig = { thinkingBudget: +thinking };
    else if (/^(minimal|low|medium|high)$/i.test(String(thinking))) generationConfig.thinkingConfig = { thinkingLevel: String(thinking).toUpperCase() };
  }
  const img = { inline_data: { mime_type: image.mime || 'image/jpeg', data: image.b64 } };
  const usage = { input: 0, output: 0, thinking: 0, total: 0 };
  let calls = 0, finishReason;
  const ask = async (again) => {
    const r = await callGemini([{ text: again ? `${PROMPT}\n\n[다시] 앞서 이 사진을 옮긴 결과가 말이 안 됐다: ${again}. 사진을 처음부터 다시 보고 적힌 그대로 옮겨라.` : PROMPT }, img], generationConfig, model);
    calls++; finishReason = r.finishReason;
    usage.input += r.usage.input; usage.output += r.usage.output; usage.thinking += r.usage.thinking;
    usage.total = usage.input + usage.output + usage.thinking;
    let parsed;
    try { parsed = JSON.parse(r.text); } catch (e) {
      const err = new Error('Gemini 응답이 JSON이 아니에요: ' + r.text.slice(0, 200)); err.code = 'bad_json'; err.usage = { ...usage }; throw err;
    }
    return chartSanity(normalize(parsed && parsed.songs));
  };
  let got = await ask();
  // 빈 결과(악보가 아님)는 다시 물어도 같다 — 바로 알린다
  if (!got.ok && !got.hard.includes('empty') && opts.retry !== false && (!opts.reserve || await opts.reserve())) {
    try { got = await ask(got.message); }
    catch (e) { if (e.status) { if (opts.release) await opts.release(); } else if (e.code !== 'bad_json') throw e; }   // 오류 응답은 과금되지 않는다 · 깨진 답은 처음 답으로
  }
  if (!got.ok) {
    const err = new Error('악보를 제대로 읽지 못했어요 — ' + got.message);
    err.code = 'nonsense'; err.reasons = got.hard; err.usage = { ...usage }; err.calls = calls; throw err;
  }
  return { songs: got.songs, model, finishReason, usage, calls };
}

// 코드 차트가 말이 되는지. 코드가 아닌 것(가사·'x2'·'1.'·반복 기호)은 코드 칸에서 뺀다.
// 뺀 것이 많으면(글자를 코드로 읽음) · 같은 마디가 끝없이 되풀이되면 · 코드도 가사도 없으면 말이 안 되는 결과
const CHORD_TOKEN = /^\(?(?:N\.?C\.?|[A-G](?:#|b)?[A-Za-z0-9#+°ºøΔ△(),.^-]*(?:\/[A-G](?:#|b)?)?|\/[A-G](?:#|b)?)\)?$/;
export function chartSanity(songs) {
  let tokens = 0, dropped = 0, bars = 0, loop = false;
  for (const s of songs) for (const sec of s.sections) {
    let run = 1, prev = null;
    for (const b of sec.bars) {
      const all = b.chords.map((c) => c.replace(/♯/g, '#').replace(/♭/g, 'b'));
      const keep = all.filter((c) => c.length <= 16 && CHORD_TOKEN.test(c));
      tokens += all.length; dropped += all.length - keep.length; bars++;
      b.chords = keep;
      const sig = JSON.stringify([keep, b.lyric]);
      run = sig === prev && (keep.length || b.lyric) ? run + 1 : 1; prev = sig;
      if (run >= 24) loop = true;
    }
  }
  const useful = songs.filter((s) => s.sections.some((sec) => sec.bars.some((b) => b.chords.length || b.lyric)));
  const hard = [];
  if (!useful.length) hard.push('empty');
  if (tokens >= 4 && dropped > tokens * 0.3) hard.push('chords');
  if (bars > 400 || loop) hard.push('loop');
  const KO = { empty: '악보에서 코드·가사를 찾지 못했어요', chords: '코드가 아닌 글자를 코드로 읽었어요', loop: '같은 마디만 되풀이돼요' };
  return { ok: !hard.length, hard, songs: useful, message: hard.map((h) => KO[h]).join(' · ') };
}

/* ---------- 악보 재구성 (사진 → 악보 데이터) ---------- */
// 짧은 JSON 으로 받는다. MusicXML 로 받으면 같은 내용에 48배를 쓰게 된다.
const NOTE_S = { type: 'OBJECT', properties: {
  p: { type: 'STRING', nullable: true, description: '음이름+옥타브 (A4, Bb3, F#5). 쉼표는 null' },
  d: { type: 'INTEGER', description: '음표 모양: 1=온음표 2=2분 4=4분 8=8분 16=16분 32=32분. 박 수가 아니다' },
  dot: { type: 'BOOLEAN', nullable: true }, tie: { type: 'BOOLEAN', nullable: true },
  l: { type: 'ARRAY', items: { type: 'STRING' }, nullable: true, description: '절별 가사 음절. 이어지는 음절은 끝에 - 를 붙임' },
}, required: ['p', 'd'] };
const MEASURE_S = { type: 'OBJECT', properties: {
  c: { type: 'ARRAY', nullable: true, items: { type: 'OBJECT', properties: { b: { type: 'NUMBER', description: '마디 안에서 코드가 시작하는 자리. 박자표 아래 숫자의 음표로 0 부터 센다 (4/4 는 4분음표 0~3, 12/8·6/8 은 8분음표 0~11)' }, t: { type: 'STRING' } }, required: ['b', 't'] } },
  n: { type: 'ARRAY', items: NOTE_S },
  rs: { type: 'BOOLEAN', nullable: true, description: '도돌이표 시작' }, re: { type: 'BOOLEAN', nullable: true, description: '도돌이표 끝' },
  end: { type: 'INTEGER', nullable: true, description: '1·2번 괄호' },
  key: { type: 'STRING', nullable: true, description: '이 마디부터 조가 바뀌면 새 조' },
}, required: ['n'] };
const SCORE_S = { type: 'OBJECT', properties: { songs: { type: 'ARRAY', items: { type: 'OBJECT', properties: {
  title: { type: 'STRING', description: '사진에 크게 인쇄된 곡 제목. 안 보이면 빈 문자열 (가사를 제목으로 적지 말 것)' },
  composer: { type: 'STRING', nullable: true }, key: { type: 'STRING' },
  time: { type: 'STRING', description: '박자 (4/4, 3/4, 6/8, 12/8). 이 사진에 박자표가 안 보이면 알려 준 박자, 그것도 없으면 빈 문자열' },
  tempo: { type: 'INTEGER', nullable: true }, verses: { type: 'INTEGER' }, pickup: { type: 'BOOLEAN', nullable: true, description: '첫 마디가 못갖춘마디면 true' },
  form: { type: 'STRING', nullable: true, description: '연주 순서 한 줄' }, measures: { type: 'ARRAY', items: MEASURE_S },
  confidence: { type: 'NUMBER' }, notes: { type: 'STRING', nullable: true },
  problem: { type: 'STRING', nullable: true, description: '오선이 잘려 음표가 안 보이거나 흐려서 읽을 수 없으면 그 까닭. 읽을 수 있으면 null' },
}, required: ['title', 'key', 'time', 'verses', 'measures', 'confidence'] } } }, required: ['songs'] };

const SCORE_PROMPT = `이 사진은 한국 교회 찬양 악보(높은음자리표 멜로디 + 코드 + 한글 가사)의 일부다. 보이는 그대로 JSON 으로 옮겨라.

[0] 사진에 보이는 마디를 처음부터 끝까지 하나도 빠뜨리지 않는다.
 오선이 여러 줄이면 모든 줄을 읽는다. 중간에 끊지 말 것.
 사진에 오선이 한 줄뿐이면 그 줄의 마디만 적는다. 없는 마디·음표를 지어내지 말 것.
 오선이 잘려 음표 머리가 안 보이거나 너무 흐려 읽을 수 없으면, 짐작해서 채우지 말고
 problem 에 까닭을 적고 measures 를 빈 배열로 둔다. 틀린 악보보다 빈 답이 낫다.

[1] 코드는 인쇄된 글자 그대로. 이것이 가장 중요하다.
 악보에 Fb 면 Fb 다. E 나 Db 로 바꾸면 오답이다. Cb/Eb 는 Cb/Eb 다.
 곡 중간에 조가 바뀌어 Fb, Cb, Abm7, Gb 같은 낯선 이름이 나와도 그대로 옮긴다.
 A9/C#, D(sus4), G° 처럼 괄호·기호도 그대로.

[2] 음표는 보이는 모양 그대로 옮긴다 (머리가 비었는지·꼬리 수·점).
 d 는 음표 모양이다 (4=4분음표, 8=8분음표, 2=2분음표). 박 수로 적지 말 것. 점음표는 dot 을 true 로.
 쉼표도 음표처럼 넣는다 (p 를 null 로).
 그대로 옮기면 마디마다 길이 합이 박자와 맞는다: 4/4 는 4분음표 4개, 3/4 는 3개, 6/8 은 8분음표 6개(점4분음표 2개), 12/8 은 8분음표 12개(점4분음표 4개).
 합이 안 맞으면 음표를 다시 세어라. 그러나 박자에 맞추려고 없는 음표·쉼표를 넣거나 음 높이·길이를 바꾸지 말 것.
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
 한 옥타브 아래로 적는 실수를 하지 말 것.

[7] 박자(time)는 사진에 인쇄된 박자표를 적는다. 박자표는 보통 곡의 첫 줄에만 인쇄된다.
 박자표가 안 보이고 알려 준 박자도 없으면 4/4 로 짐작하지 말고 빈 문자열로 둔다.
 title 은 곡 제목이 크게 인쇄돼 보일 때만 적는다.`;
// 줄 단위로 읽을 때 앞 줄에서 읽은 것(박자·조)과 몇 번째 줄인지를 알려 준다. 박자표는 첫 줄에만 인쇄돼서
// 둘째 줄부터는 AI 가 박자를 모른 채 4/4 로 짐작하고 음표를 4/4 에 맞게 지어냈다 (12/8 샘플에서 재현)
function scorePrompt(hint, again) {
  let p = SCORE_PROMPT;
  if (hint) {
    const where = hint.line ? `이 사진은 악보 한 장을 오선 줄마다 잘라 낸 것 중 ${hint.line}번째 줄이다${hint.lines ? ` (모두 ${hint.lines}줄)` : ''}.` : '이 사진은 악보 한 장을 오선 줄마다 잘라 낸 것 중 하나다.';
    p += `\n\n[앞 줄에서 읽은 것] ${where}`
      + (hint.time ? `\n 이 곡의 박자는 ${hint.time} 이다 (곡 첫 줄에서 읽음). 이 줄에 다른 박자표가 새로 인쇄돼 있지 않으면 time 을 ${hint.time} 으로 적고 그 박자로 음표를 읽어라.` : '')
      + (hint.key ? `\n 앞 줄의 조는 ${hint.key} 다. 이 줄의 조표가 같으면 key 를 ${hint.key} 로 적는다.` : '');
  }
  if (again) p += `\n\n[다시] 앞서 이 사진을 옮긴 결과가 말이 안 됐다 (${again}). 사진을 처음부터 다시 보고 보이는 그대로 옮겨라. 안 보이는 음표를 지어내지 말고, 정말 읽을 수 없으면 problem 에 적어라.`;
  return p;
}
const cleanHint = (h) => {
  if (!h || typeof h !== 'object') return null;
  const time = validTime(h.time);
  const key = /^[A-G](#|b)?m?$/.test(String(h.key || '').trim()) ? String(h.key).trim() : '';
  const int = (v) => (Number.isInteger(+v) && +v >= 1 && +v <= 60 ? +v : 0);
  const out = { time, key, line: int(h.line), lines: int(h.lines) };
  return out.time || out.key || out.line ? out : null;
};

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

// 사진 → 악보. opts.hint = { time, key, line, lines } (줄 단위로 읽을 때 앞 줄에서 읽은 것)
// 1) 박자를 다시 정한다 (인쇄된 것 · 알려 준 것 · 음 길이 합) 2) 말이 안 되면 한 번 다시 묻는다 3) 박자가 안 맞는 마디만 다시 물어 고친다
// 4) 그래도 말이 안 되면 code 'nonsense' 로 던진다 — 틀린 악보를 그리느니 까닭을 알린다.
// 다시 묻기·고치기는 부르기 전에 opts.reserve() 로 하루 한도 자리를 잡는다 (다 찼으면 더 묻지 않는다)
export async function transcribeScore(image, opts = {}) {
  const key = process.env.GEMINI_API_KEY;
  if (!key) return null;
  const model = opts.model || geminiModel();
  const hint = cleanHint(opts.hint);
  if (key === 'mock') {
    const s = mockScore(); const t = resolveTime(s, hint);
    return { songs: [s], model: 'mock', usage: { input: 0, output: 0, total: 0 }, badMeasures: [], time: { from: t.from } };
  }
  const img = { inline_data: { mime_type: image.mime || 'image/jpeg', data: image.b64 } };
  const cfg = { temperature: 0.1, responseMimeType: 'application/json', responseSchema: SCORE_S, maxOutputTokens: 32768,
    thinkingConfig: { thinkingLevel: (opts.thinking || 'LOW').toUpperCase() } };
  const usage = { input: 0, output: 0, thinking: 0 };
  let calls = 0, finishReason;   // 하루 한도에서 센다 (다시 묻기도 한 번씩 과금된다). 첫 번은 라우트가 잡았다
  const add = (u) => { usage.input += u.input; usage.output += u.output; usage.thinking += u.thinking; };
  const fail = (msg, code, extra) => {
    const err = new Error(msg); err.code = code; Object.assign(err, extra);
    err.usage = { ...usage, total: usage.input + usage.output + usage.thinking }; err.calls = calls; return err;
  };
  const ask = async (again) => {
    const r = await callGemini([{ text: scorePrompt(hint, again) }, img], cfg, model);
    calls++; add(r.usage); finishReason = r.finishReason;
    let parsed;
    try { parsed = JSON.parse(r.text); } catch (e) { throw fail('악보를 옮기다 응답이 끊겼어요. 다시 시도해 주세요', 'bad_json'); }
    const songs = normalizeScores(parsed && parsed.songs);
    const times = songs.map((s) => { const t = resolveTime(s, hint); if (t.conflict) mark(s, '_timeConflict', true); return t; });
    const chk = songs.length ? scoreSanity(songs[0]) : { ok: false, hard: ['empty'], soft: [], message: reasonKo(['empty']) };
    return { songs, time: times[0], chk };
  };
  let got = await ask();
  // 말이 안 되는 결과(음 이름·높이·길이·되풀이) · 앞 줄과 다른 박자는 한 번 다시 묻는다.
  // 잘려서 안 보인다(unreadable) · 음표가 없다(empty)는 같은 사진을 다시 물어도 같다
  const redo = !got.chk.hard.some((h) => h === 'unreadable' || h === 'empty') && (got.chk.hard.length || got.chk.soft.length);
  if (redo && opts.retry !== false && (!opts.reserve || await opts.reserve())) {
    try {
      const s0 = got.songs[0];
      const again = await ask(got.chk.message + (s0 && got.chk.soft.includes('rhythm') ? ` — ${s0.time} 박자인데 마디마다 음 길이 합이 맞지 않았다. 세로줄(마디줄) 사이가 한 마디다` : ''));
      // 둘 중 덜 나쁜 것을 쓴다 (다시 읽은 것이 더 나쁘면 처음 것)
      const worse = (c) => c.hard.length * 100 + c.soft.length * 10 + (c.badRatio || 0);
      if (worse(again.chk) <= worse(got.chk)) got = again;
    } catch (e) { if (e.status) { if (opts.release) await opts.release(); } else if (e.code !== 'bad_json') throw e; }   // 오류 응답은 과금되지 않는다 · 깨진 답은 처음 답으로
  }
  if (!got.chk.ok) throw fail('악보를 제대로 읽지 못했어요 — ' + got.chk.message, 'nonsense', { reasons: got.chk.hard });
  // 첫 곡 말고 따로 읽힌 곡도 말이 안 되면 뺀다
  const songs = [got.songs[0], ...got.songs.slice(1).filter((s) => scoreSanity(s).ok)];
  // 박자 검증 → 어긋난 마디만 다시
  let stop = false;
  for (const s of songs) {
    const bad = checkMeasures(s).filter((b) => !(b.measure === 1 && s.pickup));
    if (bad.length && opts.repair !== false && !stop) {
      // 한 번에 몰아 물으면 답이 길어져 잘린다. 8마디씩 끊어 묻는다
      const fixCfg = { temperature: 0.1, responseMimeType: 'application/json', maxOutputTokens: 16384,
        thinkingConfig: { thinkingLevel: 'LOW' },
        responseSchema: { type: 'OBJECT', properties: { fixes: { type: 'ARRAY', items: { type: 'OBJECT', properties: { measure: { type: 'INTEGER' }, n: { type: 'ARRAY', items: NOTE_S } }, required: ['measure', 'n'] } } }, required: ['fixes'] } };
      const want = measureTicks(s.time);
      // 한 마디 길이를 4분음표 개수로 알려 준다. 예전에는 박자표 윗 숫자를 '박'이라 적어 12/8 이 4분음표 12개(마디 셋)가 됐다
      const quarters = want / durTicks({ d: 4 });
      for (let k = 0; k < Math.min(bad.length, 24); k += 8) {
        try {
          const ask2 = bad.slice(k, k + 8).map((b) => ({ measure: b.measure, n: s.measures[b.measure - 1].n }));
          const msg = `아래는 방금 이 악보에서 옮긴 마디들인데, 음표 길이의 합이 ${s.time} 박자와 맞지 않는다.
사진에서 해당 마디를 다시 보고 음표와 쉼표를 정확히 세어 고쳐라. 가사(l)는 그대로 유지한다.
한 마디의 길이 합은 정확히 4분음표 ${quarters}개 분량이어야 한다 (${s.time}. 온음표=4, 2분음표=2, 4분음표=1, 8분음표=0.5, 16분음표=0.25, 점음표는 1.5배).
곡: ${s.title} / 조 ${s.key} / 박자 ${s.time}
고칠 마디: ${JSON.stringify(ask2)}`;
          // 다시 묻기도 한 번씩 과금된다 → 부르기 전에 하루 한도에서 자리를 잡는다. 다 찼으면 더 묻지 않고
          // 박자 오류 표시만 남긴다 (전에는 다 부른 뒤에 세어서, 동시에 보내면 한도의 13배까지 불렀다)
          if (opts.reserve && !(await opts.reserve())) { stop = true; break; }
          calls++;
          let fix;
          try { fix = await callGemini([{ text: msg }, img], fixCfg, model); }
          catch (e) { if (e.status) { calls--; if (opts.release) await opts.release(); } throw e; }   // 오류 응답은 과금되지 않는다
          add(fix.usage);
          const fj = JSON.parse(fix.text);
          for (const f of (fj.fixes || [])) {
            const idx = (+f.measure || 0) - 1;
            const m0 = s.measures[idx];
            if (!m0 || !Array.isArray(f.n) || !f.n.length) continue;
            const fixed = cleanNotes(f.n);
            // 고친 쪽이 박자에 더 안 맞으면 버린다. 안 그러면 더 나빠질 수 있다
            const sum = (arr) => arr.reduce((a, n) => a + durTicks(n), 0);
            if (Math.abs(sum(fixed) - want) >= Math.abs(sum(m0.n || []) - want)) continue;
            // 가사는 원래 것을 지킨다 (모델이 자주 빠뜨린다). 제자리에 못 옮기면 고친 것을 버린다 (박자 오류 표시는 남는다)
            const next = carryLyrics(m0.n || [], fixed);
            if (!next) continue;
            s.measures[idx].n = next;
          }
        } catch (e) { console.error('score repair', e.message); }
      }
    }
  }
  // 고치기까지 한 뒤에도 마디 대부분이 박자와 안 맞으면 음표를 제대로 못 읽은 것이다 — 그리지 않는다
  const fin = scoreSanity(songs[0], { final: true });
  if (!fin.ok) throw fail('악보를 제대로 읽지 못했어요 — ' + fin.message, 'nonsense', { reasons: fin.hard });
  const out = songs.filter((s, i) => i === 0 || scoreSanity(s, { final: true }).ok);
  const badMeasures = out.flatMap((s, si) => checkMeasures(s).filter((b) => !(b.measure === 1 && s.pickup)).map((b) => ({ song: si, ...b })));
  usage.total = usage.input + usage.output + usage.thinking;
  return { songs: out, model, usage, badMeasures, finishReason, calls,
    time: got.time ? { from: got.time.from, fit: got.time.fit } : null };
}
const mark = (o, k, v) => Object.defineProperty(o, k, { value: v, enumerable: false, configurable: true, writable: true });
// 고친 마디에 원래 가사를 다시 붙인다. 배열 자리로 붙이면, 고치면서 쉼표나 음표가 하나 늘거나 줄 때
// (고치는 까닭이 바로 그것이다) 음절이 한 칸씩 밀려 쉼표에 붙고 마지막 음은 가사를 잃는다.
// 소리 나는 음표끼리 순서대로 맞춘다. 개수가 다르면 음 높이 순서(LCS)로 맞춰 보고,
// 가사를 다 옮기지 못하면 null — 틀린 자리에 붙이느니 고치기 전 마디를 둔다
export function carryLyrics(old, fixed) {
  const hasL = (n) => !!(n && Array.isArray(n.l) && n.l.length);
  if (!old.some(hasL)) return fixed;
  if (fixed.filter(hasL).length >= old.filter(hasL).length) return fixed;   // 모델이 가사까지 다 옮겨 왔다
  const src = old.filter((n) => n.p || hasL(n));
  const dst = fixed.map((n, i) => i).filter((i) => fixed[i].p);
  let pairs = [];
  if (src.length === dst.length) pairs = src.map((_, k) => [k, dst[k]]);
  else {
    const a = src.map((n) => n.p || ''), b = dst.map((i) => fixed[i].p);
    const L = a.map(() => new Array(b.length + 1).fill(0)).concat([new Array(b.length + 1).fill(0)]);
    for (let x = a.length - 1; x >= 0; x--) for (let y = b.length - 1; y >= 0; y--)
      L[x][y] = a[x] && a[x] === b[y] ? L[x + 1][y + 1] + 1 : Math.max(L[x + 1][y], L[x][y + 1]);
    for (let x = 0, y = 0; x < a.length && y < b.length;) {
      if (a[x] && a[x] === b[y]) { pairs.push([x, dst[y]]); x++; y++; }
      else if (L[x + 1][y] >= L[x][y + 1]) x++; else y++;
    }
  }
  const out = fixed.map((n) => ({ ...n }));
  const placed = new Set();
  for (const [k, i] of pairs) {
    if (!hasL(src[k])) continue;
    if (!hasL(out[i])) out[i].l = src[k].l;   // 모델이 가사를 남긴 음표는 그대로 둔다
    placed.add(k);
  }
  return src.every((n, k) => !hasL(n) || placed.has(k)) ? out : null;
}
const NO_TITLE = /^(untitled|unknown|no\s*title|n\/?a|none|null|제목\s*없음|없음|-)$/i;
// st 를 주면 알아볼 수 없던 음 길이 개수를 센다 (4분음표로 바꿔 두지만, 많으면 말이 안 되는 결과다)
const cleanNotes = (arr, st) => (Array.isArray(arr) ? arr : []).filter((n) => n && typeof n === 'object').slice(0, 64).map((n) => {
  const okD = [1, 2, 4, 8, 16, 32].includes(+n.d);
  if (!okD && st) st.badDur++;
  return {
    p: normPitch(n.p),
    d: okD ? +n.d : 4,
    ...(n.dot ? { dot: true } : {}), ...(n.tie ? { tie: true } : {}),
    ...(Array.isArray(n.l) && n.l.length ? { l: n.l.slice(0, 4).map((x) => String(x == null ? '' : x).slice(0, 12)) } : {}),
  };
});
function normalizeScores(songs) {
  return (Array.isArray(songs) ? songs : []).filter((s) => s && typeof s === 'object').slice(0, 4).map((s) => {
    const st = { badDur: 0 };
    const out = {
      // 제목이 안 보이면 'Untitled' 같은 것을 적기도 한다 — 제목 없음으로 (다른 곡인지 가릴 때 제목을 쓴다)
      title: NO_TITLE.test(str(s.title)) ? '' : str(s.title).slice(0, 80), composer: s.composer ? str(s.composer) : null,
      // 박자는 비워 둘 수 있다 (안 보이면 비우라고 했다) — resolveTime 이 알려 준 박자·음 길이로 정한다
      key: str(s.key).replace(/\s/g, '') || 'C', time: validTime(s.time),
      tempo: Number.isFinite(+s.tempo) && +s.tempo >= 20 && +s.tempo <= 400 ? Math.round(+s.tempo) : null,
      verses: Math.max(1, Math.min(6, Math.round(+s.verses) || 1)), pickup: !!s.pickup,
      form: s.form ? str(s.form) : '', confidence: Math.max(0, Math.min(1, +s.confidence || 0)),
      notes: s.notes ? str(s.notes) : null,
      ...(s.problem ? { problem: str(s.problem).slice(0, 200) } : {}),
      measures: (Array.isArray(s.measures) ? s.measures : []).filter((m) => m && typeof m === 'object').slice(0, 400).map((m) => ({
        ...(Array.isArray(m.c) && m.c.length ? { c: m.c.filter((c) => c && typeof c === 'object').slice(0, 8).map((c) => ({ b: Math.max(0, +c.b || 0), t: str(c.t).replace(/\s/g, '').replace(/♯/g, '#').replace(/♭/g, 'b').slice(0, 16) })).filter((c) => c.t) } : {}),
        n: cleanNotes(m.n, st),
        ...(m.rs ? { rs: true } : {}), ...(m.re ? { re: true } : {}),
        ...(m.end ? { end: Math.max(1, Math.min(4, Math.round(+m.end) || 1)) } : {}),
        ...(m.key ? { key: str(m.key).replace(/\s/g, '').slice(0, 6) } : {}),
      })),
    };
    mark(out, '_stats', st);
    return out;
  }).filter((s) => s.measures.length || s.problem);
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

/* ---------- 코드 인식 (Vision OCR 대체) ----------
   일반 OCR 은 코드 기호를 잘 못 읽는다. 위첨자(Bm⁷, A⁹/C#), 괄호(E^(sus4)),
   ♯♭ 를 "Bm7"→"Bm?", "sus4"→"sDs4" 처럼 망가뜨리고, 옆 코드와 붙여 "A9/C#C" 를 만든다.
   Gemini 는 코드 어휘를 알아서 훨씬 정확하다. 위치는 정규화 박스로 함께 받는다. */
const CHORD_S = {
  type: 'object',
  properties: {
    title: { type: 'string' },
    key: { type: 'string' },
    chords: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          text: { type: 'string' },
          box: { type: 'array', items: { type: 'number' } },   // [ymin,xmin,ymax,xmax] 0~1000
        },
        required: ['text', 'box'],
      },
    },
  },
  required: ['chords'],
};
const CHORD_PROMPT = `이 이미지는 리드시트(악보)의 한 줄 또는 전체입니다.
오선 위에 적힌 **코드 기호만** 왼쪽에서 오른쪽, 위에서 아래 순서로 모두 읽어 주세요.

읽는 규칙
- 위첨자는 그대로 내려 적습니다. Bm⁷ → "Bm7", A⁹/C♯ → "A9/C#", F♯m⁷ → "F#m7"
- 괄호 위첨자도 그대로: E^(sus4) → "E(sus4)", A^(sus4) → "A(sus4)"
- ♯ 는 #, ♭ 는 b 로 적습니다. C♭/E♭ → "Cb/Eb", A♭m⁷ → "Abm7"
- 분수 코드의 슬래시는 그대로: "D/F#", "E/G#"
- 붙어 있는 두 코드를 하나로 합치지 마세요. 각각 따로 냅니다.
- 코드가 아닌 것(가사, 마디 번호, 제목, 작사·작곡, 반복 기호 1./2., ♩=70, 'Copyright')은 빼세요.
- 반복 구간 표시 안의 코드(예: "1. A(sus4)")는 코드 부분만("A(sus4)") 냅니다.

각 코드마다 그 코드 글자가 놓인 자리를 box 로 주세요.
box 는 [ymin, xmin, ymax, xmax] 이고 이미지 크기를 0~1000 으로 정규화한 값입니다.

이미지 전체가 보이면 title 과 key 도 함께 주세요.
- title: 맨 위 가장 큰 글씨의 곡 제목. 작사·작곡·채보 같은 것은 빼세요. 없으면 빈 문자열
- key: 조표와 코드 진행으로 본 이 악보의 조. "A", "Bb", "Em" 처럼. 자신 없으면 빈 문자열`;

// images: [{ b64, mime, w, h }] → [{ tokens: [{text,x,y,w,h,conf}] }]  (Vision 과 같은 모양)
export async function ocrChordsGemini(images, opts = {}) {
  const key = process.env.GEMINI_API_KEY;
  if (!key) return null;
  // 'mock' 이면 예전에 진짜로 받아 둔 결과를 그대로 돌려준다.
  // 테스트를 돌릴 때마다 돈이 나가지 않으면서, 코드 개수·제목·키까지 진짜와 같아
  // '인식이 됐다'는 검사가 그대로 의미를 갖는다. 진짜로 확인하려면 키를 넣고 돌린다
  if (key === 'mock') {
    const d = await mockFixture();
    if (!d) return null;
    return { bands: d.bands, usage: { input: 0, output: 0, thinking: 0 }, model: 'mock',
             title: d.title || '', key: d.key || '' };
  }
  const model = opts.model || geminiModel();
  const cfg = { temperature: 0, responseMimeType: 'application/json', responseSchema: CHORD_S,
    maxOutputTokens: 8192, thinkingConfig: { thinkingLevel: (opts.thinking || 'LOW').toUpperCase() } };
  const usage = { input: 0, output: 0, thinking: 0 };
  const meta = { title: '', key: '' };
  const out = [];
  for (const im of images) {
    if (im.kind === 'title') { out.push({ tokens: [] }); continue; }
    try {
      const r = await callGemini(
        [{ text: CHORD_PROMPT }, { inline_data: { mime_type: im.mime || 'image/jpeg', data: im.b64 } }], cfg, model);
      usage.input += r.usage.input; usage.output += r.usage.output; usage.thinking += r.usage.thinking || 0;
      const j = JSON.parse(r.text || '{}');
      if (j.title && !meta.title) meta.title = String(j.title).trim().slice(0, 60);
      if (j.key && !meta.key) meta.key = String(j.key).trim().slice(0, 8);
      const W = im.w || 1000, H = im.h || 1000;
      out.push({ tokens: (j.chords || []).filter((c) => c && c.text).map((c) => {
        const b = Array.isArray(c.box) && c.box.length === 4 ? c.box : [0, 0, 0, 0];
        const y0 = Math.min(b[0], b[2]) / 1000 * H, x0 = Math.min(b[1], b[3]) / 1000 * W;
        const y1 = Math.max(b[0], b[2]) / 1000 * H, x1 = Math.max(b[1], b[3]) / 1000 * W;
        return { text: String(c.text).trim(), x: Math.round(x0), y: Math.round(y0),
                 w: Math.max(6, Math.round(x1 - x0)), h: Math.max(6, Math.round(y1 - y0)), conf: 90 };
      }) });
    } catch (e) { out.push({ tokens: [], err: e.message, fail: e }); }
  }
  // 한 장도 못 읽었으면(과부하·한도·잘린 응답) 던진다. 빈 결과로 돌려주면 라우트는 성공으로 알고
  // Vision 으로 넘어가지도, 502 로 알리지도 않고, 클라이언트는 있던 코드를 '못 찾음'으로 지운다
  const failed = out.filter((b) => b.fail);
  if (failed.length && failed.length === images.filter((im) => im.kind !== 'title').length) throw failed[0].fail;
  return { bands: out.map(({ fail, ...b }) => b), usage, model, title: meta.title, key: meta.key };
}

// 저장해 둔 진짜 인식 결과. 파일로 읽되(로컬 Node), 파일 시스템이 없는 곳(Cloudflare Workers)에서는
// 번들에 같이 들어간 사본을 쓴다. 3.4KB 라 용량 부담이 없다
async function mockFixture() {
  try {
    const { readFileSync } = await import('node:fs');
    const { fileURLToPath } = await import('node:url');
    const { dirname, join } = await import('node:path');
    const f = join(dirname(fileURLToPath(import.meta.url)), '..', 'docs', 'ocr_fixture.json');
    return JSON.parse(readFileSync(f, 'utf8'));
  } catch (e) {
    try { const m = await import('../docs/ocr_fixture.json'); return m.default || m; }
    catch (e2) { console.error('mock fixture', e2.message); return null; }
  }
}
