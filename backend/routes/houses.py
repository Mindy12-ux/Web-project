"""[담당 B] 지도 페이지, 지역·숫자 원·빈집 카드·빈집 주변 상가 API
기록: 지역 보기 view_region, 빈집 상세 view_house → events.log_event
"""
import math
from flask import Blueprint, render_template, request, session
from db import get_conn
from routes.common import ok, fail
from routes.events import log_event

bp = Blueprint("houses", __name__)

ALL_GRADES = ("1", "2", "3", "NA")
STORE_LIMIT = 300                                # 지도에 찍는 가게 최대 수 (가까운 순)

# 두 좌표 사이 거리(m). 앞의 %s 두 개는 기준 위도, 마지막 %s 는 기준 경도
DISTANCE_SQL = """6371000 * 2 * ASIN(SQRT(
    POW(SIN(RADIANS(s.latitude - %s) / 2), 2) +
    COS(RADIANS(%s)) * COS(RADIANS(s.latitude)) * POW(SIN(RADIANS(s.longitude - %s) / 2), 2)))"""


def parse_grades():
    """?grades=1,2 → ['1', '2']. 값이 없으면 전체 등급, 아는 등급 코드만 남김"""
    raw = request.args.get("grades")
    if raw is None:
        return list(ALL_GRADES)
    return [g for g in raw.split(",") if g in ALL_GRADES]


def placeholders(values):
    """IN (...) 자리표시자. 값은 항상 %s 로 넘깁니다"""
    return ",".join(["%s"] * len(values))


# ── 화면 ────────────────────────────────────────────────

@bp.get("/map")
def map_page():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT grade_code, label, description, is_default FROM grade_code ORDER BY sort_order")
        grades = cur.fetchall()
    return render_template("houses/map.html", grades=grades)


# ── API ────────────────────────────────────────────────

@bp.get("/api/regions")
def regions():
    """선택할 수 있는 시군 목록 + 빈집 수 + 지도 중심 좌표"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT r.region_code, r.name,
                CAST(r.latitude AS DOUBLE) AS lat, CAST(r.longitude AS DOUBLE) AS lng,
                COUNT(v.house_id) AS house_count
            FROM region r
            LEFT JOIN vacant_house v ON LEFT(v.region_code, 5) = LEFT(r.region_code, 5)
            WHERE r.`level` = 'sigungu'
            GROUP BY r.region_code, r.name, r.latitude, r.longitude
            ORDER BY r.name
        """)
        return ok(cur.fetchall())


@bp.get("/api/regions/<sigungu_code>/clusters")
def clusters(sigungu_code):
    """리·동별 빈집 수 + 중심 좌표 → 지도 숫자 원. ?grades=1,2"""
    grades = parse_grades()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM region WHERE region_code = %s AND `level` = 'sigungu'", (sigungu_code,))
        if not cur.fetchone():
            return fail("없는 지역입니다", 404)
        if not grades:
            return ok([])
        cur.execute(f"""
            SELECT r.region_code, r.name, p.name AS parent_name,
                CAST(r.latitude AS DOUBLE) AS lat, CAST(r.longitude AS DOUBLE) AS lng,
                COUNT(*) AS house_count
            FROM vacant_house v
            JOIN region r      ON r.region_code = v.region_code
            LEFT JOIN region p ON p.region_code = r.parents_code
            WHERE LEFT(v.region_code, 5) = LEFT(%s, 5)
            AND v.grade_code IN ({placeholders(grades)})
            AND r.latitude IS NOT NULL
            GROUP BY r.region_code, r.name, p.name, r.latitude, r.longitude
            ORDER BY house_count DESC, r.name
        """, (sigungu_code, *grades))
        rows = cur.fetchall()
    log_event("view_region", sigungu_code)
    return ok(rows)


