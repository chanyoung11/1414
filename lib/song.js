// 곡 검색·정규화. 서버(색인 만들기)와 브라우저(즉석 검색)가 같은 규칙을 써야 결과가 맞는다.
// 초성 검색: 'ㅇㅅㄹ' 로 '오 신 령' 을 찾는다. 한글 자모는 유니코드 계산으로 뽑는다.

const CHO = ['ㄱ','ㄲ','ㄴ','ㄷ','ㄸ','ㄹ','ㅁ','ㅂ','ㅃ','ㅅ','ㅆ','ㅇ','ㅈ','ㅉ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ'];

// 공백·기호를 지우고 소문자로. 'D/F#' 같은 코드는 곡 제목에 잘 안 나오니 그냥 지운다
export const norm = (s) => String(s || '').normalize('NFC').toLowerCase()
  .replace(/[\s\-–—''"()[\]·,.!?+/&]/g, '');

// 각 글자의 첫소리만. 한글이 아니면 글자 그대로 (영문 제목도 같이 걸리게)
export const cho = (s) => [...String(s || '')].map((ch) => {
  const c = ch.charCodeAt(0);
  return (c >= 0xAC00 && c <= 0xD7A3) ? CHO[Math.floor((c - 0xAC00) / 588)] : ch;
}).join('');

// 입력이 전부 자음이면 초성 검색으로 본다 (ㅇㅅㄹ)
export const isChoQuery = (s) => {
  const t = norm(s);
  return t.length >= 2 && /^[ㄱ-ㅎ]+$/.test(t);
};

// 곡 하나의 색인. 저장할 때 만들어 둔다
export function indexOf(song) {
  const t = norm(song.title);
  return { title_norm: t, title_cho: cho(t) };
}

// 검색어가 어디에 걸렸는지까지 돌려준다. 결과 줄에 '가사: …' 로 보여 주려고
// 우선순위 (명세 A.4.1): 제목 접두 > 제목 포함 > 별칭·메들리 > 아티스트 > 가사 첫 줄 > 태그 > 편곡 이름
const FIELDS = [
  { key: 'aliases', label: '다른 이름' },
  { key: 'artist', label: '아티스트' },
  { key: 'first_line', label: '가사' },
  { key: 'tags', label: '태그' },
  { key: 'arrNames', label: '편곡' },
];
export function matchSong(song, query) {
  const raw = String(query || '').trim();
  if (raw.length < 2) return { rank: 0, where: '' };
  if (isChoQuery(raw)) {
    const c = norm(raw);
    const tc = song.title_cho || cho(norm(song.title));
    if (tc.startsWith(c)) return { rank: 1, where: '' };
    if (tc.includes(c)) return { rank: 2, where: '' };
    return { rank: 0, where: '' };
  }
  const n = norm(raw);
  const tn = song.title_norm || norm(song.title);
  if (tn.startsWith(n)) return { rank: 1, where: '' };
  if (tn.includes(n)) return { rank: 2, where: '' };
  for (let i = 0; i < FIELDS.length; i++) {
    const { key, label } = FIELDS[i];
    const v = song[key];
    const list = Array.isArray(v) ? v : (v ? [v] : []);
    const hit = list.find((x) => norm(x).includes(n));
    if (hit) return { rank: 3 + i, where: `${label}: ${hit}` };
  }
  return { rank: 0, where: '' };
}

// 제목이 같아 보이는 곡 찾기 (새 곡 만들 때 중복 확인 · 정리 도구)
export const sameTitle = (a, b) => {
  const an = a.title_norm || norm(a.title), bn = b.title_norm || norm(b.title);
  if (an && an === bn) return true;
  const ac = a.title_cho || cho(an), bc = b.title_cho || cho(bn);
  return !!ac && ac === bc;
};
