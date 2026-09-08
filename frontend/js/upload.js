/* ===== 选择 / 拖拽上传入库（upload）===== */
"use strict";

function pickDocs() {
  $("#fileInput").value = "";
  $("#fileInput").click();
}

async function uploadDocs(files) {
  if (!files.length) return;
  const fd = new FormData();
  [...files].forEach((f) => fd.append("files", f));

  $("#taskModal").classList.remove("hidden");
  $("#taskBar").style.width = "0%";
  $("#taskText").textContent = `正在上传 ${files.length} 个文档…`;
  $("#taskResult").innerHTML = "";

  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/upload");
  xhr.upload.onprogress = (e) => {
    if (e.lengthComputable) {
      const pct = Math.round(e.loaded / e.total * 100);
      $("#taskBar").style.width = pct + "%";
      $("#taskText").textContent = `上传中 ${pct}%…`;
    }
  };
  xhr.onload = () => {
    try {
      const r = JSON.parse(xhr.responseText);
      if (xhr.status !== 200) throw new Error(r.detail || "上传失败");
      $("#taskText").textContent = `上传完成，开始解析入库 ${r.count} 个文档…`;
      $("#taskBar").style.width = "100%";
      if (r.skipped) toast(`${r.skipped} 个文件格式不支持，已跳过`);
      pollTaskProgress(r.task_id);
    } catch (e) {
      $("#taskText").textContent = "上传失败: " + e.message;
    }
  };
  xhr.onerror = () => { $("#taskText").textContent = "上传失败：网络错误"; };
  xhr.send(fd);
}

$("#homePickBtn").addEventListener("click", pickDocs);
$("#libPickBtn").addEventListener("click", pickDocs);
$("#fileInput").addEventListener("change", (e) => uploadDocs(e.target.files));

// 拖拽上传：把文档拖到页面任意位置即可入库
let dragDepth = 0;
document.addEventListener("dragenter", (e) => {
  e.preventDefault();
  dragDepth++;
  document.body.classList.add("drag-over");
});
document.addEventListener("dragleave", () => {
  dragDepth = Math.max(0, dragDepth - 1);
  if (!dragDepth) document.body.classList.remove("drag-over");
});
document.addEventListener("dragover", (e) => e.preventDefault());
document.addEventListener("drop", (e) => {
  e.preventDefault();
  dragDepth = 0;
  document.body.classList.remove("drag-over");
  const files = [...(e.dataTransfer?.files || [])].filter((f) =>
    /\.(pdf|docx|doc|xlsx|pptx|txt|md)$/i.test(f.name));
  if (files.length) uploadDocs(files);
  else if (e.dataTransfer?.files?.length) toast("仅支持 PDF/DOCX/DOC/XLSX/PPTX/TXT/MD 文档");
});
