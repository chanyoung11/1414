-- 콘티 서버 스키마 (계정 · 팀 · 멤버)
-- 적용: npm run db:migrate   (DATABASE_URL 필요)  또는  psql "$DATABASE_URL" -f db/schema.sql
-- 여러 번 실행해도 안전합니다.

create extension if not exists pgcrypto;

create table if not exists users (
  id            uuid primary key default gen_random_uuid(),
  username      text not null unique,          -- 소문자로 저장
  password_hash text not null,                 -- scrypt$N$salt$hash
  display_name  text not null,
  created_at    timestamptz not null default now(),
  last_login_at timestamptz
);

create table if not exists teams (
  id           uuid primary key default gen_random_uuid(),
  name         text not null,
  sessions     jsonb not null default '["드럼","베이스","건반","일렉","어쿠스틱","싱어","인도자"]',
  phrases      jsonb not null default '["Down","Full","쉬기","패드만","브레이크","하프타임","반복"]',
  invite_token text not null unique,
  created_by   uuid not null references users(id),
  created_at   timestamptz not null default now()
);

create table if not exists members (
  user_id    uuid not null references users(id) on delete cascade,
  team_id    uuid not null references teams(id) on delete cascade,
  name       text not null,
  session    text not null,
  role       text not null default 'member' check (role in ('leader','session_lead','member')),
  created_at timestamptz not null default now(),
  primary key (user_id, team_id)
);
create index if not exists members_team_idx on members(team_id);

-- ---------- 발행본 · 파일 · 메모 동기화 ----------
create table if not exists services (
  team_id    uuid not null references teams(id) on delete cascade,
  id         text not null,                    -- 앱의 예배 id
  doc        jsonb not null,                   -- 발행본 스냅샷 (items 안의 notes 없음)
  version    int not null default 0,
  name       text,
  date       text,
  updated_by uuid references users(id),
  updated_at timestamptz not null default now(),
  primary key (team_id, id)
);

create table if not exists blobs (
  team_id    uuid not null references teams(id) on delete cascade,
  id         text not null,                    -- 앱의 blob id
  url        text not null,                    -- Vercel Blob URL
  type       text,
  size       int,
  created_at timestamptz not null default now(),
  primary key (team_id, id)
);

create table if not exists notes (
  id          text primary key,
  team_id     uuid not null references teams(id) on delete cascade,
  service_id  text not null,
  item_id     text not null,
  marker_id   text,                            -- 섹션 메모
  media_id    text,                            -- 타임라인 메모
  t           real,
  layer       text not null check (layer in ('leader','session','mine')),
  session     text,
  text        text not null,
  author_id   uuid references users(id) on delete cascade,
  author_name text,
  created_at  timestamptz not null default now()
);
create index if not exists notes_svc_idx on notes(team_id, service_id);

-- 로그인 시도 제한
create table if not exists login_attempts (
  username text primary key,
  n        int not null default 0,
  last     timestamptz not null default now()
);

-- 기타 카포 (멤버별 표시용)
alter table members add column if not exists capo int not null default 0;

-- 비밀번호 복구 코드 (해시만 저장)
alter table users add column if not exists recovery_hash text;

-- 초안 (인도자 기기 간 이어서 편집)
create table if not exists drafts (
  team_id    uuid not null references teams(id) on delete cascade,
  id         text not null,
  doc        jsonb not null,
  updated_by uuid references users(id),
  updated_at timestamptz not null default now(),
  primary key (team_id, id)
);
-- 비공개 Blob: 서명 URL 발급용 경로
alter table blobs add column if not exists pathname text;

-- ---------- §2 정기 예배 · 사역 날짜 ----------
-- 팀 설정 확장 (없으면 추가)
alter table teams add column if not exists settings jsonb not null default '{}';
-- settings: { serviceAutoCreateWeeks:4, nameRule:'{월}/{일} {요일}', reminderDay:25, wordRequestDay:2, rehearsalUploadRole:'member', slots:{}, defaultLineup:{} }

-- 정기 예배 (요일 기반)
create table if not exists recurring (
  id         uuid primary key default gen_random_uuid(),
  team_id    uuid not null references teams(id) on delete cascade,
  weekday    int  not null check (weekday between 0 and 6),   -- 0=일
  label      text not null,
  time       text,                                            -- 'HH:MM'
  active     bool not null default true,
  created_at timestamptz not null default now()
);
create index if not exists recurring_team_idx on recurring(team_id);

