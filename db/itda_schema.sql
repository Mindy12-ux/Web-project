-- ============================================================
-- 빈집을 잇다 · itda 최종 테이블 구조 (MariaDB)
-- 기준: 팀 최종 백업 itda_backup.sql · 테이블 13개 · 외래키 21개
-- 실행: HeidiSQL에서 파일 열기 → 전체 실행(F9)
-- 표는 참조 순서대로 만들므로 위에서부터 그대로 실행하면 됨
-- ============================================================

CREATE DATABASE IF NOT EXISTS `itda` DEFAULT CHARACTER SET utf8mb4;
USE `itda`;

-- 처음부터 다시 만들 때만 아래 주석을 풀고 실행 (데이터가 모두 지워짐!)
-- SET FOREIGN_KEY_CHECKS = 0;
-- DROP TABLE IF EXISTS `interest_event`, `saved_house_industry`, `saved_house`, `official_invite`, `region_store_stat`, `store`, `contractor`, `local_office`, `vacant_house`, `member`, `industry`, `grade_code`, `region`;
-- SET FOREIGN_KEY_CHECKS = 1;

-- ------------------------------------------------------------
-- ① 기준표 — 다른 표를 참조하지 않음
-- ------------------------------------------------------------

CREATE TABLE `region` (
  `region_code` char(10) NOT NULL COMMENT '법정동코드 10자리',
  `level` enum('sido','sigungu','emd','ri') NOT NULL COMMENT '지역 단계',
  `name` varchar(50) NOT NULL COMMENT '지역 이름',
  `parents_code` char(10) DEFAULT NULL COMMENT '상위 지역 (시도는 NULL)',
  `latitude` decimal(9,6) DEFAULT NULL COMMENT '위도 (빈집 있는 리·동만)',
  `longitude` decimal(9,6) DEFAULT NULL COMMENT '경도 (빈집 있는 리·동만)',
  PRIMARY KEY (`region_code`),
  KEY `fk_region_parent` (`parents_code`),
  CONSTRAINT `fk_region_parent` FOREIGN KEY (`parents_code`) REFERENCES `region` (`region_code`),
  CONSTRAINT `ck_region_lat` CHECK (`latitude` is null or `latitude` between 33 and 39),
  CONSTRAINT `ck_region_lng` CHECK (`longitude` is null or `longitude` between 124 and 132)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='지역 계층표';

CREATE TABLE `grade_code` (
  `grade_code` varchar(2) NOT NULL COMMENT '1, 2, 3, NA',
  `label` varchar(20) NOT NULL COMMENT '배지 이름',
  `description` varchar(50) NOT NULL COMMENT '짧은 설명',
  `sort_order` int(11) NOT NULL COMMENT '표시 순서',
  `is_default` tinyint(1) NOT NULL DEFAULT 0 COMMENT '처음 화면에서 체크 여부',
  PRIMARY KEY (`grade_code`),
  UNIQUE KEY `uq_grade_sort` (`sort_order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='빈집 등급 설명';

CREATE TABLE `industry` (
  `industry_code` varchar(20) NOT NULL COMMENT 'cafe, restaurant ...',
  `name` varchar(20) NOT NULL COMMENT '화면 이름',
  `sort_order` int(11) NOT NULL COMMENT '표시 순서',
  `for_stats` tinyint(1) NOT NULL DEFAULT 0 COMMENT '상권 그래프에 사용',
  `for_wish` tinyint(1) NOT NULL DEFAULT 0 COMMENT '희망 업종 칩에 표시',
  PRIMARY KEY (`industry_code`),
  UNIQUE KEY `uq_industry_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='업종 이름표';

-- ------------------------------------------------------------
-- ② 회원·빈집 — region, grade_code 참조
-- ------------------------------------------------------------

CREATE TABLE `member` (
  `member_id` varchar(50) NOT NULL COMMENT '로그인 아이디',
  `password_hash` varchar(255) NOT NULL COMMENT '암호화된 비밀번호',
  `nickname` varchar(30) NOT NULL COMMENT '화면 표시 이름',
  `email` varchar(100) DEFAULT NULL COMMENT '비밀번호 찾기용',
  `role` varchar(10) NOT NULL DEFAULT 'user' COMMENT 'user / official / admin',
  `region_code` char(10) DEFAULT NULL COMMENT '공무원 소속 시군 (일반 회원 NULL)',
  `share_consent` tinyint(1) NOT NULL DEFAULT 0 COMMENT '지자체 정보 제공 동의',
  `created_at` datetime NOT NULL DEFAULT current_timestamp() COMMENT '가입 시각',
  PRIMARY KEY (`member_id`),
  UNIQUE KEY `uq_member_email` (`email`),
  KEY `fk_member_region` (`region_code`),
  CONSTRAINT `fk_member_region` FOREIGN KEY (`region_code`) REFERENCES `region` (`region_code`),
  CONSTRAINT `ck_member_role` CHECK (`role` in ('user','official','admin'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='회원';

CREATE TABLE `vacant_house` (
  `house_id` int(11) NOT NULL AUTO_INCREMENT COMMENT '빈집 번호',
  `region_code` char(10) NOT NULL COMMENT '어느 리·동 소속',
  `grade_code` varchar(2) NOT NULL COMMENT '등급',
  `main_use` varchar(50) DEFAULT NULL COMMENT '주택 유형',
  `built_year` smallint(6) DEFAULT NULL COMMENT '준공연도 (양산은 NULL)',
  `structure` varchar(50) DEFAULT NULL COMMENT '구조',
  `floor_area` decimal(8,2) DEFAULT NULL COMMENT '연면적 ㎡',
  `land_area` decimal(10,2) DEFAULT NULL COMMENT '대지면적 ㎡ (양산은 NULL)',
  `road_contact` varchar(20) DEFAULT NULL COMMENT '도로접면 (양산은 NULL)',
  `zoning` varchar(30) DEFAULT NULL COMMENT '용도지역 (양산은 NULL)',
  `data_date` date NOT NULL COMMENT '조사 기준일',
  PRIMARY KEY (`house_id`),
  KEY `fk_house_region` (`region_code`),
  KEY `fk_house_grade` (`grade_code`),
  CONSTRAINT `fk_house_grade` FOREIGN KEY (`grade_code`) REFERENCES `grade_code` (`grade_code`),
  CONSTRAINT `fk_house_region` FOREIGN KEY (`region_code`) REFERENCES `region` (`region_code`),
  CONSTRAINT `ck_house_year` CHECK (`built_year` is null or `built_year` between 1800 and 2100),
  CONSTRAINT `ck_house_floor` CHECK (`floor_area` is null or `floor_area` > 0),
  CONSTRAINT `ck_house_land` CHECK (`land_area` is null or `land_area` > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='빈집';

-- ------------------------------------------------------------
-- ③ 지역 주변 정보 — region, industry 참조
-- ------------------------------------------------------------

CREATE TABLE `local_office` (
  `office_id` int(11) NOT NULL AUTO_INCREMENT COMMENT '부서 번호',
  `region_code` char(10) NOT NULL COMMENT '소속 시군 행',
  `role_type` varchar(10) NOT NULL COMMENT 'vacant / permit / lodging',
  `dept_name` varchar(50) NOT NULL COMMENT '부서 이름',
  `phone` varchar(20) DEFAULT NULL COMMENT '부서 대표 전화',
  `url` varchar(300) DEFAULT NULL COMMENT '시군청 안내 페이지',
  `description` varchar(200) DEFAULT NULL COMMENT '물어볼 수 있는 내용',
  `data_date` date NOT NULL COMMENT '확인한 날짜',
  PRIMARY KEY (`office_id`),
  KEY `fk_office_region` (`region_code`),
  CONSTRAINT `fk_office_region` FOREIGN KEY (`region_code`) REFERENCES `region` (`region_code`),
  CONSTRAINT `ck_office_role` CHECK (`role_type` in ('vacant','permit','lodging'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='지자체 담당 부서';

CREATE TABLE `contractor` (
  `registration_no` varchar(10) NOT NULL COMMENT '사업자등록번호 (화면 표시 안 함)',
  `industry` varchar(50) NOT NULL COMMENT '등록 업종',
  `name` varchar(100) NOT NULL COMMENT '상호',
  `phone` varchar(20) DEFAULT NULL COMMENT '사무실 전화',
  `address` varchar(200) DEFAULT NULL COMMENT '사업장 주소',
  `region_code` char(10) DEFAULT NULL COMMENT '카카오 b_code (주소 변환 실패 시 NULL)',
  `latitude` decimal(9,6) DEFAULT NULL COMMENT '위도',
  `longitude` decimal(9,6) DEFAULT NULL COMMENT '경도',
  PRIMARY KEY (`registration_no`,`industry`),
  KEY `fk_contractor_region` (`region_code`),
  CONSTRAINT `fk_contractor_region` FOREIGN KEY (`region_code`) REFERENCES `region` (`region_code`),
  CONSTRAINT `ck_contractor_lat` CHECK (`latitude` is null or `latitude` between 33 and 39),
  CONSTRAINT `ck_contractor_lng` CHECK (`longitude` is null or `longitude` between 124 and 132)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='시공 업체';

CREATE TABLE `store` (
  `store_id` varchar(30) NOT NULL COMMENT '상가업소번호',
  `name` varchar(100) NOT NULL COMMENT '상호',
  `category` varchar(50) DEFAULT NULL COMMENT '원본 업종 (소분류)',
  `industry_code` varchar(20) DEFAULT NULL COMMENT '우리 업종 (해당 없으면 NULL)',
  `region_code` char(10) NOT NULL COMMENT '원본의 법정동코드',
  `latitude` decimal(9,6) NOT NULL COMMENT '위도',
  `longitude` decimal(9,6) NOT NULL COMMENT '경도',
  `address` varchar(200) DEFAULT NULL COMMENT '주소',
  PRIMARY KEY (`store_id`),
  KEY `fk_store_industry` (`industry_code`),
  KEY `fk_store_region` (`region_code`),
  CONSTRAINT `fk_store_industry` FOREIGN KEY (`industry_code`) REFERENCES `industry` (`industry_code`),
  CONSTRAINT `fk_store_region` FOREIGN KEY (`region_code`) REFERENCES `region` (`region_code`),
  CONSTRAINT `ck_store_lat` CHECK (`latitude` between 33 and 39),
  CONSTRAINT `ck_store_lng` CHECK (`longitude` between 124 and 132)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='가게 원본';

CREATE TABLE `region_store_stat` (
  `region_code` char(10) NOT NULL COMMENT '기준 동네 (동그라미)',
  `radius_m` int(11) NOT NULL COMMENT '반경 m (고창 1000/2500/5000, 양산 500/1000/1500)',
  `industry_code` varchar(20) NOT NULL COMMENT '업종',
  `store_count` int(11) NOT NULL DEFAULT 0 COMMENT '가게 수 (0도 저장)',
  `data_date` date NOT NULL COMMENT '상가정보 기준일',
  PRIMARY KEY (`region_code`,`radius_m`,`industry_code`),
  KEY `fk_rss_industry` (`industry_code`),
  CONSTRAINT `fk_rss_industry` FOREIGN KEY (`industry_code`) REFERENCES `industry` (`industry_code`),
  CONSTRAINT `fk_rss_region` FOREIGN KEY (`region_code`) REFERENCES `region` (`region_code`),
  CONSTRAINT `ck_rss_count` CHECK (`store_count` >= 0),
  CONSTRAINT `ck_rss_radius` CHECK (`radius_m` in (500,1000,1500,2500,5000))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='반경별 가게 수';

-- ------------------------------------------------------------
-- ④ 회원 활동 — member, vacant_house 참조
-- ------------------------------------------------------------

CREATE TABLE `official_invite` (
  `invite_id` int(11) NOT NULL AUTO_INCREMENT COMMENT '코드 번호',
  `code_hash` char(64) NOT NULL COMMENT '코드 원문이 아니라 SHA-256 해시만 저장',
  `region_code` char(10) NOT NULL COMMENT '이 코드로 전환되는 소속 시군',
  `created_by` varchar(50) NOT NULL COMMENT '발급한 관리자',
  `created_at` datetime NOT NULL DEFAULT current_timestamp() COMMENT '발급 시각',
  `expires_at` datetime NOT NULL COMMENT '만료 시각',
  `used_by` varchar(50) DEFAULT NULL COMMENT '사용한 회원 (미사용이면 NULL)',
  `used_at` datetime DEFAULT NULL COMMENT '사용 시각',
  PRIMARY KEY (`invite_id`),
  UNIQUE KEY `uq_invite_code` (`code_hash`),
  KEY `fk_invite_region` (`region_code`),
  KEY `fk_invite_admin` (`created_by`),
  KEY `fk_invite_used_by` (`used_by`),
  CONSTRAINT `fk_invite_admin` FOREIGN KEY (`created_by`) REFERENCES `member` (`member_id`),
  CONSTRAINT `fk_invite_region` FOREIGN KEY (`region_code`) REFERENCES `region` (`region_code`),
  CONSTRAINT `fk_invite_used_by` FOREIGN KEY (`used_by`) REFERENCES `member` (`member_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='공무원 전환용 초대 코드';

CREATE TABLE `saved_house` (
  `member_id` varchar(50) NOT NULL COMMENT '누가',
  `house_id` int(11) NOT NULL COMMENT '어떤 빈집',
  `memo` varchar(500) DEFAULT NULL COMMENT '메모',
  `preference` tinyint(4) DEFAULT NULL COMMENT '선호도 1~5',
  `saved_at` datetime NOT NULL DEFAULT current_timestamp() COMMENT '처음 찜한 시각',
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp() COMMENT '마지막 수정 시각',
  PRIMARY KEY (`member_id`,`house_id`),
  KEY `fk_saved_house` (`house_id`),
  CONSTRAINT `fk_saved_house` FOREIGN KEY (`house_id`) REFERENCES `vacant_house` (`house_id`),
  CONSTRAINT `fk_saved_member` FOREIGN KEY (`member_id`) REFERENCES `member` (`member_id`) ON DELETE CASCADE,
  CONSTRAINT `ck_saved_pref` CHECK (`preference` is null or `preference` between 1 and 5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='찜';

CREATE TABLE `saved_house_industry` (
  `member_id` varchar(50) NOT NULL COMMENT '어느 찜 (회원)',
  `house_id` int(11) NOT NULL COMMENT '어느 찜 (빈집)',
  `industry_code` varchar(20) NOT NULL COMMENT '희망 업종',
  PRIMARY KEY (`member_id`,`house_id`,`industry_code`),
  KEY `fk_shi_industry` (`industry_code`),
  CONSTRAINT `fk_shi_industry` FOREIGN KEY (`industry_code`) REFERENCES `industry` (`industry_code`),
  CONSTRAINT `fk_shi_saved` FOREIGN KEY (`member_id`, `house_id`) REFERENCES `saved_house` (`member_id`, `house_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='찜의 희망 업종';

CREATE TABLE `interest_event` (
  `event_id` int(11) NOT NULL AUTO_INCREMENT COMMENT '기록 번호',
  `member_id` varchar(50) DEFAULT NULL COMMENT '누가 (비회원 NULL)',
  `region_code` char(10) NOT NULL COMMENT '어느 지역에서',
  `house_id` int(11) DEFAULT NULL COMMENT '어떤 집 (지역 보기는 NULL)',
  `industry_code` varchar(20) DEFAULT NULL COMMENT '고른 업종 (select_industry일 때)',
  `event_type` enum('view_region','view_house','save','edit','unsave','select_industry') NOT NULL COMMENT '행동 종류',
  `created_at` datetime NOT NULL DEFAULT current_timestamp() COMMENT '발생 시각',
  PRIMARY KEY (`event_id`),
  KEY `fk_event_member` (`member_id`),
  KEY `fk_event_region` (`region_code`),
  KEY `fk_event_house` (`house_id`),
  KEY `fk_event_industry` (`industry_code`),
  KEY `idx_event_type_time` (`event_type`,`created_at`),
  CONSTRAINT `fk_event_house` FOREIGN KEY (`house_id`) REFERENCES `vacant_house` (`house_id`),
  CONSTRAINT `fk_event_industry` FOREIGN KEY (`industry_code`) REFERENCES `industry` (`industry_code`),
  CONSTRAINT `fk_event_member` FOREIGN KEY (`member_id`) REFERENCES `member` (`member_id`) ON DELETE SET NULL,
  CONSTRAINT `fk_event_region` FOREIGN KEY (`region_code`) REFERENCES `region` (`region_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='행동 기록';














