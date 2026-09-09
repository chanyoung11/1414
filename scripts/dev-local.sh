#!/usr/bin/env sh
# 로컬 개발·테스트 서버. 운영 DB 를 건드리지 않으려고 도커 안의 포스트그레스를 쓴다.
#   sh scripts/dev-local.sh
# GEMINI_API_KEY 처럼 밖에서 받아야 하는 값은 .env.local 에서 가져오되 DB 는 항상 로컬로 덮어쓴다.
set -e
cd "$(dirname "$0")/.."

if ! docker ps --format '{{.Names}}' | grep -qx conti-pg; then
  echo "도커 포스트그레스를 켭니다 (conti-pg, 54329 포트)"
  docker start conti-pg 2>/dev/null || \
    docker run -d --name conti-pg -e POSTGRES_PASSWORD=pg -p 54329:5432 postgres:16
  sleep 3
fi

[ -f .env.local ] && { set -a; . ./.env.local; set +a; }
export DATABASE_URL="postgres://postgres:pg@localhost:54329/postgres"
export AUTH_SECRET="${AUTH_SECRET_DEV:-local-dev-secret-0123456789}"
export PORT="${PORT:-8766}"

node scripts/migrate.mjs
exec node scripts/dev.mjs
