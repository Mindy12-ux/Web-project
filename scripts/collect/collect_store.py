import os, time, requests, pandas as pd
from dotenv import load_dotenv
load_dotenv()

URL = "https://apis.data.go.kr/B553077/api/open/sdsc2/storeListInDong"
TARGETS = {"gochang": "52790", "yangsan": "48330"}   # 1단계 결과에 맞게 고창 코드 수정

def fetch_all(code):
    rows, page = [], 1
    while True:
        r = requests.get(URL, params={
            "serviceKey": os.environ["DATA_GO_KR_KEY"], "divId": "signguCd", "key": code,
            "numOfRows": 1000, "pageNo": page, "type": "json"}, timeout=30)
        body = r.json().get("body", {})
        items = body.get("items", [])
        rows += items
        print(f"{code} {page}페이지: 누적 {len(rows)} / {body.get('totalCount')}")
        if not items or len(rows) >= int(body.get("totalCount", 0)):
            return rows
        page += 1
        time.sleep(0.3)

os.makedirs("data/raw", exist_ok=True)
for name, code in TARGETS.items():
    df = pd.DataFrame(fetch_all(code))
    df.to_csv(f"data/raw/store_raw_{name}.csv", index=False, encoding="utf-8-sig")