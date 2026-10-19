"""冒烟测试：实体识别 → 意图分类 → 图谱查询 → 模板作答"""
import sys

from answer import format_answer
from classifier import INTENT_ENTITY_TYPE, QuestionClassifier
from graph_query import GraphQuery


def main() -> int:
    clf = QuestionClassifier()
    g = GraphQuery()

    print("=" * 60)
    print("疾病清单（数据库）")
    print("=" * 60)
    diseases = g.run_raw("MATCH (n:Disease) RETURN n.name AS name ORDER BY name")
    for r in diseases:
        print("  ", r["name"])
    if not diseases:
        print("  （空）—— 需要先导入数据")
        return 1

    host = diseases[0]["name"]
    questions = [
        f"{host}的症状有哪些",
        f"{host}不能吃什么",
        f"{host}会引发什么并发症",
    ]
    drugs = g.run_raw("MATCH (n:Drug) RETURN n.name AS name ORDER BY name LIMIT 1")
    if drugs:
        questions.append(f"{drugs[0]['name']}治疗什么")
    else:
        print("\n（图谱里没有药品节点，跳过药品问句）")

    print()
    print("=" * 60)
    print("问答测试")
    print("=" * 60)
    for q in questions:
        res = clf.classify(q)
        print(f"\n问：{q}")
        print(f"  识别实体：{res['entities']}")
        print(f"  意图：{res['intents']}")
        answers = []
        for intent in res["intents"]:
            etype = INTENT_ENTITY_TYPE.get(intent)
            for name, types in res["entities"].items():
                if etype in types:
                    rows = g.run_intent(intent, name)
                    text = format_answer(intent, rows)
                    if text:
                        answers.append(text)
        if answers:
            print("  答：" + "\n      ".join(answers))
        else:
            print("  答：（无结果）")

    g.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
