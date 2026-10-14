/* 빈집을 잇다 — 머리글 메뉴 펼치기 (index.html) [담당 B]
   ☰ 버튼을 누르면 메뉴가 열리고, 바깥을 누르거나 Esc 를 누르면 닫힙니다. */
(function () {
  var btn  = document.getElementById("hdrMenuBtn");
  var menu = document.getElementById("hdrMenu");
  if (!btn || !menu) return;

  function setOpen(open) {
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    btn.setAttribute("aria-label", open ? "메뉴 닫기" : "메뉴 열기");
    menu.hidden = !open;
  }

  btn.addEventListener("click", function () {
    setOpen(btn.getAttribute("aria-expanded") !== "true");
  });
  document.addEventListener("click", function (e) {
    if (!menu.hidden && !menu.contains(e.target) && !btn.contains(e.target)) setOpen(false);
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !menu.hidden) { setOpen(false); btn.focus(); }
  });
})();
