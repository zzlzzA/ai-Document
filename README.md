# AIWenJian · AI 智能文档知识库

> 本地私有 AI 文档知识库：自动入库、AI 分类、混合检索、RAG 溯源问答。**原始文件、向量库、行为数据 100% 留在本机。**

![license](https://img.shields.io/badge/license-MIT-blue)
![python](https://img.shields.io/badge/python-3.9%2B-blue)
![platform](https://img.shields.io/badge/platform-Windows-blue)
![prs](https://img.shields.io/badge/PRs-welcome-brightgreen)

AIWenJian 是一个运行在本地的 AI 文档知识库客户端：把散落在电脑里的 PDF / Word / Excel / PPT / 文本等文档统一收进知识库，自动完成**解析、切片、向量化、AI 分类**，然后通过**混合检索 + RAG 溯源问答**直接向文档提问，答案附带参考来源。所有数据处理都在本机完成，原始文件绝不上传。

---

## ✨ 功能特性

| 能力 | 说明 |
|---|---|
| 📥 多方式入库 | 文件选择器、**拖拽上传**、目录扫描（勾选确认后入库，MD5 全局去重） |
| 📄 多格式解析 | PDF / DOCX / DOC / XLSX / PPTX / TXT / MD，智能切片（256/512/768 自适应） |
| 🏷️ AI 自动分类 | 8 个默认分类 + 语义/关键词打分，人工修正后 AI 持续学习你的归档习惯 |
| 🔍 混合检索 | BM25 关键词 + bge 向量语义双路召回，RRF 融合排序，行为权重修正 |
| 💬 RAG 溯源问答 | 基于检索片段生成答案，防幻觉固定回复，展示参考来源，点赞/点踩反馈学习 |
| ⭐ 智能推荐 | 六维权重（语义/时间/访问/引用/反馈/完整度）最佳文档推荐 |
| 🗂️ 文档管理 | 分类侧栏、标签筛选、关键词搜索、重命名/改分类/打标签、批量删除、打开原文件 |
| 🔔 新文档提醒 | 监控目录静默扫描，发现新文件只提醒、确认后才入库 |
| 🖥️ 桌面版 | PyInstaller 打包 Windows 原生窗口（pywebview + WebView2），双击即用 |
| 🛡️ 隐私优先 | 全本地存储，一键清空销毁；仅把检索命中的少量片段发给 AI 服务 |

## 🏗️ 技术栈

- **后端**：Python · FastAPI · SQLite · Chroma 向量库
- **向量化**：bge-small-zh-v1.5（ONNX 本地推理，免装 torch）
- **检索**：rank-bm25 + Chroma 向量召回，RRF 融合
- **前端**：原生 HTML / CSS / JS 单页应用（无框架依赖，模块化组织）
- **AI 接入**：OpenAI 兼容 API（设置页配置，支持任意兼容服务）

## 🚀 快速开始（开发模式）

### 环境要求

- Python 3.9+
- Windows 10/11（核心功能跨平台可用，桌面版窗口仅 Windows）

### 安装与启动

```powershell
git clone https://github.com/zzlzzA/aiwenjian.git
cd aiwenjian
pip install -r requirements.txt      # 首次安装依赖（约 2-3 分钟）
python run.py                        # 启动，自动打开浏览器
```

访问 `http://127.0.0.1:8000`（端口被占用时自动顺延 8001/8002…，可用环境变量 `AIWJ_PORT` / `AIWJ_HOST` 修改）。

> 首次使用会自动从国内镜像下载 Embedding 模型 `bge-small-zh-v1.5`（约 95MB，缓存于 `data/models`）。下载期间检索自动降级为关键词模式，模型就绪后自动启用语义检索。

## 📖 使用指南

- **首页**：知识库统计、格式分布、收藏文档、最近新增
- **添加文档**：点「选择文档」多选入库 / 把文档**拖进页面任意位置** / 「扫描目录」批量扫描勾选入库
- **文档库**：分类侧栏、标签筛选、关键词搜索、行内操作（打开/编辑/删除）、批量删除
- **AI 问答**：向知识库提问 → 溯源答案（文档名 + 命中片段）→ 点赞/点踩 → 右侧相关文档推荐
- **设置**：AI 服务配置（API 地址/密钥/模型）、监控目录、主题与背景、一键清空

## ⚙️ AI 服务配置

AI 问答使用 OpenAI 兼容 API，在 **设置 → AI 问答服务** 中填写：

| 字段 | 说明 |
|---|---|
| API 地址 | 兼容 OpenAI 的服务地址，如 `https://ark.cn-beijing.volces.com/api/v3` |
| API 密钥 | 你的服务密钥（仅保存在本机） |
| 模型名称 | 模型 ID，如 `doubao-seed-1-6-250615`、`qwen-plus`、`gpt-4o-mini` 等 |

也可通过环境变量或 `.env` 文件预置默认值（`AIWJ_API_BASE` / `AIWJ_API_KEY` / `AIWJ_MODEL`），设置页保存后以设置页为准。密钥不写入代码，`.env` 已被 `.gitignore` 排除，不会提交到仓库。

## 🛡️ 隐私与安全

- **全本地存储**：原始文件、向量库、行为数据均保存在本机 `data/` 目录，删除整个目录即彻底清除隐私数据
- **原始文件绝不出本机**：解析、切片、向量化全部本地完成
- **AI 调用最小化**：仅把检索命中的少量片段发给 AI 服务端，用于生成回答
- **密钥本机保存**：API 密钥仅存于本机（设置页 / `.env`），不会写入代码或仓库

## 📁 项目结构

```
aiwenjian/
├── run.py                  # 启动入口（开发模式 / 桌面版）
├── requirements.txt
├── aiwenjian.spec          # PyInstaller 打包配置
├── backend/                # FastAPI 后端
│   ├── api.py              # HTTP 路由
│   ├── config.py           # 全局配置
│   ├── db.py               # SQLite：文档/行为/切片/设置/任务
│   ├── scanner.py          # 目录扫描 + MD5 去重 + 忽略规则
│   ├── parser.py           # 文档解析（pdf/docx/xlsx/pptx/txt/md/doc）
│   ├── chunker.py          # 智能切片（256/512/768 自适应）
│   ├── embedder.py         # bge-small-zh 本地向量化（ONNX）
│   ├── vector_store.py     # Chroma 持久化向量库
│   ├── retriever.py        # BM25 + 向量混合检索 + 行为权重
│   ├── classifier.py       # AI 分类 + 个性化学习
│   ├── rag.py              # RAG 溯源问答（防幻觉）
│   ├── recommender.py      # 六维权重最佳文档推荐
│   ├── llm.py              # 大模型推理（OpenAI 兼容 API）
│   ├── pipeline.py         # 入库流水线（异步任务）
│   ├── watcher.py          # 监控目录后台扫描
│   └── model_manager.py    # 本地模型状态管理
├── frontend/               # 原生 HTML/CSS/JS 单页应用
│   └── js/                 # 前端模块（utils/tasks/notifications/home/library/…）
└── tests/                  # 端到端冒烟测试
```

> `data/`（运行时数据）、`build/`、`dist/`（打包产物）、`.env` 均已被 `.gitignore` 排除，不会进入版本库。

## ✅ 测试

```powershell
python tests\smoke_test.py
```

覆盖：解析 → 切片 → 向量化 → 分类 → 混合检索 → 推荐 → 防幻觉问答全链路。

## 📦 桌面版打包（Windows）

```powershell
pip install pyinstaller
python -m PyInstaller --noconfirm --clean aiwenjian.spec
```

产物在 `dist\AI文档知识库\`：双击 `AI文档知识库.exe` 即弹出原生桌面窗口（无控制台），数据保存在 exe 同目录 `data/`，整目录拷贝即可迁移。

## 🗺️ Roadmap

- [x] 文档解析、切片、向量化、AI 分类、混合检索、RAG 问答、推荐、学习闭环
- [x] 设置页 API 配置、监控目录新文档提醒、桌面版打包
- [ ] 扫描件 OCR（PaddleOCR 可选组件）
- [ ] 知识库导入导出、问答记录导出
- [ ] 个性化学习闭环调优（分类/检索/问答权重微调）

## ⚠️ 已知限制

- `.doc` 旧格式为尽力提取（OLE 文本流），建议另存为 `.docx`
- 扫描件 PDF 需安装 PaddleOCR 可选组件（约 1GB，低配机不建议）
- AI 问答依赖外部 API 服务，未配置时仅返回检索片段

## 📄 开源协议

本项目采用 [MIT License](LICENSE)。
