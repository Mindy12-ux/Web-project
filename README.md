# Web-project
# 빈집을 잇다

> 농어촌 빈집의 위치와 지역 상권 데이터를 보여주는 지도 기반 웹 서비스를 제공합니다.
> 농어촌 빈집을 "철거의 대상"이 아닌 "다시 쓸 수 있는 자원"으로 바라볼 수 있도록 돕는 것이 우리프로젝트의 목표입니다.
> 에이콘 아카데미 3팀 · 대상 지역: 전북 고창군(52790), 경남 양산시(48330)

<br>

## 1. 프로젝트 개요

### 배경
- 빈집은 꾸준히 늘고 있지만, 지자체의 빈집 정책과 조사는 대부분 철거·정비와 붕괴 위험을 중심으로 이루어진다는 한계점을 인식.
- 빈집을 활용하려는 사람에게 필요한 입지 정보(주변 상권, 시공 업체, 담당 부서)를 제공하는 서비스는 찾기 힘듦.

### 목표
흩어진 공공데이터를 한 장의 지도로 모아, 빈집을 고르고 활용 계획을 세우는 데 필요한 정보를 한곳에서 제공한다.
지자체 공무원은 빈집 수요 통계 대시보드를 이용하여 정책 수립에 활용할 수 있다.

### 주요 기능

| 구분 | 기능 |
| --- | --- |
| 빈집 찾기 (지도) | 시군 → 리·동별 빈집 수 → 빈집 목록 → 상세 정보 순으로 탐색, 등급 필터 |
| 주변 정보 | 반경별·업종별 상가 수, 가까운 가게, 시공 업체, 지자체 담당 부서 연락처 |
| 찜 | 빈집 찜하기, 메모·선호도(1~5)·희망 업종 기록 |
| 대시보드 (일반) | 기간별(7·30·90일) 많이 본 동네, 조회·찜 추이 |
| 대시보드 (공무원) | 관할 시군의 관심 빈집, 정보 제공에 동의한 회원의 관심 내역 |
| 관리 (관리자) | 회원 역할 관리, 공무원 전환용 1회용 초대 코드 발급 |

### 사용자 역할

| 역할 | 설명 |
| --- | --- |
| `user` | 일반 회원. 지도 탐색, 찜, 공개 대시보드 |
| `official` | 공무원. 관리자가 발급한 초대 코드로 전환되며, 자기 시군의 통계만 볼 수 있음 |
| `admin` | 관리자. 회원·초대 코드 관리, 모든 시군의 공무원용 통계 열람 |

### 사용 데이터
- 지자체 빈집 실태조사 결과 (고창군 736채, 양산시 160채 · 총 896채)
- 행정안전부 법정동코드 (지역 계층: 시도 → 시군구 → 읍면동 → 리)
- 소상공인시장진흥공단 상가(상권)정보 (공공데이터포털)
- 건설산업지식정보시스템(KISCON) 건설업체 정보
- 카카오맵 API (지도 표시, 주소 → 좌표 변환)

<br>

## 2. 업무 분장

| 담당 | 이름 | 영역 | 주요 파일 |
| --- | --- | --- | --- |
| A | 김찬우 | 회원·찜 | `routes/auth.py`, `routes/mypage.py`, `templates/auth/`, `mypage.html`, `js/saved.js` |
| B | 전우진 | 메인·지도 | `routes/main.py`, `routes/houses.py`, `index.html`, `map.html`, `js/map.js` |
| C | 서지범 | 카드 정보 탭 (상권·시공 업체·담당 부서) | `routes/stores.py`, `routes/contractors.py`, `partials/card_tabs.html`, `js/card_tabs.js` |
| D | 김민채 | 행동 기록·대시보드·관리 | `routes/events.py`, `routes/trends.py`, `routes/admin.py`, `routes/manage.py`, `dashboard.html`, `manage/` |

데이터 구축 단계 역할
- A: 빈집 원본 통합·정제 (`vacant_house`)
- B: 지역 단위 정리·좌표 변환 (`region`)
- C: 상가·건설업체 수집 (`store`, `contractor`, `region_store_stat`)
- D: 행동 기록 설계 (`interest_event`, `official_invite`)

<br>

## 3. 사용 프로그램

