# 채보·악보 만들기: 말이 안 되는 AI 결과를 그리지 않는다
# 실사용 제보 (2026-09-30) "OMR 아예 말 안 되게 엉터리로 그려 줄 때가 있음". docs 샘플로 재현한 원인과 이 검사:
#  A. 폰 사진이 1° 만 기울어도 오선 찾기가 한 줄을 반 토막 두 줄로 잘랐고(오른쪽 반이 먼저), 2° 부터는 오선을 못 찾아
#     한 장을 통째로 보냈다. 반 토막 띠에서 AI 는 없는 음표를 확신 0.9 로 지어냈다 → 기울기 바로 세우기 (앱)
#  B. 두 쪽을 나란히 찍은 사진은 두 곡의 줄이 번갈아 섞였다 → 쪽 나누기 · 옆 쪽 첫 줄 제목이 다르면 첫 곡만 (앱)
#  C. 박자표는 첫 줄에만 인쇄돼서 둘째 줄부터 AI 가 4/4 로 짐작하고 음표를 4/4 에 맞게 지어냈다(합이 맞아 경고도 없음)
#     → 첫 줄 박자를 다음 줄에 알려 주고, 앞 줄과 박자가 다르면 다시 묻는다 (앱·서버). 합쳐도 첫 줄 박자를 따른다
#  D. 말이 안 되는 결과(음 이름·높이·길이 엉터리, 되풀이, 박자 합이 대부분 안 맞음, 잘려서 안 보임)는 한 번 다시 묻고,
#     그래도 안 되면 422 와 까닭 — 그리지 않는다. 채보(/omr)는 이때 이번 달 채보 횟수·크레딧을 쓰지 않는다
#  AI 는 부르지 않는다: 진짜로 받아 둔 엉터리 답(tests/fixtures/omr_real_outputs.json)과 손으로 만든 답을 가짜 fetch 로 돌려준다
# 사용: CONTI_URL=http://localhost:9911/ CONTI_DB=postgres://postgres@localhost:55111/postgres .venv/bin/python tests/test_omr_sanity.py
#  (서버는 GEMINI_API_KEY=mock 인 dev 서버. CONTI_DB 는 서버와 같은 DB — API 검사는 서버 코드를 이 프로세스 안에서 부른다)
import os, sys, time, json, subprocess, base64
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
if not URL.endswith('/'): URL += '/'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.environ.get('CONTI_DB', 'postgres://postgres:pg@localhost:54329/postgres')
tag = str(int(time.time() * 10))[-7:]
def fail(m): print('FAIL:', m); sys.exit(1)

def node(js, env=None):
  out = subprocess.run(['node', '--input-type=module', '-e', js], cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, 'ROOT': ROOT, 'DB': DB, 'TAG': tag, **(env or {})}, timeout=180)
  lines = [l for l in out.stdout.strip().splitlines() if l.startswith('{')]
  if not lines: fail('node 실행 실패: %s %s' % (out.stdout[-800:], out.stderr[-1500:]))
  return json.loads(lines[-1])

# 손으로 만든 답: 12/8 둘째 줄의 바른 답 · 엉터리 음 이름 · 되풀이 · 잘려서 못 읽음 · 코드 차트 셋
COMMON = r"""
import fs from 'node:fs';
const R = process.env.ROOT;
const fx = JSON.parse(fs.readFileSync(R + '/tests/fixtures/omr_real_outputs.json', 'utf8'));
const txt = (o, tok = 1000) => ({ candidates: [{ content: { parts: [{ text: JSON.stringify(o) }] }, finishReason: 'STOP' }],
  usageMetadata: { promptTokenCount: tok, candidatesTokenCount: 100, thoughtsTokenCount: 0 } });
const N = (p, d, x = {}) => ({ p, d, ...x });
const GOOD128 = { title: '', key: 'C', time: '12/8', verses: 1, confidence: 0.8, measures: [
  { c: [{ b: 0, t: 'Gsus4' }, { b: 6, t: 'A' }], n: [N('G4', 2, { dot: true, tie: true, l: ['니'] }), N('G4', 4, { dot: true }), N('E4', 8, { l: ['이'] }), N('D4', 8, { l: ['세'] }), N('C4', 8, { l: ['상'] })] },
  { c: [{ b: 0, t: 'C' }, { b: 6, t: 'F/C' }], n: [N('G4', 4, { dot: true, l: ['에'] }), N('G4', 4, { dot: true, tie: true, l: ['서'] }), N('G4', 4, { dot: true }), N('F4', 8, { l: ['내'] }), N('G4', 8, { l: ['영'] }), N('A4', 8, { tie: true, l: ['혼'] })] },
  { c: [{ b: 0, t: 'D' }], n: [N('A4', 8), N('G4', 4, { l: ['이'] }), N('G4', 4, { dot: true, tie: true }), N('G4', 4, { dot: true }), N('C4', 8, { l: ['하'] }), N('D4', 8, { l: ['늘'] }), N('E4', 8, { l: ['의'] })] },
] };
const JUNK = { title: 'Untitled', key: 'C', time: '4/4', verses: 1, confidence: 0.9, measures: [
  { n: [N('H9', 4), N('X4', 4), N('C#12', 4), N('Q', 4)] }, { n: [N('Z3', 4), N('C4', 4), N('D9', 4), N('?', 4)] } ] };
const LOOP = { title: '', key: 'G', time: '4/4', verses: 1, confidence: 0.9, measures: Array.from({ length: 12 }, () => ({ c: [{ b: 0, t: 'G' }], n: [N('G4', 4), N('G4', 4), N('G4', 4), N('G4', 4)] })) };
const CUT = { title: '', key: 'C', time: '', verses: 1, confidence: 0.2, measures: [], problem: '오선 아래쪽이 잘려 음표 머리가 안 보임' };
const OK44 = { title: '주 은혜', key: 'G', time: '4/4', verses: 1, confidence: 0.9, measures: [
  { c: [{ b: 0, t: 'G' }], n: [N('D4', 4, { l: ['주'] }), N('G4', 4, { l: ['은'] }), N('B4', 2, { l: ['혜'] })] },
  { c: [{ b: 0, t: 'C' }], n: [N('C5', 4), N('B4', 4), N('A4', 2)] } ] };
const bar = (chords, lyric = null) => ({ chords, lyric });
const sec = (name, bars) => ({ name, bars });
const song = (sections) => ({ title: '우리 주 하나님', key: 'A', timeSignature: '4/4', sections, form: 'A – B', confidence: 0.9 });
const CH_GOOD = { songs: [song([sec('A', [bar(['A']), bar(['Bm7', 'A9/C#'], '하나님'), bar(['D(sus4)', 'D']), bar(['Fb', 'Cb/Eb'])])])] };
// 가사를 코드 칸에 읽음 (코드 아닌 글자 5/8)
const CH_JUNK = { songs: [song([sec('A', [bar(['우리', '주']), bar(['하나님']), bar(['A', 'x2']), bar(['영광을', 'D', 'E'])])])] };
const CH_LOOP = { songs: [song([sec('A', Array.from({ length: 40 }, () => bar(['G'], '할렐루야')))])] };
const CH_EMPTY = { songs: [] };
"""

