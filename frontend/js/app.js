/* ===== 应用入口（app）：全局状态 + 视图切换 + 初始化 ===== */
"use strict";

/* 全局状态 */
const state = {
  libCategory: "",
  libTag: "",
  libQ: "",
  libExt: "",
  libCreatedFrom: 0,
  libPage: 1,
  libTotal: 0,
  selected: new Set(),
  // 筛选面板暂存选择（点"应用"才生效）
  fpCat: "",
  fpTime: "0",
  fpExt: "",
  fpTag: "",
};

/* 视图切换 */
const views = { home: "#view-home", library: "#view-library", chat: "#view-chat", settings: "#view-settings" };
$$(".nav-item").forEach((item) => {
  item.addEventListener("click", () => {
    $$(".nav-item").forEach((i) => i.classList.remove("active"));
    item.classList.add("active");
    Object.entries(views).forEach(([k, sel]) => $(sel).classList.toggle("active", k === item.dataset.view));
    if (item.dataset.view === "home") loadHome();
    if (item.dataset.view === "library") loadLibrary();
    if (item.dataset.view === "settings") loadSettings();
  });
});

/* 初始化 */
loadHome();
loadChatBadge();
pollNotifications();
setTimeout(pollNotifications, 5000);   // 等启动扫描完成后刷新一次提醒徽标

// 恢复上次背景设置
applyTheme(localStorage.getItem("aiwj_theme") === "dark" ? "dark" : "light");
applyBg(localStorage.getItem("aiwj_bg") === "1");
