/* 빈집을 잇다 — 메인 화면 스크롤 연출 [담당 B]
  스크롤하면 가운데 사진 덩어리가 화면 전체로 커지고(1페이지 → 2페이지),
  그 위로 ABOUT 글과 바닥글(index.html)이 천천히 나타납니다.
   진행값: p(전체 0→1) → g(사진 커짐 0→1), r(2페이지 글 0→1) */
(function () {
  const intro  = document.getElementById("intro");
  const stage  = document.getElementById("stage");
  const photo  = document.getElementById("photo");
  const anchor = document.getElementById("photoAnchor");
  const shade  = stage.querySelector(".shade");
  const header = document.getElementById("homeHeader");
  if (!intro || !stage || !photo || !anchor) return;

  // 덩어리 모양: 위가 좁고 둥근 삼각형 느낌. 시계 방향 점들 (0~1, 덩어리 기준 상자 안의 위치)
  // 이 점들을 부드러운 곡선으로 잇고, 스크롤하면 각 점이 화면 바깥쪽으로 퍼져 전체 화면이 됨
  const BLOB = [
    [.36, .00], [.60, .10], [.84, .30], [1.0, .58], [.94, .86], [.72, .99],
    [.47, .95], [.16, 1.0], [.00, .82], [.04, .45], [.17, .14]
  ];
  const SPREAD = 1.8;  // 다 퍼졌을 때 화면보다 몇 배 큰 상자로 (모서리까지 확실히 덮기)

  // 각 점을 중심에서 같은 방향으로 밀어 정사각형 테두리 위에 올린 위치 = 다 퍼졌을 때의 점
  const EDGE = BLOB.map(function (pt) {
    const dx = pt[0] - .5, dy = pt[1] - .5, k = .5 / Math.max(Math.abs(dx), Math.abs(dy));
    return [.5 + dx * k, .5 + dy * k];
  });

  // 닫힌 점 목록 → 부드러운 곡선 경로 (Catmull-Rom → 베지어)
  function smoothPath(pts) {
    const n = pts.length; let d = "M" + pts[0][0].toFixed(1) + "," + pts[0][1].toFixed(1);
    for (let i = 0; i < n; i++) {
      const p0 = pts[(i - 1 + n) % n], p1 = pts[i], p2 = pts[(i + 1) % n], p3 = pts[(i + 2) % n];
      d += "C" + (p1[0] + (p2[0] - p0[0]) / 6).toFixed(1) + "," + (p1[1] + (p2[1] - p0[1]) / 6).toFixed(1) +
           " " + (p2[0] - (p3[0] - p1[0]) / 6).toFixed(1) + "," + (p2[1] - (p3[1] - p1[1]) / 6).toFixed(1) +
           " " + p2[0].toFixed(1) + "," + p2[1].toFixed(1);
    }
    return d + "Z";
  }

  // 사진 구도 (원본 픽셀 기준, hero.jpg 를 바꾸면 여기만 고치면 됨)
  //  FOCUS: 1페이지 덩어리 안에 보일 부분 — 집 전체 + 주변 풍경
  //  WIDE_X: 2페이지 전체 화면일 때 가로 중심 (0~1, 집이 화면 밖으로 안 나가게)
  const FOCUS = { cx: 1300, cy: 388, w: 1010, h: 776 };
  const WIDE_X = .6;
  let img = null;
  const probe = new Image();
  probe.onload = function () { img = { w: probe.naturalWidth, h: probe.naturalHeight }; render(); };
  const m = /url\(["']?([^"')]+)/.exec(getComputedStyle(photo).getPropertyValue("--photo"));
  if (m) probe.src = m[1];

  function lerp(a, b, t) { return a + (b - a) * t; }
  function clamp(v) { return Math.min(1, Math.max(0, v)); }
  function ease(t) { return t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2; }

  let ticking = false;
  function render() {
    ticking = false;
    const total = intro.offsetHeight - window.innerHeight;
    const p = total > 0 ? clamp(-intro.getBoundingClientRect().top / total) : 0;
    const g = ease(clamp(p / .5));             // 0 ~ 50% 구간: 사진이 커짐
    const r = ease(clamp((p - .45) / .3));     // 45 ~ 75% 구간: 2페이지 글이 나타남

    const s = stage.getBoundingClientRect();
    const a = anchor.getBoundingClientRect();
    // 처음: 덩어리 기준 상자(anchor) 안의 BLOB 점 → 끝: 화면을 SPREAD 배로 키운 상자 테두리의 EDGE 점
    const ax = a.left - s.left, ay = a.top - s.top;
    const bw = s.width * SPREAD, bh = s.height * SPREAD;
    const bx = (s.width - bw) / 2, by = (s.height - bh) / 2;
    const pts = BLOB.map(function (pt, i) {
      return [lerp(ax + pt[0] * a.width, bx + EDGE[i][0] * bw, g),
              lerp(ay + pt[1] * a.height, by + EDGE[i][1] * bh, g)];
    });
    const clip = "path('" + smoothPath(pts) + "')";
    photo.style.clipPath = clip;
    if (shade) shade.style.clipPath = clip;  // 어둡게는 사진 위에만

    // 사진 크기·위치: 처음엔 FOCUS 가 덩어리에 꼭 맞게(작게) → 끝엔 화면 전체를 덮게(넓게)
    if (img) {
      const aw = a.width, ah = a.height, acx = a.left - s.left + aw / 2, acy = a.top - s.top + ah / 2;
      const s0 = Math.max(aw / FOCUS.w, ah / FOCUS.h);
      const x0 = acx - FOCUS.cx * s0, y0 = acy - FOCUS.cy * s0;
      const W = s.width, H = s.height;
      const s1 = Math.max(W / img.w, H / img.h);
      const x1 = Math.min(0, Math.max(W - img.w * s1, W / 2 - img.w * WIDE_X * s1));
      const y1 = (H - img.h * s1) / 2;
      const sc = lerp(s0, s1, g);
      photo.style.backgroundSize = (img.w * sc).toFixed(1) + "px " + (img.h * sc).toFixed(1) + "px, cover, cover";
      photo.style.backgroundPosition = lerp(x0, x1, g).toFixed(1) + "px " + lerp(y0, y1, g).toFixed(1) + "px, center, center";
    }

    // body 에 넣어야 index.html 의 바닥글(무대 밖)도 같은 값을 씀
    document.body.style.setProperty("--g", g.toFixed(3));
    document.body.style.setProperty("--r", r.toFixed(3));
    document.body.classList.toggle("is-about", r > 0);
    if (header) header.classList.toggle("is-dark", g > .6);
  }
  function request() { if (!ticking) { ticking = true; requestAnimationFrame(render); } }

  window.addEventListener("scroll", request, { passive: true });
  window.addEventListener("resize", request);
  render();
})();
