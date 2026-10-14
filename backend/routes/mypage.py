"""A 담당: 내 정보·동의 설정·찜 조회/저장/수정/삭제."""
import secrets
from collections import Counter

import pymysql
from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

from db import get_conn
from routes.auth import login_required, valid_csrf
from routes.common import fail, ok
from routes.events import log_event

bp = Blueprint('mypage', __name__)


def saved_rows(cur):
    """내 찜과 원본 집 정보, 희망업종을 합쳐 반환합니다. 조회만 합니다."""
    member_id = session['member_id']
    cur.execute('''
        SELECT s.*, v.region_code, v.grade_code, v.main_use, v.built_year, v.floor_area,
               r.name AS region_name, g.label AS grade_label
        FROM saved_house s
        JOIN vacant_house v ON v.house_id = s.house_id
        JOIN region r ON r.region_code = v.region_code
        JOIN grade_code g ON g.grade_code = v.grade_code
        WHERE s.member_id = %s
        ORDER BY s.saved_at DESC, s.house_id DESC
    ''', (member_id,))
    houses = cur.fetchall()

    cur.execute('''
        SELECT si.house_id, si.industry_code, i.name
        FROM saved_house_industry si
        JOIN industry i ON i.industry_code = si.industry_code
        WHERE si.member_id = %s ORDER BY i.sort_order
    ''', (member_id,))
    industries_by_house = {}
    for industry in cur.fetchall():
        house_id = industry['house_id']
        industries_by_house.setdefault(house_id, []).append({
            'industry_code': industry['industry_code'],
            'name': industry['name'],
        })
    for house in houses:
        house['industries'] = industries_by_house.get(house['house_id'], [])
    return houses


@bp.route('/mypage', methods=['GET', 'POST'])
@login_required
def mypage():
    """내 정보와 동의만 처리합니다. 사용하지 않는 찜 조회는 제거했습니다."""
    member_id = session['member_id']
    if request.method == 'POST' and not valid_csrf():
        return fail('요청이 만료됐어요. 새로고침해 주세요.', 400)
    try:
        with get_conn() as conn, conn.cursor() as cur:
            if request.method == 'POST':
                consent = request.form.get('share_consent') == 'on'
                cur.execute('UPDATE member SET share_consent=%s WHERE member_id=%s',
                            (consent, member_id))
                conn.commit()
                return redirect(url_for('mypage.mypage', updated='1'))
            cur.execute('''
                SELECT m.member_id, m.nickname, m.email, m.role, m.region_code,
                       m.share_consent, m.created_at, r.name AS affiliation
                FROM member m LEFT JOIN region r ON r.region_code=m.region_code
                WHERE m.member_id=%s
            ''', (member_id,))
            member = cur.fetchone()
        if not member:
            session.clear()
            return redirect(url_for('auth.login'))
        return render_template('mypage.html', member=member,
                               consent=member['share_consent'],
                               updated=request.args.get('updated') == '1')
    except pymysql.MySQLError:
        return fail('DB에 연결할 수 없어요.', 503)


@bp.get('/saved')
@login_required
def saved_page():
    try:
        with get_conn() as conn, conn.cursor() as cur:
            houses = saved_rows(cur)
            cur.execute('SELECT industry_code,name FROM industry WHERE for_wish=TRUE ORDER BY sort_order')
            industries = cur.fetchall()
        # Counter는 동일한 이름이 몇 번 나오는지 세는 도구입니다.
        grades = Counter(house['grade_label'] for house in houses)
        regions = Counter(house['region_name'] for house in houses)
        return render_template('saved.html', houses=houses, industries=industries,
                               grades=grades, regions=regions)
    except pymysql.MySQLError:
        return fail('DB에 연결할 수 없어요.', 503)


@bp.get('/api/saved')
@login_required
def list_saved():
    try:
        with get_conn() as conn, conn.cursor() as cur:
            return ok(saved_rows(cur))
    except pymysql.MySQLError:
        return fail('DB에 연결할 수 없어요.', 503)


def input_error(data, house_id):
    """입력에 문제가 있으면 문구, 정상이면 None을 돌려줍니다."""
    if type(house_id) is not int or house_id <= 0:
        return '유효한 house_id가 필요합니다.'
    memo = data.get('memo')
    preference = data.get('preference')
    industries = data.get('industries', [])
    if memo is not None and (not isinstance(memo, str) or len(memo) > 500):
        return '메모는 500자 이내로 입력해 주세요.'
    if preference is not None and (type(preference) is not int or not 1 <= preference <= 5):
        return '선호도는 1~5 또는 null입니다.'
    if not isinstance(industries, list) or len(industries) > 100:
        return '희망업종은 코드 배열로 보내 주세요.'
    if any(not isinstance(code, str) or len(code) > 20 for code in industries):
        return '희망업종은 코드 배열로 보내 주세요.'
    return None


