"""A 담당: 회원가입·로그인·로그아웃과 접근 권한 검사."""
import re
import secrets
from functools import wraps
from urllib.parse import urlsplit

import pymysql
from flask import Blueprint, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_conn
from routes.common import fail, ok

bp = Blueprint('auth', __name__)  # 인증 URL을 묶는 Blueprint입니다. app.py가 이 bp를 등록합니다.


# 화면과 서버가 비교할 보안 토큰을 준비합니다.
@bp.app_context_processor  # HTML을 만들 때 아래 함수의 반환값을 공통 템플릿 변수로 제공합니다.
def auth_context():
    if 'auth_csrf' not in session:  # 세션에 요청 확인용 토큰이 없을 때만 새로 준비합니다.
        session['auth_csrf'] = secrets.token_urlsafe(32)  # 회원 ID가 아닌 CSRF 보안 토큰을 세션에 저장합니다.
    return {'auth_csrf': session['auth_csrf']}  # HTML의 hidden 입력·meta에서 auth_csrf라는 이름으로 사용합니다.


def valid_csrf():
    expected = session.get('auth_csrf', '')  # 서버가 세션에 보관한 토큰입니다.
    supplied = request.form.get('csrf_token', '')  # 이번 POST 폼이 보낸 토큰입니다. .get()은 HTTP GET이 아니라 값 꺼내기입니다.
    return bool(expected and secrets.compare_digest(expected, supplied))  # 토큰이 존재하고 서로 같으면 True, 아니면 False를 돌려줍니다.


# 다른 담당자도 사용하는 로그인·공무원 접근 검사입니다.
def login_required(view):  # view는 로그인 보호를 붙일 원래 함수입니다.
    @wraps(view)
    def wrapper(*args, **kwargs):  # 원래 함수가 받을 URL 인자 등을 그대로 받아 검사 후 전달합니다.
        if not session.get('member_id'):  # 로그인 성공 때 저장한 회원 ID가 있는지 확인합니다.
            if request.path.startswith('/api/'):
                return fail('로그인이 필요합니다', 401)  # API는 화면 이동 대신 로그인 필요 JSON을 반환합니다.
            return redirect(url_for('auth.login', next=request.path))  # 일반 화면은 로그인으로 이동하고 원래 경로를 next로 전달합니다.
        return view(*args, **kwargs)  # 검사를 통과하면 보호하려던 원래 함수를 실행합니다.
    return wrapper


def official_required(view):  # 공무원 접근 검사를 다른 라우트에 붙이는 데코레이터입니다.
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if session.get('role') != 'official':  # DB 전체를 다시 조회하지 않고 로그인 세션의 권한을 검사합니다.
            return fail('공무원 계정만 볼 수 있습니다', 403)
        return view(*args, **kwargs)
    return wrapper


def safe_next(value):  # value는 로그인 뒤 이동할 주소입니다. 외부 사이트 이동을 막습니다.
    """로그인 후 외부 사이트로 이동하지 않도록 내부 주소만 허용합니다."""
    parts = urlsplit(value)  # 주소를 호스트·스킴·경로 등의 구성 요소로 나눕니다.
    internal = value.startswith('/') and not value.startswith('//')
    unsafe = parts.netloc or parts.scheme or '\\' in value
    control_character = any(ord(char) < 32 for char in value)
    if internal and not unsafe and not control_character:  # 안전한 내부 경로일 때만 사용자가 요청한 이동 주소를 허용합니다.
        return value
    return url_for('main.index')  # 허용되지 않은 next 주소는 홈 경로로 바꿉니다.


