// db/schema.sql 적용. 사용: DATABASE_URL=... npm run db:migrate
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import pg from 'pg';

const url = process.env.DATABASE_URL || process.env.POSTGRES_URL;
if (!url) { console.error('DATABASE_URL이 없습니다'); process.exit(1); }
const sql = fs.readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'db', 'schema.sql'), 'utf8');
const client = new pg.Client({ connectionString: url, ssl: /neon\.tech|sslmode=require/.test(url) ? { rejectUnauthorized: false } : undefined });
await client.connect();
await client.query(sql);
await client.end();
console.log('schema 적용 완료');
