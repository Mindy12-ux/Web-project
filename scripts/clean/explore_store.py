import pandas as pd

pd.set_option("display.max_rows", 200)
pd.set_option("display.width", 200)

# 코드 칸은 문자열로 읽어야 숫자로 바뀌지 않아요
dtype = {"bizesId": str, "ldongCd": str,
         "indsLclsCd": str, "indsMclsCd": str, "indsSclsCd": str}

g = pd.read_csv("data/raw/store_raw_gochang.csv", dtype=dtype, encoding="utf-8-sig")
y = pd.read_csv("data/raw/store_raw_yangsan.csv", dtype=dtype, encoding="utf-8-sig")
g["sigungu"] = "고창"
y["sigungu"] = "양산"
df = pd.concat([g, y], ignore_index=True)

print("=== 1. 전체 건수 ===")
print(df["sigungu"].value_counts(), "\n")

print("=== 2. 빈 값 개수 (store 테이블에 들어갈 칸) ===")
cols = ["bizesId", "bizesNm", "indsSclsNm", "ldongCd", "lat", "lon", "rdnmAdr"]
print(df[cols].isna().sum(), "\n")

print("=== 3. 중복 bizesId 개수 ===")
print(df["bizesId"].duplicated().sum(), "\n")

print("=== 4. ldongCd 자릿수 / 서로 다른 코드 개수 ===")
print(df["ldongCd"].str.len().value_counts())
print("서로 다른 법정동코드:", df["ldongCd"].nunique(), "\n")

print("=== 5. 대분류 ===")
print(df.groupby(["indsLclsNm", "sigungu"]).size().unstack(fill_value=0), "\n")

print("=== 6. 중분류 ===")
print(df.groupby(["indsLclsNm", "indsMclsNm"]).size().sort_values(ascending=False), "\n")

# 소분류 전체 목록은 파일로 저장 → 매핑표의 기초가 돼요
sub = (df.groupby(["indsLclsNm", "indsMclsNm", "indsSclsCd", "indsSclsNm", "sigungu"])
         .size().unstack(fill_value=0).reset_index())
sub["합계"] = sub[["고창", "양산"]].sum(axis=1)
sub = sub.sort_values("합계", ascending=False)
sub.to_csv("data/clean/category_list.csv", index=False, encoding="utf-8-sig")
print("=== 7. 소분류 ===")
print("소분류 종류 수:", len(sub))
print("저장: data/clean/category_list.csv")