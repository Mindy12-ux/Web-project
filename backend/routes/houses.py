"""[담당 B] 지도 페이지, 지역·숫자 원·빈집 카드 API
기록: 지역 보기 view_region, 빈집 상세 view_house → events.log_event
"""
from flask import Blueprint, render_template
from routes.common import ok

bp = Blueprint("houses", __name__)


@bp.get("/map")
def map_page():
    return render_template("placeholder.html", title="빈집 찾기", owner="B")


@bp.get("/api/regions")
def regions():
    return ok([])                                # TODO(B): 시군 목록 + 빈집 수


@bp.get("/api/regions/<sigungu_code>/clusters")
def clusters(sigungu_code):
    return ok([])                                # TODO(B): 리·동별 빈집 수 + 중심 좌표


@bp.get("/api/houses")
def houses_in_region():
    return ok([])                                # TODO(B): ?region=&grades=


@bp.get("/api/houses/<int:house_id>")
def house_detail(house_id):
    return ok(None)                              # TODO(B): 상세 + is_saved
