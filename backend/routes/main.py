"""[담당 B] 메인 화면"""
from flask import Blueprint, render_template
from routes.trends import top_regions

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    # 이번 주 인기 지역 TOP 3: D의 top_regions() (지금은 빈 목록이라 화면에 안 보임)
    return render_template("main.html", top=top_regions(3))
