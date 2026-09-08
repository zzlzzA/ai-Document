/* ===== 设置页（settings）：API 配置 / 监控目录 / 主题 / 背景 ===== */
"use strict";

/* ---- AI 问答服务（API 配置） ---- */
async function loadSettings() {
  try {
    const s = await api("/api/settings");
    $("#setApiBase").value = s.api_base || "";
    $("#setApiKey").value = s.api_key || "";
    $("#setApiModel").value = s.model || "";
    $("#modeHint").textContent = s.api_key
      ? `当前使用：${s.model || "未命名模型"}（${s.api_base || ""}）密钥已保存在本机。`
      : "尚未配置：请填写下方服务地址与密钥后保存。";
    const st = $("#llmSaveState");
    if (st) st.textContent = s.api_key ? "已连接 API 服务" : "等待填写密钥";
    renderMonitorDirs();
  } catch (e) { toast("加载 AI 设置失败: " + e.message); }
}

$("#saveLlmSettings").addEventListener("click", async () => {
  const patch = {
    llm_api_base: $("#setApiBase").value.trim(),
    llm_api_key: $("#setApiKey").value.trim(),
    llm_model: $("#setApiModel").value.trim(),
  };
  if (!patch.llm_api_key) { toast("请填写 API 密钥"); return; }
  if (!patch.llm_api_base) { toast("请填写 API 地址"); return; }
  if (!patch.llm_model) { toast("请填写模型名称"); return; }
  try {
    await api("/api/settings", { method: "POST", body: JSON.stringify(patch) });
    $("#llmSaveState").textContent = "已保存";
    toast(`API 配置已保存：${patch.llm_model}`);
    loadChatBadge();
  } catch (e) { toast("保存失败: " + e.message); }
});

/* ---- 监控目录（新文档提醒） ---- */
async function renderMonitorDirs() {
  try {
    const s = await api("/api/settings");
    const dirs = s.monitor_dirs || [];
    const el = $("#monDirList");
    if (!el) return;
    el.innerHTML = "";
    if (!dirs.length) {
      el.innerHTML = '<p class="muted center" style="padding:12px">未配置监控目录，新文档提醒不会触发。添加目录后，放入其中的新文档会在左侧出现提醒。</p>';
      $("#monScanNow").disabled = true;
      return;
    }
    $("#monScanNow").disabled = false;
    dirs.forEach((d) => {
      const row = document.createElement("div");
      row.className = "scan-file";
      row.innerHTML = `<span class="sf-name">${esc(d)}</span>
        <button class="btn small danger" data-mon-dir="${esc(d)}">移除</button>`;
      row.querySelector("button").addEventListener("click", async () => {
        try {
          const cur = (await api("/api/settings")).monitor_dirs || [];
          await api("/api/monitor-dirs", { method: "POST", body: JSON.stringify({ directories: cur.filter((x) => x !== d) }) });
          await renderMonitorDirs();
          pollNotifications();
          toast("已移除监控目录");
        } catch (e) { toast("移除失败: " + e.message); }
      });
      el.appendChild(row);
    });
  } catch (e) { toast("加载监控目录失败: " + e.message); }
}

$("#monAddBtn").addEventListener("click", async () => {
  const dir = $("#monDirInput").value.trim();
  if (!dir) { toast("请输入目录路径"); return; }
  try {
    const cur = (await api("/api/settings")).monitor_dirs || [];
    if (cur.includes(dir)) { toast("该目录已在监控列表中"); return; }
    await api("/api/monitor-dirs", { method: "POST", body: JSON.stringify({ directories: [...cur, dir] }) });
    $("#monDirInput").value = "";
    await renderMonitorDirs();
    toast("已添加监控目录");
  } catch (e) { toast("添加失败: " + e.message); }
});

$("#monAddDownloads").addEventListener("click", async () => {
  try {
    const { path } = await api("/api/default-downloads");
    $("#monDirInput").value = path;
    toast(`已填入下载目录：${path}`);
  } catch (e) { toast(e.message); }
});

$("#monScanNow").addEventListener("click", async () => {
  const btn = $("#monScanNow");
  btn.disabled = true;
  const st = $("#monScanState");
  st.textContent = "扫描中…";
  try {
    const r = await api("/api/monitor-scan", { method: "POST" });
    st.textContent = r.added ? `发现 ${r.added} 个新文件，已生成提醒` : "未发现新文件";
    await pollNotifications();
  } catch (e) { st.textContent = "扫描失败: " + e.message; }
  btn.disabled = false;
  setTimeout(() => { st.textContent = ""; }, 5000);
});

/* ---- 主题（浅色 / 深色） ---- */
function applyTheme(theme) {
  document.body.classList.toggle("theme-dark", theme === "dark");
  $$(".theme-chip").forEach((c) => c.classList.toggle("active", c.dataset.theme === theme));
  localStorage.setItem("aiwj_theme", theme);
}

$$(".theme-chip").forEach((chip) => chip.addEventListener("click", () => applyTheme(chip.dataset.theme)));

/* ---- 背景图片 ---- */
function applyBg(on) {
  const body = document.body;
  if (on) {
    body.style.backgroundImage = `url("/api/background?v=${Date.now()}")`;
    body.style.backgroundSize = "cover";
    body.style.backgroundPosition = "center";
    body.style.backgroundAttachment = "fixed";
    body.classList.add("has-bg");
  } else {
    body.style.backgroundImage = "";
    body.classList.remove("has-bg");
  }
  localStorage.setItem("aiwj_bg", on ? "1" : "0");
  const has = !!on;
  $("#bgRemoveBtn").disabled = !has;
  $("#bgHint").textContent = has ? "已启用自定义背景图（仅本地保存，不上传云端）。" : "上传本机图片作为软件背景（仅本地保存，不上传云端）。";
}

$("#bgPickBtn").addEventListener("click", () => $("#bgInput").click());
$("#bgInput").addEventListener("change", async (e) => {
  const f = e.target.files?.[0];
  if (!f) return;
  const fd = new FormData();
  fd.append("bg", f);
  try {
    await api("/api/background", { method: "POST", body: fd });
    applyBg(true);
    toast("背景图已更新");
  } catch (err) { toast("上传失败: " + err.message); }
  e.target.value = "";
});
$("#bgRemoveBtn").addEventListener("click", async () => {
  try {
    await api("/api/background", { method: "DELETE" });
    applyBg(false);
    toast("已恢复默认背景");
  } catch (err) { toast(err.message); }
});
