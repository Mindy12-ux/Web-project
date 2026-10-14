"""[담당 B] 지도 페이지, 지역·숫자 원·빈집 카드 API
기록: 지역 보기 view_region, 빈집 상세 view_house → events.log_event
"""
import re

from flask import Blueprint, render_template, request, session
from db import get_conn
from routes.common import ok, fail
from routes.events import log_event

bp = Blueprint("houses", __name__)

SIGUNGU_RE = re.compile(r"[0-9]{5}(?:[0-9]{5})?")    # 시군코드 5자리 (10자리 법정동코드도 받음)
REGION_RE = re.compile(r"[0-9]{10}")                 # 리·동 법정동코드 10자리
BAD_GRADES = "grades는 1, 2, 3, NA 중에서 쉼표로 고르세요"

# 빈집 카드 한 장 = 빈집 + 지역 이름 + 등급 이름 + 그 시군의 빈집 담당 부서(문의처)
CARD_SQL = """
    SELECT v.house_id, v.region_code, r.name AS region_name,
           CASE WHEN r.level = 'ri' THEN p.name END AS parent_name,
           v.grade_code, g.label AS grade_label,
           v.main_use, v.built_year, v.structure, v.floor_area, v.land_area,
           v.road_contact, v.zoning, v.data_date,
           o.dept_name AS office_dept, o.phone AS office_phone
    FROM vacant_house v
    JOIN region r      ON r.region_code = v.region_code
    LEFT JOIN region p ON p.region_code = r.parents_code
    JOIN grade_code g  ON g.grade_code = v.grade_code
    LEFT JOIN local_office o ON o.region_code = CONCAT(LEFT(v.region_code, 5), '00000')
                            AND o.role_type = 'vacant'
"""


def _grades(cur):
    """?grades=1,2 → ['1', '2']. 없으면 is_default 등급(1·2등급), 모르는 값이 있으면 None"""
    cur.execute("SELECT grade_code, is_default FROM grade_code")
    rows = cur.fetchall()
    raw = request.args.get("grades")
    if raw is None:
        return [r["grade_code"] for r in rows if r["is_default"]]
    picked = {g.strip().upper() for g in raw.split(",") if g.strip()}
    if not picked <= {r["grade_code"] for r in rows}:
        return None
    return sorted(picked)


def _card(row):
    """DB 한 줄 → 카드 JSON (Decimal·날짜를 JSON에 맞게, 문의처는 office로 묶기)"""
    for key in ("floor_area", "land_area"):
        if row[key] is not None:
            row[key] = float(row[key])
    row["data_date"] = row["data_date"].isoformat()
    dept, phone = row.pop("office_dept"), row.pop("office_phone")
    row["office"] = {"dept_name": dept, "phone": phone} if dept else None
    return row


@bp.get("/map")
def map_page():
    # map.html을 만들면 render_template("map.html")로 바꾼다
    return render_template("placeholder.html", title="빈집 찾기", owner="B")


