"""A 담당: 내 정보·동의 설정·찜 조회/저장/수정/삭제."""
import secrets
from collections import Counter

import pymysql
from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

from db import get_conn
from routes.auth import login_required, valid_csrf
from routes.common import fail, ok
from routes.events import log_event

bp = Blueprint('mypage', __name__)  # 마이페이지·찜 URL 묶음입니다. app.py가 이 Blueprint를 등록합니다.


def saved_rows(cur):  # cur는 DB 커서입니다. 조회한 내 찜 리스트를 saved_page()/list_saved()에 돌려줍니다.
    """내 찜과 원본 집 정보, 희망업종을 합쳐 반환합니다. 조회만 합니다."""
    member_id = session['member_id']  # 현재 로그인 회원 ID는 요청 입력이 아니라 세션에서 가져옵니다.
    # 내 찜과 원본 집·지역·등급을 JOIN합니다. 회원 조건은 아래 WHERE에 적용합니다.
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
    # %s에 세션 회원 ID를 전달하므로 다른 회원의 찜은 조회하지 않습니다.
    houses = cur.fetchall()  # 여러 찜 행을 딕셔너리 리스트로 읽습니다.

    # 여러 개 선택할 수 있는 희망업종은 별도 조회해 집별로 묶습니다.
    cur.execute('''
        SELECT si.house_id, si.industry_code, i.name
        FROM saved_house_industry si
        JOIN industry i ON i.industry_code = si.industry_code
        WHERE si.member_id = %s ORDER BY i.sort_order
    ''', (member_id,))
    # 업종 조회에도 같은 로그인 회원 ID 조건을 사용합니다.
    industries_by_house = {}  # 집 번호를 키, 그 집에 선택한 업종 리스트를 값으로 저장할 딕셔너리입니다.
    for industry in cur.fetchall():
        house_id = industry['house_id']  # 이 집 번호는 폼이 아니라 DB의 희망업종 조회 행에서 가져옵니다.
        # 집별 리스트가 없으면 만들고 업종 코드·이름을 추가합니다.
        industries_by_house.setdefault(house_id, []).append({
            'industry_code': industry['industry_code'],
            'name': industry['name'],
        })
    for house in houses:
        house['industries'] = industries_by_house.get(house['house_id'], [])  # 각 집 딕셔너리에 업종 목록을 붙입니다. 선택이 없으면 빈 리스트입니다.
    return houses  # 반환 리스트가 saved_page()의 houses 또는 API JSON으로 전달됩니다.


@bp.route('/mypage', methods=['GET', 'POST'])  # GET은 내 정보 조회, POST는 선택 동의 변경입니다.
@login_required  # 세션에 로그인 회원 ID가 없으면 아래 기능을 실행하지 않습니다.
def mypage():
    """내 정보와 동의만 처리합니다. 사용하지 않는 찜 조회는 제거했습니다."""
    member_id = session['member_id']  # 다른 사람의 ID를 폼에 보내도 수정 기준은 로그인 세션 ID입니다.
    if request.method == 'POST' and not valid_csrf():  # 조회 GET과 달리 변경 POST에는 폼 보안 토큰을 검사합니다.
        return fail('요청이 만료됐어요. 새로고침해 주세요.', 400)
    try:
        with get_conn() as conn, conn.cursor() as cur:
            if request.method == 'POST':  # 동의 저장 버튼이 보낸 POST인지 구분합니다.
                consent = request.form.get('share_consent') == 'on'  # 체크 시 True, 미체크 시 False를 저장할 값으로 만듭니다.
                # share_consent만 수정합니다. WHERE member_id로 본인 회원 행을 제한합니다.
                cur.execute('UPDATE member SET share_consent=%s WHERE member_id=%s',
                            (consent, member_id))  # 첫 %s는 동의 값, 둘째 %s는 세션 회원 ID입니다.
                conn.commit()  # 동의 변경을 DB에 확정합니다.
                return redirect(url_for('mypage.mypage', updated='1'))  # 302 응답 뒤 브라우저가 GET으로 다시 조회해 저장된 상태를 보여줍니다.
            # GET이면 회원과 소속 지역을 조회합니다. LEFT JOIN이라 지역 없는 일반 회원도 남습니다.
            cur.execute('''
                SELECT m.member_id, m.nickname, m.email, m.role, m.region_code,
                       m.share_consent, m.created_at, r.name AS affiliation
                FROM member m LEFT JOIN region r ON r.region_code=m.region_code
                WHERE m.member_id=%s
            ''', (member_id,))
            # 정보 조회 기준도 로그인 세션의 회원 ID입니다.
            member = cur.fetchone()  # DB 회원 정보를 member 딕셔너리에 받습니다.
        if not member:  # 계정이 삭제되어 DB에 없으면 오래된 세션을 정리합니다.
            session.clear()
            return redirect(url_for('auth.login'))
        return render_template('mypage.html', member=member,  # member와 동의·완료 여부를 mypage.html에 전달합니다.
                               consent=member['share_consent'],
                               updated=request.args.get('updated') == '1')  # updated=1은 회원 ID가 아니라 저장 완료 안내를 띄울 조회값입니다.
    except pymysql.MySQLError:
        return fail('DB에 연결할 수 없어요.', 503)


