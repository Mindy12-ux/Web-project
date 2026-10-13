"""[담당 D] 행동 기록 함수 (라우팅 함수 아님 — 다른 라우트 안에서 호출)
다른 담당자는 이렇게 씁니다:
    from routes.events import log_event
    log_event("view_house", region_code, house_id=house_id)
event_type: view_region / view_house / save / edit / unsave / select_industry
"""
from flask import Blueprint, session
from db import get_conn

bp = Blueprint("events", __name__)


def log_event(event_type, region_code, house_id=None, industry_code=None):
    """행동 1건을 interest_event에 기록. 실패해도 원래 요청은 계속 진행."""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO interest_event
                   (member_id, region_code, house_id, industry_code, event_type)
                   VALUES (%s, %s, %s, %s, %s)""",
                (session.get("member_id"), region_code, house_id, industry_code, event_type),
            )
            conn.commit()
    except Exception as e:                       # 기록 실패가 화면 오류로 번지지 않게
        print("log_event 실패:", e)
