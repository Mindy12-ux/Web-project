"""DB 접속은 이 함수 하나만 씁니다. 파일마다 pymysql.connect()를 따로 쓰지 마세요.

사용 예:
    from db import get_conn
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM region WHERE region_code = %s", (code,))   # 값은 항상 %s 로
        rows = cur.fetchall()                    # [{'region_code': ..., 'name': ...}, ...]
    # INSERT/UPDATE/DELETE 뒤에는 conn.commit() 필요
"""
import os
from pathlib import Path
import pymysql
from pymysql.cursors import DictCursor

BACKEND_DIR = Path(__file__).resolve().parent


def _ssl_options():
    """DB_SSL_CA 가 있을 때만 TLS를 씀 (Aiven 같은 원격 DB용). 로컬 MariaDB는 비워 둠.
    값은 backend 폴더 기준 상대 경로, 예: certs/aiven-ca.pem"""
    ca = os.getenv("DB_SSL_CA")
    return {"ca": str(BACKEND_DIR / ca)} if ca else None


def get_conn():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "itda"),
        charset="utf8mb4",
        cursorclass=DictCursor,                  # 결과를 dict로 받음 → 그대로 jsonify 가능
        ssl=_ssl_options(),
    )
