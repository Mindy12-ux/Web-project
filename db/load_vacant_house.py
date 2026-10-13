"""7단계: data/clean/vacant_house.csv → MariaDB itda.vacant_house
사용법:  python db/load_vacant_house.py
전제:    create_vacant_house.py → insert_grade_code.py 실행, region 테이블 적재, clean_vacant_house.py 로 CSV 생성
다시 실행해도 house_id가 같으면 같은 행을 덮어씀 (CSV 행 순서가 바뀌면 house_id도 바뀌니 주의)
"""
import os
from pathlib import Path
import pandas as pd
import pymysql
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]          # 이 파일 위치: 프로젝트/db/load_vacant_house.py
CLEAN = ROOT / "data" / "clean"
CSV = CLEAN / "vacant_house.csv"
load_dotenv(ROOT / ".env")

if not CSV.exists():
    raise SystemExit(f"{CSV} 없음 → python scripts/clean/clean_vacant_house.py 먼저 실행")

conn = pymysql.connect(host=os.getenv("DB_HOST"), user=os.getenv("DB_USER"),
                       password=os.getenv("DB_PASSWORD"), database=os.getenv("DB_NAME"),
                       charset="utf8mb4")
cur = conn.cursor()

# 1) 부모 테이블 확인 (vacant_house가 grade_code, region을 참조하므로 먼저 채워져 있어야 함)
cur.execute("SELECT grade_code FROM grade_code")
known_grade = {r[0] for r in cur.fetchall()}
cur.execute("SELECT region_code FROM region")
known_region = {r[0] for r in cur.fetchall()}
if not known_grade:
    raise SystemExit("grade_code가 비어 있음 → python db/insert_grade_code.py 먼저 실행")
if not known_region:
    raise SystemExit("region이 비어 있음 → region 먼저 적재")

# 2) 빈 칸만 NULL로 읽기 (기본 설정이면 등급 'NA'가 NaN으로 바뀌어 버림)
vh = pd.read_csv(CSV, dtype=str, encoding="utf-8-sig", keep_default_na=False, na_values=[""])
print("CSV:", len(vh), "건")

# 3) region, grade_code에 있는 코드만 적재, 나머지는 따로 저장
good = vh["region_code"].isin(known_region) & vh["grade_code"].isin(known_grade)
ok, failed = vh[good], vh[~good]
if len(failed):
    failed.to_csv(CLEAN / "vacant_house_failed.csv", index=False, encoding="utf-8-sig")
    print("region에 없는 코드:", failed.loc[~failed["region_code"].isin(known_region), "region_code"].nunique(), "종,",
          "grade_code에 없는 코드:", failed.loc[~failed["grade_code"].isin(known_grade), "grade_code"].nunique(), "종,",
          len(failed), "건 → vacant_house_failed.csv")

def null_if_nan(v):
    return None if pd.isna(v) else v                # NaN → NULL (pymysql은 NaN을 못 보냄)


rows = [(int(r.house_id), r.region_code, r.grade_code, null_if_nan(r.main_use),
         None if pd.isna(r.built_year) else int(r.built_year), null_if_nan(r.structure),
         null_if_nan(r.floor_area), null_if_nan(r.land_area), null_if_nan(r.road_contact),
         null_if_nan(r.zoning), r.data_date)
        for r in ok.itertuples(index=False)]
cur.executemany("""
    INSERT INTO vacant_house (house_id, region_code, grade_code, main_use, built_year, structure,
                              floor_area, land_area, road_contact, zoning, data_date)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE region_code=VALUES(region_code), grade_code=VALUES(grade_code),
        main_use=VALUES(main_use), built_year=VALUES(built_year), structure=VALUES(structure),
        floor_area=VALUES(floor_area), land_area=VALUES(land_area), road_contact=VALUES(road_contact),
        zoning=VALUES(zoning), data_date=VALUES(data_date)
""", rows)
conn.commit()
print("vacant_house:", len(ok), "건 적재")

# 4) 확인: 테이블 전체 건수와 등급별 건수
cur.execute("SELECT COUNT(*) FROM vacant_house")
total = cur.fetchone()[0]
if total != len(ok):
    print("주의: 테이블에", total, "건 → 이번 적재", len(ok), "건과 다름 (이전에 넣은 다른 데이터가 남아 있는지 확인)")
cur.execute("""
    SELECT g.grade_code, g.label, COUNT(v.house_id)
    FROM grade_code g LEFT JOIN vacant_house v ON v.grade_code = g.grade_code
    GROUP BY g.grade_code, g.label, g.sort_order
    ORDER BY g.sort_order
""")
for code, label, n in cur.fetchall():
    print(f"  {code:>2} {label}: {n}건")
conn.close()
