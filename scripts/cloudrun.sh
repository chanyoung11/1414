#!/usr/bin/env bash
# Google Cloud Run 배포 · 크론 · 도메인
#
#   bash scripts/cloudrun.sh deploy     # 이미지 빌드(Cloud Build) + 배포. 환경변수는 .env.cloudrun 에서
#   bash scripts/cloudrun.sh cron       # Cloud Scheduler 크론 두 개를 만들거나 고친다 (처음엔 멈춘 상태로)
#   bash scripts/cloudrun.sh cron-on    # 크론을 켠다. 도메인을 넘기는 날, Vercel 크론을 끄는 것과 같이
#   bash scripts/cloudrun.sh url        # 서비스 주소
#
# 리전은 싱가포르다. DB(Neon ap-southeast-1)가 싱가포르에 있고 로그인 한 번에 쿼리가 7~8 번 오간다.
# 서울에 두면 그 왕복마다 70ms 씩 붙는다 (docs/속도_2026-09-22.md). 서울 리전은 도메인 연결도 안 된다.
set -euo pipefail
cd "$(dirname "$0")/.."

PROJECT="${GCP_PROJECT:-united-blend-507510-r0}"
REGION="${GCP_REGION:-asia-southeast1}"
SERVICE="${SERVICE:-lets1414}"
# 실행 계정. Firebase 프로젝트에 FCM 전송 권한이 있다 (키 파일 없이 푸시를 보낸다)
RUN_SA="${RUN_SA:-lets1414-run@$PROJECT.iam.gserviceaccount.com}"
# 빌드 계정. 기본 계정에 넓은 권한을 주지 않으려고 run.builder 만 가진 계정을 따로 둔다
BUILD_SA="${BUILD_SA:-lets1414-build@$PROJECT.iam.gserviceaccount.com}"
ENV_FILE="${ENV_FILE:-.env.cloudrun}"
G="gcloud --project=$PROJECT --quiet"

# .env 형식(KEY=VALUE, 따옴표·여러 줄 PEM 허용)을 gcloud 의 --env-vars-file(YAML)로 바꾼다
env_yaml() {
  node -e '
    const fs = require("fs");
    const src = fs.readFileSync(process.argv[1], "utf8");
    const out = {};
    const re = /^\s*(?:export\s+)?([A-Z0-9_]+)=(?:"((?:[^"\\]|\\.)*)"|'"'"'([^'"'"']*)'"'"'|(.*))\s*$/gm;
    for (const m of src.matchAll(re)) {
      const v = m[2] != null ? m[2].replace(/\\n/g, "\n").replace(/\\"/g, "\"") : (m[3] ?? m[4] ?? "").trim();
      if (v !== "") out[m[1]] = v;
    }
    for (const need of ["DATABASE_URL", "AUTH_SECRET", "CRON_SECRET"])
      if (!out[need]) { console.error(`[막음] ${process.argv[1]} 에 ${need} 가 없습니다`); process.exit(1); }
    if (/localhost|127\.0\.0\.1/.test(out.DATABASE_URL)) { console.error("[막음] DATABASE_URL 이 로컬입니다"); process.exit(1); }
    delete out.PORT;   // Cloud Run 이 정한다
    process.stdout.write(Object.entries(out).map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join("\n") + "\n");
  ' "$ENV_FILE"
}

url() { $G run services describe "$SERVICE" --region="$REGION" --format='value(status.url)'; }

case "${1:-}" in
  deploy)
    [ -f "$ENV_FILE" ] || { echo "$ENV_FILE 이 없습니다. docs/서버_설정.md 의 'Cloud Run' 을 보세요"; exit 1; }
    tmp="$(mktemp)"; trap 'rm -f "$tmp"' EXIT
    env_yaml > "$tmp"
    $G services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com >/dev/null
    # --source . 는 Dockerfile 로 Cloud Build 에서 빌드한다 (.dockerignore 로 서버에 필요한 것만 올라간다)
    # max-instances 는 비용 사고 방지용 상한. 지금 트래픽이면 1~2 대로 충분하다
    $G run deploy "$SERVICE" --source . --region="$REGION" \
      --allow-unauthenticated --env-vars-file="$tmp" --service-account="$RUN_SA" \
      --build-service-account="projects/$PROJECT/serviceAccounts/$BUILD_SA" \
      --cpu=1 --memory=512Mi --concurrency=80 --timeout=300 \
      --min-instances=0 --max-instances=10 --cpu-boost \
      --labels="app=lets1414,commit=$(git rev-parse --short HEAD)"
    u="$(url)"; echo "배포됨: $u"
    curl -fsS "$u/api/health" && echo
    ;;
  cron)
    $G services enable cloudscheduler.googleapis.com >/dev/null
    u="$(url)"
    secret="$(ENV_FILE="$ENV_FILE" env_yaml | sed -n 's/^CRON_SECRET: "\(.*\)"$/\1/p')"
    # Vercel 때와 같은 시각 (UTC 18:00 = KST 03:00, UTC 01:00 = KST 10:00)
    for job in "dates|0 3 * * *" "remind|0 10 * * *"; do
      name="lets1414-cron-${job%%|*}"; sched="${job#*|}"
      args=(--location="$REGION" --schedule="$sched" --time-zone="Asia/Seoul"
            --uri="$u/api/cron/${job%%|*}" --http-method=GET
            --attempt-deadline=300s --max-retry-attempts=3 --min-backoff=60s --max-backoff=600s)
      # 재시도: 크론은 몇 팀이라도 실패하면 500 을 돌려주고(시간이 끊겨도 실패로 친다), 다시 불리면 남은 것만 한다
      # (dates 는 몇 번 돌아도 결과가 같고, remind 는 팀마다 끝낸 날을 적어 둔다 — cron_marks). 한 번 끊기면 그날 뒤쪽 팀이 통째로 빠졌다
      if $G scheduler jobs describe "$name" --location="$REGION" >/dev/null 2>&1; then
        $G scheduler jobs update http "$name" "${args[@]}" --update-headers="Authorization=Bearer $secret"
      else
        $G scheduler jobs create http "$name" "${args[@]}" --headers="Authorization=Bearer $secret"
        # 도메인을 넘기기 전에는 Vercel 크론도 돌고 있다. 둘 다 돌면 알림이 두 번 간다
        $G scheduler jobs pause "$name" --location="$REGION"
      fi
    done
    $G scheduler jobs list --location="$REGION"
    ;;
  cron-on)
    for n in dates remind; do $G scheduler jobs resume "lets1414-cron-$n" --location="$REGION"; done
    $G scheduler jobs list --location="$REGION"
    ;;
  url) url ;;
  *) sed -n '2,9p' "$0"; exit 1 ;;
esac
