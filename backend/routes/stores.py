"""[담당 C] 업종, 주변 상권(반경별 가게 수, 가게 목록)"""
import re
from flask import Blueprint, request
from db import get_conn
from routes.common import ok, fail

bp = Blueprint("stores", __name__)
REGION_RE = re.compile(r"[0-9]{10}")             # 리·동 법정동코드 10자리 (B가 넘겨주는 값)
MAX_LIMIT = 200


def _region_arg(): 
    region = request.args.get("region", "") # 브라우저 요청에서 ?region=... 으로 넘어온 값 수신
    return region if REGION_RE.fullmatch(region) else None # 법정동코드 10자리인지 확인 아니면 None 반환


@bp.get("/api/industries") # 업종 목록 API
def industries():
    """업종 목록. ?for=wish(찜의 희망업종 칩) | stats(상권 탭 순서). 없으면 전체"""

    purpose = request.args.get("for") # 선호 업종 찜,상권 탭 버튼 누른 거 확인
    if purpose not in (None, "wish", "stats"):
        return fail("for는 wish 또는 stats입니다", 400)
    where = {"wish": " WHERE for_wish = 1", "stats": " WHERE for_stats = 1"}.get(purpose, "") # sql 쪼개서 저장
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT industry_code, name, sort_order FROM industry" + where
                    + " ORDER BY sort_order")
        return ok(cur.fetchall()) # sql 결과를 JSON으로 반환. 전부 출력


@bp.get("/api/stores/stats")
def store_stats():
    """반경별·업종별 가게 수. ?region=<10자리>&radius=1000
    반경 목록(radii)은 지역마다 다르므로 DB에서 읽어 함께 준다. radius를 생략하면 가장 작은 반경"""

    region = _region_arg() #12번줄 법정동 조회 함수결과 저장
    if region is None:
        return fail("region은 리·동 법정동코드 10자리입니다", 400)

    raw = request.args.get("radius") # 확인된 법정동코드에 대해 반경값을 받아옴. 없으면 None

    if raw is not None and not raw.isascii():
        return fail("radius는 숫자(m)입니다", 400)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT DISTINCT radius_m FROM region_store_stat WHERE region_code = %s "
                    "ORDER BY radius_m", (region,))
        radii = [r["radius_m"] for r in cur.fetchall()]

        if not radii:                                # 상권 자료가 없는 지역
            return ok({"region_code": region, "radius_m": None, "radii": [],
                       "data_date": None, "items": []})
        
        if raw is None: # 법정동 코드가 없으면 반경도 없는걸로 처리
            radius = radii[0] # 반경을 최소값으로 지정
        elif raw.isdigit() and int(raw) in radii: # 법정동 코드 o 반경 o, radil에 저장된 DB 조회값 o
            radius = int(raw) # 반경을 요청값으로 함
        else:
            return fail("radius는 %s 중에서 고르세요" % ", ".join(map(str, radii)), 400) # DB 조회값 없으면 에러
        
        cur.execute( # 업종별 가게 수 조회
            """SELECT s.industry_code, i.name, s.store_count, s.data_date
               FROM region_store_stat s
               JOIN industry i ON i.industry_code = s.industry_code
               WHERE s.region_code = %s AND s.radius_m = %s AND i.for_stats = 1
               ORDER BY i.sort_order""",
            (region, radius),
        )
        rows = cur.fetchall()
    data_date = max((r["data_date"] for r in rows), default=None)
    # rows를 dict로 받아서 data_date를 찾아서 최대값을 반환. 없으면 None

    for r in rows:
        del r["data_date"]
    return ok({"region_code": region, "radius_m": radius, "radii": radii,
               "data_date": data_date.isoformat() if data_date else None, "items": rows})
    # 반경별·업종별 가게 수를 JSON으로 반환. data_date가 있으면 isoformat으로 변환, 없으면 None
    # 브라우저의 fetch로 받는 JSON에는 날짜 타입이 없어서 "2026-10-14"라는 문자열로 보내야함


@bp.get("/api/stores")
def store_list():
    """같은 리·동의 가게 목록(지도 마커용). ?region=<10자리>&industry=cafe&limit=50"""
    region = _region_arg()

    if region is None:
        return fail("region은 리·동 법정동코드 10자리입니다", 400)
    limit = request.args.get("limit", "50") # 가게 목록을 몇 개까지 가져올지. 없으면 50개.

    if not (limit.isascii() and limit.isdigit() and 1 <= int(limit) <= MAX_LIMIT): # 입력받은 limit이 숫자인지 확인
        return fail("limit은 1~%d 사이 숫자입니다" % MAX_LIMIT, 400)
    
    industry = request.args.get("industry")

    sql = """SELECT s.store_id, s.name, s.category, s.industry_code, i.name AS industry_name,
                    s.address, s.latitude AS lat, s.longitude AS lng
             FROM store s
             LEFT JOIN industry i ON i.industry_code = s.industry_code
             WHERE s.region_code = %s"""
    # 법정동코드에 해당하는 가게 목록을 가져오는 SQL. 업종코드가 있으면 LEFT JOIN으로 업종명도 가져옴
    
    args = [region]

    if industry:
        sql += " AND s.industry_code = %s" # 업종코드가 있으면 WHERE 절에 추가
        args.append(industry) # 업종코드가 있으면 args에 추가
    sql += " ORDER BY s.name LIMIT %s" 
    args.append(int(limit))

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, args)
        rows = cur.fetchall()

    for r in rows:
        r["lat"], r["lng"] = float(r["lat"]), float(r["lng"])
    return ok(rows) # 위경도는 float로 변환해서 JSON으로 반환
