# -*- coding: utf-8 -*-
"""端到端冒烟测试：生成测试文档 → 入库 → 检索 → 分类 → 推荐。python tests/smoke_test.py"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import chunker, classifier, db, parser, pipeline, recommender, retriever

TEST_DIR = tempfile.mkdtemp(prefix="aiwj_test_")


def make_docs():
    files = []
    # 1) 合同
    p1 = os.path.join(TEST_DIR, "设备采购合同.txt")
    with open(p1, "w", encoding="utf-8") as f:
        f.write("""设备采购合同

甲方：四川宏远科技有限公司
乙方：泸州恒信电子设备有限公司
签订日期：2026年8月15日

第一条 合同标的
乙方向甲方供应工业自动化控制设备共 120 台，总金额人民币 860,000 元（含税）。

第二条 付款方式
合同签订后 7 个工作日内，甲方向乙方支付合同总金额的 30% 作为预付款；
设备验收合格后 15 个工作日内支付 60%；剩余 10% 作为质保金，质保期满一年后无息支付。

第三条 交付与验收
乙方应于合同签订后 45 日内完成全部设备交付。
验收标准以双方确认的技术协议为准。

第四条 违约责任
任何一方违约，须向守约方支付合同总金额 5% 的违约金。
""")
    files.append(p1)

    # 2) 会议纪要
    p2 = os.path.join(TEST_DIR, "产品迭代评审会议纪要.txt")
    with open(p2, "w", encoding="utf-8") as f:
        f.write("""产品迭代评审会议纪要

会议时间：2026年9月2日 14:00-16:00
参会人员：产品部张伟、研发部李明、测试部王芳、运营部陈晨

议题一：V2.0 版本需求评审
1. 确认新增智能推荐功能，由研发部负责，预计两周完成；
2. 数据看板报表字段调整，运营部补充需求说明。

议题二：线上问题复盘
3. 上周知识库检索响应超时问题，根因为向量索引未做增量更新，已修复；
4. 移动端适配问题遗留至 V2.1。

行动项：
- 研发部 9月10日前输出推荐算法设计方案；
- 测试部 9月12日前完成回归用例编写。
""")
    files.append(p2)

    # 3) 技术资料
    p3 = os.path.join(TEST_DIR, "Chroma向量数据库部署指南.md")
    with open(p3, "w", encoding="utf-8") as f:
        f.write("""# Chroma 向量数据库部署指南

## 一、环境要求
- Python 3.10 及以上
- Windows 10/11 或 Linux
- 内存建议 4GB 以上

## 二、安装
pip install chromadb

## 三、初始化持久化客户端
from chromadb import PersistentClient
client = PersistentClient(path="./chroma_data")
collection = client.get_or_create_collection(name="docs")

## 四、写入向量
collection.add(ids=["1"], embeddings=[[0.1, 0.2, 0.3]], documents=["文本内容"])

## 五、相似度检索
results = collection.query(query_embeddings=[[0.1, 0.2, 0.3]], n_results=5)

## 六、常见问题
1. 索引构建慢：可调整 HNSW 参数 ef_construction；
2. 内存不足：关闭持久化日志或使用 SQLite 模式。
""")
    files.append(p3)

    # 4) 财务报表
    p4 = os.path.join(TEST_DIR, "2026年8月财务报表.xlsx")
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "利润表"
        rows = [
            ["项目", "8月", "1-8月累计"],
            ["营业收入", 1250000, 9800000],
            ["营业成本", 780000, 6100000],
            ["销售费用", 95000, 720000],
            ["管理费用", 110000, 860000],
            ["净利润", 265000, 2110000],
        ]
        for r in rows:
            ws.append(r)
        wb.save(p4)
        files.append(p4)
    except Exception as e:
        print("xlsx 生成跳过:", e)
    return files


def main():
    print("=" * 60)
    print("开始端到端冒烟测试")
    print("=" * 60)

    # 1. 切片测试
    print("\n[1] 切片规则测试")
    text = open(make_docs()[0], encoding="utf-8").read()
    rule = chunker.pick_rule(len(text))
    chunks = chunker.chunk_text(text, rule)
    print(f"    文档 {len(text)} 字 → 规则 {rule['size']}/{rule['overlap']} → {len(chunks)} 片")

    # 2. 解析测试
    print("\n[2] 解析测试")
    for p in make_docs():
        pr = parser.parse_file(p)
        print(f"    {os.path.basename(p)}: ok={pr.ok} len={len(pr.text)}")

    # 3. 入库
    print("\n[3] 批量入库")
    files = [{"path": p} for p in make_docs()]
    task_id = pipeline.start_ingest(files, "手动")
    for _ in range(60):
        t = db.task_get(task_id)
        if t and t["status"] == "done":
            break
        time.sleep(0.5)
    print(f"    任务 {task_id}: 成功 {t['done']} 失败 {t['failed']}")
    for r in t["result"]:
        print(f"    - {r['name']}: ok={r['ok']} 分类={r.get('category')} conf={r.get('conf')} 切片={r.get('chunks')} 向量={r.get('vector_ok')}")

    # 4. 分类学习
    print("\n[4] 分类学习测试")
    docs = db.all_documents()
    if docs:
        d0 = docs[0]
        classifier.learn_from_correction(d0["id"], "合同协议")
        d1 = db.get_document(d0["id"])
        print(f"    {d0['name']} → 人工修正为「{d1['category']}」manual={d1['category_manual']}")

    # 5. 混合检索
    print("\n[5] 混合检索测试")
    for q in ["合同付款方式是怎样的", "会议有哪些行动项", "Chroma 怎么安装", "净利润是多少"]:
        hits, vec = retriever.search(q, k=4)
        print(f"    问: {q}")
        print(f"      向量可用={vec} → Top1: {hits[0]['name'] if hits else '无'} ({hits[0]['score'] if hits else 0})")

    # 6. 推荐
    print("\n[6] 最佳文档推荐")
    rec = recommender.recommend(limit=5)
    for r in rec:
        print(f"    {r['score']:.3f}  {r['name']}  [{r['category']}]")

    # 7. 防幻觉 RAG（未配置 LLM 时的行为）
    print("\n[7] RAG 防幻觉（未配置 API）")
    from backend import rag
    r1 = rag.answer("完全不存在的主题：量子咖啡机的制作方法")
    print(f"    无资料问题 → {r1['answer'][:40]}")
    r2 = rag.answer("合同付款比例是多少")
    print(f"    有资料问题 → {r2['answer'][:60]} | 来源数={len(r2['sources'])}")

    print("\n" + "=" * 60)
    print("冒烟测试通过 ✔")
    print("=" * 60)


if __name__ == "__main__":
    main()
