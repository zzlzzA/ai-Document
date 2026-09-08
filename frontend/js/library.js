/* ===== 文档库（library）===== */
"use strict";

async function loadLibrary() {
  await loadFilterPanel();
  await loadDocs();
}

const EXT_OPTIONS = ["PDF", "DOCX", "DOC", "XLSX", "PPTX", "TXT", "MD"];
const TIME_OPTIONS = [
  ["0", "全部时间"], ["1", "今天"], ["7", "近 7 天"],
  ["30", "近 30 天"], ["90", "近 90 天"], ["year", "今年"],
];

// 筛选面板：分类 / 时间 / 类型 / 标签
async function loadFilterPanel() {
  try {
    const [cats, tags] = await Promise.all([api("/api/categories"), api("/api/tags")]);
    const total = cats.reduce((a, c) => a + c.count, 0);
    $("#fpCategory").innerHTML = chipHTML("cat", "", "全部", total) +
      cats.map((c) => chipHTML("cat", c.name, c.name, c.count)).join("");
    $("#fpTime").innerHTML = TIME_OPTIONS.map(([v, t]) => chipHTML("time", v, t)).join("");
    $("#fpExt").innerHTML = chipHTML("ext", "", "全部") +
      EXT_OPTIONS.map((e) => chipHTML("ext", e.toLowerCase(), e)).join("");
    $("#fpTag").innerHTML = chipHTML("tag", "", "全部") +
      (tags.length ? tags.map((t) => chipHTML("tag", t.name, `${t.name} ${t.count}`)).join("")
                   : '<span class="muted fp-empty">暂无标签</span>');
    bindFilterChips();
    syncFilterPanel();
  } catch (e) { toast("加载筛选失败: " + e.message); }
}

function chipHTML(group, value, label, count) {
  return `<button class="fp-chip" data-group="${group}" data-val="${esc(value)}" data-label="${esc(label)}">${esc(label)}${count != null ? ` <i>${count}</i>` : ""}</button>`;
}

function bindFilterChips() {
  $$(".fp-chip").forEach((chip) => chip.addEventListener("click", () => {
    const group = chip.dataset.group;
    const val = chip.dataset.val;
    if (group === "cat") state.fpCat = val;
    if (group === "time") state.fpTime = val;
    if (group === "ext") state.fpExt = val;
    if (group === "tag") state.fpTag = val;
    syncFilterPanel();
  }));
}

// 面板勾选状态与筛选按钮徽标
function syncFilterPanel() {
  $$(".fp-chip").forEach((chip) => {
    const g = chip.dataset.group;
    const active = (g === "cat" && chip.dataset.val === state.fpCat) ||
                   (g === "time" && chip.dataset.val === state.fpTime) ||
                   (g === "ext" && chip.dataset.val === state.fpExt) ||
                   (g === "tag" && chip.dataset.val === state.fpTag);
    chip.classList.toggle("active", active);
  });
  const n = (state.fpCat ? 1 : 0) + (state.fpTime !== "0" ? 1 : 0) +
            (state.fpExt ? 1 : 0) + (state.fpTag ? 1 : 0);
  const badge = $("#filterCount");
  badge.classList.toggle("hidden", n === 0);
  badge.textContent = n;
}

$("#libFilterBtn").addEventListener("click", () => $("#filterPanel").classList.toggle("hidden"));

$("#fpApply").addEventListener("click", () => {
  state.libCategory = state.fpCat;
  state.libCreatedFrom = resolveTimeFilter(state.fpTime);
  state.libExt = state.fpExt;
  state.libTag = state.fpTag;
  state.libPage = 1;
  $("#filterPanel").classList.add("hidden");
  loadDocs();
});

$("#fpReset").addEventListener("click", () => {
  state.fpCat = ""; state.fpTime = "0"; state.fpExt = ""; state.fpTag = "";
  syncFilterPanel();
});

async function loadDocs() {
  try {
    const params = new URLSearchParams({ page: state.libPage, page_size: 50 });
    if (state.libCategory) params.set("category", state.libCategory);
    if (state.libTag) params.set("tag", state.libTag);
    if (state.libQ) params.set("q", state.libQ);
    if (state.libExt) params.set("ext", state.libExt);
    if (state.libCreatedFrom) params.set("created_from", state.libCreatedFrom);
    const data = await api("/api/documents?" + params);
    state.libTotal = data.total;
    renderDocs(data.items);
    renderPager();
  } catch (e) { toast("加载文档失败: " + e.message); }
}

// 时间筛选：计算起始时间戳（秒）
function resolveTimeFilter(val) {
  if (!val || val === "0") return 0;
  const now = new Date();
  if (val === "year") {
    return Math.floor(new Date(now.getFullYear(), 0, 1).getTime() / 1000);
  }
  const days = Number(val);
  const d = new Date(now.getTime() - days * 86400000);
  d.setHours(0, 0, 0, 0); // 从当天零点起算
  return Math.floor(d.getTime() / 1000);
}