UNIT = COMMON + r"""
const S = await import(R + '/lib/score.js');
const G = await import(R + '/lib/gemini.js');
const out = {};
// ---- 박자 정하기 ----
const ms = (sums) => sums.map((q) => ({ n: q === 144 ? [N('G4', 2, { dot: true }), N('G4', 4, { dot: true }), N('E4', 8), N('D4', 8), N('C4', 8)]
  : q === 72 ? [N('G4', 4, { dot: true }), N('A4', 4, { dot: true })] : [N('C4', 4), N('D4', 4), N('E4', 4), N('F4', 4)] }));
const a = { time: '', measures: ms([144, 144, 144]) }; out.inferred = S.resolveTime(a, null);
const b = { time: '', measures: ms([144, 144]) }; out.hinted = S.resolveTime(b, { time: '12/8' });
const c = { time: '12/8', measures: ms([72, 72, 72, 72]) }; out.noRescue = S.resolveTime(c, { time: '12/8' });
out.noRescueFinal = S.scoreSanity(c, { final: true });
const d = { time: '4/4', measures: ms([96, 96, 96]) }; out.conflict = S.resolveTime(d, { time: '12/8' });
const e = { time: '', measures: ms([96, 96]) }; out.dflt = S.resolveTime({ time: '', measures: [] }, null);
// ---- 검사 ----
const san = (o, opts) => S.scoreSanity(o, opts);
out.junk = san({ time: '4/4', measures: JUNK.measures });
out.loop = san({ time: '4/4', measures: LOOP.measures });
out.cut = san({ time: '4/4', measures: [], problem: 'x' });
out.range = san({ time: '4/4', measures: [{ n: [N('C2', 4), N('C7', 4), N('C2', 4), N('C7', 4)] }, { n: [N('C2', 4), N('C7', 4), N('C2', 4), N('C7', 4)] }] });
out.dense = san({ time: '4/4', measures: [{ n: Array.from({ length: 40 }, () => N('C4', 32)) }] });
out.good = san({ time: '4/4', measures: OK44.measures }, { final: true });
out.pitchNorm = [S.normPitch('b♭4'), S.normPitch(' F♯5 '), S.normPitch('rest'), S.normPitch(null)];
// ---- 코드 차트 검사 ----
const norm = (x) => JSON.parse(JSON.stringify(x.songs));
out.chGood = G.chartSanity(norm(CH_GOOD)); out.chJunk = G.chartSanity(norm(CH_JUNK)); out.chLoop = G.chartSanity(norm(CH_LOOP)); out.chEmpty = G.chartSanity([]);
out.chGoodChords = out.chGood.songs[0].sections[0].bars.map((b) => b.chords);
for (const k of ['chGood', 'chJunk', 'chLoop', 'chEmpty']) out[k] = { ok: out[k].ok, hard: out[k].hard };
console.log(JSON.stringify(out));
"""