def signup_error(member_id, nickname, password, confirmation):  # signup()이 읽은 가입 폼의 네 값을 순서대로 받습니다. HTTP 요청을 새로 받는 함수는 아닙니다.
    """입력 오류 문구를 반환합니다. 정상일 때는 None입니다."""
    if not valid_csrf():  # 정상 화면에서 제출한 폼 토큰인지 먼저 검사합니다.
        return '요청이 만료됐어요. 다시 시도해 주세요.'
    if not re.fullmatch(r'[A-Za-z0-9_]{4,50}', member_id):  # 아이디 전체가 영문·숫자·밑줄 4~50자인지 검사합니다.
        return '아이디는 영문·숫자·밑줄로 4~50자 입력해 주세요.'
    if not 1 <= len(nickname) <= 30:  # 닉네임은 비어 있지 않고 30자 이하여야 합니다.
        return '닉네임은 1~30자로 입력해 주세요.'
    if not 8 <= len(password) <= 128:  # 비밀번호 길이는 8~128자여야 합니다.
        return '비밀번호는 8~128자로 입력해 주세요.'
    if password != confirmation:  # 입력 비밀번호와 확인 입력이 서로 같은지 검사합니다.
        return '비밀번호 확인이 일치하지 않아요.'
    return None  # 오류가 없다는 표시입니다. 호출한 signup()의 error로 돌아갑니다.


def create_member(member_id, nickname, password, consent):  # signup()에서 받은 값으로 member를 저장하고 (오류 문구, 상태 코드)를 돌려줍니다.
    """중복 확인 후 member에 저장합니다. 결과는 (오류 문구, 상태 코드)입니다."""
    with get_conn() as conn, conn.cursor() as cur:  # conn은 DB 연결, cur는 SQL을 실행하고 결과를 읽는 커서입니다.
        # 동시 가입 사이에 같은 닉네임이 등록되지 않도록 잠급니다.
        cur.execute("SELECT GET_LOCK('itda_signup', 5) AS acquired")  # 동시 가입의 중복 검사·저장을 순서대로 처리할 DB 잠금을 요청합니다.
        if cur.fetchone()['acquired'] != 1:
            return '가입 요청이 많아요. 잠시 후 다시 시도해 주세요.', 503
        try:
            # 가입 확정 직전에 아이디·닉네임 중복을 DB에서 다시 조회합니다.
            cur.execute('''
                SELECT member_id, nickname FROM member
                WHERE member_id=%s OR nickname=%s
            ''', (member_id, nickname))
            # 두 %s에 가입 입력 아이디·닉네임을 순서대로 전달합니다.
            if cur.fetchone():  # 같은 회원이 한 행이라도 있으면 중복으로 처리합니다.
                return '이미 사용 중인 아이디 또는 닉네임이에요.', 409

            # 비밀번호 원문 대신 해시를 만들어 회원 정보와 함께 INSERT합니다.
            cur.execute('''
                INSERT INTO member (member_id, password_hash, nickname, share_consent)
                VALUES (%s, %s, %s, %s)
            ''', (member_id, generate_password_hash(password), nickname, consent))
            # 컬럼 순서에 맞춰 아이디·해시·닉네임·선택 동의를 전달합니다.
            # role과 region_code는 DB 기본값 user/NULL을 사용합니다.
            conn.commit()  # INSERT를 DB에 확정합니다.
            return None, 200  # signup()의 error, status가 각각 None, 200을 받습니다.
        finally:
            cur.execute("SELECT RELEASE_LOCK('itda_signup')")  # 중간에 return하거나 오류가 나도 가입 잠금은 해제합니다.


