"""[담당 D] 행동 기록 함수
다른 담당자는 이렇게 씁니다:
    from routes.events import log_event
    log_event("view_house", region_code, house_id=house_id)
"""
from flask import Blueprint

bp = Blueprint("events", __name__)


def log_event(event_type, region_code, house_id=None, industry_code=None):
    """지금은 아무것도 하지 않는 임시 버전입니다.
    TODO(D): session의 member_id(비회원 None)와 함께 interest_event에 INSERT.
             실패해도 원래 요청은 계속되도록 try/except.
    """
    return None
