# -*- coding: utf-8 -*-
"""全局配置：路径、模型、切片参数、默认分类。"""
import os
import sys


def _base_dir():
    """数据根目录：
    - 开发模式：项目根目录
    - 打包运行（PyInstaller frozen）：exe 所在目录（便携式，数据/模型/日志与 exe 同目录）
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_env_file(path: str) -> dict:
    """读取 .env 文件（支持 key=value 与 export key=value，忽略 # 注释），文件缺失返回空。"""
    env = {}
    if not os.path.isfile(path):
        return env
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:].strip()
                if "=" in line:
                    k, _, v = line.partition("=")
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k:
                        env[k] = v
    except OSError:
        pass
    return env


def _env_get(key: str, default: str) -> str:
    """配置优先级：系统环境变量 > .env 文件 > 代码默认值。
    .env 位置：开发模式在项目根目录，桌面版在 exe 同目录。"""
    return os.environ.get(key) or _ENV.get(key) or default


_ENV = _load_env_file(os.path.join(_base_dir(), ".env"))


# ---------- 路径 ----------
BASE_DIR = _base_dir()
DATA_DIR = os.path.join(BASE_DIR, "data")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma")
DB_PATH = os.path.join(DATA_DIR, "knowledge.db")
MODEL_DIR = os.path.join(DATA_DIR, "models")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")  # 手动上传文件落盘目录（原件本地保存）
LOG_DIR = os.path.join(DATA_DIR, "logs")

for _d in (DATA_DIR, CHROMA_DIR, MODEL_DIR, UPLOAD_DIR, LOG_DIR):
    os.makedirs(_d, exist_ok=True)

# 国内网络：HuggingFace 镜像，用于下载 Embedding 模型
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_CACHE", MODEL_DIR)

# ---------- Embedding ----------
# 本地轻量化中文 Embedding 模型（约 40MB ONNX，全程离线）
EMBED_MODEL = "BAAI/bge-small-zh-v1.5"
EMBED_DIM = 512
EMBED_BATCH = 32
# bge 系列模型建议在查询侧加指令前缀
EMBED_QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："

# ---------- 切片规则（PRD 3.2 智能切片） ----------
CHUNK_RULES = {
    "short":    {"size": 256, "overlap": 64},    # 短笔记/文本
    "default":  {"size": 512, "overlap": 128},   # 通用文档
    "long":     {"size": 768, "overlap": 128},   # 长文档/合同
}
CHUNK_LONG_THRESHOLD = 8000   # 文本长度超过该值按长文档规则
CHUNK_SHORT_THRESHOLD = 1200  # 文本长度低于该值按短文档规则

# ---------- 默认分类体系（PRD 3.3.1） ----------
DEFAULT_CATEGORIES = [
    "工作文档", "合同协议", "会议纪要", "技术资料",
    "财务报表", "学习资料", "个人笔记", "其他",
]

