"""A 담당: 내 찜 CRUD와 동의 설정. D의 log_event 인터페이스에 연결."""
import secrets
import pymysql
from flask import Blueprint,render_template,request,session,redirect,url_for,current_app
from db import get_conn
from routes.auth import login_required,valid_csrf
from routes.common import ok,fail
from routes.events import log_event
bp=Blueprint('mypage',__name__)

def saved_rows(cur):
    cur.execute('''SELECT s.*,v.region_code,v.grade_code,v.main_use,v.built_year,v.floor_area,
        r.name AS region_name,g.label AS grade_label FROM saved_house s
        JOIN vacant_house v ON v.house_id=s.house_id JOIN region r ON r.region_code=v.region_code
        JOIN grade_code g ON g.grade_code=v.grade_code
        WHERE s.member_id=%s ORDER BY s.saved_at DESC,s.house_id DESC''',(session['member_id'],))
    rows=cur.fetchall()
    cur.execute('''SELECT si.house_id,si.industry_code,i.name FROM saved_house_industry si
        JOIN industry i ON i.industry_code=si.industry_code WHERE si.member_id=%s
        ORDER BY i.sort_order''',(session['member_id'],))
    groups={}
    for item in cur.fetchall():groups.setdefault(item['house_id'],[]).append({'industry_code':item['industry_code'],'name':item['name']})
    for row in rows:row['industries']=groups.get(row['house_id'],[])
    return rows

@bp.route('/mypage',methods=['GET','POST'])
@login_required
def mypage():
    try:
        with get_conn() as c,c.cursor() as q:
            if request.method=='POST':
                if not valid_csrf():return fail('요청이 만료됐어요. 새로고침해 주세요.',400)
                q.execute('UPDATE member SET share_consent=%s WHERE member_id=%s',(request.form.get('share_consent')=='on',session['member_id']))
                c.commit();return redirect(url_for('mypage.mypage',updated='1'))
            q.execute('SELECT m.member_id,m.nickname,m.email,m.role,m.region_code,m.share_consent,m.created_at,r.name AS affiliation FROM member m LEFT JOIN region r ON r.region_code=m.region_code WHERE m.member_id=%s',(session['member_id'],));member=q.fetchone()
            if not member:
                session.clear();return redirect(url_for('auth.login'))
            rows=saved_rows(q)
            q.execute('SELECT industry_code,name FROM industry WHERE for_wish=TRUE ORDER BY sort_order');industries=q.fetchall()
        grades={};regions={}
        for row in rows:
            grades[row['grade_label']]=grades.get(row['grade_label'],0)+1
            regions[row['region_name']]=regions.get(row['region_name'],0)+1
        return render_template('mypage.html',member=member,consent=member['share_consent'],updated=request.args.get('updated')=='1',houses=rows,industries=industries,grades=grades,regions=regions)
    except pymysql.MySQLError:return fail('DB에 연결할 수 없어요.',503)

@bp.get('/api/saved')
@login_required
def list_saved():
    try:
        with get_conn() as c,c.cursor() as q:return ok(saved_rows(q))
    except pymysql.MySQLError:return fail('DB에 연결할 수 없어요.',503)

def emit(kind,region,house,industries=()):
    try:
        log_event(kind,region,house_id=house)
        for code in industries:log_event('select_industry',region,house_id=house,industry_code=code)
    except Exception:
        current_app.logger.warning('행동 기록 연동 실패',exc_info=True)