REPLAY = COMMON + r"""
process.env.GEMINI_API_KEY = 'fake';
let queue = [], sent = [];
globalThis.fetch = async (u, o) => {
  if (!String(u).includes('generativelanguage')) throw new Error('blocked ' + u);
  sent.push(JSON.parse(o.body).contents[0].parts.filter((p) => p.text).map((p) => p.text).join('\n'));
  const r = queue.shift(); if (!r) return { ok: false, status: 503, json: async () => ({ error: { message: 'no more' } }) };
  return { ok: true, status: 200, json: async () => r };
};
const G = await import(R + '/lib/gemini.js');
const FIXNONE = txt({ fixes: [] });
const run = async (fn, resps, opts = {}) => {
  queue = resps.slice(); sent = []; let reserves = 0; const res = {};
  try {
    const r = await G[fn]({ b64: 'x'.repeat(200), mime: 'image/jpeg' }, { reserve: async () => { reserves++; return true; }, release: async () => {}, ...opts });
    const s = r.songs[0];
    Object.assign(res, { ok: true, calls: r.calls, n: r.songs.length, time: s.time, m: s.measures ? s.measures.length : null, bad: (r.badMeasures || []).length, from: r.time && r.time.from, title: s.title });
  } catch (e) { Object.assign(res, { ok: false, code: e.code, msg: e.message, calls: e.calls, tokens: e.usage && e.usage.total }); }
  res.reserves = reserves; res.left = queue.length;
  res.sent = sent.map((t) => ({ hint12: t.includes('이 곡의 박자는 12/8'), line2: t.includes('2번째 줄'), again: t.includes('[다시]'), repair: t.includes('고칠 마디'), q6: t.includes('4분음표 6개') }));
  return res;
};
const hint = { time: '12/8', key: 'C', line: 2, lines: 5 };
const out = {};
// C: 진짜 답 — 박자표가 안 보이는 12/8 줄을 4/4 로 지어낸 것. 12/8 을 알려 줬는데 4/4 로 오면 앞 줄과 다르다 → 다시 묻는다
out.fab = await run('transcribeScore', [fx.fabricated_44.res, txt({ songs: [GOOD128] })], { hint, repair: false });
// 진짜 답 — 12/8 이라 적고 음표는 6/8 토막(7마디 모두 합이 틀림). 6/8 로 '살려' 주지 않는다: 다시 묻고 · 고쳐 보고 · 그래도 안 되면 거절
out.split = await run('transcribeScore', [fx.split_68.res, fx.split_68.res, FIXNONE], { hint });
// 진짜 답 — 3마디 중 2마디가 12/8 과 안 맞음. 박자 고치기 프롬프트는 4분음표 개수로 (12/8 = 4분음표 6개)
out.wrong = await run('transcribeScore', [fx.wrong_12_8.res, FIXNONE], { hint });
// 진짜 답 — 바로 세운 사진 첫 줄의 첫 답(마디 합 84) → 다시 묻고 나은 답을 쓴다
out.line1 = await run('transcribeScore', [fx.line1_garbled.res, fx.line1_retry.res], { hint: { line: 1, lines: 4 }, repair: false });
// 진짜 답 — 반 토막 띠에서 지어낸 음표: 서버는 모양만으로는 못 가린다 (그래서 앱이 반 토막 띠를 만들지 않는다) — 기록만
out.halfStaff = await run('transcribeScore', [fx.half_staff_invented.res], { repair: false });
// D: 엉터리 음 이름 → 다시 묻고 또 엉터리면 거절 (토큰은 센다)
out.junk = await run('transcribeScore', [txt({ songs: [JUNK] }), txt({ songs: [JUNK] })], { repair: false });
// 같은 마디 되풀이 → 다시 물어 바른 답이면 쓴다
out.loop = await run('transcribeScore', [txt({ songs: [LOOP] }), txt({ songs: [OK44] })], { repair: false });
// 잘려서 안 보인다 → 다시 묻지 않고 바로 거절
out.cut = await run('transcribeScore', [txt({ songs: [CUT] })], { repair: false });
// 다시 묻기 자리가 없으면(하루 한도) 더 묻지 않는다
queue = []; out.noReserve = await (async () => { queue = [txt({ songs: [JUNK] })]; sent = [];
  try { await G.transcribeScore({ b64: 'x'.repeat(200) }, { reserve: async () => false, release: async () => {}, repair: false }); return { ok: true }; }
  catch (e) { return { ok: false, code: e.code, calls: e.calls, sent: sent.length }; } })();
// 정상 답은 그대로
out.good = await run('transcribeScore', [txt({ songs: [OK44] })], { hint: { time: '4/4', line: 2, lines: 3 } });
// 코드 차트
out.chJunk = await run('transcribeSheet', [txt(CH_JUNK), txt(CH_JUNK)]);
out.chRetry = await run('transcribeSheet', [txt(CH_LOOP), txt(CH_GOOD)]);
out.chEmpty = await run('transcribeSheet', [txt(CH_EMPTY)]);
out.chGood = await run('transcribeSheet', [txt(CH_GOOD)]);
console.log(JSON.stringify(out));
"""

