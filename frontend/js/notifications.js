/* ===== 新文档通知（notifications · 后台静默扫描）===== */
"use strict";

let notifyTimer = null;

async function pollNotifications() {
  try {
    const r = await api("/api/notifications");
    const n = r.pending || 0;
    const badge = $("#notifyBadge");
    badge.textContent = n;
    badge.classList.toggle("hidden", n === 0);
    return n;
  } catch (_) { return 0; }
}

$("#navNotify").addEventListener("click", async () => {
  const r = await api("/api/notifications");
  const items = r.items || [];
  $("#notifyModal").classList.remove("hidden");
  const el = $("#notifyList");
  el.innerHTML = "";
  if (!items.length) {
    el.innerHTML = '<p class="muted center" style="padding:16px">没有待确认的新文档</p>';
    $("#notifyIngestAll").disabled = true;
  } else {
    items.forEach((n) => {
      const row = document.createElement("div");
      row.className = "scan-file";
      row.innerHTML = `<span class="sf-name">${esc(n.name)}</span>
        <span class="muted">${fmtSize(n.size)}</span>
        <span class="muted">${esc(n.dir || "未知目录")}</span>`;
      el.appendChild(row);
    });
    $("#notifyIngestAll").disabled = false;
  }
  $("#notifyCount").textContent = `共 ${items.length} 个新文件`;
});

$("#notifyModalClose").addEventListener("click", () => $("#notifyModal").classList.add("hidden"));

$("#notifyDismissAll").addEventListener("click", async () => {
  await api("/api/notifications/dismiss-all", { method: "POST" });
  $("#notifyModal").classList.add("hidden");
  toast("已全部忽略");
  pollNotifications();
});

$("#notifyIngestAll").addEventListener("click", async () => {
  try {
    const r = await api("/api/notifications/ingest-all", { method: "POST" });
    $("#notifyModal").classList.add("hidden");
    if (r.task_id) {
      toast("已确认入库，开始处理…");
      $("#taskModal").classList.remove("hidden");
      pollTaskProgress(r.task_id);
    } else {
      toast("没有可入库的文件");
    }
    pollNotifications();
  } catch (e) { toast(e.message); }
});
