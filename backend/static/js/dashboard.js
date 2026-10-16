/* [담당 D] 대시보드 — 공통 도우미(window.dash) + 일반 사용자용 대시보드
   templates/dashboard.html 에서 모든 사용자에게 불러옴. 데이터: GET /api/trends?days= */

/* 두 대시보드가 같이 쓰는 도우미 (공무원용 조각도 이 함수들을 사용) */
window.dash = {
  async get(url) {
    const res = await fetch(url);
    const body = await res.json();
    if (!body.ok) throw new Error(body.error || "불러오기 실패");
    return body.data;
  },
  esc(s) {                               // 화면에 넣기 전 HTML 특수문자 처리
    return String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  },
  /* 순위 목록 그리기: items = [{name, sub, count}] */
  rank(el, items, unit) {
    if (!items.length) { el.innerHTML = '<li class="empty">아직 기록이 없어요</li>'; return; }
    const max = Math.max(...items.map(i => i.count));
    el.innerHTML = items.map(i => `
      <li>
        <span class="name">${dash.esc(i.name)} ${i.sub ? `<span class="sub">${dash.esc(i.sub)}</span>` : ""}</span>
        <span class="num">${i.count.toLocaleString()}${unit}</span>
        <span class="bar"><span style="width:${Math.max(4, i.count / max * 100)}%"></span></span>
      </li>`).join("");
  },
  houseName(h) { return `${h.main_use || "빈집"} #${h.house_id}`; },
  /* 기간 버튼 묶음 연결, 기간 버튼 3개에 이벤트 감지 등록 */
  bindDays(section, onChange) {
    const buttons = section.querySelectorAll(".seg button");
    buttons.forEach(b => b.addEventListener("click", () => {
      buttons.forEach(x => x.setAttribute("aria-pressed", x === b));
      onChange(Number(b.dataset.days));
    }));
  },
};

(function () {
  const section = document.getElementById("dash-public");
  const $ = id => document.getElementById(id);

  /* 서버에서 통계받아 화면 채우기 */ 
  async function load(days) {
    try {
      const d = await dash.get(`/api/trends?days=${days}`);
      $("pub-views").textContent = d.summary.views.toLocaleString();
      $("pub-saves").textContent = d.summary.saves.toLocaleString();
      $("pub-regions-n").textContent = d.summary.regions.toLocaleString();
      dash.rank($("pub-regions"), d.top_regions.map(r => ({ name: r.name, count: r.count })), "회");
      dash.rank($("pub-houses"), d.top_houses.map(h => ({ name: dash.houseName(h), sub: h.region_name, count: h.count })), "회");
      dash.rank($("pub-saved"), d.top_saved.map(h => ({ name: dash.houseName(h), sub: h.region_name, count: h.count })), "명");
      dash.rank($("pub-industries"), d.top_industries.map(i => ({ name: i.name, count: i.count })), "건");
      $("pub-note").textContent = `조회·찜 횟수는 최근 ${d.days}일 기록, '지금 많이 찜된 빈집'과 '희망업종'은 현재 찜 목록 기준이에요.`;
    } catch (e) {
      $("pub-note").textContent = "통계를 불러오지 못했어요: " + e.message;
    }
  }

  dash.bindDays(section, load);
  load(7);
})();
