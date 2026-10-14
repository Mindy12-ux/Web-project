"""[담당 D] 회원 역할 관리(관리자) + 공무원 초대 코드
화면:  GET  /manage/members                  관리자: 회원 목록·역할 변경·초대 코드 발급
       GET/POST /official/verify             회원: 초대 코드를 입력해 공무원으로 전환
처리:  POST /manage/members/<id>/role        관리자: 역할 변경
       POST /manage/invites                  관리자: 초대 코드 발급 (원문은 이때 한 번만 보여 줌)
       POST /manage/invites/<id>/revoke      관리자: 안 쓴 코드 폐기

A의 auth.py는 고치지 않고 login_required, valid_csrf를 가져다 씁니다.
세션 키(member_id, role, region_code)는 A의 로그인과 같은 이름을 씁니다.
"""
import hashlib
import secrets
import time
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, session
from db import get_conn
from routes.auth import login_required, valid_csrf
from routes.common import fail

bp = Blueprint("manage", __name__)

ROLES = {"user": "일반", "official": "공무원", "admin": "관리자"}
INVITE_DAYS = 7                     # 초대 코드 유효기간
MAX_FAILS, LOCK_SECONDS = 5, 600    # 코드를 5번 틀리면 10분 동안 입력 막기
CODE_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"   # 헷갈리는 0/O, 1/I/L 제외


# ---------- 공통 도우미 ----------
def admin_required(view):
    """관리자만 쓸 수 있는 라우트에 붙입니다."""
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            return fail("관리자만 사용할 수 있습니다", 403)
        return view(*args, **kwargs)
    return wrapper


def normalize(code):
    """사용자가 공백·하이픈·소문자로 입력해도 같은 코드로 처리"""
    return "".join(ch for ch in code.upper() if ch.isalnum())


def hash_code(code):
    return hashlib.sha256(normalize(code).encode()).hexdigest()


def new_code():
    body = "".join(secrets.choice(CODE_CHARS) for _ in range(8))
    return f"BJ-{body[:4]}-{body[4:]}"              # 예: BJ-7KQ2-M9XP


def sigungu_list(cur):
    cur.execute("SELECT region_code, name FROM region WHERE level = 'sigungu' ORDER BY name")
    return cur.fetchall()