@bp.get('/auth/check-duplicate')  # signup.js가 보내는 GET 중복 조회 요청을 아래 함수에 연결합니다.
def check_duplicate():
    """가입 화면에서 아이디 또는 닉네임 중복 여부만 확인합니다."""
    field = request.args.get('field', '')  # URL의 field는 검사 항목 이름입니다. 예: member_id 또는 nickname.
    value = request.args.get('value', '').strip()  # URL의 value는 사용자가 입력한 실제 아이디·닉네임 문자열입니다.
    if field == 'member_id':
        if not re.fullmatch(r'[A-Za-z0-9_]{4,50}', value):
            return fail('아이디는 영문·숫자·밑줄로 4~50자 입력해 주세요.')
        query = 'SELECT 1 FROM member WHERE member_id=%s LIMIT 1'  # 아직 SQL 실행은 하지 않고 아이디 존재 여부를 찾는 쿼리를 정합니다.
    elif field == 'nickname':
        if not 1 <= len(value) <= 30:
            return fail('닉네임은 1~30자로 입력해 주세요.')
        query = 'SELECT 1 FROM member WHERE nickname=%s LIMIT 1'  # 닉네임 검사라면 서버가 정한 닉네임 조회 쿼리를 사용합니다.
    else:
        return fail('확인할 수 없는 항목입니다.')
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(query, (value,))  # URL 입력값을 %s 매개변수로 전달해 DB를 조회합니다.
            duplicate = cur.fetchone() is not None  # 회원이 있으면 True(중복), 없으면 False(사용 가능)입니다.
        response, status = ok({'duplicate': duplicate}) # {"ok": true,"data": {"duplicate": true}} , 200 값이나옴 함수떄문에
        response.headers['Cache-Control'] = 'no-store'  # 이전 중복 결과가 캐시에 남아 재사용되지 않게 합니다.
        return response, status  # GET 요청을 보낸 브라우저의 fetch에 JSON 응답을 돌려줍니다.
    except pymysql.MySQLError:
        return fail('중복 확인을 할 수 없어요. 잠시 후 다시 시도해 주세요.', 503)


@bp.route('/auth/signup', methods=['GET', 'POST'])  # GET은 가입 화면 조회, POST는 가입 버튼으로 제출한 폼 처리입니다.
def signup():
    # 오류가 나도 다시 표시할 가입 입력 아이디·닉네임을 묶습니다.
    values = {
        'member_id': request.form.get('member_id', '').strip(),  # name=member_id의 폼 값을 꺼내 앞뒤 공백을 제거합니다. HTTP GET 방식과는 다릅니다.
        'nickname': request.form.get('nickname', '').strip(),  # name=nickname의 폼 입력값입니다. DB에서 읽은 값이 아닙니다.
    }
    consent = request.form.get('share_consent') == 'on'  # 동의 체크박스는 체크하면 on이 와서 True, 미체크면 값이 없어 False입니다.
    error, status = None, 200  # 초기에는 오류 없음·정상 상태입니다. 아직 가입 성공을 확정한 것은 아닙니다.

    if request.method == 'POST':  # POST로 가입 폼을 제출했을 때만 검사·저장합니다. GET이면 화면만 보여줍니다.
        password = request.form.get('password', '')  # 이번 회원가입 폼의 비밀번호 원문을 읽습니다.
        confirmation = request.form.get('password_confirm', '')  # name=password_confirm 입력을 confirmation 변수에 받습니다.
        # 네 값을 검사 함수에 전달하고 오류 문구 또는 None을 error로 받습니다.
        error = signup_error(values['member_id'], values['nickname'], password, confirmation)
        if error:
            status = 400  # 검사 실패면 아래 가입 HTML에 오류와 400 상태를 반환합니다.
        else:
            try:
                # 검사 성공 후 저장 함수로 값을 넘기고 반환된 두 결과를 나눠 받습니다.
                error, status = create_member(
                    values['member_id'], values['nickname'], password, consent)
            except pymysql.IntegrityError:
                error, status = '이미 사용 중인 아이디 또는 닉네임이에요.', 409
            except pymysql.MySQLError:
                error, status = 'DB에 연결할 수 없어요. 잠시 후 다시 시도해 주세요.', 503
            if not error:  # DB 저장까지 오류가 없어야 로그인 화면으로 이동합니다.
                return redirect(url_for('auth.login', joined='1'))  # 302 이동 응답을 보내면 브라우저가 GET /auth/login?joined=1을 요청합니다.

    # GET 또는 실패 POST는 입력값·동의·오류를 넣은 가입 HTML을 반환합니다.
    return render_template('auth/signup.html', error=error, values=values, consent=consent), status