@bp.get('/saved')  # GET /saved가 이 함수를 실행해 내 찜 HTML을 만듭니다.
@login_required
def saved_page():
    try:
        with get_conn() as conn, conn.cursor() as cur:
            houses = saved_rows(cur)  # DB 커서를 saved_rows()에 넘기고 완성된 집 리스트를 받습니다.
            # 수정 폼의 체크박스 후보는 실제 희망업종 허용 코드만 사용합니다.
            cur.execute('SELECT industry_code,name FROM industry WHERE for_wish=TRUE ORDER BY sort_order')
            industries = cur.fetchall()
        # Counter는 동일한 이름이 몇 번 나오는지 세는 도구입니다.
        grades = Counter(house['grade_label'] for house in houses)  # 등급 이름별 건수를 세어 목록 위의 요약에 표시합니다.
        regions = Counter(house['region_name'] for house in houses)  # 지역 이름별 건수를 셉니다. 집의 지역명이며 회원 소속 지역과는 다릅니다.
        # saved.html에 집·업종 후보·건수를 넘기고 saved_cards.html이 카드로 표시합니다.
        return render_template('saved.html', houses=houses, industries=industries,
                               grades=grades, regions=regions)
    except pymysql.MySQLError:
        return fail('DB에 연결할 수 없어요.', 503)


@bp.get('/api/saved')  # 같은 찜 데이터를 HTML 대신 JSON으로 읽는 GET API입니다.
@login_required
def list_saved():
    try:
        with get_conn() as conn, conn.cursor() as cur:
            return ok(saved_rows(cur))  # saved_rows() 반환 리스트를 공통 성공 JSON에 담아 응답합니다.
    except pymysql.MySQLError:
        return fail('DB에 연결할 수 없어요.', 503)


def input_error(data, house_id):  # data는 요청 JSON, house_id는 JSON 또는 URL에서 읽은 집 번호입니다.
    """입력에 문제가 있으면 문구, 정상이면 None을 돌려줍니다."""
    if type(house_id) is not int or house_id <= 0:  # 집 번호는 양의 정수만 허용합니다. True/False도 집 번호로 받지 않습니다.
        return '유효한 house_id가 필요합니다.'
    memo = data.get('memo')  # 요청에 memo가 없으면 None입니다. 기존값 유지 여부는 write_saved()에서 처리합니다.
    preference = data.get('preference')
    industries = data.get('industries', [])
    if memo is not None and (not isinstance(memo, str) or len(memo) > 500):  # 메모가 있다면 문자열이고 500자 이하여야 합니다.
        return '메모는 500자 이내로 입력해 주세요.'
    if preference is not None and (type(preference) is not int or not 1 <= preference <= 5):  # 선호도는 미설정(None) 또는 정수 1~5만 허용합니다.
        return '선호도는 1~5 또는 null입니다.'
    if not isinstance(industries, list) or len(industries) > 100:  # 희망업종은 코드 문자열들의 리스트로 받아야 합니다.
        return '희망업종은 코드 배열로 보내 주세요.'
    if any(not isinstance(code, str) or len(code) > 20 for code in industries):  # 각 코드의 형식을 검사합니다. 실제 선택 가능 여부는 DB와 비교합니다.
        return '희망업종은 코드 배열로 보내 주세요.'
    return None  # 오류가 없다는 의미이며 mutate()의 error로 돌아갑니다.