@bp.get("/api/grades")
def grades_list():
    """등급 필터 칩용. is_default가 true인 등급을 처음에 체크한다"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT grade_code, label, description, is_default "
                    "FROM grade_code ORDER BY sort_order")
        rows = cur.fetchall()
    for r in rows:
        r["is_default"] = bool(r["is_default"])
    return ok(rows)


@bp.get("/api/regions")
def regions():
    """시군 목록 + 빈집 수. lat·lng는 빈집이 많은 쪽으로 기운 중심(지도 첫 화면용)"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT s.region_code, LEFT(s.region_code, 5) AS sigungu_code, s.name,
                      d.name AS sido_name, COUNT(*) AS house_count,
                      COUNT(DISTINCT v.region_code) AS area_count,
                      GROUP_CONCAT(DISTINCT r.level ORDER BY r.level) AS levels,
                      AVG(r.latitude) AS lat, AVG(r.longitude) AS lng
               FROM region s
               JOIN region d       ON d.region_code = s.parents_code
               JOIN vacant_house v ON LEFT(v.region_code, 5) = LEFT(s.region_code, 5)
               JOIN region r       ON r.region_code = v.region_code
               WHERE s.level = 'sigungu'
               GROUP BY s.region_code, s.name, d.name
               ORDER BY house_count DESC"""
        )
        rows = cur.fetchall()
    for r in rows:
        r["levels"] = r["levels"].split(",")
        r["lat"], r["lng"] = round(float(r["lat"]), 6), round(float(r["lng"]), 6)
    return ok(rows)


@bp.get("/api/regions/<sigungu_code>/clusters")
def clusters(sigungu_code):
    """리·동별 빈집 수 + 중심 좌표(숫자 원). 많은 곳부터. 개별 빈집 좌표는 없다"""
    if not SIGUNGU_RE.fullmatch(sigungu_code):
        return fail("시군코드는 숫자 5자리입니다 (예: 52790)", 400)
    sgg = sigungu_code[:5]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT region_code FROM region WHERE region_code = %s AND level = 'sigungu'",
                    (sgg + "00000",))
        sigungu = cur.fetchone()
        if sigungu is None:
            return fail("지역을 찾을 수 없습니다", 404)
        grades = _grades(cur)
        if grades is None:
            return fail(BAD_GRADES, 400)
        if not grades:                               # 칩을 모두 끈 경우
            return ok([])
        marks = ", ".join(["%s"] * len(grades))      # 값이 아니라 %s 자리표시자만 이어 붙임
        cur.execute(
            f"""SELECT r.region_code, r.name,
                       CASE WHEN r.level = 'ri' THEN p.name END AS parent_name,
                       r.level, r.latitude AS lat, r.longitude AS lng,
                       COUNT(*) AS house_count
                FROM vacant_house v
                JOIN region r      ON r.region_code = v.region_code
                LEFT JOIN region p ON p.region_code = r.parents_code
                WHERE LEFT(v.region_code, 5) = %s AND v.grade_code IN ({marks})
                GROUP BY r.region_code, r.name, p.name, r.level, r.latitude, r.longitude
                ORDER BY house_count DESC, r.region_code""",
            [sgg, *grades],
        )
        rows = cur.fetchall()
    for r in rows:
        r["lat"], r["lng"] = float(r["lat"]), float(r["lng"])
    log_event("view_region", sigungu["region_code"])
    return ok(rows)


@bp.get("/api/houses")
def houses_in_region():
    """한 리·동의 빈집 카드 목록. ?region=<10자리>&grades=1,2"""
    region = request.args.get("region", "")
    if not REGION_RE.fullmatch(region):
        return fail("region은 리·동 법정동코드 10자리입니다", 400)
    with get_conn() as conn, conn.cursor() as cur:
        grades = _grades(cur)
        if grades is None:
            return fail(BAD_GRADES, 400)
        if not grades:
            return ok([])
        marks = ", ".join(["%s"] * len(grades))
        cur.execute(
            CARD_SQL + f" WHERE v.region_code = %s AND v.grade_code IN ({marks})"
                       " ORDER BY g.sort_order, v.house_id",
            [region, *grades],
        )
        return ok([_card(r) for r in cur.fetchall()])


@bp.get("/api/houses/<int:house_id>")
def house_detail(house_id):
    """빈집 상세. 로그인 상태면 is_saved(내가 찜했는지)를 함께 준다"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(CARD_SQL + " WHERE v.house_id = %s", (house_id,))
        row = cur.fetchone()
        if row is None:
            return fail("빈집을 찾을 수 없습니다", 404)
        card = _card(row)
        member_id = session.get("member_id")
        if member_id:
            cur.execute("SELECT 1 FROM saved_house WHERE member_id = %s AND house_id = %s",
                        (member_id, house_id))
            card["is_saved"] = cur.fetchone() is not None
    log_event("view_house", card["region_code"], house_id=house_id)
    return ok(card)
