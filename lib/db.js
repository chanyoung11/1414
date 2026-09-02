// DB 접근 한 곳. Neon(운영)이면 @neondatabase/serverless(HTTP), 그 외(로컬 Docker Postgres 등)는 pg.
// 사용: const rows = await q('select * from users where id=$1', [id])

let impl = null;

function url() {
  const u = process.env.DATABASE_URL || process.env.POSTGRES_URL;
  if (!u) throw new Error('DATABASE_URL이 없습니다');
  return u;
}

async function init() {
  if (impl) return impl;
  const u = url();
  if (/neon\.tech/.test(u)) {
    const { neon } = await import('@neondatabase/serverless');
    const sql = neon(u);
    impl = (text, params) => sql.query(text, params || []);
  } else {
    const { default: pg } = await import('pg');
    const pool = new pg.Pool({ connectionString: u, max: 3 });
    impl = async (text, params) => (await pool.query(text, params || [])).rows;
  }
  return impl;
}

export async function q(text, params) {
  const f = await init();
  return f(text, params);
}

export async function one(text, params) {
  const rows = await q(text, params);
  return rows[0] || null;
}