-- 사역 날짜 (실제 달력에 뜨는 개별 날짜)
create table if not exists service_dates (
  id           uuid primary key default gen_random_uuid(),
  team_id      uuid not null references teams(id) on delete cascade,
  date         date not null,
  label        text not null,
  time         text,
  source       text not null default 'manual' check (source in ('recurring','manual')),
  recurring_id uuid references recurring(id) on delete set null,
  open         bool not null default true,
  service_id   text,                                          -- 연결된 콘티(Service.id)
  created_at   timestamptz not null default now(),
  unique (team_id, date, label)
);
create index if not exists sdate_team_idx on service_dates(team_id, date);

-- 비밀번호 변경·초기화·복구 시각. 이보다 먼저 발급된 세션 토큰(iat)은 무효 (null 이면 검사 안 함)
alter table users add column if not exists auth_epoch timestamptz;

-- §1 알림함: 사용자별 알림. (team,user,type,target) 중복 키는 24시간 안에 갱신만
create table if not exists notifications (
  id              uuid primary key default gen_random_uuid(),
  team_id         uuid not null references teams(id) on delete cascade,
  user_id         uuid not null references users(id) on delete cascade,
  type            text not null,
  target_id       text not null default '',
  title           text not null,
  body            text not null default '',
  link            text not null default '',
  actionable      bool not null default false,
  read_at         timestamptz,
  acknowledged_at timestamptz,
  expires_at      timestamptz,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  unique (team_id, user_id, type, target_id)
);
create index if not exists notifications_user_idx on notifications(team_id, user_id, updated_at desc);

-- §4 말씀: 콘티와 별개로 저장해 저장 즉시 전원에게 보이게 한다 (목회자·인도자·링크가 씀)
create table if not exists service_words (
  team_id    uuid not null references teams(id) on delete cascade,
  service_id text not null,
  word       jsonb not null default '{}',
  updated_by uuid references users(id),
  updated_at timestamptz not null default now(),
  primary key (team_id, service_id)
);
-- §4.5 예배 노트 바텀시트: 어디까지 읽었는지 (기기 + 서버)
create table if not exists service_reads (
  team_id    uuid not null references teams(id) on delete cascade,
  service_id text not null,
  user_id    uuid not null references users(id) on delete cascade,
  rev        int not null default 0,
  at         timestamptz not null default now(),
  primary key (team_id, service_id, user_id)
);

-- §0 역할에 목회자(pastor) 추가. 세션 없음, 콘티 편집·편성 없음, 말씀을 쓴다
alter table members drop constraint if exists members_role_check;
alter table members add constraint members_role_check check (role in ('leader','session_lead','member','pastor'));

-- §3 편성: 멤버는 세션을 여러 개 맡을 수 있다(겸임)
alter table members add column if not exists sessions text[];
-- 가능 여부. 'unset'은 행이 없는 것과 같아 저장하지 않는다
create table if not exists availability (
  team_id    uuid not null references teams(id) on delete cascade,
  user_id    uuid not null references users(id) on delete cascade,
  date       date not null,
  state      text not null check (state in ('ok','maybe','no')),
  memo       text not null default '',
  updated_at timestamptz not null default now(),
  primary key (team_id, user_id, date)
);
-- 편성은 사역 날짜에 붙는다 (콘티가 없어도 미리 짤 수 있게)
alter table service_dates add column if not exists lineup jsonb not null default '[]';

-- §5 합주 녹음: 파일은 Blob, 메타·메모는 여기. 90일 뒤 삭제(보관 잠금이면 유지)
create table if not exists rehearsals (
  id          uuid primary key default gen_random_uuid(),
  team_id     uuid not null references teams(id) on delete cascade,
  service_id  text not null,
  date        date not null,
  label       text not null default '',
  blob_id     text not null,
  mime        text not null default 'audio/mp4',
  duration    int not null default 0,
  size_bytes  bigint not null default 0,
  uploaded_by uuid references users(id),
  keep        bool not null default false,
  expires_at  timestamptz,
  warned_at   timestamptz,
  created_at  timestamptz not null default now()
);
create index if not exists rehearsals_svc_idx on rehearsals(team_id, service_id, created_at desc);
alter table rehearsals add column if not exists notes jsonb not null default '[]';

-- §4.6 목회자 링크: 로그인 없이 말씀을 보내는 1회용 링크 (7일)
create table if not exists word_links (
  token      text primary key,
  team_id    uuid not null references teams(id) on delete cascade,
  service_id text not null,
  created_by uuid references users(id),
  expires_at timestamptz not null,
  used_at    timestamptz,
  created_at timestamptz not null default now()
);

