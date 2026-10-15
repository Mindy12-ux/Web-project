/* 빈집을 잇다 — 머리글 메뉴 펼치기 (index.html) [담당 B]
   ☰ 버튼을 누르면 메뉴가 열리고, 바깥을 누르거나 Esc 를 누르면 닫힙니다. */
(function () {
  var btn  = document.getElementById("hdrMenuBtn"); // 4줄: ☰ 버튼
  var menu = document.getElementById("hdrMenu"); // 5줄: 메뉴 카드
  if (!btn || !menu) return;

  function setOpen(open) { // 8–12줄: 열기/닫기 한곳에서
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    btn.setAttribute("aria-label", open ? "메뉴 닫기" : "메뉴 열기");
    menu.hidden = !open; // 숨김 해제 = 펼치기
  }

  btn.addEventListener("click", function () { // 14–16줄: ☰ 누르면 반대로
    setOpen(btn.getAttribute("aria-expanded") !== "true");
  });
  document.addEventListener("click", function (e) { // 17–19줄: 바깥을 누르면 닫기
    if (!menu.hidden && !menu.contains(e.target) && !btn.contains(e.target)) setOpen(false);
  });
  document.addEventListener("keydown", function (e) { // 20–22줄: Esc 누르면 닫기
    if (e.key === "Escape" && !menu.hidden) { setOpen(false); btn.focus(); }
  });
})();
