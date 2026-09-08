/* ===== 文档详情 / 编辑弹窗（doc-modal）===== */
"use strict";

async function openOriginalFile(id) {
  try {
    await api(`/api/documents/${id}/open`, { method: "POST" });
    toast("已用系统默认应用打开原文件");
  } catch (e) {
    toast("打开原文件失败: " + e.message);
  }
}

async function openDocModal(id) {
  try {
    const d = await api(`/api/documents/${id}`);
    const tags = (d.tags || []).join(",");
    $("#docModalTitle").textContent = "文档详情";
    $("#docModalBody").innerHTML = `
      <div class="detail-block"><label>文件名（可重命名）</label>
        <input type="text" id="dmName" value="${esc(d.name)}"></div>
      <div class="detail-block"><label>AI 分类（手动修改会触发个性化学习）</label>
        <select id="dmCategory"></select></div>
      <div class="detail-block"><label>标签（逗号分隔）</label>
        <input type="text" id="dmTags" value="${esc(tags)}"></div>
      <div class="detail-block"><label>摘要</label>
        <div class="summary-box">${esc(d.summary || "（无摘要）")}</div></div>
      <div class="detail-block">
        <label>元信息</label>
        <p class="muted">路径：${esc(d.path)}<br>
        大小：${fmtSize(d.size)} · 切片：${d.chunk_count} · 来源：${esc(d.source)} · 入库：${fmtTime(d.created_at)}<br>
        打开 ${d.visit_count} 次 · 问答引用 ${d.cite_count} 次 · 反馈分 ${d.fb_score}
        ${d.parse_ok ? "" : `<br><span style="color:var(--danger)">解析异常：${esc(d.parse_msg)}</span>`}</p>
      </div>
      <div style="display:flex;gap:8px">
        <button class="btn primary" id="dmSave">保存修改</button>
        <button class="btn" id="dmOpen">打开原文件</button>
        <button class="btn danger" id="dmDel">删除</button>
      </div>`;
    const sel = $("#dmCategory");
    const cats = await api("/api/categories");
    sel.innerHTML = cats.map((c) => `<option value="${esc(c.name)}" ${c.name === d.category ? "selected" : ""}>${esc(c.name)}</option>`).join("");
    $("#docModal").classList.remove("hidden");

    $("#dmSave").addEventListener("click", async () => {
      const patch = { name: $("#dmName").value.trim() || d.name, tags: $("#dmTags").value.split(/[,，]/).map((t) => t.trim()).filter(Boolean) };
      const newCat = $("#dmCategory").value;
      if (newCat !== d.category) patch.category = newCat;
      try {
        await api(`/api/documents/${id}`, { method: "PATCH", body: JSON.stringify(patch) });
        if (patch.category) toast("分类已修正，AI 正在学习你的归档习惯");
        else toast("已保存");
        $("#docModal").classList.add("hidden");
        loadDocs(); loadHome(); loadSidebarStats();
      } catch (e) { toast(e.message); }
    });
    $("#dmOpen").addEventListener("click", async () => {
      try { await api(`/api/documents/${id}/open`, { method: "POST" }); toast("已调用系统打开"); }
      catch (e) { toast(e.message); }
    });
    $("#dmDel").addEventListener("click", () => { $("#docModal").classList.add("hidden"); deleteDoc(id); });
  } catch (e) { toast("加载文档失败: " + e.message); }
}

$("#docModalClose").addEventListener("click", () => $("#docModal").classList.add("hidden"));
