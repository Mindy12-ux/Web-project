-- =========================================================
-- 셀5 · DB 만들기 + 기존 테이블 지우기 (개발 중 다시 만들 때용)
-- =========================================================
CREATE DATABASE IF NOT EXISTS itda
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_general_ci;      -- 한글이 깨지지 않게
USE itda;

-- 지울 때는 적재 순서의 반대로 (자식 → 부모)
-- 주의: 안에 들어 있던 데이터도 전부 사라짐
SET FOREIGN_KEY_CHECKS = 0;                 -- 지우는 동안만 FK 검사 끄기
DROP TABLE IF EXISTS inquiry;
DROP TABLE IF EXISTS interest_event;
DROP TABLE IF EXISTS saved_house_industry;
DROP TABLE IF EXISTS saved_house;
DROP TABLE IF EXISTS region_building_stat;
DROP TABLE IF EXISTS region_store_stat;
DROP TABLE IF EXISTS local_office;
DROP TABLE IF EXISTS contractor;
DROP TABLE IF EXISTS store;
DROP TABLE IF EXISTS vacant_house;
DROP TABLE IF EXISTS member;
DROP TABLE IF EXISTS industry;
DROP TABLE IF EXISTS grade_code;
DROP TABLE IF EXISTS region;
SET FOREIGN_KEY_CHECKS = 1;                 -- 다시 켜기 (꼭!)

-- =========================================================
-- 셀6 · 1단계: 아무것도 가리키지 않는 기준 테이블
-- =========================================================

-- 1. region : 법정동코드 계층표 (시도 → 시군 → 읍면동 → 리)
CREATE TABLE region (
    region_code   CHAR(10)      NOT NULL COMMENT '법정동코드 10자리',
    level         ENUM('sido','sigungu','emd','ri') NOT NULL COMMENT '지역 단계',
    name          VARCHAR(50)   NOT NULL COMMENT '지역 이름',
    parents_code  CHAR(10)      NULL     COMMENT '상위 지역 (시도는 NULL)',
    latitude      DECIMAL(9,6)  NULL     COMMENT '위도 (빈집 있는 리·동만)',
    longitude     DECIMAL(9,6)  NULL     COMMENT '경도 (빈집 있는 리·동만)',
    PRIMARY KEY (region_code),
    CONSTRAINT fk_region_parent
        FOREIGN KEY (parents_code) REFERENCES region (region_code),   -- 자기 자신을 가리킴
    CONSTRAINT ck_region_lat CHECK (latitude  IS NULL OR latitude  BETWEEN 33 AND 39),   -- 위·경도 뒤바뀜 방지
    CONSTRAINT ck_region_lng CHECK (longitude IS NULL OR longitude BETWEEN 124 AND 132)
) ENGINE=InnoDB COMMENT='지역 계층표';

-- 2. grade_code : 등급 설명서 (4줄)
CREATE TABLE grade_code (
    grade_code   VARCHAR(2)   NOT NULL COMMENT '1, 2, 3, NA',
    label        VARCHAR(20)  NOT NULL COMMENT '배지 이름',
    description  VARCHAR(50)  NOT NULL COMMENT '짧은 설명',
    sort_order   INT          NOT NULL COMMENT '표시 순서',
    is_default   BOOLEAN      NOT NULL DEFAULT FALSE COMMENT '처음 화면에서 체크 여부',
    PRIMARY KEY (grade_code),
    UNIQUE KEY uq_grade_sort (sort_order)
) ENGINE=InnoDB COMMENT='빈집 등급 설명';

-- 4. industry : 업종 이름표 (칩, 상권 통계, 행동 기록이 같은 코드 사용)
CREATE TABLE industry (
    industry_code  VARCHAR(20)  NOT NULL COMMENT 'cafe, restaurant ...',
    name           VARCHAR(20)  NOT NULL COMMENT '화면 이름',
    sort_order     INT          NOT NULL COMMENT '표시 순서',
    for_stats      BOOLEAN      NOT NULL DEFAULT FALSE COMMENT '상권 그래프에 사용',
    for_wish       BOOLEAN      NOT NULL DEFAULT FALSE COMMENT '희망 업종 칩에 표시',
    PRIMARY KEY (industry_code),
    UNIQUE KEY uq_industry_name (name)
) ENGINE=InnoDB COMMENT='업종 이름표';

