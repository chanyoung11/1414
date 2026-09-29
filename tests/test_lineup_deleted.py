# 편성에 지운 예배만 보이고 지금 예배는 안 보이던 것 (운영 제보 2026-09-30, 웹)
#
# 편성(표·폰 카드·그날 편성 패널·달력)과 편성 알림은 사역 날짜 줄(service_dates)의 이름(label)을 썼다.
# 그 이름은 줄을 만들 때 한 번 정해지고 콘티를 바꾸거나 지워도 그대로다. 그래서
#  A  (운영 그대로) 9/17 전 코드는 콘티 때문에 생긴 날짜도 '인도자가 연 날짜(manual)'로 적었다 → 그 콘티를 지우면 날짜가
#     남고, 같은 날 새 콘티('개회예배')를 만들면 그 줄을 잡아 편성에 지운 콘티 이름('11/21 LIKE MT 저녁집회')이 떴다.
#     날짜를 옮긴 콘티의 옛 줄('예배')도 콘티 없이 남아 편성에 보였고, 자동 생성 기간에 들어오면 빈 초안으로 되살아났다
#  B  (지금 코드) 콘티 이름을 바꾸면('저녁집회'→'개회예배') 줄 이름은 옛 이름 → 같은 날 '저녁집회'를 새로 만들면
#     (팀·날짜·이름)이 겹쳐 새 콘티는 줄을 못 얻어 편성 어디에도 안 보였다. 이름 없는 콘티 둘도 둘째가 안 보였다
#  C  인도자가 연 날짜에서 콘티를 지우고 새 콘티를 만들면 편성에는 새 콘티 이름이 아니라 날짜 이름이 보였다
# 고친 뒤: 콘티가 있는 날짜는 그 콘티의 지금 이름으로 보이고, 콘티마다 줄이 하나씩 있으며, 지운 콘티 몫 날짜는 사라진다.
# 인도자가 직접 연 날짜는 콘티를 지워도 그 날짜의 이름으로 남는다.
# 실행: CONTI_URL=http://localhost:9910/ CONTI_DB=postgres://postgres@localhost:55110/postgres .venv/bin/python tests/test_lineup_deleted.py
import os, sys, time, datetime, shutil, subprocess
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
DB = os.environ.get('CONTI_DB', 'postgres://postgres:pg@localhost:54329/postgres')
tag = str(int(time.time() * 1000))[-8:]
H = {'x-conti': '1'}
def fail(m): print('FAIL:', m); sys.exit(1)

def sql(s):
    if shutil.which('psql'): cmd = ['psql', DB, '-tAc', s]
    else: cmd = ['docker', 'exec', 'conti-pg', 'psql', '-U', 'postgres', '-tAc', s]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: raise RuntimeError('psql: ' + r.stderr.strip()[:300])
    return r.stdout.strip()

KST_TODAY = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=9)).date()
def day(n): return (KST_TODAY + datetime.timedelta(days=n)).isoformat()
def md(iso): y, m, d = iso.split('-'); return '%d/%d' % (int(m), int(d))
# 9/17 전 코드가 만든 줄을 흉내 낸다. 그 줄을 고치는 근거(인도자가 열었으면 남는 date.opened 알림)는
# 알림을 90일 뒤 지우므로 줄이 생긴 지 85일 안에만 쓴다 → 그 뒤로는 A 의 옛 줄 검사를 건너뛴다
LEGACY_OK = datetime.datetime.now(datetime.timezone.utc) < datetime.datetime(2026, 9, 9, tzinfo=datetime.timezone.utc) + datetime.timedelta(days=84)

D, D_ORPHAN_FAR, D_ORPHAN_NEAR, D_OPENED = day(20), day(45), day(15), day(40)
D_B, D_B2, D_C = day(34), day(36), day(38)