@bp.get("/api/houses")
def houses_in_region():
    """그 리·동의 빈집 카드 목록. ?region=<리·동코드>&grades=1,2"""
    region = request.args.get("region")
    if not region:
        return fail("region이 필요합니다", 400)
    grades = parse_grades()
    if not grades:
        return ok([])
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(f"""
            SELECT v.house_id, v.region_code, v.grade_code, g.label AS grade_label,
                   v.main_use, v.built_year, CAST(v.floor_area AS DOUBLE) AS floor_area
            FROM vacant_house v
            JOIN grade_code g ON g.grade_code = v.grade_code
            WHERE v.region_code = %s AND v.grade_code IN ({placeholders(grades)})
            ORDER BY g.sort_order, v.house_id
        """, (region, *grades))
        rows = cur.fetchall()
    log_event("view_region", region)     # ← 추가: 리·동 단위 지역 보기
    return ok(rows)
    # return ok(cur.fetchall())


def find_house(cur, house_id):
    """빈집 한 채 + 리·동 중심 좌표 + 상위 지역 이름들. 없으면 None"""
    cur.execute("""
        SELECT v.house_id, v.region_code, v.grade_code,
               g.label AS grade_label, g.description AS grade_description,
               v.main_use, v.built_year, v.structure,
               CAST(v.floor_area AS DOUBLE) AS floor_area, CAST(v.land_area AS DOUBLE) AS land_area,
               v.road_contact, v.zoning, DATE_FORMAT(v.data_date, '%%Y-%%m-%%d') AS data_date,
               CAST(r.latitude AS DOUBLE) AS lat, CAST(r.longitude AS DOUBLE) AS lng,
               r.name AS r_name, r.`level` AS r_level,
               p.name AS p_name, p.`level` AS p_level,
               gp.name AS gp_name, gp.`level` AS gp_level
        FROM vacant_house v
        JOIN grade_code g   ON g.grade_code = v.grade_code
        JOIN region r       ON r.region_code = v.region_code
        LEFT JOIN region p  ON p.region_code = r.parents_code
        LEFT JOIN region gp ON gp.region_code = p.parents_code
        WHERE v.house_id = %s
    """, (house_id,))
    row = cur.fetchone()
    if not row:
        return None
    # "고창군 고창읍 읍내리" 처럼 시군부터 이어 붙인 이름 (시도는 뺌)
    parts = [(row.pop("gp_name"), row.pop("gp_level")), (row.pop("p_name"), row.pop("p_level")),
             (row.pop("r_name"), row.pop("r_level"))]
    row["region_name"] = " ".join(name for name, level in parts if name and level != "sido")
    return row


@bp.get("/api/houses/<int:house_id>")
def house_detail(house_id):
    """빈집 상세. 로그인 상태면 is_saved 포함"""
    with get_conn() as conn, conn.cursor() as cur:
        house = find_house(cur, house_id)
        if not house:
            return fail("없는 빈집입니다", 404)
        house["is_saved"] = False
        if session.get("member_id"):
            cur.execute("SELECT 1 FROM saved_house WHERE member_id = %s AND house_id = %s",
                        (session["member_id"], house_id))
            house["is_saved"] = cur.fetchone() is not None
    log_event("view_house", house["region_code"], house_id=house_id)
    return ok(house)


