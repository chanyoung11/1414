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
