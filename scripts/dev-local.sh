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
# 푸시: .env.local 에 없으면 개발용 키를 쓴다
export VAPID_PUBLIC_KEY="${VAPID_PUBLIC_KEY:-BBq9nqw8YvL_wusVh4V6jQIXo-nph79oqnhr8VhzTfO67ssHN4FwThabeFwyq7YKeYl3lIOHJRklS6kfO8sbEVo}"
export VAPID_PRIVATE_KEY="${VAPID_PRIVATE_KEY:-Qy2iS5vLHI40osMnj_7AQwXeTtFRf0aP24RkV21cMY8}"

# AI 는 기본으로 '가짜'다. 테스트를 돌릴 때마다 진짜로 부르면 한 번에 300~400원이 나간다.
# 저장해 둔 진짜 결과(docs/ocr_fixture.json)를 돌려주므로 코드 개수·제목·키까지 같다.
# 진짜로 확인하려면:  REAL_AI=1 sh scripts/dev-local.sh
if [ "${REAL_AI:-}" = "1" ]; then
  echo "⚠️  진짜 AI 를 부릅니다 — 전체 테스트 한 번에 300~400원쯤 듭니다"
else
  export GEMINI_API_KEY=mock
  unset GOOGLE_VISION_KEY GOOGLE_APPLICATION_CREDENTIALS
fi

# 파일 저장소도 로컬로 (운영 저장소에 테스트 파일이 쌓이지 않게)
export BLOB_LOCAL_DIR="${BLOB_LOCAL_DIR:-$PWD/.localblob}"
export BLOB_LOCAL_BASE="http://localhost:$PORT"
unset BLOB_READ_WRITE_TOKEN R2_ENDPOINT R2_BUCKET R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY
mkdir -p "$BLOB_LOCAL_DIR"

node scripts/migrate.mjs
exec node scripts/dev.mjs