def write_saved(cur, member_id, house_id, data, old, previous):  # mutate()가 넘긴 커서·세션 회원 ID·집 번호·JSON·기존 찜·기존 업종을 받습니다.
    """생성/수정 SQL을 실행합니다. commit은 호출한 함수가 담당합니다."""
    wanted = set(data.get('industries', previous))  # industries 키가 없으면 기존 업종 유지, 빈 배열이면 모두 해제입니다. set은 중복을 없앱니다.
    cur.execute('SELECT industry_code FROM industry WHERE for_wish=TRUE')  # DB에서 희망업종으로 허용된 코드 목록을 읽습니다.
    allowed = {row['industry_code'] for row in cur.fetchall()}
    if not wanted <= allowed:  # 요청 코드가 모두 허용된 코드에 포함되는지 검사합니다.
        return None, '선택할 수 없는 희망업종이에요.'  # 신규 업종 없음과 오류 문구를 mutate()의 added, error로 돌려줍니다.

    old_values = old or {'memo': None, 'preference': None}  # 새 찜이면 기본 메모·선호도는 None, 기존 찜이면 저장된 값을 사용합니다.
    memo = data.get('memo', old_values['memo'])  # JSON에 memo 키가 없으면 기존 메모를 유지합니다. 명시적 null은 None으로 바꿉니다.
    preference = data.get('preference', old_values['preference'])  # 선호도도 요청에서 생략하면 기존값을 유지합니다.
    if old is None:  # old가 없으면 최초 추가, 있으면 기존 찜 수정입니다.
        # 찜 본체를 추가합니다. 회원 ID는 세션에서 온 값, 집 번호는 요청에서 온 값입니다.
        cur.execute('INSERT INTO saved_house(member_id,house_id,memo,preference) VALUES(%s,%s,%s,%s)',
                    (member_id, house_id, memo, preference))
    else:
        # 본인 찜의 메모·선호도만 수정하고 수정 시각도 갱신합니다.
        cur.execute('UPDATE saved_house SET memo=%s,preference=%s,updated_at=CURRENT_TIMESTAMP WHERE member_id=%s AND house_id=%s',
                    (memo, preference, member_id, house_id))

    # 해당 찜의 업종 관계를 지운 뒤 선택 목록을 다시 넣습니다. 빈집 원본 삭제가 아닙니다.
    cur.execute('DELETE FROM saved_house_industry WHERE member_id=%s AND house_id=%s',
                (member_id, house_id))
    if wanted:
        # 선택한 업종마다 회원 ID·집 번호·업종 코드 한 행씩 삽입합니다.
        cur.executemany('INSERT INTO saved_house_industry(member_id,house_id,industry_code) VALUES(%s,%s,%s)',
                        [(member_id, house_id, code) for code in sorted(wanted)])
    return sorted(wanted - previous), None  # 새 업종 목록과 오류 없음(None)을 반환합니다. commit은 호출한 mutate()가 한 번 합니다.


def emit(kind, region, house_id, added):  # 찜 저장이 완료된 뒤 다른 담당자의 행동 기록 함수에 연결합니다.
    """기록에 실패해도 이미 완료한 찜 요청은 성공으로 처리합니다."""
    try:
        log_event(kind, region, house_id=house_id)  # save/edit/unsave와 집 지역·집 번호를 이벤트 기록으로 전달합니다.
        for code in added:
            log_event('select_industry', region, house_id=house_id, industry_code=code)  # 기존에 없던 신규 업종만 select_industry로 기록합니다.
    except Exception:
        current_app.logger.warning('행동 기록 연동 실패', exc_info=True)  # 이벤트 실패는 경고로 남깁니다. 이미 확정한 찜 저장은 성공 상태로 유지합니다.