# 每个类别的语义描述（用于生成类中心向量）与关键词规则
CATEGORY_PROFILES = {
    "工作文档": {
        "desc": "工作文档：项目计划、方案、汇报、周报、月报、总结、商业计划书、制度、流程、岗位职责、工作计划",
        "keywords": ["项目", "方案", "汇报", "周报", "月报", "总结", "计划", "计划书", "制度", "流程", "工作", "岗位", "职责", "复盘"],
    },
    "合同协议": {
        "desc": "合同协议：合同、协议、条款、甲方乙方、签署、违约责任、付款方式、保密协议、劳动合同、采购合同、租赁合同",
        "keywords": ["合同", "协议", "条款", "甲方", "乙方", "签署", "违约", "付款", "保密", "劳动合同", "采购", "租赁"],
    },
    "会议纪要": {
        "desc": "会议纪要：会议记录、会议纪要、议题、决议、参会人员、讨论事项、行动项、例会、会议总结",
        "keywords": ["会议", "纪要", "议题", "决议", "参会", "讨论", "行动项", "例会", "会议记录"],
    },
    "技术资料": {
        "desc": "技术资料：技术文档、开发文档、接口文档、架构、代码、部署、数据库、API、使用手册、技术方案、故障排查、配置",
        "keywords": ["技术", "开发", "接口", "API", "架构", "代码", "部署", "数据库", "手册", "配置", "系统", "软件", "故障", "调试", "编程"],
    },
    "财务报表": {
        "desc": "财务报表：财务报表、资产负债表、利润表、现金流量表、预算、发票、报销、成本、营收、利润、税务、财务分析",
        "keywords": ["财务", "报表", "资产", "负债", "利润", "现金流", "预算", "发票", "报销", "成本", "营收", "税务", "审计"],
    },
    "学习资料": {
        "desc": "学习资料：教材、讲义、笔记、课程、考试、复习、知识点、习题、论文、研究、读书笔记、学习心得、培训资料",
        "keywords": ["学习", "课程", "考试", "复习", "知识点", "习题", "论文", "研究", "笔记", "讲义", "教材", "培训"],
    },
    "个人笔记": {
        "desc": "个人笔记：个人记录、日记、随笔、想法、清单、备忘、灵感、日常生活记录、个人规划",
        "keywords": ["日记", "随笔", "备忘", "清单", "灵感", "个人", "记录", "生活"],
    },
    "其他": {
        "desc": "其他：无法归入以上分类的杂项文档、通用资料",
        "keywords": [],
    },
}

# ---------- 检索（PRD 3.4 混合检索） ----------
RETRIEVE_TOP_K = 8          # 混合检索召回片段数
RAG_CONTEXT_LIMIT = 6       # 送入 LLM 的片段数
RRF_K = 60                  # 混合排序 RRF 常数
BEHAVIOR_WEIGHT_MAX = 0.35  # 行为权重对排序的最大修正幅度
VEC_SIM_MIN = 0.38          # 向量命中相似度下限（过滤语义无关误召回）
BM25_MIN_SCORE = 1.5        # BM25 原始分下限（过滤关键词巧合命中）

# ---------- 推荐（PRD 3.6 六维权重） ----------
RECOMMEND_LIMIT = 10
TIME_DECAY_DAYS = 90        # 时间权重半衰期（天）
W_WEIGHTS = {               # 六维权重
    "semantic": 0.20,       # 文档语义价值
    "time":     0.15,       # 时间权重
    "visit":    0.20,       # 访问次数
    "cite":     0.20,       # 问答引用次数
    "feedback": 0.15,       # 问答反馈
    "quality":  0.10,       # 完整度/解析成功率
}

# ---------- LLM ----------
# 自定义 API 模式：用户在「设置」页填写 API 地址/密钥/模型；.env 中的值仅作为默认值，
# 设置页保存后会覆盖。密钥仅存于本机（.env / 本地数据库），不写入源码。
LLM_MODE = _env_get("AIWJ_LLM_MODE", "custom")  # 固定自定义模式（兼容旧配置读取）

# 自定义模式默认值（用户可在设置页修改）
LLM_API_BASE = _env_get("AIWJ_API_BASE", "https://ark.cn-beijing.volces.com/api/v3")
LLM_API_KEY = _env_get("AIWJ_API_KEY", "")
LLM_MODEL = _env_get("AIWJ_MODEL", "doubao-seed-1-6-250615")
LLM_TIMEOUT = 60
LLM_MAX_TOKENS = 1024
LLM_TEMPERATURE = 0.3       # 低温度，减少幻觉

# 防幻觉固定回复
NO_ANSWER_REPLY = "未在本地知识库中查询到相关资料"
NO_API_REPLY = "AI 服务未配置：请到设置页填写 API 地址与密钥，或稍后重试"

# ---------- 扫描（PRD 3.1.1） ----------
SUPPORTED_EXTS = {".pdf", ".docx", ".doc", ".xlsx", ".pptx", ".txt", ".md"}
# 扫描策略：每次进入软件时扫描一次监控目录（不做后台循环轮询），
# 另支持手动「立即扫描一次」（POST /api/monitor-scan）