def mutate(kind,house_id=None):
    expected=session.get('auth_csrf','');supplied=request.headers.get('X-CSRF-Token','')
    if not expected or not secrets.compare_digest(expected,supplied):return fail('요청이 만료됐어요. 새로고침해 주세요.',400)
    data={} if kind=='unsave' else request.get_json(silent=True)
    if not isinstance(data,dict):return fail('JSON 객체를 보내 주세요.',400)
    if kind=='save':house_id=data.get('house_id')
    if type(house_id) is not int or house_id<=0:return fail('유효한 house_id가 필요합니다.',400)
    if kind!='unsave':
        if 'memo' in data and data['memo'] is not None and (not isinstance(data['memo'],str) or len(data['memo'])>500):return fail('메모는 500자 이내로 입력해 주세요.',400)
        if 'preference' in data and data['preference'] is not None and (type(data['preference']) is not int or not 1<=data['preference']<=5):return fail('선호도는 1~5 또는 null입니다.',400)
        if 'industries' in data and (not isinstance(data['industries'],list) or len(data['industries'])>100 or any(not isinstance(x,str) or len(x)>20 for x in data['industries'])):return fail('희망업종은 코드 배열로 보내 주세요.',400)
    try:
        with get_conn() as c,c.cursor() as q:
            # Same-member changes serialize on the member row, including concurrent saves.
            q.execute('SELECT member_id FROM member WHERE member_id=%s FOR UPDATE',(session['member_id'],))
            if not q.fetchone():return fail('다시 로그인해 주세요.',401)
            q.execute('SELECT region_code FROM vacant_house WHERE house_id=%s',(house_id,));house=q.fetchone()
            if not house:return fail('빈집을 찾을 수 없어요.',404)
            q.execute('SELECT memo,preference FROM saved_house WHERE member_id=%s AND house_id=%s FOR UPDATE',(session['member_id'],house_id));old=q.fetchone()
            if kind=='save' and old:return fail('이미 찜한 빈집이에요.',409)
            if kind!='save' and not old:return fail('내 찜 목록에 없는 빈집이에요.',404)
            q.execute('SELECT industry_code FROM saved_house_industry WHERE member_id=%s AND house_id=%s',(session['member_id'],house_id));previous={r['industry_code'] for r in q.fetchall()}
            added=[]
            if kind=='unsave':q.execute('DELETE FROM saved_house WHERE member_id=%s AND house_id=%s',(session['member_id'],house_id))
            else:
                wanted=set(data.get('industries',previous))
                q.execute('SELECT industry_code FROM industry WHERE for_wish=TRUE');allowed={r['industry_code'] for r in q.fetchall()}
                if not wanted<=allowed:return fail('선택할 수 없는 희망업종이에요.',400)
                memo=data.get('memo',old['memo'] if old else None);pref=data.get('preference',old['preference'] if old else None)
                if kind=='save':q.execute('INSERT INTO saved_house(member_id,house_id,memo,preference) VALUES(%s,%s,%s,%s)',(session['member_id'],house_id,memo,pref))
                else:q.execute('UPDATE saved_house SET memo=%s,preference=%s,updated_at=CURRENT_TIMESTAMP WHERE member_id=%s AND house_id=%s',(memo,pref,session['member_id'],house_id))
                q.execute('DELETE FROM saved_house_industry WHERE member_id=%s AND house_id=%s',(session['member_id'],house_id))
                if wanted:q.executemany('INSERT INTO saved_house_industry(member_id,house_id,industry_code) VALUES(%s,%s,%s)',[(session['member_id'],house_id,x) for x in sorted(wanted)])
                added=sorted(wanted-previous)
            c.commit()
        emit(kind,house['region_code'],house_id,added)
        return ok({'house_id':house_id},201 if kind=='save' else 200)
    except pymysql.MySQLError:return fail('찜을 저장할 수 없어요. 잠시 후 다시 시도해 주세요.',503)

@bp.post('/api/saved')
@login_required
def save_house():return mutate('save')
@bp.patch('/api/saved/<int:house_id>')
@login_required
def edit_saved(house_id):return mutate('edit',house_id)
@bp.delete('/api/saved/<int:house_id>')
@login_required
def unsave(house_id):return mutate('unsave',house_id)

@bp.get('/saved')
@login_required
def saved_page():
    try:
        with get_conn() as c,c.cursor() as q:
            rows=saved_rows(q)
            q.execute('SELECT industry_code,name FROM industry WHERE for_wish=TRUE ORDER BY sort_order')
            industries=q.fetchall()
        grades={};regions={}
        for row in rows:
            grades[row['grade_label']]=grades.get(row['grade_label'],0)+1
            regions[row['region_name']]=regions.get(row['region_name'],0)+1
        return render_template('saved.html',houses=rows,industries=industries,grades=grades,regions=regions)
    except pymysql.MySQLError:
        return fail('DB에 연결할 수 없어요.',503)