def run():
    with sync_playwright() as p:
        b = p.chromium.launch(); errs = []
        L = b.new_context(viewport={'width': 1280, 'height': 800}); R = L.request

        def ok(r, what):
            if not r.ok: fail('%s → %s %s' % (what, r.status, r.text()[:200]))
            return r.json()
        def signup(ctx, name, un):
            return ok(ctx.request.post(URL + 'api/auth/signup', headers=H, data={'username': un, 'password': 'secret1', 'name': name}), 'signup')['user']['id']
        signup(L, '하은', 'ldl' + tag)
        t = ok(R.post(URL + 'api/teams', headers=H, data={'name': 'LIKE ' + tag, 'myName': '하은', 'session': '건반'}), 'team')
        tid, inv = t['teamId'], t['invite']
        M1 = b.new_context(); M2 = b.new_context()
        m1 = signup(M1, '영서', 'ldm1' + tag); signup(M2, '유나', 'ldm2' + tag)
        ok(M1.request.post(URL + 'api/invite/%s/join' % inv, headers=H, data={'name': '영서', 'sessions': ['건반']}), 'join1')
        ok(M2.request.post(URL + 'api/invite/%s/join' % inv, headers=H, data={'name': '유나', 'sessions': ['싱어']}), 'join2')

        def draft(sid, name, date):
            ok(R.put(URL + 'api/services/%s/draft' % sid, headers=H, data={'teamId': tid, 'doc': {'id': sid, 'name': name, 'date': date, 'items': [], 'version': 0, 'editedAt': int(time.time() * 1000)}}), 'draft ' + sid)
        def delete(sid):
            ok(R.delete(URL + 'api/services/%s?team=%s' % (sid, tid), headers=H), 'delete ' + sid)
        def sched():
            return ok(R.get(URL + 'api/teams/%s/schedule?from=%s&to=%s' % (tid, day(-3), day(60)), headers=H), 'schedule')['dates']
        def on(date, rows=None): return [x for x in (rows if rows is not None else sched()) if x['date'] == date]

        # ---- A: 운영 LIKE 팀 그대로 (9/17 전 코드가 만든 줄 = source manual, 알림 없음) ----
        if LEGACY_OK:
            sql("update members set created_at='2026-09-01' where team_id='%s'" % tid)
            X, Y, Z = 'ldx' + tag, 'ldy' + tag, 'ldz' + tag
            draft(X, '%s LIKE MT 저녁집회' % md(D), D)
            sql("update service_dates set source='manual', created_at='2026-09-09 10:36+00' where team_id='%s' and service_id='%s'" % (tid, X))
            delete(X)   # 옛 줄은 '인도자가 연 날짜'로 알고 남긴다
            draft(Y, '26 하반기 LIKE MT 개회예배', D)   # 남은 줄을 잡는다 (줄 이름은 지운 콘티 이름)
            draft(Z, '26 하반기 LIKE MT 저녁집회', D)
            sql("update service_dates set source='manual', created_at='2026-09-14 15:15+00' where team_id='%s' and service_id='%s'" % (tid, Z))
            # 날짜를 옮긴 콘티가 남긴 옛 줄 (콘티 없음) — 하나는 자동 생성 기간 밖(운영 11/25), 하나는 안
            for d0 in (D_ORPHAN_FAR, D_ORPHAN_NEAR):
                sql("insert into service_dates(team_id, date, label, source, open, created_at) values('%s','%s','예배','manual',true,'2026-09-14 15:09+00')" % (tid, d0))
            # 대조: 같은 때 인도자가 정말로 연 날짜 (멤버에게 date.opened 알림이 갔다) → 남아야 한다
            ok(R.post(URL + 'api/teams/%s/dates' % tid, headers=H, data={'date': D_OPENED, 'label': '수련회'}), 'open date')
            sql("update service_dates set created_at='2026-09-10 00:00+00' where team_id='%s' and date='%s'" % (tid, D_OPENED))
        else:
            print('SKIP A — 옛 줄을 고칠 근거(알림)가 지워진 뒤라 건너뜀')

        # ---- B: 지금 코드 — 이름을 바꾼 콘티와 같은 이름의 새 콘티, 이름 없는 콘티 둘 ----
        P, Q, U1, U2 = 'ldp' + tag, 'ldq' + tag, 'ldu1' + tag, 'ldu2' + tag
        draft(P, '저녁집회', D_B); draft(P, '개회예배', D_B)
        draft(Q, '저녁집회', D_B)
        draft(U1, '', D_B2); draft(U2, '', D_B2)

        # ---- C: 인도자가 연 날짜 — 콘티를 지우고 같은 날 새 콘티 ----
        Rs, S = 'ldr' + tag, 'lds' + tag
        ok(R.post(URL + 'api/teams/%s/dates' % tid, headers=H, data={'date': D_C, 'label': '청년예배'}), 'open C')
        draft(Rs, 'LIKE 저녁', D_C); delete(Rs); draft(S, '개회예배', D_C)

        # 인도자가 앱을 연다 (GET /services 가 자동 초안을 만들고, 편성은 GET /schedule)
        pg = L.new_page(); pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
        pg.goto(URL); pg.wait_for_selector('.shell[data-page]', timeout=10000); pg.wait_for_timeout(1500)

        rows = sched()
        print('편성 줄:', [(x['date'][5:], x['label'], (x['serviceId'] or '')[-6:]) for x in rows])
        by_svc = {}
        for x in rows:
            if x.get('serviceId'): by_svc.setdefault(x['serviceId'], []).append(x)
        def one_row(sid, name):
            got = by_svc.get(sid, [])
            if len(got) != 1: fail('콘티 %s(%s)의 편성 줄이 %d개: %s' % (sid, name, len(got), got))
            if got[0]['label'] != name: fail('콘티 %s 는 편성에 "%s"로 보여야 하는데 "%s"' % (sid, name, got[0]['label']))
            return got[0]

        if LEGACY_OK:
            labels = sorted(x['label'] for x in on(D, rows))
            if labels != ['26 하반기 LIKE MT 개회예배', '26 하반기 LIKE MT 저녁집회']:
                fail('%s 편성에 지운 콘티 이름이 보이거나 지금 콘티가 안 보임: %s' % (D, labels))
            yrow = one_row(Y, '26 하반기 LIKE MT 개회예배'); one_row(Z, '26 하반기 LIKE MT 저녁집회')
            if on(D_ORPHAN_FAR, rows): fail('콘티가 떠난 옛 줄(%s 예배)이 편성에 남음: %s' % (D_ORPHAN_FAR, on(D_ORPHAN_FAR, rows)))
            if on(D_ORPHAN_NEAR, rows): fail('콘티가 떠난 옛 줄이 자동 초안으로 되살아남(%s): %s' % (D_ORPHAN_NEAR, on(D_ORPHAN_NEAR, rows)))
            ok(R.get(URL + 'api/services?team=' + tid, headers=H), 'services')   # 자동 초안을 한 번 더 돌린다
            if sql("select count(*) from drafts where team_id='%s' and doc->>'date'='%s'" % (tid, D_ORPHAN_NEAR)) != '0':
                fail('콘티가 떠난 옛 날짜(%s)에 빈 초안이 되살아남' % D_ORPHAN_NEAR)
            opened = on(D_OPENED, rows)
            if len(opened) != 1 or opened[0]['source'] != 'manual': fail('인도자가 연 날짜가 사라지거나 바뀜: %s' % opened)
            if opened[0]['label'] != '수련회': fail('인도자가 연 날짜 이름이 바뀜: %s' % opened)
            # 옛 줄이 이제 콘티 몫 → 개회예배를 지우면 그 날짜도 같이 사라진다 (지운 콘티 이름으로 다시 뜨지 않는다)
            if sql("select source from service_dates where team_id='%s' and service_id='%s'" % (tid, Y)) != 'service':
                fail('옛 코드가 만든 콘티 몫 날짜가 그대로 manual')
            print('A ok — 지운 콘티 이름·옛 줄이 사라지고 지금 콘티가 이름대로 보임')

        one_row(P, '개회예배'); one_row(Q, '저녁집회')
        u = [one_row(U1, '예배'), by_svc.get(U2, [None])[0]]
        if not u[1] or len(by_svc.get(U2, [])) != 1: fail('같은 날 이름 없는 둘째 콘티가 편성에 안 보임: %s' % on(D_B2, rows))
        print('B ok — 이름을 바꾼 콘티와 같은 이름의 새 콘티가 둘 다 보임:', [x['label'] for x in on(D_B, rows)], [x['label'] for x in on(D_B2, rows)])
        crow = one_row(S, '개회예배')
        print('C ok — 인도자가 연 날짜의 새 콘티 이름:', crow['label'])

        # 팀 설정의 날짜 목록도 같은 이름
        dl = ok(R.get(URL + 'api/teams/%s/dates' % tid, headers=H), 'dates')['dates']
        for sid, name in [(P, '개회예배'), (Q, '저녁집회'), (S, '개회예배')] + ([(Y, '26 하반기 LIKE MT 개회예배')] if LEGACY_OK else []):
            got = [x['label'] for x in dl if x.get('serviceId') == sid]
            if got != [name]: fail('팀 설정 날짜 목록에서 %s 이 %s' % (name, got))

        # 편성 통보·카톡 문구도 지금 콘티 이름으로
        target = yrow if LEGACY_OK else by_svc[P][0]
        want = '26 하반기 LIKE MT 개회예배' if LEGACY_OK else '개회예배'
        ok(R.put(URL + 'api/teams/%s/dates/%s/lineup' % (tid, target['id']), headers=H, data={'lineup': [{'session': '건반', 'memberId': m1}]}), 'lineup')
        ok(R.post(URL + 'api/teams/%s/dates/%s/notify' % (tid, target['id']), headers=H, data={}), 'notify')
        ns = ok(M1.request.get(URL + 'api/notifications?team=' + tid, headers=H), 'notis')['notifications']
        nt = [n['title'] for n in ns if n['type'] == 'lineup.notify' and n['targetId'] == target['id']]
        if not nt or want not in nt[0]: fail('편성 통보 제목에 지금 콘티 이름이 없음: %s' % nt)
        txt = ok(R.get(URL + 'api/teams/%s/dates/%s/text' % (tid, target['id']), headers=H), 'text')['text']
        if want not in txt: fail('카톡 문구에 지금 콘티 이름이 없음: %s' % txt)
        print('통보·카톡 ok:', nt[0], '|', txt.splitlines()[0])

        # ---- 화면: 데스크톱 1280x800 편성 표 ----
        pg.goto(URL + '#/sched'); pg.wait_for_selector('.schtab', timeout=10000); pg.wait_for_timeout(1200)
        heads = pg.evaluate("""[...document.querySelectorAll('.schtab .dcol')].map(e=>({t:e.getAttribute('title')||'',s:(e.querySelector('small')||{}).innerText||'',id:e.dataset.id}))""")
        titles = [h['t'] for h in heads]
        print('표 머리글:', [(h['t'].split(' — ')[0], h['s']) for h in heads])
        need = ['개회예배', '저녁집회'] + (['26 하반기 LIKE MT 개회예배', '26 하반기 LIKE MT 저녁집회', '수련회'] if LEGACY_OK else [])
        for n in need:
            if not any(x.startswith(n + ' — ') for x in titles): fail('편성 표에 "%s"가 안 보임: %s' % (n, titles))
        if LEGACY_OK:
            if any(x.startswith('%s LIKE MT 저녁집회' % md(D)) or x.startswith('LIKE MT 저녁집회') for x in titles): fail('편성 표에 지운 콘티 이름: %s' % titles)
            same = [h['s'] for h in heads if h['id'] in (by_svc[Y][0]['id'], by_svc[Z][0]['id'])]
            if len(same) != 2 or same[0] == same[1]: fail('같은 날 두 예배의 머리글이 똑같아 구분이 안 됨: %s' % same)
            pg.click('.schtab .dcol[data-id="%s"]' % by_svc[Y][0]['id']); pg.wait_for_selector('.lnpanel', timeout=6000); pg.wait_for_timeout(400)
            hd = pg.locator('.lnhd b').first.inner_text()
            if '26 하반기 LIKE MT 개회예배' not in hd: fail('그날 편성 패널 제목이 지금 콘티가 아님: %s' % hd)
            print('패널 제목 ok:', hd)
        pg.screenshot(path=os.environ.get('SHOT_DIR', '/tmp') + '/lineup_deleted_desktop.png')

        # ---- 화면: 폰 390x844 편성 카드 ----
        ph = b.new_context(viewport={'width': 390, 'height': 844}, storage_state=L.storage_state(), is_mobile=True, has_touch=True)
        pp = ph.new_page(); pp.on('pageerror', lambda e: errs.append(str(e)))
        pp.goto(URL + '#/sched'); pp.wait_for_selector('.schlist .schrow', timeout=10000); pp.wait_for_timeout(1000)
        cards = pp.evaluate("""[...document.querySelectorAll('.schlist .schrow')].map(e=>({d:e.querySelector('.d b').innerText,n:e.querySelector('.grow b').innerText}))""")
        print('폰 카드:', [(c['d'], c['n']) for c in cards])
        names = [c['n'] for c in cards]
        for n in need:
            if n not in names: fail('폰 편성 카드에 "%s"가 안 보임: %s' % (n, names))
        if LEGACY_OK:
            if any('LIKE MT 저녁집회' in n and not n.startswith('26 ') for n in names): fail('폰 편성 카드에 지운 콘티 이름: %s' % names)
            if any(c['d'] in (md(D_ORPHAN_FAR), md(D_ORPHAN_NEAR)) for c in cards): fail('폰 편성 카드에 콘티가 떠난 옛 날짜: %s' % cards)
        pp.screenshot(path=os.environ.get('SHOT_DIR', '/tmp') + '/lineup_deleted_phone.png', full_page=True)

        # 인도자가 연 날짜에서 콘티를 지우면 날짜는 남되(설계) 지운 콘티 이름이 아니라 날짜 이름으로 돌아간다
        delete(S)
        cr = on(D_C)
        if len(cr) != 1 or cr[0]['label'] != '청년예배' or cr[0]['serviceId'] or cr[0]['source'] != 'manual':
            fail('인도자가 연 날짜에서 콘티를 지운 뒤: %s' % cr)
        print('C2 ok — 콘티를 지운 뒤 인도자가 연 날짜는 제 이름으로 남음')

        # 자동 초안(이름 규칙으로 날짜 이름에서 만든 이름)은 전처럼 날짜 이름으로 보인다 — 규칙에 요일이 있어도
        ok(R.patch(URL + 'api/teams/%s/settings' % tid, headers=H, data={'nameRule': '{이름} ({요일})'}), 'rule')
        D_AUTO = day(12)
        ok(R.post(URL + 'api/teams/%s/dates' % tid, headers=H, data={'date': D_AUTO, 'label': '주일 2부'}), 'open auto')
        ok(R.get(URL + 'api/services?team=' + tid, headers=H), 'services')
        ar = on(D_AUTO)
        if len(ar) != 1 or not ar[0]['serviceId'] or ar[0]['label'] != '주일 2부': fail('자동 초안 날짜 이름이 바뀜: %s' % ar)
        print('D ok — 자동 초안은 날짜 이름 그대로:', ar[0]['label'])

        if errs: fail('콘솔 오류: ' + errs[0])
        print('OK — 편성에 지금 예배가 이름대로 보이고, 지운 예배는 안 보인다')
        b.close()

run()
