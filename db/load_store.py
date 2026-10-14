"""5단계: industry.csv, store.csv → MariaDB itda"""
import os
from pathlib import Path
import pandas as pd
import pymysql
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]          # 이 파일 위치: 프로젝트/db/load_store.py
CLEAN = ROOT / "data" / "clean"
load_dotenv(ROOT / ".env")

conn = pymysql.connect(host=os.getenv("DB_HOST"), port=int(os.getenv("DB_PORT", "3306")),
                       user=os.getenv("DB_USER"), password=os.getenv("DB_PASSWORD"),
                       database=os.getenv("DB_NAME"), charset="utf8mb4")
cur = conn.cursor()

# 1) industry 먼저 (store가 industry를 참조하므로)
ind = pd.read_csv(CLEAN / "industry.csv", dtype={"industry_code": str}, encoding="utf-8-sig")
cur.executemany("""
    INSERT INTO industry (industry_code, name, sort_order, for_stats, for_wish)
    VALUES (%s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE name=VALUES(name), sort_order=VALUES(sort_order),
                            for_stats=VALUES(for_stats), for_wish=VALUES(for_wish)
""", [(r.industry_code, r.name, int(r.sort_order), bool(r.for_stats), bool(r.for_wish))
      for r in ind.itertuples()])
print("industry:", len(ind), "건")

# 2) region에 있는 코드만 적재, 나머지는 따로 저장
store = pd.read_csv(CLEAN / "store.csv", dtype={"store_id": str, "region_code": str,
                                                "industry_code": str}, encoding="utf-8-sig")
cur.execute("SELECT region_code FROM region")
known = {r[0] for r in cur.fetchall()}
ok = store[store["region_code"].isin(known)]
failed = store[~store["region_code"].isin(known)]
if len(failed):
    failed.to_csv(CLEAN / "store_failed.csv", index=False, encoding="utf-8-sig")
    print("region에 없는 코드:", failed["region_code"].nunique(), "종,", len(failed), "건 → store_failed.csv")

ok = ok.astype(object).where(ok.notna(), None)      # NaN → NULL
cur.executemany("""
    INSERT INTO store (store_id, name, category, industry_code, region_code,
                       latitude, longitude, address)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE name=VALUES(name), category=VALUES(category),
        industry_code=VALUES(industry_code), region_code=VALUES(region_code),
        latitude=VALUES(latitude), longitude=VALUES(longitude), address=VALUES(address)
""", ok[["store_id", "name", "category", "industry_code", "region_code",
         "latitude", "longitude", "address"]].values.tolist())
conn.commit()
print("store:", len(ok), "건 적재")
conn.close()
