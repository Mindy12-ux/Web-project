"""grade_code 4줄 넣기 → MariaDB itda
사용법:  python db/insert_grade_code.py
전제: create_vacant_house.py 로 grade_code 테이블을 먼저 만들어 둘 것 (다시 실행해도 같은 값으로 덮어씀)
"""
import os
from pathlib import Path
import pymysql
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]          # 이 파일 위치: 프로젝트/db/insert_grade_code.py
load_dotenv(ROOT / ".env")

GRADES = [
    # (grade_code, label, description, sort_order, is_default)
    ("1",  "1등급",       "활용 대상",    1, True),
    ("2",  "2등급",       "관리 대상",    2, True),
    ("3",  "3등급",       "정비 대상",    3, False),
    ("NA", "등급 미산정", "현장 등급 전", 4, False),     # 양산시 미산정 7채
]

conn = pymysql.connect(host=os.getenv("DB_HOST"), port=int(os.getenv("DB_PORT", "3306")),
                       user=os.getenv("DB_USER"), password=os.getenv("DB_PASSWORD"),
                       database=os.getenv("DB_NAME"), charset="utf8mb4")
cur = conn.cursor()

cur.executemany("""
    INSERT INTO grade_code (grade_code, label, description, sort_order, is_default)
    VALUES (%s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE label=VALUES(label), description=VALUES(description),
                            sort_order=VALUES(sort_order), is_default=VALUES(is_default)
""", GRADES)
conn.commit()

cur.execute("SELECT grade_code, label, description, sort_order, is_default FROM grade_code ORDER BY sort_order")
for row in cur.fetchall():
    print(row)
conn.close()
