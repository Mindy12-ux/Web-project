"""[담당 A] 회원가입·로그인·로그아웃, 권한 데코레이터
세션 키 약속: session["member_id"], session["role"], session["nickname"], session["region_code"](공무원)
"""
from functools import wraps
from flask import Blueprint, session, request, redirect, url_for, render_template
from routes.common import fail

bp = Blueprint("auth", __name__)


def login_required(view):
    """로그인해야 쓸 수 있는 라우트에 붙입니다. API는 401, 페이지는 로그인 화면으로."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("member_id"):
            if request.path.startswith("/api/"):
                return fail("로그인이 필요합니다", 401)
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapper


def official_required(view):
    """공무원만 쓸 수 있는 라우트에 붙입니다."""
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if session.get("role") != "official":
            return fail("공무원 계정만 볼 수 있습니다", 403)
        return view(*args, **kwargs)
    return wrapper


@bp.route("/auth/signup", methods=["GET", "POST"])
def signup():
    # TODO(A): 아이디 중복 검사, generate_password_hash 로 저장, share_consent 체크박스
    return render_template("auth/signup.html")


@bp.route("/auth/login", methods=["GET", "POST"])
def login():
    # TODO(A): check_password_hash 로 확인 후 세션 저장
    return render_template("auth/login.html")


@bp.post("/auth/logout")
def logout():
    session.clear()
    return redirect(url_for("main.index"))
