"""Vercel 진입점. backend/app.py 의 Flask 앱을 그대로 불러와 노출합니다.
로컬 실행은 기존처럼: python -m flask --app backend/app run --debug --port 5000
"""
import sys
from pathlib import Path

# backend/app.py 안의 `from routes import ...`, `from db import ...` 가 동작하도록 backend 폴더를 import 경로에 추가
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app import app  # noqa: E402,F401  (Vercel이 이름 `app`을 찾아 실행합니다)