@bp.get("/api/houses/<int:house_id>/stores")
def house_stores(house_id):
    """빈집(리·동 중심) 주변 반경 안의 가게. ?radius=1000&industry=cafe
    반경 선택지는 그 시군의 region_store_stat 반경(고창 1000·2500·5000, 양산 500·1000·1500)을 씁니다.
    업종별 수는 반경 안 가게 전체, 목록은 가까운 순 STORE_LIMIT 곳까지."""
    industry = request.args.get("industry") or None
    with get_conn() as conn, conn.cursor() as cur:
        house = find_house(cur, house_id)
        if not house:
            return fail("없는 빈집입니다", 404)
        lat, lng = house["lat"], house["lng"]

        cur.execute("""
            SELECT radius_m, DATE_FORMAT(MAX(data_date), '%%Y-%%m-%%d') AS data_date
            FROM region_store_stat WHERE LEFT(region_code, 5) = LEFT(%s, 5)
            GROUP BY radius_m ORDER BY radius_m
        """, (house["region_code"],))
        stat_rows = cur.fetchall()
        radii = [r["radius_m"] for r in stat_rows]
        data_date = max((r["data_date"] for r in stat_rows), default=None)

        result = {"house_id": house_id, "region_code": house["region_code"],
                "center": {"lat": lat, "lng": lng}, "radii": radii, "radius": None,
                "data_date": data_date, "industry": industry, "total": 0,
                "stats": [], "stores": [], "limit": STORE_LIMIT}
        if not radii or lat is None:
            return ok(result)

        try:
            radius = int(request.args.get("radius", radii[0]))
        except ValueError:
            return fail("radius는 숫자여야 합니다", 400)
        if radius not in radii:
            radius = radii[0]
        result["radius"] = radius

        if industry:
            cur.execute("SELECT 1 FROM industry WHERE industry_code = %s", (industry,))
            if not cur.fetchone():
                return fail("없는 업종입니다", 400)

        # 반경을 감싸는 네모로 먼저 거르고(빠름), 정확한 거리는 DISTANCE_SQL 로
        # ① 네모 범위 구하기: 반경(m)을 위도·경도 '도' 단위로 바꿈
        dlat = radius / 111320                                   # 위도 1도 ≈ 111,320m
        dlng = radius / (111320 * math.cos(math.radians(lat)))   # 경도 1도 길이는 위도가 높을수록 짧아져서 cos 로 보정
        box = (lat - dlat, lat + dlat, lng - dlng, lng + dlng)   # 원을 딱 감싸는 네모 (남·북·서·동 끝)
        dist_args = (lat, lat, lng)                              # 하버사인 공식(DISTANCE_SQL)에 넣을 빈집 좌표

        # ② 업종별 가게 수 (왼쪽 칸 막대그래프): 반경 안 가게 '전체'를 셈
        cur.execute(f"""
            SELECT i.industry_code, i.name, COUNT(t.store_id) AS store_count
            FROM industry i
            LEFT JOIN (
                SELECT s.store_id, s.industry_code FROM store s
                WHERE s.latitude BETWEEN %s AND %s AND s.longitude BETWEEN %s AND %s  -- 1차: 네모 안 가게만 (빠름)
                AND {DISTANCE_SQL} <= %s                                            -- 2차: 실제 거리가 반경 안인 가게만 (정확)
            ) t ON t.industry_code = i.industry_code   -- LEFT JOIN: 가게가 0곳인 업종도 0으로 나옴
            WHERE i.for_stats                          -- 통계용 업종만
            GROUP BY i.industry_code, i.name, i.sort_order
            ORDER BY i.sort_order
        """, (*box, *dist_args, radius))
        result["stats"] = cur.fetchall()
        result["total"] = sum(r["store_count"] for r in result["stats"])   # "반경 안 가게 OO곳"

        # ③ 지도에 찍을 가게 목록 (빨간 점): 업종을 골랐으면 그 업종만
        industry_sql = "AND s.industry_code = %s" if industry else ""
        cur.execute(f"""
            SELECT s.store_id, s.name, s.category, s.industry_code, i.name AS industry_name,
                CAST(s.latitude AS DOUBLE) AS lat, CAST(s.longitude AS DOUBLE) AS lng,   -- 점을 찍을 가게 좌표
                s.address, ROUND({DISTANCE_SQL}) AS distance_m                           -- 빈집에서 가게까지 거리(m)
            FROM store s
            JOIN industry i ON i.industry_code = s.industry_code   -- 업종 이름 붙이기
            WHERE i.for_stats
              AND s.latitude BETWEEN %s AND %s AND s.longitude BETWEEN %s AND %s   -- 1차: 네모로 거르기
              {industry_sql}
            HAVING distance_m <= %s   -- 2차: 계산한 거리로 원 안 가게만 남김
            ORDER BY distance_m       -- 가까운 순
            LIMIT %s                  -- 최대 300곳 (STORE_LIMIT)
        """, (*dist_args, *box, *([industry] if industry else []), radius, STORE_LIMIT))
        result["stores"] = cur.fetchall()
    return ok(result)
