"""[담당 C] 업종, 주변 상권(반경별 가게 수, 가게 목록)"""
from flask import Blueprint
from routes.common import ok

bp = Blueprint("stores", __name__)


@bp.get("/api/industries")
def industries():
    return ok([])                                # TODO(C): ?for=wish|stats


@bp.get("/api/stores/stats")
def store_stats():
    return ok([])                                # TODO(C): ?region=&radius=


@bp.get("/api/stores")
def store_list():
    return ok([])                                # TODO(C): ?region=&industry=&limit=
