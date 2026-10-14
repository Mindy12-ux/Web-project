"""빈집을 잇다 — Flask 앱 시작점
실행 (프로젝트 최상위에서):  flask --app backend/app run --debug
이 파일은 Blueprint를 '등록'만 합니다. 기능 코드는 routes/ 안의 각자 파일에 씁니다.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, session

ROOT = Path(__file__).resolve().parents[1]      # 프로젝트 최상위 (backend의 한 단계 위)
load_dotenv(ROOT / ".env")

from routes import auth, mypage, main, houses, stores, contractors, events, trends, admin, manage  # noqa: E402

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-change-me")   # 세션 암호화 키
app.config["JSON_AS_ASCII"] = False
app.json.ensure_ascii = False                    # JSON 응답에서 한글이 \uXXXX로 바뀌지 않게

# 담당자별 Blueprint 등록 (새 파일을 만들 때만 여기에 한 줄 추가)
for module in (auth, mypage, main, houses, stores, contractors, events, trends, admin, manage):
    app.register_blueprint(module.bp)


@app.context_processor
def inject_common():
    """모든 템플릿에서 쓸 수 있는 값: 로그인 정보, 카카오맵 키"""
    return {
        "me": {
            "member_id": session.get("member_id"),
            "nickname": session.get("nickname"),
            "role": session.get("role"),
        },
        "KAKAO_JS_KEY": os.getenv("KAKAO_JS_KEY", ""),
    }


if __name__ == "__main__":                       # python backend/app.py 로도 실행 가능
    app.run(debug=True)
