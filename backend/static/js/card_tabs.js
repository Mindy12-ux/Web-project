// [담당 C] 빈집 카드 옆 정보 탭 (주변 상권 · 시공 업체 · 연락처)
// 쓰는 법: B의 map.js가 빈집 카드를 보여줄 때  cardTabs.show(house.region_code)  를 부른다.
//         (map.js가 먼저 실행돼도 되도록 document.dispatchEvent(new CustomEvent('card-region',
//          {detail: {region_code}})) 로 알려 줘도 된다.)  cardTabs.clear() 는 카드를 닫을 때.
// 내용은 /api/stores/stats · /api/contractors · /api/offices 에서 탭을 열 때 가져온다(읽기 전용).
(function () {
  const root = document.getElementById('card-tabs');
  if (!root) return;

  const panel = root.querySelector('#ct-panel');
  const tabButtons = Array.from(root.querySelectorAll('[data-tab]'));
  const ROLE_LABEL = {vacant: '빈집 관리', permit: '건축 인허가', lodging: '농어촌민박'};
  const EMPTY_HINT = '빈집 카드를 고르면 이 동네의 주변 상권, 시공 업체, 담당 부서 연락처를 보여 드려요.';

  let region = null;       // 지금 보여 주는 리·동 법정동코드(10자리)
  let tab = 'stats';
  let radius = null;       // null이면 서버가 가장 작은 반경을 고른다
  let seq = 0;             // 늦게 도착한 옛 응답이 화면을 덮어쓰지 않게 하는 번호
  const cache = new Map();

  // ---- 작은 도우미 ------------------------------------------------------------
  function h(tag, attrs, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs || {})) {
      if (value === null || value === undefined || value === false) continue;
      if (key === 'class') node.className = value;
      else if (key === 'text') node.textContent = value;
      else node.setAttribute(key, value);
    }
    for (const child of children.flat()) {
      if (child === null || child === undefined || child === false) continue;
      node.append(child);                       // 문자열은 텍스트로 들어가므로 HTML로 해석되지 않는다
    }
    return node;
  }
  const notice = (text) => h('p', {class: 'notice', text});
  const dateText = (iso) => (iso ? iso : '확인 안 됨');
  const meters = (m) => (m >= 1000 ? `${m / 1000}km` : `${m}m`);
  const telHref = (phone) => 'tel:' + String(phone).replace(/[^0-9+]/g, '');
  const safeUrl = (url) => (/^https?:\/\//i.test(url || '') ? url : null);

  async function api(path) {
    const response = await fetch(path, {credentials: 'same-origin'});
    let body = null;
    try { body = await response.json(); } catch (e) { /* JSON이 아니면 아래에서 실패 처리 */ }
    if (!response.ok || !body || !body.ok) throw new Error((body && body.error) || '정보를 불러오지 못했어요.');
    return body.data;
  }

  function setPanel(...nodes) { panel.replaceChildren(...nodes); }

  // ---- 탭별 화면 --------------------------------------------------------------
  function renderStats(data) {
    if (!data.radii.length) return [notice('이 지역의 상권 자료가 없어요.')];
    const radiusButtons = h('div', {class: 'seg', role: 'group', 'aria-label': '반경 선택'},
      data.radii.map((m) => {
        const button = h('button', {type: 'button', 'aria-pressed': String(m === data.radius_m), text: meters(m)});
        button.addEventListener('click', () => { radius = m; load(); });
        return button;
      }));
    const max = Math.max(1, ...data.items.map((item) => item.store_count));
    const bars = h('ul', {class: 'ct-bars'}, data.items.map((item) => {
      const fill = h('span', {class: 'fill'});
      fill.style.width = (item.store_count / max * 100) + '%';
      return h('li', {class: item.store_count === 0 ? 'is-zero' : null},
        h('span', {class: 'name', text: item.name}),
        h('span', {class: 'track'}, fill),
        h('span', {class: 'count', text: String(item.store_count)}));
    }));
    return [
      h('div', {class: 'ct-radius'},
        h('p', {class: 'ct-radius-label', text: '이 동네 중심에서 반경'}), radiusButtons),
      bars,
      h('p', {class: 'ct-source', text: `업종별 가게 수 · 상가정보 기준일 ${dateText(data.data_date)} · 출처: 소상공인시장진흥공단`}),
    ];
  }

  function renderContractors(rows) {
    if (!rows.length) return [notice('이 시군에서 확인된 시공 업체 자료가 없어요.')];
    return [
      h('p', {class: 'ct-radius-label', text: '같은 시군의 시공 업체 · 이 동네 중심에서 가까운 순'}),
      h('ul', {class: 'ct-list'}, rows.map((row) => h('li', {class: 'ct-item'},
        h('h4', {text: row.name}),
        h('ul', {class: 'tags'}, row.industries.map((industry) => h('li', {text: industry}))),
        row.distance_km === null ? null : h('p', {class: 'sub', text: `직선거리 약 ${row.distance_km}km`}),
        row.phone ? h('p', {class: 'row'}, '전화 ', h('a', {href: telHref(row.phone), text: row.phone})) : null,
        row.address ? h('p', {class: 'row', text: row.address}) : null))),
      h('p', {class: 'ct-source', text: '출처: 국토교통부 건설업체 정보 · 거리는 직선거리 기준이에요.'}),
    ];
  }

  function renderOffices(rows) {
    if (!rows.length) return [notice('이 시군의 담당 부서 자료가 없어요.')];
    const byRole = new Map(rows.map((row) => [row.role_type, row]));
    const items = Object.keys(ROLE_LABEL).map((role) => {
      const row = byRole.get(role);
      if (!row) {                                // 확인된 값이 없으면 지어내지 않고 '자료 없음'
        return h('li', {class: 'ct-item is-missing'}, h('h4', {text: ROLE_LABEL[role]}),
          h('p', {class: 'row', text: '확인된 담당 부서 자료가 없어요.'}));
      }
      const url = safeUrl(row.url);
      return h('li', {class: 'ct-item'},
        h('h4', {text: `${ROLE_LABEL[role]} · ${row.dept_name}`}),
        row.description ? h('p', {class: 'sub', text: row.description}) : null,
        row.phone ? h('p', {class: 'row'}, '전화 ', h('a', {href: telHref(row.phone), text: row.phone})) : null,
        url ? h('p', {class: 'row'}, h('a', {href: url, target: '_blank', rel: 'noopener noreferrer', text: '안내 페이지 열기'})) : null,
        h('p', {class: 'mono', text: `확인일 ${dateText(row.data_date)}`}));
    });
    return [h('ul', {class: 'ct-list'}, items)];
  }

  // ---- 불러오기 ---------------------------------------------------------------
  function request() {
    const code = encodeURIComponent(region);
    if (tab === 'stats') {
      const suffix = radius ? `&radius=${radius}` : '';
      return {key: `stats:${region}:${radius}`, path: `/api/stores/stats?region=${code}${suffix}`, render: renderStats};
    }
    if (tab === 'contractors') return {key: `contractors:${region}`, path: `/api/contractors?region=${code}`, render: renderContractors};
    return {key: `offices:${region}`, path: `/api/offices?region=${code}`, render: renderOffices};
  }

  async function load() {
    if (!region) { setPanel(notice(EMPTY_HINT)); return; }
    const mine = ++seq;
    const {key, path, render} = request();
    try {
      let data = cache.get(key);
      if (data === undefined) {
        setPanel(notice('불러오는 중…'));
        data = await api(path);
        if (tab === 'stats' && radius === null) radius = data.radius_m;   // 서버가 고른 기본 반경을 기억
        cache.set(key, data);
      }
      if (mine === seq) setPanel(...render(data));
    } catch (error) {
      if (mine !== seq) return;
      const retry = h('button', {type: 'button', class: 'btn', text: '다시 시도'});
      retry.addEventListener('click', load);
      setPanel(h('div', {class: 'notice ct-error'}, h('span', {text: error.message}), retry));
    }
  }

  function select(name, focus) {
    tab = name;
    tabButtons.forEach((button) => {
      const on = button.dataset.tab === name;
      button.setAttribute('aria-selected', String(on));
      button.tabIndex = on ? 0 : -1;
      if (on && focus) button.focus();
    });
    panel.setAttribute('aria-labelledby', 'ct-tab-' + name);
    load();
  }

  tabButtons.forEach((button, index) => {
    button.addEventListener('click', () => select(button.dataset.tab, false));
    button.addEventListener('keydown', (event) => {      // 좌우 화살표로 탭 이동
      const step = {ArrowRight: 1, ArrowLeft: -1}[event.key];
      if (!step) return;
      event.preventDefault();
      select(tabButtons[(index + step + tabButtons.length) % tabButtons.length].dataset.tab, true);
    });
  });

  // ---- 바깥에서 부르는 곳 -----------------------------------------------------
  function show(regionCode) {
    if (!/^[0-9]{10}$/.test(String(regionCode || ''))) { clear(); return; }
    if (regionCode === region) return;
    region = regionCode;
    radius = null;
    cache.clear();
    select(tab, false);
  }
  function clear() { region = null; radius = null; seq++; setPanel(notice(EMPTY_HINT)); }

  window.cardTabs = {show, clear};
  document.addEventListener('card-region', (event) => show(event.detail && event.detail.region_code));
  if (root.dataset.region) show(root.dataset.region);
})();
