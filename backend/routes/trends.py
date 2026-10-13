"""[담당 D] 공개 대시보드 (지역 동향)"""
from flask import Blueprint, render_template
from routes.common import ok

bp = Blueprint("trends", __name__)


def top_regions(n=3):
    """메인 화면용 인기 지역. TODO(D)"""
    return []


@bp.get("/trends")
def trends_page():
    return render_template("placeholder.html", title="지역 동향", owner="D")


@bp.get("/api/trends")
def trends_data():
    return ok({})                                # TODO(D): ?days=7