def mutate(kind, house_id=None):  # 추가·수정·취소의 공통 처리입니다. kind는 save/edit/unsave 문자열입니다.
    """요청 확인 -> DB 확인 -> 저장 -> 기록 순서로 처리합니다."""
    expected = session.get('auth_csrf', '')  # 세션에 보관된 CSRF 토큰입니다. member_id가 아닙니다.
    supplied = request.headers.get('X-CSRF-Token', '')  # JavaScript가 헤더에 보낸 토큰입니다. 이 요청은 HTML 폼 대신 JSON을 사용합니다.
    if not expected or not secrets.compare_digest(expected, supplied):  # 토큰이 없거나 일치하지 않으면 DB 변경 전에 중단합니다.
        return fail('요청이 만료됐어요. 새로고침해 주세요.', 400)
    data = {} if kind == 'unsave' else request.get_json(silent=True)  # 취소는 본문 없이 처리하고, 추가·수정은 JSON을 dict로 읽습니다.
    if not isinstance(data, dict):  # JSON이 객체 형태가 아니면 오류입니다.
        return fail('JSON 객체를 보내 주세요.', 400)
    if kind == 'save':  # 추가 요청만 JSON에서 house_id를 읽습니다. 수정·취소는 URL 인자로 받았습니다.
        house_id = data.get('house_id')
    error = input_error(data, house_id)  # 형식 검사 결과가 오류 문자열인지 None인지 받습니다.
    if error:
        return fail(error, 400)

    member_id = session['member_id']  # 찜 소유자는 로그인 세션에서 정합니다. JSON의 임의 회원 ID를 신뢰하지 않습니다.
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # 같은 회원의 동시 변경을 순서대로 처리합니다.
            cur.execute('SELECT member_id FROM member WHERE member_id=%s FOR UPDATE', (member_id,))  # 같은 회원의 동시 변경이 겹치지 않도록 회원 행을 잠급니다.
            if not cur.fetchone():
                return fail('다시 로그인해 주세요.', 401)
            # 실제로 존재하는 빈집인지 요청 집 번호로 조회하고 집 지역도 읽습니다.
            cur.execute('SELECT region_code FROM vacant_house WHERE house_id=%s', (house_id,))
            house = cur.fetchone()  # 이 house는 DB에서 조회한 집 정보입니다. 로그인 회원 정보가 아닙니다.
            if not house:
                return fail('빈집을 찾을 수 없어요.', 404)
            # 회원 ID와 집 번호를 함께 조건으로 본인 찜만 잠금 조회합니다.
            cur.execute('SELECT memo,preference FROM saved_house WHERE member_id=%s AND house_id=%s FOR UPDATE',
                        (member_id, house_id))
            old = cur.fetchone()  # 기존 메모·선호도 딕셔너리 또는 None을 받습니다.
            if kind == 'save' and old:  # 이미 내 찜에 있는데 다시 추가하면 중복입니다.
                return fail('이미 찜한 빈집이에요.', 409)
            if kind != 'save' and old is None:  # 수정·취소는 본인 찜이 반드시 있어야 합니다.
                return fail('내 찜 목록에 없는 빈집이에요.', 404)

            added = []
            if kind == 'unsave':
                cur.execute('DELETE FROM saved_house WHERE member_id=%s AND house_id=%s',  # 본인의 찜 관계만 삭제합니다. vacant_house 원본 집은 유지합니다.
                            (member_id, house_id))
            else:
                # 추가·수정 전에 기존 업종을 읽어 누락된 입력의 보존과 신규 선택 비교에 사용합니다.
                cur.execute('SELECT industry_code FROM saved_house_industry WHERE member_id=%s AND house_id=%s',
                            (member_id, house_id))
                previous = {row['industry_code'] for row in cur.fetchall()}  # 기존 업종 코드를 중복 없는 집합으로 묶습니다.
                added, error = write_saved(cur, member_id, house_id, data, old, previous)  # 여섯 값을 저장 함수로 넘기고 신규 업종 목록·오류를 나눠 받습니다.
                if error:
                    return fail(error, 400)
            conn.commit()  # 찜 정보·업종 변경을 같은 트랜잭션으로 확정합니다.
        emit(kind, house['region_code'], house_id, added)  # 확정 후 행동 기록을 호출합니다. region_code는 집의 지역입니다.
        return ok({'house_id': house_id}, 201 if kind == 'save' else 200)  # JSON 응답은 saved.js로 돌아갑니다. 추가 201, 수정·취소 200입니다.
    except pymysql.MySQLError:
        return fail('찜을 저장할 수 없어요. 잠시 후 다시 시도해 주세요.', 503)


@bp.post('/api/saved')  # POST /api/saved로 찜 추가 요청을 받습니다.
@login_required
def save_house():
    return mutate('save')  # 집 번호 인자를 생략하면 기본 None이며 mutate()가 JSON에서 읽습니다.


@bp.patch('/api/saved/<int:house_id>')  # PATCH URL의 집 번호를 정수 house_id 인자로 받습니다. 예: /api/saved/49.
@login_required
def edit_saved(house_id):
    return mutate('edit', house_id)  # HTTP를 다시 보내지 않고 Python 내부에서 수정 처리를 호출합니다.


@bp.delete('/api/saved/<int:house_id>')  # DELETE URL의 집 번호를 정수로 받아 본인 찜을 취소합니다.
@login_required
def unsave(house_id):
    return mutate('unsave', house_id)  # 공통 함수에 동작 종류와 집 번호를 전달합니다.
