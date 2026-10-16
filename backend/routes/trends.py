"""[담당 D] 대시보드 페이지 + 일반 사용자용 통계 API
화면:  GET /dashboard          → templates/dashboard.html
       (공무원이면 같은 페이지 아래에 공무원용 대시보드가 추가로 들어감)
API:   GET /api/trends?days=7  → 누구나 볼 수 있는 집계
"""
from flask import Blueprint, render_template, request, session, redirect, url_for
from db import get_conn
from routes.common import ok

bp = Blueprint("trends", __name__)

ALLOWED_DAYS = (7, 30, 90)

# 지역 이름: '대산면 춘산리'처럼 상위 지역 이름 + 자기 이름
REGION_NAME = "CONCAT_WS(' ', p.name, r.name)"


def get_days():
    """?days= 값을 7/30/90 중 하나로 제한 (그 외 값은 7)"""
    try:
        days = int(request.args.get("days", 7))
    except ValueError:
        days = 7
    return days if days in ALLOWED_DAYS else 7


@bp.get("/dashboard")
def dashboard():
    official_region = None
    if session.get("role") == "official" and session.get("region_code"):
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT name FROM region WHERE region_code = %s", (session["region_code"],))
            row = cur.fetchone()
            official_region = row["name"] if row else None
    sigungu_options = []                        # 관리자: 볼 시군을 고르는 목록
    if session.get("role") == "admin":
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT region_code, name FROM region WHERE `level` = 'sigungu' ORDER BY name")
            sigungu_options = cur.fetchall()
    return render_template("dashboard.html", official_region=official_region,
                           sigungu_options=sigungu_options)


@bp.get("/trends")
def trends_page():
    """예전 주소 호환용: /trends 로 와도 /dashboard 로 보냄
    (기존 base.html 이 url_for('trends.trends_page') 를 쓰고 있어서 이름을 유지)"""
    return redirect(url_for("trends.dashboard"))


@bp.get("/api/trends")
def trends_data():
    days = get_days()
    since = "e.created_at >= NOW() - INTERVAL %s DAY"

    with get_conn() as conn, conn.cursor() as cur:
        # 1) 요약 숫자
        cur.execute(f"""
            SELECT SUM(e.event_type IN ('view_region','view_house')) AS views,
                   SUM(e.event_type = 'save')                        AS saves,
                   COUNT(DISTINCT CASE WHEN r.`level` IN ('ri','emd')
                                       THEN e.region_code END)       AS regions
            FROM interest_event e
            JOIN region r ON r.region_code = e.region_code
            WHERE {since}""", (days,))
        summary = {k: int(v or 0) for k, v in cur.fetchone().items()}

        cur.execute(f"""
            SELECT SUM(e.event_type IN ('view_region','view_house')) AS views,
                   SUM(e.event_type = 'save')                        AS saves,
                   COUNT(DISTINCT CASE WHEN r.`level` IN ('ri','emd')
                                       THEN e.region_code END)       AS regions
            FROM interest_event e
            JOIN region r ON r.region_code = e.region_code
            WHERE {since}""", (days,))

        # 2) 많이 본 지역 (수정사항 - 리·동 단위만. 시군 단위 '지역 보기' 기록은 제외, '전북특별자치도 고창군'이 압도적으로 많이 나옴)
        cur.execute(f"""
            SELECT e.region_code, {REGION_NAME} AS name, COUNT(*) AS count
            FROM interest_event e
            JOIN region r ON r.region_code = e.region_code
            LEFT JOIN region p ON p.region_code = r.parents_code
            WHERE {since} AND e.event_type IN ('view_region','view_house')
              AND r.`level` IN ('ri', 'emd')
            GROUP BY e.region_code ORDER BY count DESC LIMIT 5""", (days,))
        top_regions = cur.fetchall()

        # 3) 많이 본 빈집
        cur.execute(f"""
            SELECT v.house_id, v.main_use, v.grade_code, {REGION_NAME} AS region_name, COUNT(*) AS count
            FROM interest_event e
            JOIN vacant_house v ON v.house_id = e.house_id
            JOIN region r ON r.region_code = v.region_code
            LEFT JOIN region p ON p.region_code = r.parents_code
            WHERE {since} AND e.event_type = 'view_house'
            GROUP BY v.house_id ORDER BY count DESC LIMIT 5""", (days,))
        top_houses = cur.fetchall()

        # 4) 지금 많이 찜된 빈집 (현재 상태 = saved_house)
        cur.execute(f"""
            SELECT v.house_id, v.main_use, v.grade_code, {REGION_NAME} AS region_name, COUNT(*) AS count
            FROM saved_house s
            JOIN vacant_house v ON v.house_id = s.house_id
            JOIN region r ON r.region_code = v.region_code
            LEFT JOIN region p ON p.region_code = r.parents_code
            GROUP BY v.house_id ORDER BY count DESC LIMIT 5""")
        top_saved = cur.fetchall()

        # 5) 많이 고른 희망업종 (현재 찜 기준)
        cur.execute("""
            SELECT i.industry_code, i.name, COUNT(*) AS count
            FROM saved_house_industry si JOIN industry i ON i.industry_code = si.industry_code
            GROUP BY i.industry_code ORDER BY count DESC LIMIT 5""")
        top_industries = cur.fetchall()

    return ok({"days": days, "summary": summary, "top_regions": top_regions,
               "top_houses": top_houses, "top_saved": top_saved, "top_industries": top_industries})
