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
  } else if (process.env.DB_NO_POOL === '1') {
    // Workers 로 로컬 테스트할 때. Workers 는 요청끼리 TCP 연결을 나눠 쓸 수 없어서
    // 풀을 두면 두 번째 요청이 멈춘다. 느리지만 쿼리마다 새로 연결한다.
    // 운영은 Neon(HTTP)이라 이 길로 오지 않는다.
    const { default: pg } = await import('pg');
    impl = async (text, params) => {
      const c = new pg.Client({ connectionString: u });
      await c.connect();
      try { return (await c.query(text, params || [])).rows; }
      finally { try { await c.end(); } catch (e) {} }
    };
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
