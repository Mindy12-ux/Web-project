/* [담당 D] 공무원용 대시보드
   templates/dashboard.html 에서 role == 'official' 일 때만 불러옴 (dashboard.js 다음에)
   데이터: GET /api/admin/stats?days=, GET /api/admin/members/<id> */

(function () {
  const section = document.getElementById("dash-official");
  const $ = id => document.getElementById(id);
  const EVENT_LABEL = { view_region: "지역 보기", view_house: "빈집 보기", save: "찜", edit: "찜 수정",
                        unsave: "찜 취소", select_industry: "희망업종 선택" };
  const GRADE_LABEL = { "1": "1등급", "2": "2등급", "3": "3등급", "NA": "미산정" };

  /* 세로 막대 그리기: values = [{v, title, cls}] */
  function cols(el, values) {
    const max = Math.max(1, ...values.map(x => x.v));
    el.innerHTML = values.map(x =>
      `<div class="${x.cls || ""}" title="${dash.esc(x.title)}" style="height:${x.v ? Math.max(3, x.v / max * 100) : 0}%"></div>`
    ).join("");
  }

  async function showMember(id) {
    const box = $("off-member-detail");
    try {
      const d = await dash.get(`/api/admin/members/${encodeURIComponent(id)}`);
      box.innerHTML = `<h3>${dash.esc(d.nickname)}님의 최근 활동</h3>
        <div class="table-wrap"><table class="dash-table">
          <thead><tr><th>시각</th><th>행동</th><th>위치</th><th>빈집</th><th>업종</th></tr></thead>
          <tbody>${d.events.map(e => `<tr><td>${e.created_at}</td><td>${EVENT_LABEL[e.event_type] || e.event_type}</td>
            <td>${dash.esc(e.region_name)}</td><td>${e.house_id ? "#" + e.house_id : "–"}</td><td>${dash.esc(e.industry || "–")}</td></tr>`).join("")}
          </tbody></table></div>`;
    } catch (e) {
      box.innerHTML = `<p class="empty">${dash.esc(e.message)}</p>`;
    }
  }

  async function load(days) {
    try {
      const d = await dash.get(`/api/admin/stats?days=${days}`);

      // 날짜별: 하루에 조회·찜 막대 두 개
      cols($("off-daily"), d.daily.flatMap(x => [
        { v: x.views, title: `${x.date} 조회 ${x.views}` },
        { v: x.saves, title: `${x.date} 찜 ${x.saves}`, cls: "save" },
      ]));
      $("off-daily-axis").innerHTML = `<span>${d.daily[0].date}</span><span>${d.daily[d.daily.length - 1].date}</span>`;

      cols($("off-hours"), d.hours.map((v, h) => ({ v, title: `${h}시 ${v}건`, cls: "save" })));
      dash.rank($("off-industries"), d.industries.map(i => ({ name: i.name, count: i.count })), "건");

      $("off-houses").innerHTML = d.houses.length ? d.houses.map(h => `
        <tr><td>${dash.esc(dash.houseName(h))}</td><td>${dash.esc(h.region_name)}</td>
            <td><span class="grade g${h.grade_code === "NA" ? "0" : h.grade_code}">${GRADE_LABEL[h.grade_code] || h.grade_code}</span></td>
            <td class="n">${h.views}</td><td class="n">${h.saves}</td><td class="n">${h.saved_now}</td></tr>`).join("")
        : `<tr><td colspan="6" class="empty">이 기간에 관심 받은 빈집이 없어요</td></tr>`;

      $("off-members").innerHTML = d.members.length ? d.members.map(m => `
        <tr class="clickable" data-id="${dash.esc(m.member_id)}"><td>${dash.esc(m.nickname)}</td>
            <td class="n">${m.events}</td><td class="n">${m.saves}</td><td>${m.last_at}</td></tr>`).join("")
        : `<tr><td colspan="4" class="empty">표시할 회원이 없어요</td></tr>`;
      $("off-members").querySelectorAll("tr.clickable").forEach(tr =>
        tr.addEventListener("click", () => showMember(tr.dataset.id)));

      $("off-hidden").textContent = d.hidden_members
        ? `동의하지 않은 회원 ${d.hidden_members}명의 활동은 위 집계에만 포함되고 이름은 표시하지 않아요.` : "";
      $("off-member-detail").innerHTML = "";
      $("off-note").textContent = `최근 ${d.days}일, 소속 시군(${d.sigungu}) 기록만 집계했어요.`;
    } catch (e) {
      $("off-note").textContent = "공무원용 통계를 불러오지 못했어요: " + e.message;
    }
  }

  dash.bindDays(section, load);
  load(30);
})();
