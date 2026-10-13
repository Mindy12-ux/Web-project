// B 담당: saveHouse(houseId, {memo, preference, industries}) 호출.
// 페이지에 <meta name="csrf-token" content="{{ auth_csrf }}"> 추가 필요.
async function savedRequest(url, method, data) {
  const token = document.querySelector('meta[name="csrf-token"]')?.content;
  if (!token) throw new Error('보안 토큰이 없어요. 페이지를 새로고침해 주세요.');
  const response = await fetch(url, {method, credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': token}, ...(data ? {body: JSON.stringify(data)} : {})});
  const result = await response.json();
  if (response.status === 401) { window.location.assign('/auth/login?next=' + encodeURIComponent(location.pathname)); throw new Error('로그인이 필요합니다.'); }
  if (!response.ok || !result.ok) throw new Error(result.error || '요청에 실패했어요.');
  return result.data;
}
window.saveHouse = (houseId, options = {}) => savedRequest('/api/saved', 'POST', {...options, house_id: Number(houseId)});
document.querySelectorAll('.saved-edit').forEach(form => {
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = form.querySelector('button[type="submit"]'); button.disabled = true;
    try {
      const data = new FormData(form);
      await savedRequest('/api/saved/' + form.dataset.house, 'PATCH', {memo: data.get('memo'), preference: data.get('preference') ? Number(data.get('preference')) : null, industries: data.getAll('industries')});
      sessionStorage.setItem('saved-updated', '1');
      location.reload();
    } catch (error) { document.getElementById('saved-message').textContent = error.message; }
    finally { button.disabled = false; }
  });
});
document.querySelectorAll('[data-unsave]').forEach(button => {
  button.addEventListener('click', async () => {
    if (!window.confirm('이 빈집의 찜을 취소할까요?')) return;
    button.disabled = true;
    try { await savedRequest('/api/saved/' + button.dataset.unsave, 'DELETE'); location.reload(); }
    catch (error) { document.getElementById('saved-message').textContent = error.message; button.disabled = false; }
  });
});

document.querySelectorAll('[data-edit]').forEach(button => {
  button.addEventListener('click', () => {
    const card = button.closest('article');
    card.querySelector('.saved-view').hidden = true;
    const form = card.querySelector('.saved-edit');
    form.hidden = false;
    form.querySelector('textarea').focus();
  });
});
document.querySelectorAll('[data-cancel-edit]').forEach(button => {
  button.addEventListener('click', () => {
    const form = button.closest('form');
    if (form.querySelector('button[type="submit"]').disabled) return;
    form.reset(); form.hidden = true;
    const card = form.closest('article');
    card.querySelector('.saved-view').hidden = false;
    card.querySelector('[data-edit]').focus();
  });
});
if (sessionStorage.getItem('saved-updated')) {
  sessionStorage.removeItem('saved-updated');
  const message = document.getElementById('saved-message');
  if (message) {
    message.textContent = '수정 내용을 저장했어요.';
    const savedNotice = message.textContent;
    setTimeout(() => {
      if (message.textContent === savedNotice) {
        message.textContent = '';

      }
    }, 10000);
  }
}
