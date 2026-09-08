/* ===== 首页（home）===== */
"use strict";

const FORMAT_SHORT = { PDF: "PDF", DOCX: "DOC", DOC: "DOC", XLSX: "XLS", PPTX: "PPT", TXT: "TXT", MD: "MD" };

function renderFormatStats(formats) {
  const el = $("#formatStats");
  const total = formats.reduce((s, f) => s + f.count, 0);
  if (!total) {
    el.innerHTML = '<p class="muted">暂无文档，添加后这里会展示 PDF / Excel / PPT 等格式分布。</p>';
    return;
  }
  el.innerHTML = formats.map((f) => {
    const pct = Math.round(f.count / total * 100);
    const key = String(f.ext).toUpperCase();
    return `
      <div class="fmt-row">
        <span class="fmt-badge">${esc(FORMAT_SHORT[key] || key)}</span>
        <span class="fmt-name">${esc(f.ext)}</span>
        <div class="fmt-bar"><div class="fmt-fill" style="width:${pct}%"></div></div>
        <span class="fmt-num">${f.count} 份 · ${pct}%</span>
      </div>`;
  }).join("");
}

async function loadHome() {
  try {
    const [stats, fav, recent] = await Promise.all([
      api("/api/stats"), api("/api/favorites"), api("/api/recent?limit=8"),
    ]);
    const cd = $("#cardDocs"); if (cd) cd.textContent = stats.documents;
    const cc = $("#cardChunks"); if (cc) cc.textContent = stats.chunks;
    const ccat = $("#cardCats"); if (ccat) ccat.textContent = stats.categories;
    const cf = $("#cardFail"); if (cf) cf.textContent = stats.parse_failed;
    renderFormatStats(stats.formats || []);

    const recEl = $("#favList");
    recEl.innerHTML = fav.items.length
      ? ""
      : '<p class="muted">还没有收藏的文档 —— 到「文档库」中点击 ☆ 收藏常用文档，它们会出现在这里。</p>';
    fav.items.forEach((d) => {
      const el = document.createElement("div");
      el.className = "doc-card";
      el.innerHTML = `
        <div class="dc-head">
          <div class="dc-name">${esc(d.name)}</div>
          <button class="fav-star active" title="取消收藏" data-id="${d.id}">★</button>
        </div>
        <div class="dc-sum">${esc(d.summary || "暂无摘要")}</div>
        <div class="dc-meta">
          <span class="tag-cat">${esc(d.category)}</span>
          <span class="tag-score">已收藏</span>
        </div>
        <div class="dc-meta">
          <span>浏览 ${d.visit_count} 次 · 引用 ${d.cite_count}</span>
          <span>${fmtTime(d.created_at)}</span>
        </div>`;
      el.addEventListener("click", (ev) => {
        if (ev.target.closest(".fav-star")) return;
        openOriginalFile(d.id);
      });
      el.querySelector(".fav-star").addEventListener("click", async (ev) => {
        ev.stopPropagation();
        await toggleFavorite(d.id, false);
      });
      recEl.appendChild(el);
    });

    const recentEl = $("#recentList");
    recentEl.innerHTML = "";
    recent.forEach((d) => {
      const row = document.createElement("div");
      row.className = "doc-row";
      row.innerHTML = `<div><span class="dr-name">${esc(d.name)}</span></div>
        <div class="dr-meta"><span class="tag-cat">${esc(d.category)}</span> · ${fmtTime(d.created_at)} · ${fmtSize(d.size)}</div>`;
      row.addEventListener("click", () => openOriginalFile(d.id));
      recentEl.appendChild(row);
    });
    loadSidebarStats();
  } catch (e) { toast("加载首页失败: " + e.message); }
}

async function loadSidebarStats() {
  try {
    const s = await api("/api/stats");
    const sd = $("#statDocs"); if (sd) sd.textContent = s.documents;
    const sc = $("#statChunks"); if (sc) sc.textContent = s.chunks;
    const sca = $("#statCats"); if (sca) sca.textContent = s.categories;
  } catch (_) {}
}
