"""[담당 A] 찜 저장·수정·취소, 마이페이지
기록: 저장 save, 수정 edit, 취소 unsave, 희망업종 선택 select_industry → events.log_event
"""
from flask import Blueprint, render_template
from routes.auth import login_required
from routes.common import ok

bp = Blueprint("mypage", __name__)


@bp.get("/mypage")
@login_required
def mypage():
    return render_template("placeholder.html", title="마이페이지", owner="A")


@bp.get("/api/saved")
@login_required
def list_saved():
    return ok([])                                # TODO(A)


@bp.post("/api/saved")
@login_required
def save_house():
    return ok(None, 201)                         # TODO(A)


@bp.patch("/api/saved/<int:house_id>")
@login_required
def edit_saved(house_id):
    return ok(None)                              # TODO(A)


@bp.delete("/api/saved/<int:house_id>")
@login_required
def unsave(house_id):
    return ok(None)                              # TODO(A)
