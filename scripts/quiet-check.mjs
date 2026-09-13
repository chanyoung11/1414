// 조용한 시간 계산 확인 (테스트에서 부른다)
import { inQuietHours } from '../lib/push.js';
const at = h => new Date(Date.UTC(2026, 8, 13, (h - 9 + 24) % 24, 0, 0));   // KST h시
const bad = [];
for (const [h, w] of [[23,true],[2,true],[7,true],[8,false],[12,false],[21,false],[22,true]])
  if (inQuietHours({}, at(h)) !== w) bad.push(`${h}시 want ${w}`);
if (inQuietHours({ quiet: { on: false } }, at(2)) !== false) bad.push('꺼도 조용함');
if (inQuietHours({ quiet: { on: true, from: 23, to: 6 } }, at(4)) !== true) bad.push('23~06 04시');
if (inQuietHours({ quiet: { on: true, from: 23, to: 6 } }, at(7)) !== false) bad.push('23~06 07시');
console.log(bad.length ? 'BAD ' + bad.join(' / ') : 'OK');