function renderDocs(items) {
  const tb = $("#docTbody");
  tb.innerHTML = "";
  state.selected.clear();
  $("#checkAll").checked = false;
  $("#libDelSel").classList.add("hidden");
  if (!items.length) {
    tb.innerHTML = '<tr><td colspan="9" class="muted center" style="padding:30px">没有匹配的文档</td></tr>';
    return;
  }
  items.forEach((d) => {
    const tr = document.createElement("tr");
    const tags = (d.tags || []).map((t) => `<span class="tag-chip">${esc(t)}</span>`).join(" ");
    const fav = d.favorite ? "active" : "";
    tr.innerHTML = `
      <td><input type="checkbox" class="row-check" data-id="${d.id}"></td>
      <td class="fav-cell"><button class="fav-star ${fav}" data-fav="${d.id}" title="${d.favorite ? "取消收藏" : "收藏"}">${d.favorite ? "★" : "☆"}</button></td>
      <td class="fn" data-id="${d.id}">${esc(d.name)}</td>
      <td><span class="tag-cat">${esc(d.category)}</span>${d.category_manual ? '<span class="cat-manual" title="人工修正过">手动</span>' : ""}</td>
      <td>${tags || '<span class="muted">-</span>'}</td>
      <td>${esc(d.source)}</td>
      <td>${fmtSize(d.size)}</td>
      <td>${d.parse_ok ? '<span class="badge-ok">已索引</span>' : `<span class="badge-fail" title="${esc(d.parse_msg)}">解析失败</span>`}</td>
      <td class="row-op">
        <button data-act="open" data-id="${d.id}">打开</button>
        <button data-act="edit" data-id="${d.id}">编辑</button>
        <button data-act="del" data-id="${d.id}">删除</button>
      </td>`;
    tr.querySelectorAll(".row-check").forEach((cb) => cb.addEventListener("change", onCheckChange));
    tr.querySelectorAll(".fn").forEach((el) => el.addEventListener("click", () => openDocModal(d.id)));
    tr.querySelectorAll(".fav-star").forEach((btn) => {
      btn.addEventListener("click", async (ev) => {
        ev.stopPropagation();
        const id = Number(btn.dataset.fav);
        const toFav = btn.textContent === "☆";
        await toggleFavorite(id, toFav);
      });
    });
    tr.querySelectorAll("[data-act]").forEach((btn) => {
      btn.addEventListener("click", async (ev) => {
        ev.stopPropagation();
        const id = Number(btn.dataset.id);
        if (btn.dataset.act === "open") { try { await api(`/api/documents/${id}/open`, { method: "POST" }); toast("已调用系统打开原文件"); } catch (e) { toast(e.message); } }
        if (btn.dataset.act === "edit") openDocModal(id);
        if (btn.dataset.act === "del") deleteDoc(id);
      });
    });
    tb.appendChild(tr);
  });
}

async function toggleFavorite(id, toFav) {
  try {
    await api(`/api/documents/${id}/favorite`, {
      method: "POST",
      body: JSON.stringify({ favorite: toFav }),
    });
    toast(toFav ? "已收藏" : "已取消收藏");
    loadDocs(); loadHome();
  } catch (e) { toast(e.message); }
}

function onCheckChange() {
  state.selected.clear();
  $$(".row-check:checked").forEach((cb) => state.selected.add(Number(cb.dataset.id)));
  $("#libDelSel").classList.toggle("hidden", state.selected.size === 0);
}

function renderPager() {
  const pages = Math.max(1, Math.ceil(state.libTotal / 50));
  const el = $("#libPager");
  el.innerHTML = `<span class="muted">共 ${state.libTotal} 篇</span>
    <button ${state.libPage <= 1 ? "disabled" : ""} id="pgPrev">‹</button>
    <span>${state.libPage} / ${pages}</span>
    <button ${state.libPage >= pages ? "disabled" : ""} id="pgNext">›</button>`;
  $("#pgPrev")?.addEventListener("click", () => { state.libPage--; loadDocs(); });
  $("#pgNext")?.addEventListener("click", () => { state.libPage++; loadDocs(); });
}

async function deleteDoc(id) {
  if (!confirm("确定删除该文档？知识库记录与向量将一并移除。")) return;
  try {
    await api(`/api/documents/${id}`, { method: "DELETE" });
    toast("已删除");
    loadDocs(); loadSidebarStats();
  } catch (e) { toast(e.message); }
}

$("#libSearch").addEventListener("input", debounce(() => {
  state.libQ = $("#libSearch").value.trim();
  state.libPage = 1;
  loadDocs();
}, 400));
$("#libRefresh").addEventListener("click", () => loadLibrary());
$("#checkAll").addEventListener("change", (e) => {
  $$(".row-check").forEach((cb) => { cb.checked = e.target.checked; });
  onCheckChange();
});
$("#libDelSel").addEventListener("click", async () => {
  if (!confirm(`确定删除选中的 ${state.selected.size} 篇文档？`)) return;
  for (const id of state.selected) await api(`/api/documents/${id}`, { method: "DELETE" });
  toast("已批量删除");
  state.selected.clear();
  loadDocs(); loadSidebarStats();
});
