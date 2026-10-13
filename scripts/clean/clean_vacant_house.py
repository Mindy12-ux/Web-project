"""6단계: 원본 빈집 CSV(고창·양산) → vacant_house 테이블 모양의 data/clean/vacant_house.csv

원본 (data/raw/ 에 저장해 둘 것)
  vacant_raw_gochang.csv : 전북특별자치도 고창군_빈집현황 (공공데이터포털 15151879, 1,288행)
  vacant_raw_yangsan.csv : 경상남도 양산시_빈집 현황   (공공데이터포털 15144630, 160행)
지역 코드표
  scripts/clean/vacant_region_map.csv : 법정동코드 (행정표준코드관리시스템 code.go.kr 에서 양산시·고창군만 정리)
"""
from pathlib import Path
import re
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]          # 프로젝트 최상위
RAW, CLEAN = ROOT / "data" / "raw", ROOT / "data" / "clean"
MAP = ROOT / "scripts" / "clean" / "vacant_region_map.csv"
CLEAN.mkdir(parents=True, exist_ok=True)

# 고창 원본의 건축년도 1901은 '연도 모름'으로 보고 NULL 처리
#   근거: 빈집 736채 중 연도가 있는 562채에서 1901이 52채 (다음으로 많은 해는 1995의 23채, 1902~1919는 해마다 1~7채)
#   원본 설명에는 이 규칙이 적혀 있지 않음 → 그대로 두려면 set() 으로 바꾸기
UNKNOWN_BUILT_YEARS = {1901}


def read_raw(path):
    """글자는 전부 문자열로 읽고, 앞뒤 공백 제거, 빈 칸은 NULL(NaN)로"""
    for enc in ("utf-8-sig", "cp949"):
        try:
            df = pd.read_csv(path, dtype=str, encoding=enc, keep_default_na=False)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"인코딩을 읽지 못함: {path}")
    df = df.apply(lambda c: c.str.strip())
    return df.mask(df == "")


def grade_of(s):
    """'1등급' → '1', 등급이 비었거나 '1~3등급'이 아니면 'NA'"""
    return s.str.extract(r"^([123])\s*등급")[0].fillna("NA")


def area_of(s):
    """㎡ 숫자로. 비었거나 0 이하는 NULL (테이블 CHECK: 0보다 커야 함)"""
    v = pd.to_numeric(s, errors="coerce").round(2)
    return v.where(v > 0)


m = pd.read_csv(MAP, dtype=str, encoding="utf-8-sig")
code_to_name = dict(zip(m["region_code"], m["name"]))
name_to_code = dict(zip(m["name"], m["region_code"]))

# ---------------------------------------------------------------- 고창군
go = read_raw(RAW / "vacant_raw_gochang.csv")
print("고창 원본:", len(go), "행")
go = go[go["빈집판정결과"] == "해당"].copy()          # '미해당'(거주 확인·멸실·비주택 등)은 빈집이 아님
print("고창 빈집(해당):", len(go), "행")

# 법정동코드 10자리 = 자치단체코드(5) + 법정동(번호)(3) + 법정리(번호)(2)
go["region_code"] = (go["자치단체코드"].str.zfill(5) + go["법정동(번호)"].str.zfill(3)
                     + go["법정리(번호)"].str.zfill(2))
unknown = sorted(set(go["region_code"]) - set(code_to_name))
if unknown:
    raise SystemExit(f"법정동코드표에 없는 코드: {unknown}")
differ = go[go["region_code"].map(code_to_name) != go["소재지(바뀐후)"]]
if len(differ):
    print("경고: 코드와 소재지 이름이 다른 행", len(differ), "건")
    print(differ[["소재지(바뀐후)", "region_code"]].drop_duplicates().head(10).to_string(index=False))

built = pd.to_numeric(go["건축년도"], errors="coerce").round()
built = built.where(built.between(1800, 2100) & ~built.isin(UNKNOWN_BUILT_YEARS)).astype("Int64")
date = pd.to_datetime(go["빈집판정일자"], errors="coerce").fillna(pd.to_datetime(go["등급산정일자"], errors="coerce"))

gochang = pd.DataFrame({
    "region_code":  go["region_code"],
    "grade_code":   grade_of(go["등급판정결과"]),
    "main_use":     go["용도"].str.slice(0, 50),
    "built_year":   built,
    "structure":    go["건축물대장 주구조"].str.slice(0, 50),
    "floor_area":   area_of(go["연면적"]),
    "land_area":    area_of(go["대지면적"]),
    "road_contact": go["도로접면"].str.slice(0, 20),
    "zoning":       go["용도지역"].str.slice(0, 30),
    "data_date":    date.dt.strftime("%Y-%m-%d"),
})

# ---------------------------------------------------------------- 양산시
ys = read_raw(RAW / "vacant_raw_yangsan.csv")
print("양산 빈집:", len(ys), "행")

# '경상남도 양산시 물금읍 물금리 406-**' → 지번(숫자·-·* 부분) 앞까지가 동·리 이름
ys["region_name"] = ys["소재지"].str.replace(r"\s+산?\s*\d[\d\-\*]*.*$", "", regex=True)
ys["region_code"] = ys["region_name"].map(name_to_code)
bad = ys[ys["region_code"].isna()]
if len(bad):
    raise SystemExit(f"법정동코드표에 없는 소재지: {sorted(set(bad['region_name']))}")

yangsan = pd.DataFrame({
    "region_code":  ys["region_code"],
    "grade_code":   grade_of(ys["빈집등급"]),
    "main_use":     pd.NA,                        # 양산 원본에 없음
    "built_year":   pd.array([pd.NA] * len(ys), dtype="Int64"),   # 양산은 NULL
    "structure":    ys["건축물구조"].str.slice(0, 50),
    "floor_area":   area_of(ys["연면적"]),
    "land_area":    float("nan"),                 # 양산은 NULL (숫자 칸이라 NaN)
    "road_contact": pd.NA,                        # 양산은 NULL
    "zoning":       pd.NA,                        # 양산은 NULL
    "data_date":    pd.to_datetime(ys["데이터기준일"], errors="coerce").dt.strftime("%Y-%m-%d"),
})

# ---------------------------------------------------------------- 합치기
out = pd.concat([gochang, yangsan], ignore_index=True)
if out["data_date"].isna().any():
    raise SystemExit(f"조사 기준일이 비어 있는 행: {int(out['data_date'].isna().sum())}건")
out.insert(0, "house_id", range(1, len(out) + 1))   # AUTO_INCREMENT 번호 (고창 → 양산 순)

out.to_csv(CLEAN / "vacant_house.csv", index=False, encoding="utf-8-sig", float_format="%.2f")
print("저장:", len(out), "건 →", CLEAN / "vacant_house.csv")

# ---------------------------------------------------------------- 점검용 출력
out["source"] = ["고창"] * len(gochang) + ["양산"] * len(yangsan)
print("\n[등급별]")
print(pd.crosstab(out["source"], out["grade_code"]))
print("\n[지역 수]", out.groupby("source")["region_code"].nunique().to_dict())
print("\n[빈집 많은 지역 상위 10]")
top = out.groupby(["source", "region_code"]).size().sort_values(ascending=False).head(10)
print(top.rename("빈집 수").reset_index().assign(지역=lambda d: d["region_code"].map(code_to_name)).to_string(index=False))
print("\n[NULL 개수]")
print(out.drop(columns="source").isna().sum().to_string())
print("\n[준공연도 많은 값 상위 8]  ← 1901처럼 한 해에 몰려 있으면 '연도 모름'인지 확인")
print(out["built_year"].value_counts().head(8).to_string())
