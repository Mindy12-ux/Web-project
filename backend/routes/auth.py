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

bp = Blueprint('auth', __name__)


# 화면과 서버가 비교할 보안 토큰을 준비합니다.
@bp.app_context_processor
def auth_context():
    if 'auth_csrf' not in session:
        session['auth_csrf'] = secrets.token_urlsafe(32)
    return {'auth_csrf': session['auth_csrf']}


def valid_csrf():
    expected = session.get('auth_csrf', '')
    supplied = request.form.get('csrf_token', '')
    return bool(expected and secrets.compare_digest(expected, supplied))


# 다른 담당자도 사용하는 로그인·공무원 접근 검사입니다.
def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get('member_id'):
            if request.path.startswith('/api/'):
                return fail('로그인이 필요합니다', 401)
            return redirect(url_for('auth.login', next=request.path))
        return view(*args, **kwargs)
    return wrapper


def official_required(view):
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if session.get('role') != 'official':
            return fail('공무원 계정만 볼 수 있습니다', 403)
        return view(*args, **kwargs)
    return wrapper


def safe_next(value):
    """로그인 후 외부 사이트로 이동하지 않도록 내부 주소만 허용합니다."""
    parts = urlsplit(value)
    internal = value.startswith('/') and not value.startswith('//')
    unsafe = parts.netloc or parts.scheme or '\\' in value
    control_character = any(ord(char) < 32 for char in value)
    if internal and not unsafe and not control_character:
        return value
    return url_for('main.index')


def signup_error(member_id, nickname, password, confirmation):
    """입력 오류 문구를 반환합니다. 정상일 때는 None입니다."""
    if not valid_csrf():
        return '요청이 만료됐어요. 다시 시도해 주세요.'
    if not re.fullmatch(r'[A-Za-z0-9_]{4,50}', member_id):
        return '아이디는 영문·숫자·밑줄로 4~50자 입력해 주세요.'
    if not 1 <= len(nickname) <= 30:
        return '닉네임은 1~30자로 입력해 주세요.'
    if not 8 <= len(password) <= 128:
        return '비밀번호는 8~128자로 입력해 주세요.'
    if password != confirmation:
        return '비밀번호 확인이 일치하지 않아요.'
    return None


def create_member(member_id, nickname, password, consent):
    """중복 확인 후 member에 저장합니다. 결과는 (오류 문구, 상태 코드)입니다."""
    with get_conn() as conn, conn.cursor() as cur:
        # 동시 가입 사이에 같은 닉네임이 등록되지 않도록 잠급니다.
        cur.execute("SELECT GET_LOCK('itda_signup', 5) AS acquired")
        if cur.fetchone()['acquired'] != 1:
            return '가입 요청이 많아요. 잠시 후 다시 시도해 주세요.', 503
        try:
            cur.execute('''
                SELECT member_id, nickname FROM member
                WHERE member_id=%s OR nickname=%s
            ''', (member_id, nickname))
            if cur.fetchone():
                return '이미 사용 중인 아이디 또는 닉네임이에요.', 409

            cur.execute('''
                INSERT INTO member (member_id, password_hash, nickname, share_consent)
                VALUES (%s, %s, %s, %s)
            ''', (member_id, generate_password_hash(password), nickname, consent))
            # role과 region_code는 DB 기본값 user/NULL을 사용합니다.
            conn.commit()
            return None, 200
        finally:
            cur.execute("SELECT RELEASE_LOCK('itda_signup')")


@bp.get('/auth/check-duplicate')
def check_duplicate():
    """가입 화면에서 아이디 또는 닉네임 중복 여부만 확인합니다."""
    field = request.args.get('field', '')
    value = request.args.get('value', '').strip()
    if field == 'member_id':
        if not re.fullmatch(r'[A-Za-z0-9_]{4,50}', value):
            return fail('아이디는 영문·숫자·밑줄로 4~50자 입력해 주세요.')
        query = 'SELECT 1 FROM member WHERE member_id=%s LIMIT 1'
    elif field == 'nickname':
        if not 1 <= len(value) <= 30:
            return fail('닉네임은 1~30자로 입력해 주세요.')
        query = 'SELECT 1 FROM member WHERE nickname=%s LIMIT 1'
    else:
        return fail('확인할 수 없는 항목입니다.')
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(query, (value,))
            duplicate = cur.fetchone() is not None
        response, status = ok({'duplicate': duplicate})
        response.headers['Cache-Control'] = 'no-store'
        return response, status
    except pymysql.MySQLError:
        return fail('중복 확인을 할 수 없어요. 잠시 후 다시 시도해 주세요.', 503)


@bp.route('/auth/signup', methods=['GET', 'POST'])
def signup():
    values = {
        'member_id': request.form.get('member_id', '').strip(),
        'nickname': request.form.get('nickname', '').strip(),
    }
    consent = request.form.get('share_consent') == 'on'
    error, status = None, 200

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirmation = request.form.get('password_confirm', '')
        error = signup_error(values['member_id'], values['nickname'], password, confirmation)
        if error:
            status = 400
        else:
            try:
                error, status = create_member(
                    values['member_id'], values['nickname'], password, consent)
            except pymysql.IntegrityError:
                error, status = '이미 사용 중인 아이디 또는 닉네임이에요.', 409
            except pymysql.MySQLError:
                error, status = 'DB에 연결할 수 없어요. 잠시 후 다시 시도해 주세요.', 503
            if not error:
                return redirect(url_for('auth.login', joined='1'))

    return render_template('auth/signup.html', error=error, values=values, consent=consent), status


@bp.route('/auth/login', methods=['GET', 'POST'])
def login():
    member_id = request.form.get('member_id', '').strip()
    password = request.form.get('password', '')
    next_url = safe_next(request.values.get('next', ''))
    error, status = None, 200

    if request.method == 'POST':
        if not valid_csrf():
            error, status = '요청이 만료됐어요. 다시 시도해 주세요.', 400
        elif not member_id or not password:
            error, status = '아이디와 비밀번호를 입력해 주세요.', 400
        else:
            try:
                with get_conn() as conn, conn.cursor() as cur:
                    cur.execute('''
                        SELECT member_id, password_hash, nickname, role, region_code
                        FROM member WHERE member_id=%s
                    ''', (member_id,))
                    member = cur.fetchone()
                if not member or not check_password_hash(member['password_hash'], password):
                    error, status = '아이디 또는 비밀번호가 올바르지 않아요.', 401
                else:
                    # DB 권한을 다시 읽어 로그인 세션을 갱신합니다.
                    session.clear()
                    for key in ('member_id', 'nickname', 'role', 'region_code'):
                        session[key] = member[key]
                    return redirect(next_url)
            except pymysql.MySQLError:
                error, status = 'DB에 연결할 수 없어요. 잠시 후 다시 시도해 주세요.', 503

    return render_template(
        'auth/login.html', error=error, member_id=member_id, next_url=next_url,
        joined=request.args.get('joined') == '1'), status


@bp.route('/auth/logout', methods=['GET', 'POST'])
def logout():
    # 주소를 직접 열면 확인 화면만 표시합니다. 로그아웃은 POST로 실행합니다.
    if request.method == 'GET':
        return render_template('auth/logout.html')
    if not valid_csrf():
        return fail('요청이 만료됐어요. 새로고침 후 다시 시도해 주세요.', 400)
    session.clear()
    return redirect(url_for('main.index'))
