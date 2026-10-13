-- local_office INSERT (컬럼 순서: office_id, region_code, role_type, dept_name, phone, url, description, data_date)
-- 먼저 region에 5279000000(고창군), 4833000000(양산시) 행이 있어야 함 (FK)
insert into local_office values(1,'4833000000','vacant','양산시청 (빈집 관리기관)','055-392-3034','https://www.yangsan.go.kr/portal/board/post/list.do?bcIdx=794&mid=0205031600','빈집 매입·임차·정비 문의','2026-10-12');
insert into local_office values(2,'4833000000','permit','양산시 건축과','055-392-2114','https://www.yangsan.go.kr/portal/contents.do?mid=0506010000','대수선·증축·용도변경 인허가 문의 (대표번호로 건축과 연결)','2026-10-12');
insert into local_office values(3,'5279000000','vacant','고창군 도시디자인과 주거복지팀','063-560-2385','https://www.gochang.go.kr','빈집 매입·임차·정비 문의 (고창군청 3층)','2026-10-13');
insert into local_office values(4,'5279000000','permit','고창군 종합민원과 건축팀','063-560-2401','https://www.gochang.go.kr','대수선·증축·용도변경 인허가 상담·신고 (건축물대장 발급 063-560-2853)','2026-10-13');
insert into local_office values(5,'5279000000','lodging','고창군 농업기술센터 농촌개발과','063-560-8880','https://www.gochang.go.kr','농어촌민박 신고 문의 (민박 담당자 연결 요청)','2026-10-13');