-- 라이브러리: 팀이 함께 쓰는 곡 보관함 (기기 안에만 있던 것을 서버로)
create table if not exists library (
  team_id    uuid not null references teams(id) on delete cascade,
  id         text not null,
  song       jsonb not null,
  norm_title text not null default '',
  updated_by uuid references users(id),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz,
  primary key (team_id, id)
);
create index if not exists library_team_idx on library(team_id, updated_at desc);
-- 통보한 사람 목록 (편성에서 빠진 사람을 알아내려면 현재 편성만으로는 알 수 없다)
alter table service_dates add column if not exists notified jsonb not null default '[]';

-- ─────────────────────────────────────────────────────────────
-- 팀·멤버 명세 B부
-- ─────────────────────────────────────────────────────────────

-- B.9 플랜. 지금은 값만 두고 한도 검사는 하지 않는다(결제 연동 때 켠다)
alter table teams add column if not exists plan text not null default 'free';
alter table teams drop constraint if exists teams_plan_check;
alter table teams add constraint teams_plan_check check (plan in ('free','pro'));
-- B.6.2 결제 담당자. null 이면 인도자(teams.created_by)
alter table teams add column if not exists billing_user_id uuid references users(id);
-- B.7.1 팀 삭제는 30일 유예 뒤 크론이 실제로 지운다
alter table teams add column if not exists deleted_at timestamptz;

-- B.4.3 비활성: 편성·알림에서만 빠지고 그 사람이 쓴 것은 남는다
alter table members add column if not exists active boolean not null default true;
alter table members add column if not exists deactivated_at timestamptz;
alter table members add column if not exists last_seen_at timestamptz;
-- B.2 인도자는 팀에 정확히 1명
create unique index if not exists one_leader_per_team on members (team_id) where role='leader' and active;

-- B.3 초대 링크: 역할·만료·횟수·회수. 팀당 여러 개가 동시에 살아 있을 수 있다
create table if not exists invites (
  id         uuid primary key default gen_random_uuid(),
  team_id    uuid not null references teams(id) on delete cascade,
  code       text not null unique,
  role       text not null default 'member' check (role in ('member','session_lead','pastor')),
  expires_at timestamptz,                       -- null = 만료 없음
  max_uses   int,                               -- null = 무제한
  uses       int not null default 0,
  created_by uuid not null references users(id),
  created_at timestamptz not null default now(),
  revoked_at timestamptz
);
create index if not exists invites_team_idx on invites(team_id, created_at desc);

-- 팀마다 하나뿐이던 옛 링크를 그대로 살려 옮긴다 (카톡에 이미 뿌려둔 링크가 죽지 않게)
insert into invites (team_id, code, role, created_by)
select t.id, t.invite_token, 'member', t.created_by from teams t
where t.invite_token is not null
  and not exists (select 1 from invites i where i.code = t.invite_token);

-- B.1 관리 동작만 남기는 최소 기록 (누가 인도자를 넘겼는지 같은 것)
create table if not exists team_audit (
  id       bigserial primary key,
  team_id  uuid not null references teams(id) on delete cascade,
  actor_id uuid references users(id),
  action   text not null,
  target   text,
  meta     jsonb not null default '{}',
  at       timestamptz not null default now()
);
create index if not exists team_audit_idx on team_audit(team_id, at desc);

-- ─────────────────────────────────────────────────────────────
-- 라이브러리 명세 A부: 곡 → 편곡 → 사용 이력
-- 지금 library 표는 "예배에 넣은 곡의 복사본"이라 같은 곡이 여러 번 들어간다.
-- 곡은 하나로 두고, 키·편곡이 다르면 편곡을 여러 개 단다.
-- ─────────────────────────────────────────────────────────────

create table if not exists songs (
  id         uuid primary key default gen_random_uuid(),
  team_id    uuid not null references teams(id) on delete cascade,
  title      text not null,
  title_norm text not null default '',        -- 공백·기호 뺀 소문자 (검색)
  title_cho  text not null default '',        -- 초성 문자열 (ㅇㅅㄹ 검색)
  aliases    text[] not null default '{}',
  artist     text not null default '',
  orig_key   text not null default '',        -- 원키(참고). 연주 키는 편곡에
  first_line text not null default '',        -- 가사 첫 줄 (검색용, 화면에 안 씀)
  tags       text[] not null default '{}',
  tempo      text not null default '',        -- 느림·보통·빠름
  archived   boolean not null default false,
  not_dup_of uuid[] not null default '{}',    -- "다른 곡이에요" 표시한 짝
  created_by uuid references users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);
create index if not exists songs_team_idx on songs(team_id, archived, updated_at desc);
create index if not exists songs_norm_idx on songs(team_id, title_norm);
create index if not exists songs_cho_idx  on songs(team_id, title_cho);

