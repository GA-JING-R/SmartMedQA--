"""
医疗知识图谱问答系统 · Web 端（Flask）

启动：
    python app.py
然后浏览器打开 http://127.0.0.1:5000

接口：
    GET  /             首页（聊天界面）
    POST /api/ask      问答
    GET  /api/status   数据库连接状态
    GET  /api/stats    图谱节点/关系统计
    GET  /api/examples 示例问题
"""
import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from answer import format_answer
from classifier import INTENT_ENTITY_TYPE, QuestionClassifier
from graph_query import GraphQuery, GraphQueryError

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__, static_folder=str(BASE_DIR / "static"), template_folder=str(BASE_DIR / "templates"))

classifier = QuestionClassifier()
graph = GraphQuery()

FALLBACK = (
    "没能理解你的问题。\n"
    "试试这些问法：\n"
    "· 肺气肿的症状有哪些\n"
    "· 大叶性肺炎不能吃什么\n"
    "· 肺气肿会引发什么并发症\n"
    "· 氨茶碱片治疗什么"
)

EXAMPLES = [
    "肺气肿的症状有哪些",
    "大叶性肺炎不能吃什么",
    "怎么预防肺气肿",
    "肺大疱要做什么检查",
    "肺气肿吃什么药",
    "什么人容易得肺气肿",
    "肺曲菌病怎么治疗",
    "肺气肿平时吃什么好",
]


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/examples")
def examples():
    return jsonify({"ok": True, "examples": EXAMPLES})


@app.get("/api/status")
def status():
    ok, message = graph.verify()
    return jsonify({"ok": ok, "message": message})


@app.get("/api/stats")
def stats():
    return jsonify(graph.statistics())


@app.post("/api/ask")
def ask():
    payload = request.get_json(silent=True) or {}
    question = str(payload.get("question") or "").strip()
    if not question:
        return jsonify({"ok": False, "error": "请输入问题"}), 400

    # 1) 实体识别 + 意图分类
    result = classifier.classify(question)
    intents = result["intents"]
    entities = result["entities"]

    if not intents:
        return jsonify({"ok": True, "answer": FALLBACK, "matched": False, "debug": result})

    # 2) 按意图 + 对应实体类型查询
    answers: list[str] = []
    try:
        for intent in intents:
            etype = INTENT_ENTITY_TYPE.get(intent)
            names = [w for w, types in entities.items() if etype in types]
            for name in names:
                rows = graph.run_intent(intent, name)
                text = format_answer(intent, rows)
                if text:
                    answers.append(text)
    except GraphQueryError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503

    answer = "\n".join(answers) if answers else "图谱里没有查到相关信息，换个问法或换个实体试试。"
    return jsonify({
        "ok": True,
        "answer": answer,
        "matched": bool(answers),
        "intents": intents,
        "entities": entities,
    })


if __name__ == "__main__":
    port = int(os.getenv("WEB_PORT", "5000"))
    ok, message = graph.verify()
    print("=" * 50)
    print("  医疗知识图谱问答系统 · Web")
    print(f"  数据库：{message}")
    print(f"  访问：http://127.0.0.1:{port}")
    print("=" * 50)
    app.run(host="127.0.0.1", port=port, debug=False)
