# 배포 절차 (Vercel + Aiven MySQL)

웹은 Vercel, DB는 Aiven 무료 MySQL을 씁니다. 로컬 개발 방식(MariaDB 포트 4000, `.env`)은 그대로 둡니다.

---

## 1. Aiven MySQL 만들기

1. https://aiven.io 에서 계정을 만듭니다 (직접 진행).
2. **Create service → MySQL → Free plan** 을 선택합니다. 리전은 한국과 가까운 곳을 고릅니다.
3. 서비스가 켜지면 **Overview** 화면에서 다음을 메모합니다.
   - Host, Port, User(`avnadmin`), Password
   - Database 이름 (기본값 `defaultdb`)
4. 같은 화면에서 **CA certificate** 를 내려받아 `Web-project/backend/certs/aiven-ca.pem` 으로 저장합니다.
   CA 인증서는 공개 정보라 Git에 올려도 됩니다. 비밀번호는 올리지 않습니다.
5. 빈 DB를 하나 만듭니다 (이름은 기존 설정과 맞춰 `itda`).

```bash
mariadb -h <HOST> -P <PORT> -u avnadmin -p --ssl-ca=backend/certs/aiven-ca.pem --ssl-verify-server-cert -e "CREATE DATABASE IF NOT EXISTS itda CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"
```

---

## 2. 로컬 DB 내보내기

로컬 MariaDB(포트 4000)에서 `itda` 전체를 덤프합니다. 비밀번호 입력을 물어봅니다.

```bash
mariadb-dump -h 127.0.0.1 -P 4000 -u root -p --single-transaction --no-tablespaces --default-character-set=utf8mb4 itda > itda_dump.sql
```

- 덤프 파일에는 회원 정보가 들어 있습니다. **Git에 올리지 말고**, 이관이 끝나면 지웁니다. `.gitignore`에 `itda_dump.sql` 을 추가해 두었습니다.
- 덤프 파일을 열어 `CREATE TABLE` 문에 `utf8mb4_uca1400` 같은 MariaDB 전용 콜레이션이 있는지 확인합니다. 현재 스키마는 `utf8mb4_general_ci`를 쓰므로 문제없을 것입니다.

---

## 3. Aiven으로 가져오기

```bash
mariadb -h <HOST> -P <PORT> -u avnadmin -p --ssl-ca=backend/certs/aiven-ca.pem --ssl-verify-server-cert itda < itda_dump.sql
```

가져온 뒤 확인합니다.

```bash
mariadb -h <HOST> -P <PORT> -u avnadmin -p --ssl-ca=backend/certs/aiven-ca.pem --ssl-verify-server-cert itda -e "SHOW TABLES; SELECT COUNT(*) FROM store;"
```

가져온 뒤 `itda_dump.sql` 은 삭제합니다.

---

## 4. Vercel 배포

1. https://vercel.com 에서 GitHub 계정으로 로그인하고 **Add New → Project** 로 `Mindy12-ux/Web-project` 저장소를 import 합니다.
2. Framework Preset은 **Flask** (자동 감지되면 그대로) 로 둡니다. Root Directory는 저장소 최상위입니다.
3. **Environment Variables** 에 아래 값을 넣습니다. 비밀번호와 키는 여기서만 입력합니다.

| 이름 | 값 |
|---|---|
| `SECRET_KEY` | 긴 무작위 문자열. 아래 명령으로 만듭니다 |
| `KAKAO_JS_KEY` | 카카오 개발자 콘솔의 JavaScript 키 |
| `DB_HOST` | Aiven Host |
| `DB_PORT` | Aiven Port |
| `DB_USER` | `avnadmin` |
| `DB_PASSWORD` | Aiven Password |
| `DB_NAME` | `itda` |
| `DB_SSL_CA` | `certs/aiven-ca.pem` |

`SECRET_KEY` 생성:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

4. **Deploy** 를 누릅니다. 끝나면 `https://<프로젝트명>.vercel.app` 주소가 생깁니다.

---

## 5. 카카오맵 도메인 등록

카카오 개발자 콘솔 → 내 애플리케이션 → 플랫폼 → **Web** 에 `https://<프로젝트명>.vercel.app` 을 추가합니다.
등록하지 않으면 지도가 뜨지 않습니다 (`map.js`의 안내 문구와 같은 원인입니다).

---

## 6. 동작 확인

- 메인 페이지와 `/map` 이 열리는지 확인합니다.
- 지도에 빈집 목록이 나오는지 확인합니다 (DB 연결 확인).
- 회원가입, 로그인, 찜 기능을 한 번씩 눌러 봅니다.
- 문제가 있으면 Vercel 대시보드의 **Logs** 를 봅니다.

---

## 알아둘 점

- Aiven 무료 DB는 1GB, 1 CPU입니다. 현재 데이터는 약 3MB라 여유가 많습니다.
- Aiven 무료 DB는 오랫동안 쓰지 않으면 일시 중지될 수 있습니다. 중지 전에 알림이 가며, 다시 켤 수 있습니다.
- Vercel Hobby 플랜은 개인·비상업 용도입니다. 정식 서비스로 바꾸면 요금제를 다시 확인합니다.
- 로컬에서는 `DB_SSL_CA` 를 설정하지 않으므로 기존처럼 MariaDB에 접속합니다.
