# 되돌리기 — Workers → Vercel (2026-09-20)

도메인을 Cloudflare Workers 로 넘겼다. 문제가 생기면 아래대로 되돌린다.
Vercel 배포는 지우지 않았으므로 DNS 만 되돌리면 몇 초 안에 원래대로 온다.

## 1) 가장 빠른 길 — Cloudflare 대시보드에서 DNS 만 바꾸기
dash.cloudflare.com → lets1414.com → DNS → Records

- Workers 커스텀 도메인 레코드를 지우고, 아래 둘을 다시 만든다 (둘 다 **DNS only**, 회색 구름)

| Type  | Name         | Content              |
|-------|--------------|----------------------|
| A     | lets1414.com | 76.76.21.21          |
| CNAME | www          | cname.vercel-dns.com |

## 2) 코드 쪽 (급하지 않다)
- wrangler.jsonc 의 "routes" 를 지우고 `npx wrangler deploy`
  → 커스텀 도메인이 떨어지고 lets1414.lets1414.workers.dev 만 남는다

## 참고
- 네임서버는 가비아 → Cloudflare(bjorn/holly.ns.cloudflare.com) 로 이미 옮겼다.
  되돌릴 때 네임서버까지 건드릴 필요는 없다 (Cloudflare 안에서 DNS 만 바꾸면 된다)
- 옛 네임서버(필요할 때만): ns.gabia.co.kr / ns1.gabia.co.kr / ns.gabia.net
- Vercel 운영 배포는 그대로 살아 있다. 같은 Neon DB 를 보므로 데이터는 한 곳이다
- R2 는 Vercel 에서도 그대로 쓴다 (환경변수가 양쪽에 다 있다)