# 서버 코드를 이 프로세스 안에서: 월 한도(ENFORCE_PLAN)와 크레딧·하루 한도를 DB 로 본다
INPROC = COMMON + r"""
process.env.ENFORCE_PLAN = '1'; process.env.GEMINI_API_KEY = 'fake'; process.env.TRIAL_DAYS = '0';
process.env.DATABASE_URL = process.env.DB; process.env.AUTH_SECRET = process.env.AUTH_SECRET || 'local-dev-secret-0123456789';
process.env.BLOB_LOCAL_DIR = process.env.BLOB_LOCAL_DIR || (R + '/.localblob');
let queue = [], sent = [];
globalThis.fetch = async (u, o) => {
  if (String(u).includes('generativelanguage')) { sent.push(JSON.parse(o.body).contents[0].parts.filter((p) => p.text).map((p) => p.text).join('\n'));
    const r = queue.shift(); if (!r) return { ok: false, status: 503, json: async () => ({ error: { message: 'no more' } }) };
    return { ok: true, status: 200, json: async () => r }; }
  throw new Error('blocked ' + u);
};
const { default: api } = await import(R + '/api/index.js');
const { q, one } = await import(R + '/lib/db.js');
const call = (method, path, body, headers = {}) => new Promise((resolve) => {
  const h = {};
  const res = { statusCode: 200, setHeader(k, v) { h[k.toLowerCase()] = v; }, getHeader(k) { return h[k.toLowerCase()]; },
    end(s) { let j = null; try { j = JSON.parse(s); } catch {} resolve({ status: this.statusCode, body: j, headers: h }); } };
  api({ method, url: '/api' + path, headers: { 'x-conti': '1', 'content-type': 'application/json', ...headers }, body, socket: { remoteAddress: '127.0.0.1' } }, res);
});
const T = process.env.TAG;
const r0 = await call('POST', '/auth/signup', { username: 'omsan' + T, password: 'secret12', name: '하은' });
const me = { cookie: String(r0.headers['set-cookie']).split(';')[0] };
const team = (await call('POST', '/teams', { name: '채보검사', myName: '하은' }, me)).body.teamId;
await q("update teams set plan='free', plan_until=null, plan_source=null where id=$1", [team]);
const omr = (key, resps) => { queue = resps.slice(); sent = []; return call('POST', '/omr', { teamId: team, songKey: key, b64: 'iVBOR' + 'A'.repeat(200), mime: 'image/png' }, me); };
const songs = async () => (await one("select count(*)::int n from ai_songs where team_id=$1 and kind='omr'", [team])).n;
const calls = async (k) => ((await one("select coalesce(sum(calls),0)::int n, coalesce(sum(tokens),0)::int t from ai_usage where team_id=$1 and kind=$2", [team, k])) || {});
const out = {};
let r = await omr('s1', [txt(CH_JUNK), txt(CH_JUNK)]);
out.junk = { status: r.status, error: r.body.error, msg: r.body.message, gem: sent.length, songs: await songs(), usage: await calls('omr') };
r = await omr('s2', [txt(CH_EMPTY)]);
out.empty = { status: r.status, error: r.body.error, gem: sent.length, songs: await songs(), usage: await calls('omr') };
r = await omr('s3', [txt(CH_LOOP), txt(CH_GOOD)]);
out.retryOk = { status: r.status, n: (r.body.songs || []).length, quota: r.body.quota, gem: sent.length, songs: await songs() };
// 무료 1곡을 다 썼다 → 크레딧으로 낸다. 엉터리면 크레딧을 돌려준다
await q('insert into credit_balance(team_id, omr) values($1, 2) on conflict (team_id) do update set omr=2', [team]);
r = await omr('s4', [txt(CH_JUNK), txt(CH_JUNK)]);
out.credit = { status: r.status, bal: (await one('select omr from credit_balance where team_id=$1', [team])).omr, songs: await songs() };
r = await omr('s5', [txt(CH_GOOD)]);
out.creditGood = { status: r.status, bal: (await one('select omr from credit_balance where team_id=$1', [team])).omr, songs: await songs() };
// 악보 만들기: 엉터리는 422, 부른 두 번은 하루 한도·토큰에 센다. 힌트는 프롬프트로
queue = [txt({ songs: [JUNK] }, 700), txt({ songs: [JUNK] }, 800)]; sent = [];
r = await call('POST', '/score', { teamId: team, b64: '/9j/' + 'A'.repeat(200), mime: 'image/jpeg', hint: { time: '12/8', key: 'C', line: 2, lines: 4 } }, me);
out.score = { status: r.status, error: r.body.error, msg: r.body.message, gem: sent.length, hint: sent[0] && sent[0].includes('이 곡의 박자는 12/8') && sent[0].includes('2번째 줄'), usage: await calls('score') };
queue = [txt({ songs: [GOOD128] })]; sent = [];
r = await call('POST', '/score', { teamId: team, b64: '/9j/' + 'A'.repeat(200), mime: 'image/jpeg', hint: { time: '12/8', key: 'C', line: 2, lines: 4 } }, me);
out.scoreOk = { status: r.status, time: r.body.songs && r.body.songs[0].time, m: r.body.songs && r.body.songs[0].measures.length, from: r.body.time && r.body.time.from, gem: sent.length };
// 이상한 힌트 값은 버린다
queue = [txt({ songs: [OK44] })]; sent = [];
r = await call('POST', '/score', { teamId: team, b64: '/9j/' + 'A'.repeat(200), mime: 'image/jpeg', hint: { time: '<script>', key: 'Zb', line: 999 } }, me);
out.badHint = { status: r.status, clean: !!sent[0] && !sent[0].includes('<script>') && !sent[0].includes('[앞 줄에서 읽은 것]') };
console.log(JSON.stringify(out));
process.exit(0);
"""

