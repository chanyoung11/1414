# 1414 — 찬양팀 콘티 앱

인도자가 콘티(곡 순서·키·송폼·악보·유튜브)를 만들어 발행하고, 팀원이 세션별로 보고 연습·무대에서 쓰는 PWA.

- `app/` — 프레임워크 없는 단일 `index.html` (PWA, 오프라인 지원)
- `api/` — Vercel 서버리스 함수 (계정 · 팀 · 초대), Neon Postgres
- `db/schema.sql` — DB 스키마 (`npm run db:migrate`)
- `tests/` — Playwright 자동 테스트
- `docs/` — 기능명세서 · 서버 설정 안내

## 로컬 실행

```bash
npm install
# Postgres (Docker) — 또는 Neon 연결 문자열을 DATABASE_URL 에
docker run -d --name conti-pg -e POSTGRES_PASSWORD=pg -p 54329:5432 postgres:16-alpine
export DATABASE_URL=postgres://postgres:pg@localhost:54329/postgres
export AUTH_SECRET=$(openssl rand -base64 32)
npm run db:migrate
npm run dev            # http://localhost:8766
```

서버 없이 정적으로만 열면(`cd app && python3 -m http.server 8765`) 로그인 없이 기기 안에서만 동작하는 오프라인 모드가 됩니다.

## 배포 (Vercel + Neon)

`docs/서버_설정.md` 참고.
