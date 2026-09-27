# 이름 규칙: 날짜 이름에 이미 그 날짜가 있으면 {월}/{일} 과 겹치지 않는다 ('10/7 10/7 특별예배' → '10/7 특별예배')
# 서버 fmtName·dropMd 와 앱 fmtNameC·dropMdC 를 떼어 node 로 같은 경우를 돌린다 (두 쪽이 같은 답을 내야 한다)
import json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = r'''
const fs=require('fs');const h=fs.readFileSync(process.argv[1]+'/app/index.html','utf8');const a=fs.readFileSync(process.argv[1]+'/api/index.js','utf8');
const g=(src,re)=>{const m=src.match(re);if(!m)throw new Error('못 찾음 '+re);return m[0]};
const today=()=>'2026-10-07';const WDK=['일','월','화','수','목','금','토'];const WD=WDK;const DEF_SETTINGS={nameRule:'{월}/{일} {이름}'};
eval(g(h,/function dropMdC[^\n]*/)+'\n'+g(h,/function fmtNameC[^\n]*/));
eval(g(a,/const dropMd = [\s\S]*?trim\(\);/).replace('const dropMd','var dropMd')+'\n'+g(a,/function fmtName\([\s\S]*?\n}/));
const cases=JSON.parse(process.argv[2]);
console.log(JSON.stringify(cases.map(c=>[fmtNameC(c[0],c[1],c[2]),fmtName(c[0],c[1],c[2])])));
'''
CASES = [
    ('{월}/{일} {이름}', '2026-10-07', '10/7 특별예배', '10/7 특별예배'),
    ('{월}/{일} {이름}', '2026-10-07', '특별예배', '10/7 특별예배'),
    ('{월}/{일} {이름}', '2026-10-07', '10/70 행사', '10/7 10/70 행사'),
    ('{월}월 {일}일 {이름}', '2026-10-07', '10월 7일 특별예배', '10월 7일 특별예배'),
    ('{이름} ({월}/{일})', '2026-10-07', '특별예배 (10/7)', '특별예배 (10/7)'),
    ('{이름}', '2026-10-07', '10/7 특별예배', '10/7 특별예배'),
    ('{월}/{일} {이름}', '2026-10-07', '10.7 기도회', '10/7 기도회'),
    ('{월}/{일} {요일} {이름}', '2026-10-04', '주일 오전예배', '10/4 일 주일 오전예배'),
]
out = json.loads(subprocess.check_output(['node', '-e', JS, ROOT, json.dumps([c[:3] for c in CASES])], text=True))
bad = [(c, o) for c, o in zip(CASES, out) if o[0] != c[3] or o[1] != c[3]]
if bad:
    for c, o in bad: print('FAIL:', c[:3], '기대', repr(c[3]), '앱', repr(o[0]), '서버', repr(o[1]))
    sys.exit(1)
print('OK test_name_rule — 날짜 이름 겹침 없음 (%d 경우, 앱·서버 같음)' % len(CASES))