@bp.route('/auth/login', methods=['GET', 'POST'])  # GET은 로그인 화면 조회, POST는 로그인 폼 검증입니다.
def login():
    member_id = request.form.get('member_id', '').strip()  # 이번 로그인 폼에 입력한 아이디입니다. 아직 검증된 세션 회원 ID가 아닙니다.
    password = request.form.get('password', '')  # 비밀번호는 공백을 임의로 제거하지 않고 입력 그대로 검증합니다.
    next_url = safe_next(request.values.get('next', ''))  # next는 로그인 뒤 돌아갈 주소이며 safe_next()가 내부 주소인지 검사합니다.
    error, status = None, 200

    if request.method == 'POST':  # 로그인 폼을 POST로 제출한 경우만 DB 회원을 조회합니다.
        if not valid_csrf():
            error, status = '요청이 만료됐어요. 다시 시도해 주세요.', 400
        elif not member_id or not password:
            error, status = '아이디와 비밀번호를 입력해 주세요.', 400
        else:
            try:
                with get_conn() as conn, conn.cursor() as cur:
                    # 폼에서 읽은 아이디로 DB 회원 한 명과 로그인에 필요한 값을 조회합니다.
                    cur.execute('''
                        SELECT member_id, password_hash, nickname, role, region_code
                        FROM member WHERE member_id=%s
                    ''', (member_id,))
                    # %s에 로그인 입력 아이디를 전달합니다. 쉼표는 값 하나짜리 튜플 문법입니다.
                    member = cur.fetchone()  # 결과는 회원 딕셔너리 또는 None입니다.
                if not member or not check_password_hash(member['password_hash'], password):  # 회원이 없거나 입력 비밀번호의 해시 검증이 실패하면 로그인 실패입니다.
                    error, status = '아이디 또는 비밀번호가 올바르지 않아요.', 401
                else:
                    # DB 권한을 다시 읽어 로그인 세션을 갱신합니다.
                    session.clear()  # 이전 로그인 상태·토큰을 비우고 새 로그인 정보를 저장합니다.
                    for key in ('member_id', 'nickname', 'role', 'region_code'):
                        session[key] = member[key]  # DB에서 검증한 회원 정보를 세션에 넣습니다. 마이페이지·찜은 이 member_id를 읽습니다.
                    return redirect(next_url)  # 302 응답 뒤 브라우저가 next_url로 GET 요청합니다.
            except pymysql.MySQLError:
                error, status = 'DB에 연결할 수 없어요. 잠시 후 다시 시도해 주세요.', 503

    # GET 또는 로그인 실패는 오류·입력 아이디를 넣은 login.html을 반환합니다.
    return render_template(
        'auth/login.html', error=error, member_id=member_id, next_url=next_url,
        joined=request.args.get('joined') == '1'), status  # 가입 후 joined=1로 이동했다면 가입 완료 안내를 표시합니다.


@bp.route('/auth/logout', methods=['GET', 'POST'])  # 주소를 GET으로 열면 확인 화면, 유효한 POST이면 실제 로그아웃입니다.
def logout():
    # 주소를 직접 열면 확인 화면만 표시합니다. 로그아웃은 POST로 실행합니다.
    if request.method == 'GET':
        return render_template('auth/logout.html')
    if not valid_csrf():  # 로그아웃 폼의 csrf_token도 세션 토큰과 일치해야 합니다.
        return fail('요청이 만료됐어요. 새로고침 후 다시 시도해 주세요.', 400)
    session.clear()  # 로그인 상태만 삭제합니다. member·saved_house DB 데이터는 지우지 않습니다.
    return redirect(url_for('main.index'))  # 홈으로 이동하는 302 응답을 반환합니다.
