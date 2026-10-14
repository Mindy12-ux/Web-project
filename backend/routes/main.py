"""[담당 B] 메인 화면"""
from flask import Blueprint, render_template

try:
    from routes.trends import top_regions        # D가 만들면 자동으로 연결됨
except ImportError:
    top_regions = None

bp = Blueprint("main", __name__)


def popular_regions():
    """이번 주 인기 지역 TOP 3. D의 함수가 없거나 실패해도 메인 화면은 뜨게 빈 목록"""
    if top_regions is None:
        return []
    try:
        return top_regions(3)
    except Exception as e:
        print("top_regions 실패:", e)
        return []


@bp.get("/")
def index():
    return render_template("main.html", top=popular_regions())
