"""4단계: 원본 상가 CSV → store 테이블 모양의 data/clean/store.csv"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]          # 프로젝트 최상위
RAW, CLEAN = ROOT / "data" / "raw", ROOT / "data" / "clean"
MAP = ROOT / "scripts" / "clean" / "industry_map.csv"
CLEAN.mkdir(parents=True, exist_ok=True)

dtype = {"bizesId": str, "ldongCd": str, "indsSclsCd": str}
raw = pd.concat([
    pd.read_csv(RAW / "store_raw_gochang.csv", dtype=dtype, encoding="utf-8-sig"),
    pd.read_csv(RAW / "store_raw_yangsan.csv", dtype=dtype, encoding="utf-8-sig"),
], ignore_index=True)
print("원본:", len(raw))

# 1) 글자 칸 앞뒤 공백 제거 (원본에 '비알코올 ', '법무관련 '처럼 공백이 붙은 값이 있음)
for c in ["bizesId", "bizesNm", "indsSclsCd", "indsSclsNm", "ldongCd", "rdnmAdr"]:
    raw[c] = raw[c].astype("string").str.strip()

# 2) 업종 매핑: 이름이 아니라 소분류 '코드'로 연결 (이름은 바뀌거나 공백이 섞일 수 있음)
m = pd.read_csv(MAP, dtype=str, encoding="utf-8-sig")[["indsSclsCd", "industry_code"]]
raw = raw.merge(m, on="indsSclsCd", how="left")

# 3) store 테이블 칸 이름으로 바꾸기
store = pd.DataFrame({
    "store_id":      raw["bizesId"],
    "name":          raw["bizesNm"].str.slice(0, 100),
    "category":      raw["indsSclsNm"].str.slice(0, 50),
    "industry_code": raw["industry_code"],          # 매핑 안 된 업종은 NULL
    "region_code":   raw["ldongCd"],
    "latitude":      pd.to_numeric(raw["lat"], errors="coerce").round(6),
    "longitude":     pd.to_numeric(raw["lon"], errors="coerce").round(6),
    "address":       raw["rdnmAdr"].str.slice(0, 200),
})

# 4) 테이블 제약조건에 맞지 않는 행 걸러내기
before = len(store)
store = store.dropna(subset=["store_id", "name", "region_code", "latitude", "longitude"])
store = store[store["region_code"].str.fullmatch(r"\d{10}")]
store = store[store["latitude"].between(33, 39) & store["longitude"].between(124, 132)]
store = store.drop_duplicates("store_id")
print("제외된 행:", before - len(store))

store.to_csv(CLEAN / "store.csv", index=False, encoding="utf-8-sig")
print("저장:", len(store), "건 →", CLEAN / "store.csv")
print("업종 매핑됨:", store["industry_code"].notna().sum(), "/ NULL:", store["industry_code"].isna().sum())
print(store["industry_code"].value_counts(dropna=False))