create table if not exists arrangements (
  id          uuid primary key default gen_random_uuid(),
  song_id     uuid not null references songs(id) on delete cascade,
  team_id     uuid not null references teams(id) on delete cascade,
  name        text not null default '기본',
  is_default  boolean not null default false,
  medley_song_ids uuid[] not null default '{}',
  key         text not null default '',
  mod         text not null default '',       -- 곡 안에서 전조하는 키
  form        text not null default '',       -- 송폼 원문
  bpm         int,
  song_note   text not null default '',
  pieces      jsonb not null default '[]',
  media       jsonb not null default '[]',
  chart       jsonb,                          -- 채보한 코드 차트
  score       jsonb,                          -- 재구성한 악보
  created_from_service_id text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  deleted_at  timestamptz
);
create unique index if not exists one_default_per_song on arrangements (song_id) where is_default and deleted_at is null;
create index if not exists arr_team_idx on arrangements(team_id, song_id);
create index if not exists arr_updated_idx on arrangements(team_id, updated_at desc);

-- 고정 메모: 편곡에 붙어 "이 곡을 넣을 때마다" 따라오는 메모. 마커 id 가 아니라 라벨로 붙는다
create table if not exists arrangement_notes (
  id             uuid primary key default gen_random_uuid(),
  arrangement_id uuid not null references arrangements(id) on delete cascade,
  team_id        uuid not null references teams(id) on delete cascade,
  marker_label   text not null,
  layer          text not null check (layer in ('all','session','mine')),
  session        text,
  author_id      uuid references users(id) on delete set null,
  author_name    text not null default '',
  text           text not null,
  created_at     timestamptz not null default now()
);
create index if not exists arrnotes_idx on arrangement_notes(arrangement_id);

-- 사용 이력: 발행된 예배에서만 만든다. 초안은 세지 않는다
create table if not exists song_usages (
  id             uuid primary key default gen_random_uuid(),
  team_id        uuid not null references teams(id) on delete cascade,
  song_id        uuid not null references songs(id) on delete cascade,
  arrangement_id uuid references arrangements(id) on delete set null,
  service_id     text not null,
  service_date   date,
  service_name   text not null default '',
  position       int not null default 0,
  is_application boolean not null default false,   -- 마지막 곡(적용곡)
  key_used       text not null default '',
  via_medley     boolean not null default false,
  leader_id      uuid,
  unique (song_id, service_id)
);
create index if not exists usage_song_idx on song_usages(team_id, song_id, service_date desc);
create index if not exists usage_date_idx on song_usages(team_id, service_date desc);

-- 곡 공유 코드. 파일은 담지 않는다
create table if not exists share_codes (
  code       text primary key,
  team_id    uuid not null references teams(id) on delete cascade,
  created_by uuid references users(id),
  payload    jsonb not null,
  kind       text not null default 'song' check (kind in ('song','bundle')),
  max_uses   int,
  uses       int not null default 0,
  expires_at timestamptz not null,
  revoked_at timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists share_team_idx on share_codes(team_id, created_at desc);

-- 유료 AI 호출(채보·OCR·악보) 사용량. 팀·날짜별로 세어 하루 한도를 건다.
-- 아무나 가입해 팀을 만들면 곧바로 Gemini 를 무한히 부를 수 있었다
create table if not exists ai_usage (
  team_id  uuid not null references teams(id) on delete cascade,
  day      date not null,
  kind     text not null,                    -- omr | score | ocr
  calls    int  not null default 0,
  tokens   bigint not null default 0,
  primary key (team_id, day, kind)
);

-- 코드로 받은 곡의 출처 (명세 A.7.3: '코드로 받음 · {팀명}' 배지 30일)
alter table songs add column if not exists from_team text;
alter table songs add column if not exists from_at   timestamptz;

-- 그날만 세션 인원을 늘리거나 줄일 때. 없으면 팀 기본 정원(settings.slots)을 쓴다
alter table service_dates add column if not exists slots jsonb;

-- ---------- 사용자별 설정 · 푸시 알림 ----------
-- 무대 조판(기기 구간별), 조용한 시간 같은 개인 설정. 기기를 옮겨도 따라온다
-- (교회 컴퓨터에서 로그인해 PDF 뽑을 때 내 조판이 그대로 와야 한다)
alter table users add column if not exists prefs jsonb not null default '{}'::jsonb;

create table if not exists push_subs (
  endpoint   text primary key,
  user_id    uuid not null references users(id) on delete cascade,
  keys       jsonb not null,                 -- {p256dh, auth}
  ua         text,
  created_at timestamptz not null default now(),
  last_ok_at timestamptz
);
create index if not exists push_subs_user_idx on push_subs(user_id);
