// library(곡 복사본 목록) → songs + arrangements + song_usages 로 옮긴다 (명세 A.2).
// 되돌릴 수 없으니 이행 전후를 견줘 보고, 다르면 아무것도 쓰지 않는다.
//   미리보기: DATABASE_URL=... node scripts/migrate-library.mjs
//   실제 실행: DATABASE_URL=... node scripts/migrate-library.mjs --apply
import pg from 'pg';
import { norm, cho, sameTitle } from '../lib/song.js';

const url = process.env.DATABASE_URL || process.env.POSTGRES_URL;
if (!url) { console.error('DATABASE_URL 이 없습니다'); process.exit(1); }
const APPLY = process.argv.includes('--apply');
const client = new pg.Client({ connectionString: url, ssl: /neon\.tech|sslmode=require/.test(url) ? { rejectUnauthorized: false } : undefined });
await client.connect();
const q = async (sql, p) => (await client.query(sql, p)).rows;

// 이행 전후로 같아야 하는 것: 발행본이 그리는 결과 (곡 수·제목·키·송폼·조각 수)
const shapeOf = (items) => (items || []).map((it) => ({
  title: it.title || '', key: [it.key, it.mod].filter(Boolean).join(' – '),
  form: it.form || '', pieces: (it.pieces || []).length, media: (it.media || []).length,
}));

const teams = await q('select id, name from teams where deleted_at is null order by created_at');
let nSongs = 0, nArr = 0, nUse = 0, nDup = 0, mismatched = [];