| 구분 | 사용 기술 |
| --- | --- |
| 언어 | Python 3.13, JavaScript, HTML/CSS |
| 백엔드 | Flask (Blueprint로 담당자별 기능 분리, Jinja2 템플릿) |
| DB | MariaDB (`itda` 데이터베이스), PyMySQL |
| 지도 | Kakao Maps JavaScript API |
| 개발 도구 | VS Code, Anaconda, HeidiSQL, Git/GitHub |
| 주요 패키지 | `flask`, `pymysql`, `python-dotenv` |

<br>

## 4. 실행 방법

### ① 저장소 받기
```bash
git clone https://github.com/Mindy12-ux/Web-project.git
cd Web-project
```

### ② 파이썬 환경 만들기
```bash
conda create -n binjip python=3.13
conda activate binjip
pip install flask pymysql python-dotenv
```

### ③ 데이터베이스 만들기
1. MariaDB를 설치하고 실행해요.
2. HeidiSQL로 접속한 뒤 아래 둘 중 하나를 실행해요.
   - 테이블 + 데이터 한 번에: 팀 백업 파일 `itda_backup.sql`을 열어 전체 실행(F9)
   - 테이블 구조만: `db/itda_schema.sql` 전체 실행 (내용은 [5. 테이블 생성 SQL](#5-테이블-생성-sql) 참고)

### ④ `.env` 파일 만들기
프로젝트 최상위 폴더(`backend/`와 같은 위치)에 `.env` 파일을 만들고 자기 환경에 맞게 채워요.

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=비밀번호
DB_NAME=itda

SECRET_KEY=임의의_긴_문자열
KAKAO_JS_KEY=카카오_JavaScript_키
DATA_GO_KR_KEY=공공데이터포털_인증키
```
  ```
- `KAKAO_JS_KEY`를 쓰려면 카카오 개발자 콘솔에서 카카오맵 사용 설정을 켜고, JavaScript SDK 도메인에 `http://127.0.0.1:5000`과 `http://localhost:5000`을 등록해야 한다.

### ⑤ 서버 실행
프로젝트 최상위 폴더에서 실행한다.
```bash
flask --app backend/app run --debug
```
브라우저에서 <http://127.0.0.1:5000> 으로 접속한다.

### 주요 주소

| 주소 | 화면 |
| --- | --- |
| `/` | 메인 |
| `/map` | 빈집 찾기 (지도) |
| `/mypage`, `/saved` | 마이페이지, 내 찜 |
| `/dashboard` | 대시보드 (역할에 따라 공무원용 통계 추가 표시) |
| `/official/verify` | 공무원 인증 (초대 코드 입력) |
| `/manage/members` | 회원·초대 코드 관리 (관리자) |

### 폴더 구조
```
Web-project/
├── backend/
│   ├── app.py            # Flask 시작점 (Blueprint 등록)
│   ├── db.py             # DB 연결 get_conn()
│   ├── routes/           # 담당자별 기능 (auth, mypage, main, houses, stores,
│   │                     #   contractors, events, trends, admin, manage)
│   ├── templates/        # Jinja2 화면
│   └── static/           # css, js, img
├── db/                   # 테이블 생성 SQL
├── scripts/              # 데이터 적재·테스트 기록 스크립트
└── .env                  # 개인 설정 (커밋 금지)
```

<br>

## 5. 테이블 생성 SQL

테이블 13개, 외래키 21개로 구성되어 있음. 파일은 `db/itda_schema.sql`에 있음.

| 영역 | 테이블 |
| --- | --- |
| 기준표 | `region` 지역 계층, `grade_code` 빈집 등급, `industry` 업종 |
| 빈집 | `vacant_house` 빈집 |
| 지역 주변 정보 | `store` 가게, `region_store_stat` 반경별 가게 수, `contractor` 시공 업체, `local_office` 지자체 담당 부서 |
| 회원 활동 | `member` 회원, `saved_house` 찜, `saved_house_industry` 찜의 희망 업종, `interest_event` 행동 기록, `official_invite` 공무원 초대 코드 |

- 다른 표를 참조하지 않는 표부터 순서대로 만들었기 때문에, 위에서부터 그대로 실행하면 됨.
- `interest_event.event_type`: `view_region`, `view_house`, `save`, `edit`, `unsave`, `select_industry`
- `region.level`: `sido`, `sigungu`, `emd`, `ri`