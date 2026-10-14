// 입력을 잠깐 멈추면 서버에서 중복 여부를 확인합니다.
const signupForm = document.querySelector('[data-duplicate-url]');

for (const field of ['member_id', 'nickname']) {
  const input = signupForm.elements[field];
  const status = document.getElementById(`${field}-status`);
  const label = field === 'member_id' ? '아이디' : '닉네임';
  let timer;
  let version = 0;

  function show(message, error = false) {
    status.textContent = message;
    status.hidden = !message;
    status.classList.toggle('is-error', error);
    input.setAttribute('aria-invalid', String(error));
  }

  async function check(value, currentVersion) {
    show('중복 확인 중…');
    try {
      const params = new URLSearchParams({field, value});
      const response = await fetch(`${signupForm.dataset.duplicateUrl}?${params}`, {cache: 'no-store'});
      const result = await response.json();
      // 이전 입력의 응답이 늦게 와도 현재 안내를 덮어쓰지 않습니다.
      if (currentVersion !== version) return;
      if (!response.ok || !result.ok) {
        show(result.error || '중복 확인을 다시 시도해 주세요.', true);
        return;
      }
      const duplicate = result.data.duplicate;
      show(duplicate ? (field === 'member_id' ? '아이디가 중복입니다.' : '닉네임이 중복입니다.') : `사용 가능한 ${label}입니다.`, duplicate);
    } catch {
      if (currentVersion === version) show('중복 확인을 다시 시도해 주세요.', true);
    }
  }

  function schedule(delay) {
    clearTimeout(timer);
    const currentVersion = ++version;
    const value = input.value.trim();
    show('');
    if (!value) return;
    if (field === 'member_id' && !/^[A-Za-z0-9_]{4,50}$/.test(value)) {
      show('아이디는 영문·숫자·밑줄로 4~50자 입력해 주세요.', true);
      return;
    }
    if (field === 'nickname' && value.length > 30) return;
    timer = setTimeout(() => check(value, currentVersion), delay);
  }

  input.addEventListener('input', () => schedule(350));
  input.addEventListener('change', () => schedule(0));
  input.addEventListener('blur', () => schedule(0));
  if (input.value) schedule(0);
}
