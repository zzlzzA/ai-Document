/* ===== 扫描 / 导入（scan）===== */
"use strict";

let scanCandidates = [];
let scanSource = "manual";

function openScanModal(title) {
  $("#scanModalTitle").textContent = title;
  $("#scanResult").innerHTML = "";
  $("#scanCount").textContent = "";
  $("#scanConfirm").disabled = true;
  $("#scanModal").classList.remove("hidden");
  $("#scanDirInput").value = "";
}

$("#scanModalClose").addEventListener("click", () => $("#scanModal").classList.add("hidden"));

async function doScan(dir) {
  if (!dir) { toast("请输入目录路径"); return; }
  $("#scanResult").innerHTML = '<p class="muted center" style="padding:16px">扫描中…</p>';
  try {
    const data = await api("/api/scan", { method: "POST", body: JSON.stringify({ directories: [dir] }) });
    scanCandidates = data.candidates;
    renderScanCandidates();
    toast(`扫描完成：新增 ${data.new} 个，重复 ${data.duplicates} 个`);
  } catch (e) { $("#scanResult").innerHTML = `<p class="muted center" style="padding:16px">${esc(e.message)}</p>`; }
}

function renderScanCandidates() {
  const el = $("#scanResult");
  const dups = scanCandidates.filter((c) => c.duplicate).length;
  const news = scanCandidates.filter((c) => !c.duplicate);
  $("#scanCount").textContent = `共 ${scanCandidates.length} 个文件（新文件 ${news.length} · 重复 ${dups}，重复项不勾选）`;
  el.innerHTML = "";
  if (!scanCandidates.length) {
    el.innerHTML = '<p class="muted center" style="padding:16px">该目录下没有可导入的文档（支持 PDF/DOCX/DOC/XLSX/PPTX/TXT/MD）</p>';
    return;
  }
  scanCandidates.forEach((c, i) => {
    const row = document.createElement("label");
    row.className = "scan-file";
    const disabled = c.duplicate || c.error;
    row.innerHTML = `
      <input type="checkbox" data-i="${i}" ${disabled ? "disabled" : ""} ${c.duplicate ? "" : "checked"}>
      <span class="sf-name">${esc(c.name)}</span>
      <span class="muted">${fmtSize(c.size)}</span>
      ${c.duplicate ? '<span class="sf-badge">已存在</span>' : ""}
      ${c.error ? `<span class="sf-badge">${esc(c.error)}</span>` : ""}`;
    el.appendChild(row);
  });
  el.querySelectorAll("input[type=checkbox]").forEach((cb) => {
    cb.addEventListener("change", () => {
      $("#scanConfirm").disabled = !$$("#scanResult input:checked").length;
    });
  });
  $("#scanConfirm").disabled = !$$("#scanResult input:checked").length;
}

$("#scanDirBtn").addEventListener("click", () => doScan($("#scanDirInput").value.trim()));
$("#scanAddDownloads").addEventListener("click", async () => {
  try {
    const { path } = await api("/api/default-downloads");
    $("#scanDirInput").value = path;
    doScan(path);
  } catch (e) { toast(e.message); }
});

$("#scanConfirm").addEventListener("click", async () => {
  const files = [];
  $$("#scanResult input:checked").forEach((cb) => {
    const c = scanCandidates[Number(cb.dataset.i)];
    if (c && !c.duplicate) files.push({ path: c.path });
  });
  if (!files.length) { toast("请勾选至少一个文件"); return; }
  $("#scanModal").classList.add("hidden");
  await startTask(files, scanSource);
});

$("#homeScanBtn").addEventListener("click", () => { scanSource = "自动-Downloads"; openScanModal("扫描目录并入库"); });
$("#libScanBtn").addEventListener("click", () => { scanSource = "手动"; openScanModal("扫描目录并入库"); });
