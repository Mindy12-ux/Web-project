/* 빈집을 잇다 — 빈집 찾기(지도) 화면 [담당 B]
   흐름: 지역 탭 → 리·동 숫자 원(지도·왼쪽 목록) → 그 리·동의 빈집 목록 → 빈집 상세 + 반경별 주변 상가
   지도(카카오맵)를 못 불러와도 왼쪽 정보 칸만으로 끝까지 볼 수 있게 만들었습니다.
   API: /api/regions, /api/regions/<시군>/clusters, /api/houses, /api/houses/<id>, /api/houses/<id>/stores */
(function () {
  var side    = document.getElementById("side");
  var tabs    = document.getElementById("regionTabs");
  var filters = document.getElementById("gradeFilters");
  var mapEl   = document.getElementById("kmap");

  var state = {
    view: "intro",          // intro(리·동 목록) | list(빈집 목록) | detail(빈집 상세)
    regions: [], region: null,
    clusters: [], cluster: null,
    houses: [], house: null,
    stores: null, radius: null, industry: null
  };
  var map = null, clusterOverlays = [], storeOverlays = [], circle = null, tip = null;

  // ── 도우미 ────────────────────────────────────────────
  function esc(v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function api(url) {
    return fetch(url).then(function (res) {
      return res.json().then(function (body) {
        if (!body.ok) throw new Error(body.error || "요청에 실패했어요");
        return body.data;
      });
    });
  }
  function gradeQuery() {
    var boxes = filters.querySelectorAll("input[type=checkbox]");
    if (!boxes.length) return "";                       // 등급표가 비어 있으면 전체
    var on = [].filter.call(boxes, function (b) { return b.checked; }).map(function (b) { return b.value; });
    return "grades=" + encodeURIComponent(on.join(","));
  }
  function gradeClass(code) { return "grade g" + (code === "NA" ? "0" : code); }
  function none(v, fmt) { return v == null || v === "" ? null : (fmt ? fmt(v) : v); }
  function area(v) { return Number(v).toLocaleString("ko-KR", { maximumFractionDigits: 2 }) + "㎡"; }
  function dist(m) { return m < 1000 ? Math.round(m) + "m" : (m / 1000).toFixed(m % 1000 ? 1 : 0) + "km"; }
  function clusterName(c) { return (c.parent_name && c.parent_name !== currentRegion().name ? c.parent_name + " " : "") + c.name; }
  function currentRegion() {
    for (var i = 0; i < state.regions.length; i++) if (state.regions[i].region_code === state.region) return state.regions[i];
    return {};
  }
  function findCluster(code) {
    for (var i = 0; i < state.clusters.length; i++) if (state.clusters[i].region_code === code) return state.clusters[i];
    return null;
  }
  function showError(err) {
    side.innerHTML = '<p class="notice">' + esc(err.message || err) + "</p>";
  }

  // ── 지역 탭 ────────────────────────────────────────────
  function renderTabs() {
    tabs.innerHTML = state.regions.map(function (r) {
      return '<button type="button" data-region="' + esc(r.region_code) + '" aria-pressed="' +
        (r.region_code === state.region) + '">' + esc(r.name) + "<small>" + r.house_count + "</small></button>";
    }).join("");
  }
  tabs.addEventListener("click", function (e) {
    var btn = e.target.closest("button[data-region]");
    if (btn && btn.dataset.region !== state.region) selectRegion(btn.dataset.region);
  });
  filters.addEventListener("change", function () { loadClusters(false); });

  function selectRegion(code) {
    state.region = code;
    state.cluster = null; state.house = null; state.stores = null;
    renderTabs();
    loadClusters(true);
  }

  // ── 리·동 숫자 원 ─────────────────────────────────────
  function loadClusters(fit) {
    if (!state.region) return;
    side.innerHTML = '<p class="mapx-empty">빈집 수를 세는 중…</p>';
    api("/api/regions/" + state.region + "/clusters?" + gradeQuery()).then(function (rows) {
      state.clusters = rows;
      drawClusters(fit);
      if (state.view === "detail" && state.house) return showDetail();
      if (state.view === "list" && findCluster(state.cluster)) return loadHouses();
      state.cluster = null;
      showIntro();
    }).catch(showError);
  }

  function showIntro() {
    state.view = "intro";
    clearStores();
    markSelectedCluster();
    var r = currentRegion();
    var total = state.clusters.reduce(function (n, c) { return n + c.house_count; }, 0);
    var html = '<div class="side-head"><p class="eyebrow">' + esc(r.name || "") + '</p>' +
      "<h2>리·동 " + state.clusters.length + "곳 · 빈집 " + total + "채</h2>" +
      '<p class="meta">지도의 숫자 원이나 아래 목록을 눌러 보세요</p></div>';
    if (!state.clusters.length) {
      html += '<p class="mapx-empty">' + (r.house_count === 0
        ? "이 지역의 빈집 데이터가 아직 DB에 없어요."
        : "조건에 맞는 빈집이 없어요. 등급 필터를 바꿔 보세요.") + "</p>";
    } else {
      html += '<ul class="pick-list">' + state.clusters.map(function (c) {
        return '<li><button type="button" class="pick" data-action="cluster" data-code="' + esc(c.region_code) + '">' +
          "<span><b>" + esc(c.name) + "</b>" + (c.parent_name ? "<small>" + esc(c.parent_name) + "</small>" : "") + "</span>" +
          '<span class="count">' + c.house_count + "채</span></button></li>";
      }).join("") + "</ul>";
    }
    side.innerHTML = html;
  }

  function selectCluster(code) {
    state.cluster = code;
    state.house = null;
    markSelectedCluster();
    var c = findCluster(code);
    if (map && c) map.panTo(new kakao.maps.LatLng(c.lat, c.lng));
    loadHouses();
  }

  // ── 빈집 목록 ─────────────────────────────────────────
  function loadHouses() {
    side.innerHTML = '<p class="mapx-empty">빈집 목록을 불러오는 중…</p>';
    api("/api/houses?region=" + encodeURIComponent(state.cluster) + "&" + gradeQuery()).then(function (rows) {
      state.houses = rows;
      showList();
    }).catch(showError);
  }

  function showList() {
    state.view = "list";
    clearStores();
    markSelectedCluster();
    var c = findCluster(state.cluster) || {};
    var html = '<button type="button" class="side-back" data-action="intro">← ' + esc(currentRegion().name) + " 전체</button>" +
      '<div class="side-head"><p class="eyebrow">' + esc(c.parent_name || "") + "</p>" +
      "<h2>" + esc(c.name || "") + "</h2>" +
      '<p class="meta">빈집 ' + state.houses.length + "채</p></div>";
    html += '<ul class="pick-list">' + state.houses.map(function (h) {
      var sub = [none(h.built_year, function (y) { return y + "년 준공"; }), none(h.floor_area, area)].filter(Boolean).join(" · ");
      return '<li><button type="button" class="pick" data-action="house" data-id="' + h.house_id + '">' +
        '<span><span class="' + gradeClass(h.grade_code) + '">' + esc(h.grade_label) + "</span> " +
        "<b>" + esc(h.main_use || "주택 유형 정보 없음") + "</b>" +
        "<small>" + esc(sub || "건물 정보 없음") + "</small></span>" +
        '<span class="count">#' + h.house_id + "</span></button></li>";
    }).join("") + "</ul>";
    side.innerHTML = html;
  }

  // ── 빈집 상세 ─────────────────────────────────────────
  function selectHouse(id) {
    side.innerHTML = '<p class="mapx-empty">빈집 정보를 불러오는 중…</p>';
    api("/api/houses/" + id).then(function (h) {
      state.house = h;
      state.stores = null; state.radius = null; state.industry = null;
      showDetail();
      loadStores();
    }).catch(showError);
  }

  function showDetail() {
    state.view = "detail";
    var h = state.house;
    var rows = [
      ["등급", h.grade_label + " · " + h.grade_description],
      ["준공연도", none(h.built_year, function (y) { return y + "년"; })],
      ["구조", none(h.structure)],
      ["연면적", none(h.floor_area, area)],
      ["대지면적", none(h.land_area, area)],
      ["도로접면", none(h.road_contact)],
      ["용도지역", none(h.zoning)]
    ];
    side.innerHTML =
      '<button type="button" class="side-back" data-action="list">← ' + esc((findCluster(h.region_code) || {}).name || "빈집") + " 목록</button>" +
      '<div class="side-head"><p class="eyebrow">' + esc(h.region_name) + "</p>" +
      "<h2>" + esc(h.main_use || "주택 유형 정보 없음") + ' <span class="' + gradeClass(h.grade_code) + '">' + esc(h.grade_label) + "</span></h2>" +
      '<p class="meta">조사 기준일 ' + esc(h.data_date) + " · 빈집 #" + h.house_id + "</p></div>" +
      '<dl class="kv">' + rows.map(function (r) {
        return "<div><dt>" + r[0] + "</dt><dd" + (r[1] == null ? ' class="none">정보 없음' : ">" + esc(r[1])) + "</dd></div>";
      }).join("") + "</dl>" +
      // 찜하기 등 버튼 자리: 다른 담당이 data-house-id 로 연결
      '<div class="house-actions card-actions" id="houseActions" data-house-id="' + h.house_id + '"></div>' +
      '<section class="stores" id="storesBox" aria-label="주변 상가"><h3>주변 상가</h3>' +
      '<p class="mapx-empty">주변 상가를 세는 중…</p></section>';
    if (state.stores) renderStores();
  }

  // ── 반경별 주변 상가 ──────────────────────────────────
  function loadStores() {
    var h = state.house, q = [];
    if (state.radius) q.push("radius=" + state.radius);
    if (state.industry) q.push("industry=" + encodeURIComponent(state.industry));
    api("/api/houses/" + h.house_id + "/stores" + (q.length ? "?" + q.join("&") : "")).then(function (data) {
      if (!state.house || state.house.house_id !== h.house_id) return;   // 그사이 다른 집을 골랐으면 버림
      state.stores = data;
      state.radius = data.radius;
      renderStores();
      drawStores(true);
    }).catch(function (err) {
      var box = document.getElementById("storesBox");
      if (box) box.innerHTML = '<h3>주변 상가</h3><p class="notice">' + esc(err.message) + "</p>";
    });
  }

  function renderStores() {
    var box = document.getElementById("storesBox");
    var d = state.stores;
    if (!box || !d) return;
    var html = "<h3>주변 상가</h3>";
    if (!d.radii.length) {
      box.innerHTML = html + '<p class="mapx-empty">이 지역은 반경별 상가 자료가 없어요.</p>';
      return;
    }
    html += '<div class="seg" role="group" aria-label="반경">' + d.radii.map(function (r) {
      return '<button type="button" data-action="radius" data-radius="' + r + '" aria-pressed="' + (r === d.radius) + '">' + dist(r) + "</button>";
    }).join("") + "</div>";
    html += '<p class="stores-total">반경 ' + dist(d.radius) + " 안 가게 <b>" + d.total.toLocaleString("ko-KR") + "곳</b></p>";

    var max = Math.max.apply(null, d.stats.map(function (s) { return s.store_count; }).concat([1]));
    html += '<ul class="stat-list">' + d.stats.map(function (s) {
      var on = s.industry_code === d.industry;
      return '<li><button type="button" class="stat" data-action="industry" data-code="' + esc(s.industry_code) + '" aria-pressed="' + on + '"' +
        (s.store_count ? "" : " disabled") + ">" + esc(s.name) +
        '<span class="stat-bar"><i style="width:' + (s.store_count / max * 100).toFixed(1) + '%"></i></span>' +
        '<span class="stat-n">' + s.store_count + "</span></button></li>";
    }).join("") + "</ul>";

    if (d.stores.length) {
      html += '<ul class="store-list">' + d.stores.slice(0, 30).map(function (s, i) {
        return '<li><div>' + esc(s.name) + " <span>" + esc(s.industry_name) + '</span></div><span class="dist">' + dist(s.distance_m) + "</span></li>";
      }).join("") + "</ul>";
    } else {
      html += '<p class="mapx-empty">반경 안에 표시할 가게가 없어요' + (d.total ? "." : " (상가 데이터가 비어 있을 수 있어요).") + "</p>";
    }
    html += '<p class="stores-note">' + (d.industry ? "업종을 한 번 더 누르면 전체 보기 · " : "업종을 누르면 그 업종만 지도에 표시 · ") +
      "지도에는 가까운 순 " + d.limit + "곳까지" + (d.data_date ? " · 상가 데이터 기준일 " + esc(d.data_date) : "") + "</p>";
    box.innerHTML = html;
  }

  // ── 왼쪽 칸 클릭 (한곳에서 처리) ──────────────────────
  side.addEventListener("click", function (e) {
    var el = e.target.closest("[data-action]");
    if (!el || el.disabled) return;
    var a = el.dataset.action;
    if (a === "intro") { state.cluster = null; showIntro(); }
    else if (a === "list") { state.house = null; showList(); }
    else if (a === "cluster") selectCluster(el.dataset.code);
    else if (a === "house") selectHouse(el.dataset.id);
    else if (a === "radius") { state.radius = Number(el.dataset.radius); loadStores(); }
    else if (a === "industry") { state.industry = state.industry === el.dataset.code ? null : el.dataset.code; loadStores(); }
  });

  // ── 카카오맵 ──────────────────────────────────────────
  function fallback(msg) {
    if (map) return;
    mapEl.innerHTML = '<div class="mapx-fallback"><p>카카오 지도를 불러오지 못했어요.<br>' + msg +
      "<br>왼쪽 목록으로는 그대로 볼 수 있어요.</p></div>";
  }
  function initMap() {
    if (!(window.kakao && kakao.maps && kakao.maps.load)) {
      return fallback(".env 의 KAKAO_JS_KEY 와 카카오 개발자 콘솔의 사이트 도메인 등록을 확인하세요.");
    }
    var timer = setTimeout(function () {
      fallback("카카오 개발자 콘솔에 지금 주소(" + location.origin + ")가 등록됐는지 확인하세요.");
    }, 6000);
    kakao.maps.load(function () {
      clearTimeout(timer);
      mapEl.innerHTML = "";
      map = new kakao.maps.Map(mapEl, { center: new kakao.maps.LatLng(35.43, 126.70), level: 9 });
      map.addControl(new kakao.maps.ZoomControl(), kakao.maps.ControlPosition.RIGHT);
      tip = new kakao.maps.CustomOverlay({ yAnchor: 1, zIndex: 5 });
      kakao.maps.event.addListener(map, "zoom_changed", renderClusterLayer);
      drawClusters(true);
      if (state.view === "detail") drawStores(false);
    });
  }

  // 줌에 따라 원을 다르게: 멀리(GROUP_LEVEL 이상)는 읍·면으로 합친 원, 그보다 가까우면 리·동 원
  // 리·동 이름표는 LABEL_LEVEL 보다 가까울 때만 (161개 원이 겹쳐 보이지 않게)
  var GROUP_LEVEL = 9, LABEL_LEVEL = 8;

  function drawClusters(fit) {
    if (!map) return;
    if (!state.clusters.length) {
      clearClusterOverlays();
      var r = currentRegion();
      if (fit && r.lat) { map.setCenter(new kakao.maps.LatLng(r.lat, r.lng)); map.setLevel(GROUP_LEVEL); }
      return;
    }
    if (fit) {
      var bounds = new kakao.maps.LatLngBounds();
      state.clusters.forEach(function (c) { bounds.extend(new kakao.maps.LatLng(c.lat, c.lng)); });
      if (state.clusters.length === 1) { map.setCenter(bounds.getSouthWest()); map.setLevel(6); }
      else map.setBounds(bounds, 40, 40, 40, 40);
    }
    renderClusterLayer();
  }

  function clearClusterOverlays() {
    clusterOverlays.forEach(function (o) { o.overlay.setMap(null); });
    clusterOverlays = [];
  }

  function clusterButton(count, label, aria, sizes) {
    var size = count >= sizes[0] ? "l" : count >= sizes[1] ? "m" : "s";
    var px = size === "l" ? 60 : size === "m" ? 50 : 40;
    var el = document.createElement("button");
    el.type = "button";
    el.className = "cluster";
    el.dataset.size = size;
    el.setAttribute("aria-label", aria);
    el.innerHTML = '<span class="dot">' + count + '</span><span class="label">' + esc(label) + "</span>";
    return { el: el, yAnchor: (px / 2) / (px + 26) };   // 숫자 원의 가운데가 좌표에 오게 (이름표 26px 보정)
  }

  function renderClusterLayer() {
    if (!map) return;
    clearClusterOverlays();
    var level = map.getLevel();
    mapEl.classList.toggle("is-far", level >= LABEL_LEVEL);

    if (level >= GROUP_LEVEL) {
      // 읍·면(상위 지역)별로 합치기: 빈집 수 합, 위치는 빈집 수로 가중 평균
      var groups = {}, order = [];
      state.clusters.forEach(function (c) {
        var key = c.parent_name || c.name;
        if (!groups[key]) { groups[key] = { name: key, count: 0, lat: 0, lng: 0 }; order.push(key); }
        var g = groups[key];
        g.count += c.house_count; g.lat += c.lat * c.house_count; g.lng += c.lng * c.house_count;
      });
      order.forEach(function (key) {
        var g = groups[key];
        var pos = new kakao.maps.LatLng(g.lat / g.count, g.lng / g.count);
        var b = clusterButton(g.count, g.name, g.name + " 빈집 " + g.count + "채, 눌러서 확대", [60, 20]);
        b.el.classList.add("is-group");
        b.el.addEventListener("click", function () { map.setLevel(GROUP_LEVEL - 2, { anchor: pos }); });
        var overlay = new kakao.maps.CustomOverlay({ position: pos, content: b.el, yAnchor: b.yAnchor, zIndex: 2 });
        overlay.setMap(map);
        clusterOverlays.push({ code: null, overlay: overlay, el: b.el });
      });
      return;
    }

    state.clusters.forEach(function (c) {
      var b = clusterButton(c.house_count, c.name, clusterName(c) + " 빈집 " + c.house_count + "채", [30, 10]);
      b.el.addEventListener("click", function () { selectCluster(c.region_code); });
      var overlay = new kakao.maps.CustomOverlay({ position: new kakao.maps.LatLng(c.lat, c.lng), content: b.el, yAnchor: b.yAnchor, zIndex: 2 });
      overlay.setMap(map);
      clusterOverlays.push({ code: c.region_code, overlay: overlay, el: b.el });
    });
    markSelectedCluster();
  }

  function markSelectedCluster() {
    clusterOverlays.forEach(function (o) {
      var on = o.code !== null && o.code === state.cluster;   // 읍·면 원(code null)은 선택 표시 안 함
      o.el.classList.toggle("is-selected", on);
      o.overlay.setZIndex(on ? 3 : 2);
    });
  }

  function clearStores() {
    storeOverlays.forEach(function (o) { o.setMap(null); });
    storeOverlays = [];
    if (circle) { circle.setMap(null); circle = null; }
    if (tip) tip.setMap(null);
  }

  function drawStores(fit) {
    if (!map || state.view !== "detail" || !state.stores || !state.stores.radius) return;
    clearStores();
    var d = state.stores;
    var center = new kakao.maps.LatLng(d.center.lat, d.center.lng);
    circle = new kakao.maps.Circle({
      center: center, radius: d.radius,
      strokeWeight: 2, strokeColor: "#2D6A4F", strokeOpacity: .85, strokeStyle: "dashed",
      fillColor: "#2D6A4F", fillOpacity: .06
    });
    circle.setMap(map);
    d.stores.forEach(function (s) {
      var dot = document.createElement("span");
      dot.className = "store-dot";
      dot.title = s.name + " · " + s.industry_name;
      var pos = new kakao.maps.LatLng(s.lat, s.lng);
      dot.addEventListener("mouseenter", function () { showTip(s, pos); });
      dot.addEventListener("click", function () { showTip(s, pos); });
      var o = new kakao.maps.CustomOverlay({ position: pos, content: dot, zIndex: 1 });
      o.setMap(map);
      storeOverlays.push(o);
    });
    if (fit) map.setBounds(circle.getBounds(), 20, 20, 20, 20);
  }

  function showTip(s, pos) {
    if (!tip) return;
    tip.setContent('<div class="store-tip">' + esc(s.name) + " · " + esc(s.industry_name) + " · " + dist(s.distance_m) + "</div>");
    tip.setPosition(pos);
    tip.setMap(map);
  }

  // ── 시작 ──────────────────────────────────────────────
  initMap();
  api("/api/regions").then(function (rows) {
    state.regions = rows;
    if (!rows.length) { side.innerHTML = '<p class="mapx-empty">지역 정보가 없어요.</p>'; return; }
    // 빈집이 있는 첫 지역(가나다순: 고창군 → 양산시)으로 시작
    var first = rows.filter(function (r) { return r.house_count > 0; })[0] || rows[0];
    selectRegion(first.region_code);
  }).catch(showError);
})();
