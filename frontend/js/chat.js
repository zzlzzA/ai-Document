/* ===== AI 问答（chat）===== */
"use strict";

let chatting = false;

async function loadChatBadge() {
  try {
    const h = await api("/api/health");
    const badge = $("#chatModelBadge");
    badge.className = "badge" + (h.llm_configured ? "" : " warn");
    if (h.llm_configured) {
      badge.textContent = "AI 已配置";
    } else {
      badge.textContent = "AI 未配置（设置页填写密钥）";
    }
    const dot = $("#embedDot");
    dot.className = "dot " + (h.embedding.available ? "ok" : "bad");
    $("#embedStatus").textContent = h.embedding.available ? `Embedding 就绪（${h.embedding.model}）` : "Embedding 不可用（仅关键词检索）";
  } catch (_) {}
}

function addMsg(role, html) {
  const box = $("#chatBox");
  const d = document.createElement("div");
  d.className = "msg " + role;
  d.innerHTML = html;
  box.appendChild(d);
  box.scrollTop = box.scrollHeight;
  return d;
}

async function sendChat() {
  const input = $("#chatInput");
  const q = input.value.trim();
  if (!q || chatting) return;
  chatting = true;
  $("#chatSend").disabled = true;
  addMsg("user", esc(q));
  input.value = "";
  const aiMsg = addMsg("ai", '<span class="muted">正在本地知识库中检索并生成答案…</span>');

  try {
    const r = await api("/api/query", { method: "POST", body: JSON.stringify({ question: q }) });
    let html = esc(r.answer).replace(/\n/g, "<br>");
    if (r.no_result) {
      aiMsg.innerHTML = `<span style="color:#b45309">${html}</span>`;
    } else {
      if (!r.llm_ok) html += '<br><span class="muted">（AI 未配置，已展示检索到的片段）</span>';
      html += renderSources(r.sources);
      aiMsg.innerHTML = html;
      // 反馈按钮（对首个来源生效）
      if (r.sources.length) {
        const fb = document.createElement("div");
        fb.className = "msg-fb";
        const first = r.sources[0];
        fb.innerHTML = `<span class="muted">这个回答有帮助吗？</span>
          <button data-v="1">有帮助</button>
          <button data-v="-1">没帮助</button>`;
        fb.querySelectorAll("button").forEach((b) => b.addEventListener("click", async () => {
          try {
            await api("/api/feedback", { method: "POST", body: JSON.stringify({ doc_id: first.doc_id, value: Number(b.dataset.v) }) });
            fb.innerHTML = '<span class="muted">已记录反馈，检索权重已调整</span>';
            toast("反馈已记录，将持续优化检索");
          } catch (e) { toast(e.message); }
        }));
        aiMsg.appendChild(fb);
      }
      renderRelated(r.related || []);
    }
  } catch (e) {
    aiMsg.innerHTML = `<span style="color:var(--danger)">问答失败：${esc(e.message)}</span>`;
  }
  chatting = false;
  $("#chatSend").disabled = false;
  $("#chatBox").scrollTop = $("#chatBox").scrollHeight;
}

function renderSources(sources) {
  if (!sources || !sources.length) return "";
  const names = sources.map((s) => `《${esc(s.name)}》`).join("、");
  return `<div class="msg-sources"><b>参考来源：</b>${names}</div>`;
}

function renderRelated(related) {
  const el = $("#chatRelated");
  if (!related.length) { el.innerHTML = '<p class="muted">暂未发现强关联文档</p>'; return; }
  el.innerHTML = "";
  related.forEach((r) => {
    const d = document.createElement("div");
    d.className = "rel-item";
    d.innerHTML = `<b>${esc(r.name)}</b><div class="rel-snip">${esc(r.snippet || "")}</div>`;
    d.addEventListener("click", () => openDocModal(r.doc_id));
    el.appendChild(d);
  });
}

$("#chatSend").addEventListener("click", sendChat);
$("#chatInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); }
});