def check_lib():
  u = node(UNIT)
  if u['inferred']['time'] != '12/8' or u['inferred']['from'] != 'inferred': fail('박자표도 힌트도 없으면 음 길이 합(점4분음표 4개)으로 12/8 을 짐작해야: %s' % u['inferred'])
  if u['hinted']['time'] != '12/8' or u['hinted']['from'] != 'hint': fail('박자표가 안 보이면 알려 준 박자를 써야: %s' % u['hinted'])
  if u['noRescue']['time'] != '12/8': fail('12/8 이라 적고 음표가 6/8 토막이면 6/8 로 살려 주면 안 됨: %s' % u['noRescue'])
  if 'rhythm' not in u['noRescueFinal']['hard']: fail('박자 합이 대부분 틀린 악보를 그리려 함: %s' % u['noRescueFinal'])
  if not u['conflict']['conflict'] or u['conflict']['time'] != '4/4': fail('알려 준 박자와 AI 가 적은 박자가 다르면 conflict: %s' % u['conflict'])
  if u['dflt']['time'] != '4/4' or u['dflt']['from'] != 'default': fail('아무것도 모르면 4/4 (default): %s' % u['dflt'])
  for k, want in [('junk', 'pitch'), ('loop', 'loop'), ('cut', 'unreadable'), ('range', 'range'), ('dense', 'density')]:
    if want not in u[k]['hard']: fail('검사 %s: %s 를 못 잡음 %s' % (k, want, u[k]))
  if not u['good']['ok']: fail('정상 악보를 거절: %s' % u['good'])
  if u['pitchNorm'] != ['Bb4', 'F#5', None, None]: fail('음 이름 정리: %s' % u['pitchNorm'])
  if not u['chGood']['ok'] or u['chGoodChords'] != [['A'], ['Bm7', 'A9/C#'], ['D(sus4)', 'D'], ['Fb', 'Cb/Eb']]: fail('정상 코드 차트를 바꾸거나 거절: %s %s' % (u['chGood'], u['chGoodChords']))
  if 'chords' not in u['chJunk']['hard'] or 'loop' not in u['chLoop']['hard'] or 'empty' not in u['chEmpty']['hard']: fail('코드 차트 검사: %s %s %s' % (u['chJunk'], u['chLoop'], u['chEmpty']))
  print('lib ok — 박자 정하기(인쇄·알려 줌·짐작) · 6/8 로 살려 주지 않음 · 엉터리 음/되풀이/잘림/음역/밀도 · 코드 차트')

  r = node(REPLAY)
  f = r['fab']
  if not f['ok'] or f['time'] != '12/8' or f['calls'] != 2 or not f['sent'][0]['hint12'] or not f['sent'][0]['line2'] or not f['sent'][1]['again']:
    fail('C 12/8 줄을 4/4 로 지어낸 답: 12/8 힌트를 주고, 4/4 로 오면 다시 물어 12/8 답을 써야 %s' % f)
  s = r['split']
  if s['ok'] or s['code'] != 'nonsense' or s['calls'] != 3 or not s['sent'][1]['again'] or not s['sent'][2]['repair']: fail('6/8 토막 답: 다시 묻고·고쳐 보고·거절해야 %s' % s)
  if '박자' not in s['msg']: fail('거절 까닭이 박자여야: %s' % s['msg'])
  w = r['wrong']
  if w['ok'] or w['calls'] != 2 or not w['sent'][1]['q6']: fail('12/8 박자 고치기는 4분음표 6개로 묻고, 그래도 2/3 가 틀리면 거절: %s' % w)
  l1 = r['line1']
  if not l1['ok'] or l1['calls'] != 2 or l1['m'] != 4: fail('첫 줄 엉터리(합 84) → 다시 물어 나은 답: %s' % l1)
  print('   (기록) 반 토막 띠의 지어낸 음표는 서버가 모양만으로 못 가림: ok=%s — 앱이 반 토막 띠를 만들지 않는 것으로 막는다' % r['halfStaff']['ok'])
  j = r['junk']
  if j['ok'] or j['code'] != 'nonsense' or j['calls'] != 2 or not j['tokens']: fail('엉터리 음 이름: 다시 묻고 거절 + 토큰은 센다 %s' % j)
  if not r['loop']['ok'] or r['loop']['calls'] != 2: fail('되풀이 → 다시 물어 바른 답: %s' % r['loop'])
  c = r['cut']
  if c['ok'] or c['calls'] != 1 or len(c['sent']) != 1 or '잘렸' not in c['msg']: fail('잘려서 안 보이면 다시 묻지 않고 거절: %s' % c)
  nr = r['noReserve']
  if nr['ok'] or nr['sent'] != 1: fail('하루 한도 자리가 없으면 다시 묻지 않음: %s' % nr)
  g = r['good']
  if not g['ok'] or g['calls'] != 1 or g['time'] != '4/4' or g['bad'] != 0: fail('정상 답을 건드림: %s' % g)
  if r['chJunk']['ok'] or r['chJunk']['calls'] != 2: fail('코드 차트 엉터리: 다시 묻고 거절 %s' % r['chJunk'])
  if not r['chRetry']['ok'] or r['chRetry']['calls'] != 2: fail('코드 차트 되풀이 → 다시 물어 바른 답 %s' % r['chRetry'])
  if r['chEmpty']['ok'] or r['chEmpty']['calls'] != 1: fail('빈 코드 차트는 다시 묻지 않고 거절 %s' % r['chEmpty'])
  if not r['chGood']['ok'] or r['chGood']['calls'] != 1: fail('정상 코드 차트 %s' % r['chGood'])
  print('replay ok — 진짜 엉터리 답 4종(4/4 지어냄·6/8 토막·12/8 합 틀림·첫 줄 합 84) · 다시 묻기 한 번 · 거절 · 하루 한도')

