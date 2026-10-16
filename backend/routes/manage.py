"""[담당 D] 회원 역할 관리(관리자) + 공무원 초대 코드
화면:  GET  /manage/members                  관리자: 회원 목록·역할 변경·초대 코드 발급
       GET/POST /official/verify             회원: 초대 코드를 입력해 공무원으로 전환
처리:  POST /manage/members/<id>/role        관리자: 역할 변경
       POST /manage/invites                  관리자: 초대 코드 발급 (원문은 이때 한 번만 보여 줌)
       POST /manage/invites/<id>/revoke      관리자: 안 쓴 코드 폐기

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



# get: 링크를 열거나 메뉴에서 들어올 때,  get요청으로 들어온 경우, if절은 시행하지 않고 코드를 입력하는 화면만 보여준다.
# post: [인증하기] 버튼을 눌렀을 때, 코드를 검사하고 역할을 실제로 바꾼다
@bp.route("/official/verify", methods=["GET", "POST"])
def verify():
    
    # A의 login_required 는 next 에 경로만 넘겨 ?code= 가 사라지므로 여기서 직접 처리
    
    if not session.get("member_id"): # 로그인 여부 검증
        return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
    
    error, status = None, 200
    prefill = request.form.get("code") or request.args.get("code", "")
    prefill = prefill.strip()[:20]          # 링크에 담겨 온 코드를 입력 칸에 미리 채움 (자동 제출은 하지 않음)
    
    # post 요청 + 이미 회원가입이 되어있는 상태인 경우에만 코드가 실행됨.
    if request.method == "POST" and session.get("role") == "user":
        
        # 코드를 5번 틀려 걸린 잠금(verify_locked_until)이 아직 풀리지 않았는지 검사
        if locked_seconds():
            error, status = f"코드를 여러 번 틀려 잠시 막혔어요. {locked_seconds() // 60 + 1}분 뒤에 다시 시도해 주세요.", 429
        
        # CSRF 검사: 폼으로 보낸 토큰이 세션의 토큰과 같은지 (다른 사이트가 위조한 요청 차단)
        elif not valid_csrf():
            error, status = "요청이 만료됐어요. 새로고침 후 다시 시도해 주세요.", 400
        else:

             # 두 검사를 통과하면 초대 코드 확인

            # 코드에 맞는 초대 코드 한 줄을 찾고, 찾은 줄을 invite 변수에 담는다.
            with get_conn() as conn, conn.cursor() as cur:
                cur.execute("""SELECT invite_id, region_code FROM official_invite
                               WHERE code_hash = %s AND used_by IS NULL AND expires_at > NOW()
                               FOR UPDATE""", (hash_code(request.form.get("code", "")),))
                invite = cur.fetchone()

                
                if invite:
                    # 코드를 '사용됨'으로 표시한다. (사용자가 NULL -> 특정 회원 아이디로 바뀌면 사용된 것. 위의 select문에서도 'used_by IS NULL' 조건이 있음.) 
                    cur.execute("UPDATE official_invite SET used_by = %s, used_at = NOW() WHERE invite_id = %s",
                                (session["member_id"], invite["invite_id"]))

                    # DB에서 사용자 정보를 업데이트 한다. 
                    cur.execute("UPDATE member SET role = 'official', region_code = %s WHERE member_id = %s",
                                (invite["region_code"], session["member_id"]))
                    conn.commit()

            # 세션의 role, region_code 변경. 실패 기록 삭제, 대시보드로 이동. 정상적으로 작동되었다면 함수는 여기서 끝남
            if invite:
                session["role"], session["region_code"] = "official", invite["region_code"]
                session.pop("verify_fails", None)
                return redirect(url_for("trends.dashboard"))

            # invite를 찾지 못한 경우(인증 코드가 올바르지 않은 경우) 실패 횟수 +1 
            fails = session.get("verify_fails", 0) + 1
            session["verify_fails"] = fails
            if fails >= MAX_FAILS:
                session["verify_locked_until"], session["verify_fails"] = time.time() + LOCK_SECONDS, 0
            error, status = "코드가 올바르지 않거나 만료됐어요.", 400


    # get 방식으로 들어온 경우 아예 if문이 실행되지 않으므로 아래에 있는 코드블럭만이 실행된다.
    # 아래의 'region_name'이 사용되는 경우 : 이미 공무원 유형으로 로그인 되어 있을 때. 
    region_name = None
    if session.get("region_code"):
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT name FROM region WHERE region_code = %s", (session["region_code"],))
            row = cur.fetchone()
            region_name = row["name"] if row else None
    return render_template("manage/verify.html", error=error, region_name=region_name,
                           prefill=prefill), status

    # error, status : 초기에는 'None, 200'으로 셋팅. 웹페이지가 유효하지 않은 경우 저장값이 바뀌면서 해당 오류 메세지가 출력됨
    # prefill : 관리자 계정에서 생성되는 url로 들어오는 경우는 get방식이므로 prefill 되고, 잘못된 코드를 입력해서 제출한 경우
    # post 기능을 사용하는 것이므로 코드가 계속 남아있는다.    