def render_members(issued=None, error=None, status=200):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT m.member_id, m.nickname, m.role, m.region_code, r.name AS region_name,
                   m.share_consent, m.created_at
            FROM member m LEFT JOIN region r ON r.region_code = m.region_code
            ORDER BY FIELD(m.role, 'admin', 'official', 'user'), m.created_at DESC""")
        members = cur.fetchall()
        cur.execute("""
            SELECT i.invite_id, r.name AS region_name, i.created_by, i.created_at, i.expires_at,
                   i.used_by, i.used_at, (i.used_by IS NULL AND i.expires_at > NOW()) AS active
            FROM official_invite i JOIN region r ON r.region_code = i.region_code
            ORDER BY i.invite_id DESC LIMIT 30""")
        invites = cur.fetchall()
        sigungu = sigungu_list(cur)
    return render_template("manage/members.html", members=members, invites=invites,
                           sigungu=sigungu, roles=ROLES, issued=issued, error=error), status


# ---------- 관리자 ----------
@bp.get("/manage/members")
@admin_required
def members():
    return render_members()


@bp.post("/manage/members/<member_id>/role")
@admin_required
def change_role(member_id):
    if not valid_csrf():
        return render_members(error="요청이 만료됐어요. 새로고침 후 다시 시도해 주세요.", status=400)
    if member_id == session["member_id"]:
        return render_members(error="자기 자신의 역할은 바꿀 수 없어요.", status=400)
    role = request.form.get("role")
    region = request.form.get("region_code") or None
    if role not in ROLES:
        return render_members(error="알 수 없는 역할이에요.", status=400)
    with get_conn() as conn, conn.cursor() as cur:
        if role == "official":
            if region not in {r["region_code"] for r in sigungu_list(cur)}:
                return render_members(error="공무원은 소속 시군을 골라야 해요.", status=400)
        else:
            region = None                                   # 공무원이 아니면 소속 시군 비움
        cur.execute("UPDATE member SET role = %s, region_code = %s WHERE member_id = %s",
                    (role, region, member_id))
        conn.commit()
    return redirect(url_for("manage.members"))


@bp.post("/manage/invites")
@admin_required
def issue_invite():
    if not valid_csrf():
        return render_members(error="요청이 만료됐어요. 새로고침 후 다시 시도해 주세요.", status=400)
    region = request.form.get("region_code")
    with get_conn() as conn, conn.cursor() as cur:
        if region not in {r["region_code"] for r in sigungu_list(cur)}:
            return render_members(error="코드를 발급할 시군을 골라 주세요.", status=400)
        code = new_code()
        cur.execute("""INSERT INTO official_invite (code_hash, region_code, created_by, expires_at)
                       VALUES (%s, %s, %s, NOW() + INTERVAL %s DAY)""",
                    (hash_code(code), region, session["member_id"], INVITE_DAYS))
        conn.commit()
    return render_members(issued={"code": code, "days": INVITE_DAYS})   # 원문은 이 화면에서 한 번만


@bp.post("/manage/invites/<int:invite_id>/revoke")
@admin_required
def revoke_invite(invite_id):
    if not valid_csrf():
        return render_members(error="요청이 만료됐어요. 새로고침 후 다시 시도해 주세요.", status=400)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""UPDATE official_invite SET expires_at = NOW()
                       WHERE invite_id = %s AND used_by IS NULL""", (invite_id,))
        conn.commit()
    return redirect(url_for("manage.members"))


# ---------- 회원: 공무원 인증 ----------
def locked_seconds():
    until = session.get("verify_locked_until", 0)
    return max(0, int(until - time.time()))


@bp.route("/official/verify", methods=["GET", "POST"])
@login_required
def verify():
    error, status = None, 200
    if request.method == "POST" and session.get("role") == "user":
        if locked_seconds():
            error, status = f"코드를 여러 번 틀려 잠시 막혔어요. {locked_seconds() // 60 + 1}분 뒤에 다시 시도해 주세요.", 429
        elif not valid_csrf():
            error, status = "요청이 만료됐어요. 새로고침 후 다시 시도해 주세요.", 400
        else:
            with get_conn() as conn, conn.cursor() as cur:
                cur.execute("""SELECT invite_id, region_code FROM official_invite
                               WHERE code_hash = %s AND used_by IS NULL AND expires_at > NOW()
                               FOR UPDATE""", (hash_code(request.form.get("code", "")),))
                invite = cur.fetchone()
                if invite:
                    cur.execute("UPDATE official_invite SET used_by = %s, used_at = NOW() WHERE invite_id = %s",
                                (session["member_id"], invite["invite_id"]))
                    cur.execute("UPDATE member SET role = 'official', region_code = %s WHERE member_id = %s",
                                (invite["region_code"], session["member_id"]))
                    conn.commit()
            if invite:
                session["role"], session["region_code"] = "official", invite["region_code"]
                session.pop("verify_fails", None)
                return redirect(url_for("trends.dashboard"))
            fails = session.get("verify_fails", 0) + 1
            session["verify_fails"] = fails
            if fails >= MAX_FAILS:
                session["verify_locked_until"], session["verify_fails"] = time.time() + LOCK_SECONDS, 0
            error, status = "코드가 올바르지 않거나 만료됐어요.", 400

    region_name = None
    if session.get("region_code"):
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT name FROM region WHERE region_code = %s", (session["region_code"],))
            row = cur.fetchone()
            region_name = row["name"] if row else None
    return render_template("manage/verify.html", error=error, region_name=region_name), status
