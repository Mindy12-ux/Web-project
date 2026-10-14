"""[담당 D] 공무원용 통계 API — 화면은 /dashboard 아래쪽에 함께 표시
모든 쿼리는 공무원 소속 시군(session["region_code"]의 앞 5자리)으로 제한합니다.
회원 단위 정보는 share_consent(지자체 정보 제공 동의)가 TRUE인 회원만, 닉네임으로 보여 줍니다.
"""
from datetime import date, timedelta
from functools import wraps
from flask import Blueprint, session, redirect, url_for, request
from db import get_conn
from routes.auth import login_required
from routes.common import ok, fail
from routes.trends import get_days, REGION_NAME

bp = Blueprint("admin", __name__)


STAFF_ROLES = ("official", "admin")


def staff_required(view):
    """공무원 또는 관리자만. (A의 official_required 는 공무원만 통과시켜서 D가 따로 만듦)"""
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if session.get("role") not in STAFF_ROLES:
            return fail("공무원·관리자만 볼 수 있습니다", 403)
        return view(*args, **kwargs)
    return wrapper


def my_sigungu():
    """집계할 시군구 5자리 (예: '52790'). 없으면 None
    - 공무원: 자기 소속 시군 (session["region_code"]) — 다른 시군은 볼 수 없음
    - 관리자: 화면에서 고른 시군 (?sigungu=52790)"""
    if session.get("role") == "admin":
        code = request.args.get("sigungu", "")[:5]
        return code if len(code) == 5 and code.isdigit() else None
    code = session.get("region_code")
    return code[:5] if code else None


@bp.get("/admin/dashboard")
def dashboard():
    """예전 주소 호환용: /admin/dashboard 로 와도 /dashboard 로 보냄
    (기존 base.html 이 url_for('admin.dashboard') 를 쓰고 있어서 이름을 유지)"""
    return redirect(url_for("trends.dashboard"))


@bp.get("/api/admin/stats")
@staff_required
def admin_stats():
    sgg = my_sigungu()
    if not sgg:
        return fail("집계할 시군이 없습니다 (공무원은 소속 시군 설정, 관리자는 시군 선택 필요)", 403)
    days = get_days()
    scope = "LEFT(e.region_code, 5) = %s AND e.created_at >= NOW() - INTERVAL %s DAY"

    with get_conn() as conn, conn.cursor() as cur:
        # 1) 날짜별 조회·찜 추이 (빈 날짜도 0으로 채움)
        cur.execute(f"""
            SELECT DATE(e.created_at) AS d,
                   SUM(e.event_type IN ('view_region','view_house')) AS views,
                   SUM(e.event_type = 'save') AS saves
            FROM interest_event e WHERE {scope}
            GROUP BY d""", (sgg, days))
        by_day = {r["d"]: r for r in cur.fetchall()}
        today = date.today()
        daily = []
        for i in range(days - 1, -1, -1):
            d = today - timedelta(days=i)
            r = by_day.get(d, {})
            daily.append({"date": d.isoformat(), "views": int(r.get("views") or 0),
                          "saves": int(r.get("saves") or 0)})

        # 2) 찜한 시간대 분포 (0~23시)
        cur.execute(f"""
            SELECT HOUR(e.created_at) AS h, COUNT(*) AS n
            FROM interest_event e WHERE {scope} AND e.event_type = 'save'
            GROUP BY h""", (sgg, days))
        hours = [0] * 24
        for r in cur.fetchall():
            hours[r["h"]] = r["n"]

        # 3) 빈집별 관심 (기간 내 조회·찜 + 현재 찜 수)
        cur.execute(f"""
            SELECT v.house_id, v.main_use, v.grade_code, {REGION_NAME} AS region_name,
                   SUM(e.event_type = 'view_house') AS views,
                   SUM(e.event_type = 'save')       AS saves,
                   (SELECT COUNT(*) FROM saved_house s WHERE s.house_id = v.house_id) AS saved_now
            FROM vacant_house v
            JOIN region r ON r.region_code = v.region_code
            LEFT JOIN region p ON p.region_code = r.parents_code
            LEFT JOIN interest_event e
                   ON e.house_id = v.house_id AND e.created_at >= NOW() - INTERVAL %s DAY
            WHERE LEFT(v.region_code, 5) = %s
            GROUP BY v.house_id
            HAVING views > 0 OR saved_now > 0
            ORDER BY saved_now DESC, saves DESC, views DESC
            LIMIT 10""", (days, sgg))
        houses = cur.fetchall()

        # 4) 이 시군 빈집에 걸린 희망업종 (현재 찜 기준)
        cur.execute("""
            SELECT i.name, COUNT(*) AS count
            FROM saved_house_industry si
            JOIN industry i      ON i.industry_code = si.industry_code
            JOIN vacant_house v  ON v.house_id = si.house_id
            WHERE LEFT(v.region_code, 5) = %s
            GROUP BY i.industry_code ORDER BY count DESC""", (sgg,))
        industries = cur.fetchall()

        # 5) 회원 활동 — 동의한 회원만 이름(닉네임) 공개, 나머지는 인원수만
        cur.execute(f"""
            SELECT m.member_id, m.nickname,
                   COUNT(*) AS events,
                   SUM(e.event_type = 'save') AS saves,
                   MAX(e.created_at) AS last_at
            FROM interest_event e JOIN member m ON m.member_id = e.member_id
            WHERE {scope} AND m.share_consent = TRUE
            GROUP BY m.member_id ORDER BY last_at DESC LIMIT 20""", (sgg, days))
        members = cur.fetchall()
        cur.execute(f"""
            SELECT COUNT(DISTINCT e.member_id) AS n
            FROM interest_event e JOIN member m ON m.member_id = e.member_id
            WHERE {scope} AND m.share_consent = FALSE""", (sgg, days))
        hidden_members = cur.fetchone()["n"]

    for d in (houses + members):                       # Decimal/datetime → JSON 친화 값
        for k in ("views", "saves", "events"):
            if k in d:
                d[k] = int(d[k] or 0)
        if "last_at" in d:
            d["last_at"] = d["last_at"].strftime("%Y-%m-%d %H:%M")

    return ok({"days": days, "sigungu": sgg, "daily": daily, "hours": hours, "houses": houses,
               "industries": industries, "members": members, "hidden_members": hidden_members})


