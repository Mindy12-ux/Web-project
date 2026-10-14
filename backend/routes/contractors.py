"""[담당 C] 시공 업체, 지자체 연락처"""
import re

from flask import Blueprint, request
from db import get_conn
from routes.common import ok, fail

bp = Blueprint("contractors", __name__)

REGION_RE = re.compile(r"[0-9]{10}")             # 리·동 법정동코드 10자리 (B가 넘겨주는 값)
MAX_LIMIT = 50

# 지도 위 직선거리(km): 빈집 지역 중심 ↔ 업체 좌표 (하버사인)
DISTANCE_SQL = """6371 * 2 * ASIN(SQRT(
        POW(SIN(RADIANS(c.latitude - %s) / 2), 2)
        + COS(RADIANS(%s)) * COS(RADIANS(c.latitude)) * POW(SIN(RADIANS(c.longitude - %s) / 2), 2)))"""


def _region_arg():
    region = request.args.get("region", "")
    return region if REGION_RE.fullmatch(region) else None


@bp.get("/api/contractors")
def contractors():
    """같은 시군(LEFT(region_code,5))의 시공 업체. 한 회사는 한 줄(등록 업종은 industries),
    가까운 순. ?region=<10자리>&limit=10 (사업자등록번호는 화면에 안 쓰므로 내보내지 않음)"""
    region = _region_arg()
    if region is None:
        return fail("region은 리·동 법정동코드 10자리입니다", 400)
    limit = request.args.get("limit", "10")
    if not (limit.isascii() and limit.isdigit() and 1 <= int(limit) <= MAX_LIMIT):
        return fail("limit은 1~%d 사이 숫자입니다" % MAX_LIMIT, 400)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT latitude, longitude FROM region WHERE region_code = %s", (region,))
        center = cur.fetchone()
        if center is None:
            return fail("지역을 찾을 수 없습니다", 404)
        lat, lng = center["latitude"], center["longitude"]   # 좌표 없으면 거리는 NULL
        cur.execute(
            f"""SELECT c.name, c.phone, c.address, c.region_code,
                       GROUP_CONCAT(c.industry ORDER BY c.industry SEPARATOR '|') AS industries,
                       ROUND({DISTANCE_SQL}, 1) AS distance_km
                FROM contractor c
                WHERE LEFT(c.region_code, 5) = %s
                GROUP BY c.registration_no, c.name, c.phone, c.address, c.region_code,
                         c.latitude, c.longitude
                ORDER BY distance_km IS NULL, distance_km, c.name
                LIMIT %s""",
            (lat, lat, lng, region[:5], int(limit)),
        )
        rows = cur.fetchall()
    for r in rows:
        r["industries"] = r["industries"].split("|")
        if r["distance_km"] is not None:
            r["distance_km"] = float(r["distance_km"])
    return ok(rows)


@bp.get("/api/offices")
def offices():
    """그 시군의 담당 부서 연락처 (빈집 → 인허가 → 민박 순). ?region=<10자리>"""
    region = _region_arg()
    if region is None:
        return fail("region은 리·동 법정동코드 10자리입니다", 400)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT role_type, dept_name, phone, url, description, data_date
               FROM local_office
               WHERE region_code = %s
               ORDER BY FIELD(role_type, 'vacant', 'permit', 'lodging')""",
            (region[:5] + "00000",),
        )
        rows = cur.fetchall()
    for r in rows:
        r["data_date"] = r["data_date"].isoformat()
    return ok(rows)
