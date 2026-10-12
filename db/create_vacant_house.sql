-- grade_code + vacant_house 테이블 만들기 (MariaDB)
-- vacant_house가 region을 참조하니까 itda DB와 region 테이블이 이미 있어야 함. 순서 조심하기

USE itda;

-- 지우기 (자식 → 부모 순서). 처음 만들 때는 주석 처리해도 됨
-- 주의: 안에 들어 있던 데이터도 전부 사라짐
-- DROP TABLE IF EXISTS vacant_house;
-- DROP TABLE IF EXISTS grade_code;

-- 2. grade_code : 등급 설명서 (4줄) - 부모 테이블이라 먼저 만든다
CREATE TABLE IF NOT EXISTS grade_code (
    grade_code   VARCHAR(2)   NOT NULL COMMENT '1, 2, 3, NA',
    label        VARCHAR(20)  NOT NULL COMMENT '배지 이름',
    description  VARCHAR(50)  NOT NULL COMMENT '짧은 설명',
    sort_order   INT          NOT NULL COMMENT '표시 순서',
    is_default   BOOLEAN      NOT NULL DEFAULT FALSE COMMENT '처음 화면에서 체크 여부',
    PRIMARY KEY (grade_code),
    UNIQUE KEY uq_grade_sort (sort_order)
) ENGINE=InnoDB COMMENT='빈집 등급 설명';

-- 3. vacant_house : 빈집 카드 하나 = 한 줄
CREATE TABLE IF NOT EXISTS vacant_house (
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
