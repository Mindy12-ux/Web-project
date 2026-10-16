// B 담당: saveHouse(houseId, {memo, preference, industries}) 호출.
// 페이지에 <meta name="csrf-token" content="{{ auth_csrf }}"> 추가 필요.
// 호출자가 넘긴 URL·HTTP 메서드·JSON 객체로 서버에 찜 요청을 보내는 공통 함수입니다.
async function savedRequest(url, method, data) {
  const token = document.querySelector('meta[name="csrf-token"]')?.content;  // saved.html 또는 지도 HTML의 meta에서 보안 토큰을 읽습니다.
  if (!token) throw new Error('보안 토큰이 없어요. 페이지를 새로고침해 주세요.');
  // 쿠키·CSRF 헤더와 JSON 본문을 함께 전송합니다. 전송 방식은 인자로 받은 method입니다.
  const response = await fetch(url, {method, credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': token}, ...(data ? {body: JSON.stringify(data)} : {})});
  const result = await response.json();  // mypage.py가 돌려준 ok/data 또는 ok/error JSON을 읽습니다.
  // 로그인이 필요하면 로그인 화면으로 보내고 next에 현재 화면 경로를 넣습니다.
  if (response.status === 401) { window.location.assign('/auth/login?next=' + encodeURIComponent(location.pathname)); throw new Error('로그인이 필요합니다.'); }
  if (!response.ok || !result.ok) throw new Error(result.error || '요청에 실패했어요.');
  return result.data;  // 성공 결과만 호출자의 await로 돌려줍니다. 예: {house_id: 49}.
}
// 다른 화면이 호출하는 찜 추가 함수입니다. 집 번호를 숫자로 바꿔 POST /api/saved로 보냅니다.
window.saveHouse = (houseId, options = {}) => savedRequest('/api/saved', 'POST', {...options, house_id: Number(houseId)});
// 집 카드마다 있는 수정 폼에 이벤트를 연결합니다. .saved-edit는 HTML 클래스입니다.
document.querySelectorAll('.saved-edit').forEach(form => {
  // event는 폼을 제출했을 때 브라우저가 전달하는 이벤트 객체입니다.
  form.addEventListener('submit', async event => {
    event.preventDefault();  // 기본 폼 제출을 막고 아래 JSON PATCH로 대신 저장합니다.
    const button = form.querySelector('button[type="submit"]'); button.disabled = true;  // 저장 중 반복 클릭을 줄입니다.
    try {
      const data = new FormData(form);  // 입력의 name을 기준으로 메모·선호도·희망업종 값을 읽습니다.
      // data-house는 집 번호입니다. 선호도는 숫자 또는 null, 업종은 배열로 바꿔 PATCH합니다.
      await savedRequest('/api/saved/' + form.dataset.house, 'PATCH', {memo: data.get('memo'), preference: data.get('preference') ? Number(data.get('preference')) : null, industries: data.getAll('industries')});
      sessionStorage.setItem('saved-updated', '1');  // 새로고침 뒤 완료 안내를 띄울 브라우저 표식입니다. Flask 로그인 session과 다릅니다.
      location.reload();  // GET /saved로 DB의 최신 저장 결과를 다시 읽습니다.
    } catch (error) { document.getElementById('saved-message').textContent = error.message; }
    finally { button.disabled = false; }
  });
});
// data-unsave 속성에 집 번호가 들어 있는 찜 취소 버튼들을 찾습니다.
document.querySelectorAll('[data-unsave]').forEach(button => {
  button.addEventListener('click', async () => {
    if (!window.confirm('이 빈집의 찜을 취소할까요?')) return;  // 확인 창에서 취소하면 서버 요청 없이 종료합니다.
    button.disabled = true;
    // DELETE /api/saved/집번호로 본인 찜만 취소하고 성공하면 목록을 다시 읽습니다.
    try { await savedRequest('/api/saved/' + button.dataset.unsave, 'DELETE'); location.reload(); }
    catch (error) { document.getElementById('saved-message').textContent = error.message; button.disabled = false; }
  });
});

// 수정하기 버튼은 아직 저장하지 않고 편집 폼을 여는 역할입니다.
document.querySelectorAll('[data-edit]').forEach(button => {
  button.addEventListener('click', () => {
    const card = button.closest('article');  // 클릭한 버튼이 속한 집 카드만 찾습니다.
    card.querySelector('.saved-view').hidden = true;  // 조회 영역을 숨기고 같은 카드의 수정 폼을 표시합니다.
    const form = card.querySelector('.saved-edit');
    form.hidden = false;
    form.querySelector('textarea').focus();
  });
});
// 수정 취소 버튼은 입력만 되돌리고 서버에 PATCH를 보내지 않습니다.
document.querySelectorAll('[data-cancel-edit]').forEach(button => {
  button.addEventListener('click', () => {
    const form = button.closest('form');
    if (form.querySelector('button[type="submit"]').disabled) return;  // 저장 요청이 진행 중일 때는 화면 취소를 막습니다.
    form.reset(); form.hidden = true;  // 처음 표시한 입력값으로 되돌리고 편집 폼을 숨깁니다.
    const card = form.closest('article');
    card.querySelector('.saved-view').hidden = false;
    card.querySelector('[data-edit]').focus();
  });
});
// 방금 저장 성공으로 새로고침한 경우에만 완료 안내를 한 번 표시합니다.
if (sessionStorage.getItem('saved-updated')) {
  sessionStorage.removeItem('saved-updated');  // 표식을 즉시 지워 다음 새로고침에 안내가 반복되지 않게 합니다.
  const message = document.getElementById('saved-message');
  if (message) {
    message.textContent = '수정 내용을 저장했어요.';
    const savedNotice = message.textContent;  // 10초 사이 다른 오류 문구로 바뀌었는지 비교하기 위해 현재 문구를 기억합니다.
    setTimeout(() => {
      // 안내가 다른 내용으로 바뀌었다면 그 문구는 지우지 않습니다.
      if (message.textContent === savedNotice) {
        message.textContent = '';

      }
    }, 10000);  // 10000밀리초, 즉 10초 후 완료 안내를 제거합니다.
  }
}
