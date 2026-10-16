// 입력을 잠깐 멈추면 서버에서 중복 여부를 확인합니다.
const signupForm = document.querySelector('[data-duplicate-url]');  // HTML 가입 폼의 data-duplicate-url에 서버 중복 확인 주소가 들어 있습니다.

// 입력칸 이름 두 개를 같은 방식으로 처리하되 타이머·버전은 각각 관리합니다.
for (const field of ['member_id', 'nickname']) {
  const input = signupForm.elements[field];  // 폼의 name이 member_id 또는 nickname인 입력 요소입니다.
  const status = document.getElementById(`${field}-status`);  // 여기의 id는 계정 아이디가 아니라 안내 문구 HTML 요소의 식별자입니다.
  const label = field === 'member_id' ? '아이디' : '닉네임';
  let timer;
  let version = 0;  // 입력이 바뀐 순서 번호입니다. 늦게 온 예전 응답을 버릴 때 사용합니다.

  // 문구와 오류 여부를 받아 안내 글자·색상·입력 오류 상태를 함께 바꿉니다.
  function show(message, error = false) {
    status.textContent = message;
    status.hidden = !message;
    status.classList.toggle('is-error', error);
    input.setAttribute('aria-invalid', String(error));
  }

  // value는 현재 입력 문자열, currentVersion은 해당 입력의 요청 번호입니다.
  async function check(value, currentVersion) {
    show('중복 확인 중…');
    try {
      const params = new URLSearchParams({field, value});  // field는 검사 항목, value는 실제 입력값이며 URL 조회 문자열로 인코딩합니다.
      // method 생략으로 GET /auth/check-duplicate?field=...&value=... 요청을 보냅니다.
      const response = await fetch(`${signupForm.dataset.duplicateUrl}?${params}`, {cache: 'no-store'}); //chache 캐시된 응답 재사용하지않기
       //HTML 폼에 저장한 주소를 읽어 쓰기 때문입니다.
//signup.html 8줄의 data-duplicate-url에 Flask의 url_for가 /auth/check-duplicate를 넣어 줍니다
      const result = await response.json();
       // auth.py의 check_duplicate()가 반환한 JSON을 객체로 읽습니다.
      // 이전 입력의 응답이 늦게 와도 현재 안내를 덮어쓰지 않습니다.
      if (currentVersion !== version) return;  // 입력이 바뀐 뒤 도착한 오래된 응답이면 현재 안내를 덮지 않습니다.
      if (!response.ok || !result.ok) {
        show(result.error || '중복 확인을 다시 시도해 주세요.', true);
        return;
      }
      const duplicate = result.data.duplicate;  // true는 중복, false는 사용 가능이라는 서버의 결과입니다.
      // 서버 결과를 show()로 넘겨 입력칸 아래 문구를 갱신합니다. 회원을 저장하지는 않습니다.
      show(duplicate ? (field === 'member_id' ? '아이디가 중복입니다.' : '닉네임이 중복입니다.') : `사용 가능한 ${label}입니다.`, duplicate);
    } catch {
      if (currentVersion === version) show('중복 확인을 다시 시도해 주세요.', true);
    }
  }

  // delay 밀리초 뒤 중복 조회를 예약합니다. 입력은 350, 포커스 이동은 0을 넘깁니다.
  function schedule(delay) {
    clearTimeout(timer);  // 이전 예약을 취소해 연속 입력마다 서버 요청이 쌓이지 않게 합니다.
    const currentVersion = ++version;  // 이번 입력에 새 번호를 붙입니다.
    const value = input.value.trim();  // HTML 입력칸의 현재 문자열을 읽고 앞뒤 공백을 제거합니다.
    show('');
    if (!value) return;  // 비어 있으면 중복 조회를 보내지 않습니다.
    if (field === 'member_id' && !/^[A-Za-z0-9_]{4,50}$/.test(value)) {
      show('아이디는 영문·숫자·밑줄로 4~50자 입력해 주세요.', true);
      return;
    }
    if (field === 'nickname' && value.length > 30) return;
    timer = setTimeout(() => check(value, currentVersion), delay);  // 지금 즉시 호출하지 않고 delay 후 check(value, currentVersion)를 실행합니다.
  }

  input.addEventListener('input', () => schedule(350));  // 글자를 입력할 때마다 약 0.35초 뒤 확인하도록 예약합니다.
  input.addEventListener('change', () => schedule(0));  // 입력이 확정되면 바로 확인합니다.
  input.addEventListener('blur', () => schedule(0));  // 다른 입력칸으로 이동할 때도 바로 확인합니다.
  if (input.value) schedule(0);  // 가입 실패 후 기존 값이 남은 화면도 중복 안내를 확인합니다.
}
