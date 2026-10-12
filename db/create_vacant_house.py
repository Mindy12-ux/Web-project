"""grade_code, vacant_house 테이블 만들기 → MariaDB itda
사용법:  python db/create_vacant_house.py            (없으면 만들기)
         python db/create_vacant_house.py --reset    (지우고 다시 만들기 · 데이터도 삭제됨)
vacant_house가 region을 참조함. 순서 조심하기
"""
import os
import sys
from pathlib import Path
import pymysql
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]          # 이 파일 위치: 프로젝트/db/create_vacant_house.py
load_dotenv(ROOT / ".env")

DROP_SQL = [
    "DROP TABLE IF EXISTS vacant_house",             # 자식 먼저
    "DROP TABLE IF EXISTS grade_code",
]

CREATE_GRADE_CODE = """
CREATE TABLE IF NOT EXISTS grade_code (
    grade_code   VARCHAR(2)   NOT NULL COMMENT '1, 2, 3, NA',
    label        VARCHAR(20)  NOT NULL COMMENT '배지 이름',
    description  VARCHAR(50)  NOT NULL COMMENT '짧은 설명',
    sort_order   INT          NOT NULL COMMENT '표시 순서',
    is_default   BOOLEAN      NOT NULL DEFAULT FALSE COMMENT '처음 화면에서 체크 여부',
    PRIMARY KEY (grade_code),
    UNIQUE KEY uq_grade_sort (sort_order)
) ENGINE=InnoDB COMMENT='빈집 등급 설명'
"""

CREATE_VACANT_HOUSE = """
CREATE TABLE IF NOT EXISTS vacant_house (
    house_id       INT            NOT NULL AUTO_INCREMENT COMMENT '빈집 번호',
    region_code    CHAR(10)       NOT NULL COMMENT '어느 리·동 소속',
    grade_code     VARCHAR(2)     NOT NULL COMMENT '등급',
    main_use       VARCHAR(50)    NULL     COMMENT '주택 유형',
    built_year     SMALLINT       NULL     COMMENT '준공연도 (양산은 NULL)',
    structure      VARCHAR(50)    NULL     COMMENT '구조',
    floor_area     DECIMAL(8,2)   NULL     COMMENT '연면적 ㎡',
    land_area      DECIMAL(10,2)  NULL     COMMENT '대지면적 ㎡ (양산은 NULL)',
    road_contact   VARCHAR(20)    NULL     COMMENT '도로접면 (양산은 NULL)',
    zoning         VARCHAR(30)    NULL     COMMENT '용도지역 (양산은 NULL)',
    data_date      DATE           NOT NULL COMMENT '조사 기준일',
    PRIMARY KEY (house_id),
    CONSTRAINT fk_house_region FOREIGN KEY (region_code) REFERENCES region (region_code),
    CONSTRAINT fk_house_grade  FOREIGN KEY (grade_code)  REFERENCES grade_code (grade_code),
    CONSTRAINT ck_house_year  CHECK (built_year IS NULL OR built_year BETWEEN 1800 AND 2100),
    CONSTRAINT ck_house_floor CHECK (floor_area IS NULL OR floor_area > 0),
    CONSTRAINT ck_house_land  CHECK (land_area  IS NULL OR land_area  > 0)
) ENGINE=InnoDB COMMENT='빈집'
"""

conn = pymysql.connect(host=os.getenv("DB_HOST"), user=os.getenv("DB_USER"),
                       password=os.getenv("DB_PASSWORD"), database=os.getenv("DB_NAME"),
                       charset="utf8mb4")
cur = conn.cursor()

if "--reset" in sys.argv:
    for sql in DROP_SQL:
        cur.execute(sql)
    print("기존 vacant_house, grade_code 삭제")

cur.execute(CREATE_GRADE_CODE)          # 부모(grade_code) 먼저
print("grade_code 생성 완료")
cur.execute(CREATE_VACANT_HOUSE)        # 그다음 자식(vacant_house)
print("vacant_house 생성 완료")

conn.commit()
conn.close()
