"""
医疗知识图谱 · 建图脚本

把 data_medical2.json（每行一个疾病 JSON 对象）导入 Neo4j，生成问答系统需要的
7 类节点和 11 种关系。

用法：
    python load_graph.py                # 建图并打印统计
    python load_graph.py --dry-run      # 只解析数据、打印将要写入的数量，不连数据库
    python load_graph.py --data 别的文件.json

连接信息与 app.py 一致，可用环境变量覆盖：
    NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD

脚本可以重复执行：节点用 MERGE、关系也用 MERGE，不会产生重复数据。
数据里指向不存在的节点（例如并发症指向了未收录的疾病）会被自动跳过。
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA = BASE_DIR / "data_medical2.json"

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "12345678")

# Disease 节点上的文本属性（与旧版建图脚本保持一致）
DISEASE_PROPS = ("desc", "prevent", "cause", "easy_get", "cure_way", "cure_lasttime", "cured_prob")

# 关系定义：键 -> (关系类型, name 属性, 起点标签, 终点标签)
REL_DEFS = {
    "has_symptom": ("has_symptom", "症状", "Disease", "Symptom"),
    "acompany_with": ("acompany_with", "并发症", "Disease", "Disease"),
    "no_eat": ("no_eat", "忌吃", "Disease", "Food"),
    "do_eat": ("do_eat", "宜吃", "Disease", "Food"),
    "recommand_eat": ("recommand_eat", "推荐食谱", "Disease", "Food"),
    "common_drug": ("common_drug", "常用药品", "Disease", "Drug"),
    "recommand_drug": ("recommand_drug", "好评药品", "Disease", "Drug"),
    "need_check": ("need_check", "诊断检查", "Disease", "Check"),
    "disease_department": ("belongs_to", "所属科室", "Disease", "Department"),
    "department_parent": ("belongs_to", "属于", "Department", "Department"),
    "drugs_of": ("drugs_of", "生产药品", "Producer", "Drug"),
}


def read_records(path: Path) -> list[dict[str, Any]]:
    """读 JSON Lines 文件，优先 UTF-8，失败回退 GBK"""
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "gbk"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise SystemExit(f"无法识别 {path} 的编码（试过 UTF-8 / GBK）")

    records: list[dict[str, Any]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path.name} 第 {lineno} 行不是合法 JSON：{exc}")
    return records


def split_drug_detail(text: str) -> tuple[str, str]:
    """「厂商(药品名)」拆成 (厂商, 药品名)

    切分方式与旧版建图脚本保持一致（取第一个括号前、最后一个括号内），
    这样厂商名的统计结果才不会和已有图谱对不上。
    """
    text = str(text).strip()
    if "(" in text:
        parts = text.split("(")
        return parts[0].strip(), parts[-1].replace(")", "").strip()
    return text, text


def build_plan(records: list[dict[str, Any]]) -> dict[str, Any]:
    """把原始记录整理成「要建的节点 + 要连的关系」"""
    nodes: dict[str, set[str]] = {
        "Disease": set(), "Symptom": set(), "Drug": set(), "Food": set(),
        "Check": set(), "Department": set(), "Producer": set(),
    }
    diseases: list[dict[str, Any]] = []
    rels: dict[str, list[tuple[str, str]]] = {k: [] for k in REL_DEFS}

    def link(key: str, start: str, end: str) -> None:
        if start and end:
            rels[key].append((start, end))

    for record in records:
        name = str(record.get("name") or "").strip()
        if not name:
            continue

        nodes["Disease"].add(name)
        props = {key: record.get(key, "") for key in DISEASE_PROPS}
        props["cure_department"] = record.get("cure_department") or ""
        diseases.append({"name": name, "props": props})

        for symptom in record.get("symptom") or []:
            nodes["Symptom"].add(symptom)
            link("has_symptom", name, symptom)

        for other in record.get("acompany") or []:
            link("acompany_with", name, other)

        for check in record.get("check") or []:
            nodes["Check"].add(check)
            link("need_check", name, check)

        for drug in record.get("common_drug") or []:
            nodes["Drug"].add(drug)
            link("common_drug", name, drug)

        for drug in record.get("recommand_drug") or []:
            nodes["Drug"].add(drug)
            link("recommand_drug", name, drug)

        for food in record.get("not_eat") or []:
            nodes["Food"].add(food)
            link("no_eat", name, food)

        for food in record.get("do_eat") or []:
            nodes["Food"].add(food)
            link("do_eat", name, food)

        for food in record.get("recommand_eat") or []:
            nodes["Food"].add(food)
            link("recommand_eat", name, food)

        for detail in record.get("drug_detail") or []:
            producer, drug = split_drug_detail(detail)
            if producer and drug:
                nodes["Producer"].add(producer)
                link("drugs_of", producer, drug)

        departments = list(record.get("cure_department") or [])
        for department in departments:
            nodes["Department"].add(department)
        if len(departments) == 1:
            link("disease_department", name, departments[0])
        elif len(departments) >= 2:
            parent, child = departments[0], departments[1]
            link("department_parent", child, parent)
            link("disease_department", name, child)

    # 去重、保持顺序，并丢掉端点不在本图谱内的关系
    # （例如并发症指向了数据里没有收录的疾病，MATCH 不到就该跳过）
    skipped = 0
    for key, pairs in rels.items():
        _, _, start, end = REL_DEFS[key]
        unique = list(dict.fromkeys(pairs))
        rels[key] = [(a, b) for a, b in unique if a in nodes[start] and b in nodes[end]]
        skipped += len(unique) - len(rels[key])

    return {"nodes": nodes, "diseases": diseases, "rels": rels, "skipped": skipped}


def describe(plan: dict[str, Any]) -> None:
    print("将写入的节点：")
    for label, names in plan["nodes"].items():
        print(f"  {label:12s} {len(names):>5d}")
    print(f"  {'合计':12s} {sum(len(v) for v in plan['nodes'].values()):>5d}\n")

    print("将写入的关系：")
    total = 0
    for key, (rel_type, rel_name, start, end) in REL_DEFS.items():
        pairs = plan["rels"][key]
        total += len(pairs)
        print(f"  {rel_type:16s} {rel_name:6s} {start} → {end:12s} {len(pairs):>5d}")
    print(f"  {'合计':16s} {'':6s} {'':24s} {total:>5d}")
    if plan.get("skipped"):
        print(f"\n另有 {plan['skipped']} 条关系因端点不在图谱内被跳过（例如并发症指向了未收录的疾病）")


def write_graph(driver, plan: dict[str, Any]) -> None:
    with driver.session() as session:
        session.run(
            "UNWIND $rows AS row "
            "MERGE (d:Disease {name: row.name}) "
            "SET d += row.props",
            rows=plan["diseases"],
        )

        for label, names in plan["nodes"].items():
            if label == "Disease" or not names:
                continue
            session.run(
                f"UNWIND $names AS n MERGE (x:{label} {{name: n}})",
                names=sorted(names),
            )

        for key, (rel_type, rel_name, start, end) in REL_DEFS.items():
            pairs = plan["rels"][key]
            if not pairs:
                continue
            session.run(
                f"UNWIND $pairs AS p "
                f"MATCH (a:{start} {{name: p.a}}) "
                f"MATCH (b:{end} {{name: p.b}}) "
                f"MERGE (a)-[r:{rel_type}]->(b) "
                f"SET r.name = $rel_name",
                pairs=[{"a": a, "b": b} for a, b in pairs],
                rel_name=rel_name,
            )


def print_statistics(driver) -> None:
    with driver.session() as session:
        labels = list(session.run(
            "MATCH (n) UNWIND labels(n) AS label "
            "RETURN label, count(*) AS count ORDER BY count DESC"
        ))
        relations = session.run("MATCH ()-[r]->() RETURN count(r) AS count").single()["count"]

    print("\n数据库当前统计：")
    for row in labels:
        print(f"  {row['label']:12s} {row['count']:>5d}")
    print(f"  {'关系总数':12s} {relations:>5d}")


def main() -> int:
    parser = argparse.ArgumentParser(description="把医疗数据导入 Neo4j")
    parser.add_argument("--data", default=str(DEFAULT_DATA), help="数据文件路径（JSON Lines）")
    parser.add_argument("--dry-run", action="store_true", help="只解析数据并打印统计，不写数据库")
    args = parser.parse_args()

    path = Path(args.data)
    if not path.exists():
        print(f"找不到数据文件：{path}", file=sys.stderr)
        return 1

    records = read_records(path)
    if not records:
        print(f"{path.name} 里没有有效记录", file=sys.stderr)
        return 1

    print(f"读取 {path.name}：{len(records)} 条疾病记录\n")
    plan = build_plan(records)
    describe(plan)

    if args.dry_run:
        print("\n--dry-run：未连接数据库，未写入任何数据")
        return 0

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        driver.verify_connectivity()
        write_graph(driver, plan)
        print("\n建图完成")
        print_statistics(driver)
    except Exception as exc:  # noqa: BLE001
        print(f"\n建图失败：{exc}", file=sys.stderr)
        return 1
    finally:
        driver.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
