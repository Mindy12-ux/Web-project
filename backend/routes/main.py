"""[담당 B] 메인 화면"""
from flask import Blueprint, render_template

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    # TODO(B): D의 top_regions(3)으로 '이번 주 인기 지역' 표시
    return render_template("index.html")