def check_api():
  o = node(INPROC)
  j = o['junk']
  if j['status'] != 422 or j['error'] != 'omr_unreadable' or j['gem'] != 2: fail('엉터리 채보는 다시 묻고 422: %s' % j)
  if '빼지 않았어요' not in j['msg'] or '코드가 아닌' not in j['msg']: fail('까닭·횟수 안내: %s' % j['msg'])
  if j['songs'] != 0: fail('엉터리 채보가 이번 달 채보 횟수를 씀: %s' % j)
  if j['usage'].get('n') != 2: fail('Gemini 는 두 번 과금됐으니 하루 한도는 2: %s' % j['usage'])
  e = o['empty']
  if e['status'] != 422 or e['gem'] != 1 or e['songs'] != 0: fail('빈 채보(악보 아님)는 다시 묻지 않고 422 · 횟수 안 씀: %s' % e)
  k = o['retryOk']
  if k['status'] != 200 or k['gem'] != 2 or k['songs'] != 1 or (k['quota'] or {}).get('used') != 1: fail('다시 물어 바른 답이면 성공 · 1곡: %s' % k)
  if o['credit']['status'] != 422 or o['credit']['bal'] != 2 or o['credit']['songs'] != 1: fail('크레딧으로 낸 엉터리 채보는 크레딧을 돌려줘야: %s' % o['credit'])
  if o['creditGood']['status'] != 200 or o['creditGood']['bal'] != 1 or o['creditGood']['songs'] != 2: fail('정상 채보는 크레딧 1: %s' % o['creditGood'])
  s = o['score']
  if s['status'] != 422 or s['error'] != 'score_unreadable' or s['gem'] != 2 or not s['hint']: fail('엉터리 악보 줄: 힌트를 프롬프트에 넣고, 다시 묻고 422 %s' % s)
  if s['usage'].get('n') != 2 or s['usage'].get('t', 0) <= 0: fail('악보 만들기 엉터리도 부른 만큼 하루 한도·토큰을 셈: %s' % s['usage'])
  so = o['scoreOk']
  if so['status'] != 200 or so['time'] != '12/8' or so['m'] != 3 or so['from'] != 'printed' or so['gem'] != 1: fail('바른 12/8 줄: %s' % so)
  if o['badHint']['status'] != 200 or not o['badHint']['clean']: fail('이상한 힌트 값이 프롬프트에 들어감: %s' % o['badHint'])
  print('api ok — /omr 엉터리 422 + 이번 달 횟수·크레딧 안 씀 (하루 한도는 셈) · /score 엉터리 422 · 힌트')

ROT = r"""async ([d, deg])=>{const img=await CONTI.loadImg(d);const r=deg*Math.PI/180,c=Math.abs(Math.cos(r)),s=Math.abs(Math.sin(r));
  const W=Math.round(img.naturalWidth*c+img.naturalHeight*s),H=Math.round(img.naturalHeight*c+img.naturalWidth*s);
  const cv=document.createElement('canvas');cv.width=W;cv.height=H;const x=cv.getContext('2d');x.fillStyle='#f8f6f2';x.fillRect(0,0,W,H);
  x.translate(W/2,H/2);x.rotate(-r);x.drawImage(img,-img.naturalWidth/2,-img.naturalHeight/2);
  const old=CONTI.detectSystems(cv).length;const L=CONTI.scoreLayout(cv);
  return {old,deg:L.deg,segs:L.segs.map(s=>({col:s.col,song:s.song,bands:s.bands})),W:L.cv.width}}"""

def data_url(name):
  return 'data:image/jpeg;base64,' + base64.b64encode(open(os.path.join(ROOT, 'docs', name), 'rb').read()).decode()

def signup(pg, who):
  pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=8000)
  pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
  pg.check('#lgAgree'); pg.fill('#lgName', '하은'); pg.fill('#lgUser', who + tag); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')
  pg.wait_for_selector('#gtTeam', timeout=8000); pg.fill('#gtTeam', '악보팀'); pg.click('[data-act="team-create"]'); pg.wait_for_selector('.shell[data-page]', timeout=8000)
  pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]'); pg.fill('[data-f="svc.name"]', '악보 예배')

