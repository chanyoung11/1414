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