-- 9. member : 회원 (로그인 아이디가 PK, 아이디 변경 기능 없음)
CREATE TABLE member (
    member_id      VARCHAR(50)   NOT NULL COMMENT '로그인 아이디',
    password_hash  VARCHAR(255)  NOT NULL COMMENT '암호화된 비밀번호',
    nickname       VARCHAR(30)   NOT NULL COMMENT '화면 표시 이름',
    email          VARCHAR(100)  NULL     COMMENT '비밀번호 찾기용',
    role           VARCHAR(10)   NOT NULL DEFAULT 'user' COMMENT 'user / admin',
    created_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '가입 시각',
    PRIMARY KEY (member_id),
    UNIQUE KEY uq_member_email (email),                      -- NULL은 여러 개여도 됨
    CONSTRAINT ck_member_role CHECK (role IN ('user','admin'))
) ENGINE=InnoDB COMMENT='회원';

-- =========================================================
-- 셀7 · 2단계: 1단계 테이블을 가리키는 원본 데이터 테이블
-- =========================================================

-- 3. vacant_house : 빈집 카드 하나 = 한 줄
CREATE TABLE vacant_house (
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
) ENGINE=InnoDB COMMENT='빈집';

-- 5. store : 가게 원본 (상가정보)
CREATE TABLE store (
    store_id       VARCHAR(30)   NOT NULL COMMENT '상가업소번호',
    name           VARCHAR(100)  NOT NULL COMMENT '상호',
    category       VARCHAR(50)   NULL     COMMENT '원본 업종 (소분류)',
    industry_code  VARCHAR(20)   NULL     COMMENT '우리 업종 (해당 없으면 NULL)',
    region_code    CHAR(10)      NOT NULL COMMENT '원본의 법정동코드',
    latitude       DECIMAL(9,6)  NOT NULL COMMENT '위도',
    longitude      DECIMAL(9,6)  NOT NULL COMMENT '경도',
    address        VARCHAR(200)  NULL     COMMENT '주소',
    PRIMARY KEY (store_id),
    CONSTRAINT fk_store_industry FOREIGN KEY (industry_code) REFERENCES industry (industry_code),
    CONSTRAINT fk_store_region   FOREIGN KEY (region_code)   REFERENCES region (region_code),
    CONSTRAINT ck_store_lat CHECK (latitude  BETWEEN 33 AND 39),
    CONSTRAINT ck_store_lng CHECK (longitude BETWEEN 124 AND 132)
) ENGINE=InnoDB COMMENT='가게 원본';

-- 7. contractor : 시공 업체 (한 줄 = 한 회사의 업종 등록 하나)
CREATE TABLE contractor (
    registration_no  VARCHAR(10)   NOT NULL COMMENT '사업자등록번호 (화면 표시 안 함)',
    industry         VARCHAR(50)   NOT NULL COMMENT '등록 업종',
    name             VARCHAR(100)  NOT NULL COMMENT '상호',
    phone            VARCHAR(20)   NULL     COMMENT '사무실 전화',
    address          VARCHAR(200)  NULL     COMMENT '사업장 주소',
    region_code      CHAR(10)      NULL     COMMENT '카카오 b_code (주소 변환 실패 시 NULL)',
    latitude         DECIMAL(9,6)  NULL     COMMENT '위도',
    longitude        DECIMAL(9,6)  NULL     COMMENT '경도',
    PRIMARY KEY (registration_no, industry),               -- 복합키: 회사 + 업종
    CONSTRAINT fk_contractor_region FOREIGN KEY (region_code) REFERENCES region (region_code),
    CONSTRAINT ck_contractor_lat CHECK (latitude  IS NULL OR latitude  BETWEEN 33 AND 39),
    CONSTRAINT ck_contractor_lng CHECK (longitude IS NULL OR longitude BETWEEN 124 AND 132)
) ENGINE=InnoDB COMMENT='시공 업체';

-- 8. local_office : 지자체 담당 부서
CREATE TABLE local_office (
    office_id    INT           NOT NULL AUTO_INCREMENT COMMENT '부서 번호',
    region_code  CHAR(10)      NOT NULL COMMENT '소속 시군 행',
    role_type    VARCHAR(10)   NOT NULL COMMENT 'vacant / permit / lodging',
    dept_name    VARCHAR(50)   NOT NULL COMMENT '부서 이름',
    phone        VARCHAR(20)   NULL     COMMENT '부서 대표 전화',
    url          VARCHAR(300)  NULL     COMMENT '시군청 안내 페이지',
    description  VARCHAR(200)  NULL     COMMENT '물어볼 수 있는 내용',
    data_date    DATE          NOT NULL COMMENT '확인한 날짜',
    PRIMARY KEY (office_id),
    CONSTRAINT fk_office_region FOREIGN KEY (region_code) REFERENCES region (region_code),
    CONSTRAINT ck_office_role CHECK (role_type IN ('vacant','permit','lodging'))
) ENGINE=InnoDB COMMENT='지자체 담당 부서';

-- =========================================================
-- 셀8 · 3단계: store로 미리 계산해서 넣는 통계 테이블
-- =========================================================

