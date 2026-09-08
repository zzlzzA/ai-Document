/* ===== 入库任务进度（tasks）===== */
"use strict";

function pollTaskProgress(taskId) {
  $("#taskBar").style.width = "0%";
  $("#taskText").textContent = "入库中…";
  $("#taskResult").innerHTML = "";
  const poll = setInterval(async () => {
    try {
      const t = await api(`/api/tasks/${taskId}`);
      const pct = t.total ? Math.round((t.done + t.failed) / t.total * 100) : 0;
      $("#taskBar").style.width = pct + "%";
      $("#taskText").textContent = `进度 ${t.done + t.failed}/${t.total}（成功 ${t.done} · 失败 ${t.failed}）`;
      renderTaskResult(t.result);
      if (t.status === "done") {
        clearInterval(poll);
        $("#taskText").textContent = `入库完成：成功 ${t.done}，失败 ${t.failed}`;
        toast(`入库完成：成功 ${t.done} 篇`);
        loadHome(); loadSidebarStats(); loadDocs();
      }
    } catch (_) {}
  }, 800);
}

async function startTask(files, source) {
  $("#taskModal").classList.remove("hidden");
  $("#taskBar").style.width = "0%";
  $("#taskText").textContent = `开始入库 ${files.length} 个文件…`;
  $("#taskResult").innerHTML = "";
  let taskId;
  try {
    const r = await api("/api/ingest", { method: "POST", body: JSON.stringify({ files, source }) });
    taskId = r.task_id;
  } catch (e) {
    $("#taskText").textContent = "启动任务失败: " + e.message;
    return;
  }
  const poll = setInterval(async () => {
    try {
      const t = await api(`/api/tasks/${taskId}`);
      const pct = t.total ? Math.round((t.done + t.failed) / t.total * 100) : 0;
      $("#taskBar").style.width = pct + "%";
      $("#taskText").textContent = `进度 ${t.done + t.failed}/${t.total}（成功 ${t.done} · 失败 ${t.failed}）`;
      renderTaskResult(t.result);
      if (t.status === "done") {
        clearInterval(poll);
        $("#taskText").textContent = `入库完成：成功 ${t.done}，失败 ${t.failed}`;
        toast(`入库完成：成功 ${t.done} 篇`);
        loadHome(); loadSidebarStats();
      }
    } catch (_) {}
  }, 800);
}

function renderTaskResult(results) {
  const el = $("#taskResult");
  el.innerHTML = results.slice(-30).map((r) =>
    `<div><span class="${r.ok ? "ok" : "fail"}">${r.ok ? "✓" : "✕"}</span> ${esc(r.name || r.path.split(/[\\/]/).pop())} ${r.ok ? (r.category ? `→ ${esc(r.category)}` : "") : esc(r.error || "")}</div>`
  ).join("");
}

$("#taskClose").addEventListener("click", () => $("#taskModal").classList.add("hidden"));