await client.query('begin');
try {
  for (const t of teams) {
    const lib = await q(`select id, song from library where team_id=$1 and deleted_at is null order by updated_at`, [t.id]);
    const services = await q(`select id, doc, version from services where team_id=$1`, [t.id]);
    const before = new Map(services.map((s) => [s.id, shapeOf(s.doc && s.doc.items)]));

    // 이미 옮긴 팀은 건너뛴다 (여러 번 돌려도 안전하게)
    const done = await q('select count(*)::int as n from songs where team_id=$1', [t.id]);
    if (done[0].n > 0) continue;

    const made = [];   // {libId, songId, arrId, title}
    for (const row of lib) {
      const s = row.song || {};
      const title = String(s.title || '').trim() || '(제목 없음)';
      const tn = norm(title);
      // 같은 제목이 이미 있으면 그 곡에 편곡으로 붙인다. 자동 합치기는 안 하고(명세 A.2.4)
      // 제목이 똑같을 때만 한 곡으로 본다
      let hit = made.find((m) => m.titleNorm === tn && tn);
      let songId;
      if (hit) { songId = hit.songId; nDup++; }
      else {
        const r = await q(`insert into songs(team_id, title, title_norm, title_cho, orig_key, tags, created_at, updated_at)
                           values($1,$2,$3,$4,$5,$6,now(),now()) returning id`,
          [t.id, title, tn, cho(tn), String(s.key || ''), []]);
        songId = r[0].id; nSongs++;
      }
      const isFirst = !hit;
      const a = await q(`insert into arrangements(song_id, team_id, name, is_default, key, mod, form, song_note, pieces, media, chart, score, created_at, updated_at)
                         values($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,now(),now()) returning id`,
        [songId, t.id, isFirst ? '기본' : (String(s.key || '') || '다른 편곡'), isFirst,
         String(s.key || ''), String(s.mod || ''), String(s.form || ''), String(s.songNote || ''),
         JSON.stringify(s.pieces || []), JSON.stringify((s.media || []).map((m) => ({ ...m, notes: [] }))),
         s.chart ? JSON.stringify(s.chart) : null, s.score ? JSON.stringify(s.score) : null]);
      nArr++;
      made.push({ libId: row.id, songId, arrId: a[0].id, title, titleNorm: tn });
    }

    // 예배 항목에 편곡을 이어 준다. 라이브러리에 없던 곡은 여기서 곡·편곡을 만든다
    for (const sv of services) {
      const doc = sv.doc || {}; const items = doc.items || [];
      let touched = false;
      for (const it of items) {
        let m = it.libId ? made.find((x) => x.libId === it.libId) : null;
        if (!m && it.title) m = made.find((x) => x.titleNorm === norm(it.title));
        if (!m) {
          const title = String(it.title || '').trim() || '(제목 없음)';
          const tn = norm(title);
          const r = await q(`insert into songs(team_id, title, title_norm, title_cho, orig_key, created_at, updated_at)
                             values($1,$2,$3,$4,$5,now(),now()) returning id`, [t.id, title, tn, cho(tn), String(it.key || '')]);
          const a = await q(`insert into arrangements(song_id, team_id, name, is_default, key, mod, form, song_note, pieces, media, chart, score, created_from_service_id, created_at, updated_at)
                             values($1,$2,'기본',true,$3,$4,$5,$6,$7,$8,$9,$10,$11,now(),now()) returning id`,
            [r[0].id, t.id, String(it.key || ''), String(it.mod || ''), String(it.form || ''), String(it.songNote || ''),
             JSON.stringify(it.pieces || []), JSON.stringify((it.media || []).map((x) => ({ ...x, notes: [] }))),
             it.chart ? JSON.stringify(it.chart) : null, it.score ? JSON.stringify(it.score) : null, sv.id]);
          nSongs++; nArr++;
          m = { libId: it.libId || null, songId: r[0].id, arrId: a[0].id, title, titleNorm: tn };
          made.push(m);
        }
        if (it.arrId !== m.arrId) { it.arrId = m.arrId; it.songId = m.songId; touched = true; }
      }
      if (touched) await q('update services set doc=$2 where id=$1', [sv.id, JSON.stringify(doc)]);

      // 사용 이력 (발행본만)
      const last = items.length - 1;
      for (let i = 0; i < items.length; i++) {
        const it = items[i];
        if (!it.songId) continue;
        await q(`insert into song_usages(team_id, song_id, arrangement_id, service_id, service_date, service_name, position, is_application, key_used)
                 values($1,$2,$3,$4,$5,$6,$7,$8,$9) on conflict (song_id, service_id) do nothing`,
          [t.id, it.songId, it.arrId, sv.id, /^\d{4}-\d{2}-\d{2}$/.test(doc.date || '') ? doc.date : null,
           String(doc.name || ''), i, i === last, String(it.key || '')]);
        nUse++;
      }
    }

    // 검증: 발행본이 그리는 결과가 그대로인가
    const after = await q(`select id, doc from services where team_id=$1`, [t.id]);
    for (const sv of after) {
      const a = JSON.stringify(shapeOf(sv.doc && sv.doc.items));
      const b = JSON.stringify(before.get(sv.id) || []);
      if (a !== b) mismatched.push({ team: t.name, service: sv.id, before: b, after: a });
    }
  }

  if (mismatched.length) {
    console.error('\n[중단] 이행 전후 발행본이 달라졌습니다. 아무것도 쓰지 않았습니다.');
    mismatched.slice(0, 5).forEach((m) => console.error(' ', m.team, m.service, '\n   전:', m.before, '\n   후:', m.after));
    await client.query('rollback');
    process.exit(1);
  }
  if (APPLY) { await client.query('commit'); console.log('\n적용했습니다.'); }
  else { await client.query('rollback'); console.log('\n미리보기만 했습니다. 실제로 옮기려면 --apply 를 붙이세요.'); }
} catch (e) {
  await client.query('rollback');
  console.error('실패, 되돌렸습니다:', e.message);
  process.exit(1);
}
console.log(`팀 ${teams.length} · 곡 ${nSongs} · 편곡 ${nArr} (제목이 같아 한 곡으로 묶은 편곡 ${nDup}) · 사용 이력 ${nUse}`);
await client.end();