-- 6. region_store_stat : 동네별·반경별·업종별 가게 수
CREATE TABLE region_store_stat (
    region_code    CHAR(10)     NOT NULL COMMENT '기준 동네 (동그라미)',
    radius_m       INT          NOT NULL COMMENT '반경 m',
    industry_code  VARCHAR(20)  NOT NULL COMMENT '업종',
    store_count    INT          NOT NULL DEFAULT 0 COMMENT '가게 수 (0도 저장)',
    data_date      DATE         NOT NULL COMMENT '상가정보 기준일',
    PRIMARY KEY (region_code, radius_m, industry_code),
    CONSTRAINT fk_rss_region   FOREIGN KEY (region_code)   REFERENCES region (region_code),
    CONSTRAINT fk_rss_industry FOREIGN KEY (industry_code) REFERENCES industry (industry_code),
    CONSTRAINT ck_rss_radius CHECK (radius_m > 0),
    CONSTRAINT ck_rss_count  CHECK (store_count >= 0)
) ENGINE=InnoDB COMMENT='반경별 가게 수';


-- =========================================================
-- 셀9 · 4단계: 사이트를 쓰면서 쌓이는 회원 활동 테이블
-- =========================================================

-- 10. saved_house : 찜 (회원 + 빈집 한 쌍은 한 번만)
CREATE TABLE saved_house (
    member_id   VARCHAR(50)   NOT NULL COMMENT '누가',
    house_id    INT           NOT NULL COMMENT '어떤 빈집',
    memo        VARCHAR(500)  NULL     COMMENT '메모',
    preference  TINYINT       NULL     COMMENT '선호도 1~5',
    saved_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '처음 찜한 시각',
    updated_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                              ON UPDATE CURRENT_TIMESTAMP COMMENT '마지막 수정 시각',
    PRIMARY KEY (member_id, house_id),                       -- 복합키
    CONSTRAINT fk_saved_member FOREIGN KEY (member_id) REFERENCES member (member_id)
        ON DELETE CASCADE,                                   -- 탈퇴하면 찜도 삭제
    CONSTRAINT fk_saved_house  FOREIGN KEY (house_id)  REFERENCES vacant_house (house_id)
        ON DELETE RESTRICT,                                  -- 찜된 빈집은 못 지움
    CONSTRAINT ck_saved_pref CHECK (preference IS NULL OR preference BETWEEN 1 AND 5)
) ENGINE=InnoDB COMMENT='찜';

-- 11. saved_house_industry : 찜 하나에 희망 업종 여러 개
CREATE TABLE saved_house_industry (
    member_id      VARCHAR(50)  NOT NULL COMMENT '어느 찜 (회원)',
    house_id       INT          NOT NULL COMMENT '어느 찜 (빈집)',
    industry_code  VARCHAR(20)  NOT NULL COMMENT '희망 업종',
    PRIMARY KEY (member_id, house_id, industry_code),
    CONSTRAINT fk_shi_saved FOREIGN KEY (member_id, house_id)
        REFERENCES saved_house (member_id, house_id)
        ON DELETE CASCADE,                                   -- 찜 취소하면 업종도 삭제
    CONSTRAINT fk_shi_industry FOREIGN KEY (industry_code) REFERENCES industry (industry_code)
) ENGINE=InnoDB COMMENT='찜의 희망 업종';

-- 12. interest_event : 행동 기록장
CREATE TABLE interest_event (
    event_id       INT          NOT NULL AUTO_INCREMENT COMMENT '기록 번호',
    member_id      VARCHAR(50)  NULL     COMMENT '누가 (비회원 NULL)',
    region_code    CHAR(10)     NOT NULL COMMENT '어느 지역에서',
    house_id       INT          NULL     COMMENT '어떤 집 (지역 보기는 NULL)',
    industry_code  VARCHAR(20)  NULL     COMMENT '고른 업종 (select_industry일 때)',
    event_type     ENUM('view_region','save','edit','unsave','select_industry') NOT NULL COMMENT '행동 종류',
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '발생 시각',
    PRIMARY KEY (event_id),
    CONSTRAINT fk_event_member   FOREIGN KEY (member_id)     REFERENCES member (member_id)
        ON DELETE SET NULL,                                  -- 탈퇴해도 기록은 익명으로 남김
    CONSTRAINT fk_event_region   FOREIGN KEY (region_code)   REFERENCES region (region_code),
    CONSTRAINT fk_event_house    FOREIGN KEY (house_id)      REFERENCES vacant_house (house_id),
    CONSTRAINT fk_event_industry FOREIGN KEY (industry_code) REFERENCES industry (industry_code),
    KEY idx_event_type_time (event_type, created_at)     -- "이번 주 인기 지역" 조회용
) ENGINE=InnoDB COMMENT='행동 기록';















