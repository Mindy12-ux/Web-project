"""[담당 C] 시공 업체, 지자체 연락처"""
from flask import Blueprint
from routes.common import ok

bp = Blueprint("contractors", __name__)


@bp.get("/api/contractors")
def contractors():
    return ok([])                                # TODO(C): 같은 시군 LEFT(region_code,5)


@bp.get("/api/offices")
def offices():
    return ok([])                                # TODO(C): local_office