def add_item(pg, sheet):
  pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]')
  n = pg.evaluate('CONTI.S.services[0].items.length')
  pg.set_input_files('#pieceFile', [os.path.join(ROOT, 'docs', sheet)])
  pg.wait_for_function("(CONTI.S.services[0].items[%d].pieces||[]).length>0" % (n - 1), timeout=20000); pg.wait_for_timeout(500)
  return n - 1

def build(pg, idx):
  here = pg.evaluate('location.hash')
  pg.evaluate("window.__T=[];clearInterval(window.__TI);window.__TI=setInterval(()=>{const t=document.querySelector('#toast');if(t&&t.classList.contains('show')&&window.__T[window.__T.length-1]!==t.textContent)window.__T.push(t.textContent)},50)")
  pg.evaluate("()=>{if(!CONTI.aiOk())CONTI.savePrefs({aiOk:new Date().toISOString()})}")   # AI 악보 인식 동의 (처음 한 번)
  pg.evaluate("(i)=>{const s=CONTI.S.services[0],it=s.items[i];it.score=null;return CONTI.rebuildScore(s,it,it.pieces[0])}", idx)
  pg.wait_for_timeout(300)
  out = pg.evaluate("(i)=>{const s=CONTI.S.services[0].items[i].score;return {toasts:window.__T,score:s?{n:s.measures.length,time:s.time,title:s.title,lines:s.lines,failed:s.failed}:null}}", idx)
  # 다 만들면 악보 화면으로 간다 — 다음 곡을 넣으려면 편집 화면으로 돌아온다
  if pg.evaluate('location.hash') != here:
    pg.evaluate('(h)=>{location.hash=h}', here); pg.wait_for_selector('[data-act="add-item"]', timeout=10000); pg.wait_for_timeout(400)
  return out

