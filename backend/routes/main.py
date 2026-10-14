"""[담당 B] 메인 화면"""
from flask import Blueprint, render_template

try:
    from routes.trends import top_regions        # D가 만들면 자동으로 연결됨
except ImportError:
    top_regions = None

bp = Blueprint("main", __name__)


def _popular_regions():
    if top_regions is None:                      # D의 함수가 아직 없을 때
        return []
    try:
        return top_regions(3)
    except Exception as e:                       # 인기 지역 때문에 메인 화면이 죽지 않게
        print("top_regions 실패:", e)
        return []


@bp.get("/")
def index():
    return render_template("index.html", top_regions=_popular_regions())
