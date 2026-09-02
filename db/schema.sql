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