def check_app():
  with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    ctx = b.new_context(viewport={'width': 1300, 'height': 950}); pg = ctx.new_page()
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
    signup(pg, 'os')
    # ---- A: 기울어진 사진 — 예전 오선 찾기는 1° 에 줄을 조각내고 2° 부터 못 찾았다. 이제 바로 세워 11줄 그대로 ----
    for deg in [1, 1.5, 2.5, -2]:
      r = pg.evaluate(ROT, [data_url('sample_sheet.jpg'), deg])
      bands = [bd for s in r['segs'] for bd in s['bands']]
      if abs(r['deg'] - deg) > 0.1: fail('A 기울기 %s° 를 %s° 로 잼' % (deg, r['deg']))
      if len(r['segs']) != 1 or len(bands) != 11: fail('A %s° 기울인 11줄 악보가 %s 로 잘림 (예전 오선 %d개)' % (deg, [len(s['bands']) for s in r['segs']], r['old']))
      if any(bd['x0'] > 10 or bd['x1'] < r['W'] - 10 for bd in bands): fail('A %s° 줄 띠가 오선을 반 토막 냄: %s' % (deg, bands[:3]))
      if any(bands[i]['top'] < bands[i - 1]['top'] for i in range(1, len(bands))): fail('A %s° 줄 순서가 뒤섞임' % deg)
    print('A ok — 1·1.5·2.5·-2° 기울인 사진도 11줄 그대로 (예전: 조각·못 찾음)')
    # ---- B: 두 쪽 사진은 쪽마다, 왼쪽 쪽 먼저. 위아래로 붙은 다음 곡은 따로 ----
    r = pg.evaluate(ROT, [data_url('sample_two_pages.jpg'), 0])
    if [len(s['bands']) for s in r['segs']] != [7, 5] or [s['col'] for s in r['segs']] != [0, 1]: fail('B 두 쪽 사진을 쪽마다 나누지 못함: %s' % [(s['col'], len(s['bands'])) for s in r['segs']])
    cut = r['segs'][1]['bands'][0]['x0']
    if any(bd['x1'] > cut for bd in r['segs'][0]['bands']): fail('B 왼쪽 쪽 띠가 오른쪽 쪽에 걸침')
    r = pg.evaluate(ROT, [data_url('sample_stacked.jpg'), 0])
    if len(r['segs']) != 2 or not r['segs'][1]['song']: fail('B 위아래로 붙은 두 곡을 한 곡으로 봄: %s' % [(s['song'], len(s['bands'])) for s in r['segs']])
    print('B ok — 두 쪽 사진은 쪽마다(7·5줄, 섞이지 않음) · 위아래 두 곡 구분')

    # ---- 앱 흐름: /api/score 는 가짜로 답한다 (줄 번호·힌트를 보고) ----
    seen = []; mode = {'v': ''}
    def song(title, key, t, chord, from_='printed'):
      m = {'c': [{'b': 0, 't': chord}], 'n': [{'p': 'A4', 'd': 2, 'dot': True}] if t == '3/4' else [{'p': 'A4', 'd': 1}]}
      return {'songs': [{'title': title, 'key': key, 'time': t, 'verses': 1, 'pickup': False, 'confidence': 0.9, 'measures': [m, m]}], 'model': 'fake', 'usage': {'input': 1, 'output': 1}, 'badMeasures': [], 'costKRW': 1, 'time': {'from': from_}}
    def handler(route):
      body = json.loads(route.request.post_data or '{}'); h = body.get('hint') or {}
      seen.append(h); line = h.get('line') or 1
      if mode['v'] == 'hint':
        # 첫 줄만 3/4 (박자표가 인쇄된 줄). 나머지는 4/4 로 짐작해 온다 — 합칠 때 첫 줄 박자를 따라야
        return route.fulfill(json=song('우리 주 하나님', 'A', '3/4', 'A') if line == 1 else song('', 'A', '4/4', 'D'))
      if mode['v'] == 'two':
        if line == 1 and h.get('time'): return route.fulfill(json=song('예수로 나의 구주 삼고', 'C', '12/8', 'C'))   # 오른쪽 쪽 첫 줄
        return route.fulfill(json=song('우리 주 하나님' if line == 1 else '', 'A', '4/4', 'A'))
      if mode['v'] == 'most':
        if line <= 6: return route.fulfill(status=422, json={'error': 'score_unreadable', 'message': '악보를 제대로 읽지 못했어요 — 음 이름을 알아볼 수 없어요'})
        return route.fulfill(json=song('', 'A', '4/4', 'A'))
      if mode['v'] == 'one':
        if line == 3: return route.fulfill(status=422, json={'error': 'score_unreadable', 'message': '악보를 제대로 읽지 못했어요 — 마디마다 박자가 맞지 않아요'})
        return route.fulfill(json=song('우리 주 하나님' if line == 1 else '', 'A', '4/4', 'A'))
      return route.continue_()
    pg.route('**/api/score', handler)

    i1 = add_item(pg, 'sample_sheet.jpg')
    # ---- C: 첫 줄을 먼저 읽고, 나머지 줄에 첫 줄 박자·조를 알려 준다. 합쳐도 첫 줄 박자 ----
    mode['v'] = 'hint'; seen.clear()
    r = build(pg, i1)
    if len(seen) != 11: fail('C 11줄을 다 보내지 않음: %d' % len(seen))
    if seen[0].get('line') != 1 or seen[0].get('time'): fail('C 첫 줄은 박자 없이(인쇄된 것을 읽게) 먼저: %s' % seen[0])
    rest = seen[1:]
    if not all(h.get('time') == '3/4' and h.get('key') == 'A' and h.get('lines') == 11 for h in rest) or sorted(h['line'] for h in rest) != list(range(2, 12)):
      fail('C 둘째 줄부터 첫 줄 박자(3/4)·조·줄 번호를 알려 주지 않음: %s' % rest[:3])
    if not r['score'] or r['score']['time'] != '3/4' or r['score']['n'] != 22: fail('C 합친 악보가 첫 줄 박자를 따르지 않음(다수결 4/4): %s' % r)
    print('C ok — 첫 줄 먼저 · 나머지 10줄에 3/4·A·줄 번호 · 합친 박자는 첫 줄 것')

    # ---- B': 두 쪽 사진, 오른쪽 쪽 첫 줄 제목이 다르면 첫 곡만 ----
    i2 = add_item(pg, 'sample_two_pages.jpg')
    mode['v'] = 'two'; seen.clear()
    r = build(pg, i2)
    if len(seen) != 8: fail("B' 왼쪽 7줄 + 오른쪽 첫 줄만 읽고 멈춰야: %d번 보냄" % len(seen))
    if not r['score'] or r['score']['n'] != 14 or r['score']['lines'] != 7 or r['score']['time'] != '4/4': fail("B' 다른 곡을 섞음: %s" % r['score'])
    if not any('첫 곡만' in t for t in r['toasts']): fail("B' 첫 곡만 만들었다는 안내가 없음: %s" % r['toasts'])
    print("B' ok — 옆 쪽이 다른 곡이면 첫 곡만(7줄) · 안내")

    # ---- D: 절반 넘게 못 읽으면 그리지 않는다 · 한 줄만 못 읽으면 어느 줄인지 알린다 ----
    mode['v'] = 'most'
    r = build(pg, i1)
    if r['score']: fail('D 11줄 중 6줄을 못 읽었는데 악보를 만듦: %s' % r['score'])
    if not any('제대로 읽지 못했어요' in t and '다시 찍어' in t for t in r['toasts']): fail('D 까닭 안내 없음: %s' % r['toasts'])
    mode['v'] = 'one'
    r = build(pg, i1)
    if not r['score'] or r['score']['failed'] != 1 or r['score']['n'] != 20: fail('D 한 줄 실패: %s' % r['score'])
    if not any('3번째 줄은 읽지 못해' in t for t in r['toasts']): fail('D 못 읽은 줄 번호 안내 없음: %s' % r['toasts'])
    print('D ok — 절반 넘게 못 읽으면 안 그림 · 한 줄 실패는 줄 번호 안내')
    if errs: fail('page errors: %s' % errs[:3])
    b.close()

if __name__ == '__main__':
  check_lib()
  check_api()
  check_app()
  print('PASS test_omr_sanity')