@bp.get("/api/admin/members/<member_id>")
@staff_required
def admin_member(member_id):
    sgg = my_sigungu()
    if not sgg:
        return fail("집계할 시군이 없습니다", 403)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT nickname, share_consent FROM member WHERE member_id = %s", (member_id,))
        m = cur.fetchone()
        if not m or not m["share_consent"]:
            return fail("정보 제공에 동의한 회원만 볼 수 있습니다", 404)

        cur.execute(f"""
            SELECT e.created_at, e.event_type, e.house_id, {REGION_NAME} AS region_name, i.name AS industry
            FROM interest_event e
            JOIN region r ON r.region_code = e.region_code
            LEFT JOIN region p ON p.region_code = r.parents_code
            LEFT JOIN industry i ON i.industry_code = e.industry_code
            WHERE e.member_id = %s AND LEFT(e.region_code, 5) = %s
            ORDER BY e.created_at DESC LIMIT 30""", (member_id, sgg))
        events = cur.fetchall()
    for e in events:
        e["created_at"] = e["created_at"].strftime("%Y-%m-%d %H:%M")
    return ok({"nickname": m["nickname"], "events": events})   # 메모·선호도는 개인 기록이라 제외


# ---------------------------------------------------------------
# [개발용 임시] 로그인 기능(A)이 완성되기 전, 가짜 계정으로 로그인한 것처럼 만들기
# 사용: http://127.0.0.1:5000/dev/login-as/seed_official
# --debug 로 실행했을 때만 작동. A의 로그인이 완성되면 이 함수는 지우세요.
# ---------------------------------------------------------------
from flask import current_app, abort  # noqa: E402


@bp.get("/dev/login-as/<member_id>")
def dev_login_as(member_id):
    if not current_app.debug:
        abort(404)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT member_id, nickname, role, region_code FROM member WHERE member_id = %s",
                    (member_id,))
        m = cur.fetchone()
    if not m:
        return fail(f"{member_id} 회원이 없습니다. scripts/seed_events.py 를 먼저 실행하세요", 404)
    session.clear()
    session.update(m)            # member_id, nickname, role, region_code (A가 만들 로그인과 같은 키)
    return redirect(url_for("trends.dashboard"))
