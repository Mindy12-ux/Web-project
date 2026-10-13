-- =========================================================
-- grade_code 4줄 넣기 (MariaDB)
-- 전제: create_vacant_house.sql 로 grade_code 테이블을 먼저 만들어 둘 것
-- 다시 실행해도 중복 오류 없이 같은 값으로 덮어씀
-- =========================================================
USE itda;

INSERT INTO grade_code (grade_code, label, description, sort_order, is_default) VALUES
    ('1',  '1등급',       '활용 대상',    1, TRUE),     -- 처음 화면에서 체크
    ('2',  '2등급',       '관리 대상',    2, TRUE),     -- 처음 화면에서 체크
    ('3',  '3등급',       '정비 대상',    3, FALSE),
    ('NA', '등급 미산정', '현장 등급 전', 4, FALSE)     -- 양산시 미산정 7채
ON DUPLICATE KEY UPDATE
    label       = VALUES(label),
    description = VALUES(description),
    sort_order  = VALUES(sort_order),
    is_default  = VALUES(is_default);

-- 확인
SELECT * FROM grade_code ORDER BY sort_order;
