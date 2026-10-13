"""A: 회원가입, 로그인, 로그아웃과 권한 검사."""
import re
import secrets
from functools import wraps
from urllib.parse import urlsplit
import pymysql
from flask import Blueprint, session, request, redirect, url_for, render_template
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_conn
from routes.common import fail

bp = Blueprint('auth', __name__)

@bp.app_context_processor
def auth_context():
    if 'auth_csrf' not in session:
        session['auth_csrf'] = secrets.token_urlsafe(32)
    return {'auth_csrf': session['auth_csrf']}

def valid_csrf():
    expected = session.get('auth_csrf', '')
    supplied = request.form.get('csrf_token', '')
    return bool(expected and secrets.compare_digest(expected, supplied))

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
    parts = urlsplit(value)
    if value.startswith('/') and not value.startswith('//') and not parts.netloc and not parts.scheme and '\\' not in value and not any(ord(x) < 32 for x in value):
        return value
    return url_for('main.index')

@bp.route('/auth/signup', methods=['GET', 'POST'])
def signup():
    values = {name: request.form.get(name, '').strip() for name in ('member_id','nickname')}
    consent = request.form.get('share_consent') == 'on'
    error = None
    status = 200
    if request.method == 'POST':
        password = request.form.get('password', '')
        if not valid_csrf():
            error, status = '요청이 만료됐어요. 다시 시도해 주세요.', 400
        elif not re.fullmatch(r'[A-Za-z0-9_]{4,50}', values['member_id']):
            error, status = '아이디는 영문·숫자·밑줄로 4~50자 입력해 주세요.', 400
        elif not 1 <= len(values['nickname']) <= 30:
            error, status = '닉네임은 1~30자로 입력해 주세요.', 400
        elif not 8 <= len(password) <= 128:
            error, status = '비밀번호는 8~128자로 입력해 주세요.', 400
        elif password != request.form.get('password_confirm', ''):
            error, status = '비밀번호 확인이 일치하지 않아요.', 400
        else:
            try:
                with get_conn() as conn, conn.cursor() as cur:
                    # Serialize nickname checks without changing the shared DB schema.
                    cur.execute("SELECT GET_LOCK('itda_signup', 5) AS acquired")
                    if cur.fetchone()['acquired'] != 1:
                        error, status = '가입 요청이 많아요. 잠시 후 다시 시도해 주세요.', 503
                    else:
                        try:
                            cur.execute('SELECT member_id, nickname FROM member WHERE member_id=%s OR nickname=%s', (values['member_id'],values['nickname']))
                            if cur.fetchone():
                                error, status = '이미 사용 중인 아이디 또는 닉네임이에요.', 409
                            else:
                                cur.execute('INSERT INTO member (member_id,password_hash,nickname,share_consent) VALUES (%s,%s,%s,%s)', (values['member_id'],generate_password_hash(password),values['nickname'],consent))
                                conn.commit()
                        finally:
                            cur.execute("SELECT RELEASE_LOCK('itda_signup')")
                if not error:
                    return redirect(url_for('auth.login', joined='1'))
            except pymysql.IntegrityError:
                error, status = '이미 사용 중인 아이디 또는 닉네임이에요.', 409
            except pymysql.MySQLError:
                error, status = 'DB에 연결할 수 없어요. 잠시 후 다시 시도해 주세요.', 503
    return render_template('auth/signup.html', error=error, values=values, consent=consent), status

@bp.route('/auth/login', methods=['GET', 'POST'])
def login():
    member_id = request.form.get('member_id', '').strip()
    next_url = safe_next(request.values.get('next', ''))
    error = None
    status = 200
    if request.method == 'POST':
        if not valid_csrf():
            error, status = '요청이 만료됐어요. 다시 시도해 주세요.', 400
        elif not member_id or not request.form.get('password'):
            error, status = '아이디와 비밀번호를 입력해 주세요.', 400
        else:
            try:
                with get_conn() as conn, conn.cursor() as cur:
                    cur.execute('SELECT member_id,password_hash,nickname,role,region_code FROM member WHERE member_id=%s', (member_id,))
                    member = cur.fetchone()
                if not member or not check_password_hash(member['password_hash'], request.form['password']):
                    error, status = '아이디 또는 비밀번호가 올바르지 않아요.', 401
                else:
                    session.clear()
                    for key in ('member_id','nickname','role','region_code'):
                        session[key] = member[key]
                    return redirect(next_url)
            except pymysql.MySQLError:
                error, status = 'DB에 연결할 수 없어요. 잠시 후 다시 시도해 주세요.', 503
    return render_template('auth/login.html', error=error, member_id=member_id, next_url=next_url, joined=request.args.get('joined') == '1'), status

@bp.post('/auth/logout')
def logout():
    if not valid_csrf():
        return fail('요청이 만료됐어요. 새로고침 후 다시 시도해 주세요.', 400)
    session.clear()
    return redirect(url_for('main.index'))