def write_saved(cur, member_id, house_id, data, old, previous):
    """생성/수정 SQL을 실행합니다. commit은 호출한 함수가 담당합니다."""
    wanted = set(data.get('industries', previous))
    cur.execute('SELECT industry_code FROM industry WHERE for_wish=TRUE')
    allowed = {row['industry_code'] for row in cur.fetchall()}
    if not wanted <= allowed:
        return None, '선택할 수 없는 희망업종이에요.'

    old_values = old or {'memo': None, 'preference': None}
    memo = data.get('memo', old_values['memo'])
    preference = data.get('preference', old_values['preference'])
    if old is None:
        cur.execute('INSERT INTO saved_house(member_id,house_id,memo,preference) VALUES(%s,%s,%s,%s)',
                    (member_id, house_id, memo, preference))
    else:
        cur.execute('UPDATE saved_house SET memo=%s,preference=%s,updated_at=CURRENT_TIMESTAMP WHERE member_id=%s AND house_id=%s',
                    (memo, preference, member_id, house_id))

    cur.execute('DELETE FROM saved_house_industry WHERE member_id=%s AND house_id=%s',
                (member_id, house_id))
    if wanted:
        cur.executemany('INSERT INTO saved_house_industry(member_id,house_id,industry_code) VALUES(%s,%s,%s)',
                        [(member_id, house_id, code) for code in sorted(wanted)])
    return sorted(wanted - previous), None


def emit(kind, region, house_id, added):
    """기록에 실패해도 이미 완료한 찜 요청은 성공으로 처리합니다."""
    try:
        log_event(kind, region, house_id=house_id)
        for code in added:
            log_event('select_industry', region, house_id=house_id, industry_code=code)
    except Exception:
        current_app.logger.warning('행동 기록 연동 실패', exc_info=True)


def mutate(kind, house_id=None):
    """요청 확인 -> DB 확인 -> 저장 -> 기록 순서로 처리합니다."""
    expected = session.get('auth_csrf', '')
    supplied = request.headers.get('X-CSRF-Token', '')
    if not expected or not secrets.compare_digest(expected, supplied):
        return fail('요청이 만료됐어요. 새로고침해 주세요.', 400)
    data = {} if kind == 'unsave' else request.get_json(silent=True)
    if not isinstance(data, dict):
        return fail('JSON 객체를 보내 주세요.', 400)
    if kind == 'save':
        house_id = data.get('house_id')
    error = input_error(data, house_id)
    if error:
        return fail(error, 400)

    member_id = session['member_id']
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # 같은 회원의 동시 변경을 순서대로 처리합니다.
            cur.execute('SELECT member_id FROM member WHERE member_id=%s FOR UPDATE', (member_id,))
            if not cur.fetchone():
                return fail('다시 로그인해 주세요.', 401)
            cur.execute('SELECT region_code FROM vacant_house WHERE house_id=%s', (house_id,))
            house = cur.fetchone()
            if not house:
                return fail('빈집을 찾을 수 없어요.', 404)
            cur.execute('SELECT memo,preference FROM saved_house WHERE member_id=%s AND house_id=%s FOR UPDATE',
                        (member_id, house_id))
            old = cur.fetchone()
            if kind == 'save' and old:
                return fail('이미 찜한 빈집이에요.', 409)
            if kind != 'save' and old is None:
                return fail('내 찜 목록에 없는 빈집이에요.', 404)

            added = []
            if kind == 'unsave':
                cur.execute('DELETE FROM saved_house WHERE member_id=%s AND house_id=%s',
                            (member_id, house_id))
            else:
                cur.execute('SELECT industry_code FROM saved_house_industry WHERE member_id=%s AND house_id=%s',
                            (member_id, house_id))
                previous = {row['industry_code'] for row in cur.fetchall()}
                added, error = write_saved(cur, member_id, house_id, data, old, previous)
                if error:
                    return fail(error, 400)
            conn.commit()
        emit(kind, house['region_code'], house_id, added)
        return ok({'house_id': house_id}, 201 if kind == 'save' else 200)
    except pymysql.MySQLError:
        return fail('찜을 저장할 수 없어요. 잠시 후 다시 시도해 주세요.', 503)


@bp.post('/api/saved')
@login_required
def save_house():
    return mutate('save')


@bp.patch('/api/saved/<int:house_id>')
@login_required
def edit_saved(house_id):
    return mutate('edit', house_id)


@bp.delete('/api/saved/<int:house_id>')
@login_required
def unsave(house_id):
    return mutate('unsave', house_id)
