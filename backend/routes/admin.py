"""[담당 D] 공무원 대시보드 — 모든 쿼리에 공무원 소속 시군 조건을 붙입니다"""
from flask import Blueprint, render_template
from routes.auth import official_required
from routes.common import ok

bp = Blueprint("admin", __name__)


@bp.get("/admin/dashboard")
@official_required
def dashboard():
    return render_template("placeholder.html", title="관리 대시보드", owner="D")


@bp.get("/api/admin/stats")
@official_required
def admin_stats():
    return ok({})                                # TODO(D)
