"""
医疗知识图谱 · Cypher 查询层

与原项目的区别：
  - 不再用字符串 format 拼 Cypher（原写法有注入风险），全部用 $name 参数绑定
  - 换掉 py2neo（已停止维护），改用官方 neo4j 驱动
  - 连接懒加载 + 失败可读提示，不再让整个应用崩掉
"""
import os
from typing import Any

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError, Neo4jError

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "12345678")

RESULT_LIMIT = 20

# 意图 -> (主实体类型, [Cypher 模板, ...])
# 模板统一返回 subject / obj / rel 三列；$name 由驱动绑定，不拼接用户输入。
QUERY_MAP: dict[str, tuple[str, list[str]]] = {
    "disease_symptom": ("disease", [
        "MATCH (m:Disease)-[r:has_symptom]->(n:Symptom) WHERE m.name = $name "
        "RETURN m.name AS subject, n.name AS obj, r.name AS rel",
    ]),
    "symptom_disease": ("symptom", [
        "MATCH (m:Disease)-[r:has_symptom]->(n:Symptom) WHERE n.name = $name "
        "RETURN n.name AS subject, m.name AS obj, r.name AS rel",
    ]),
    "disease_cause": ("disease", [
        "MATCH (m:Disease) WHERE m.name = $name "
        "RETURN m.name AS subject, m.cause AS obj, '病因' AS rel",
    ]),
    "disease_prevent": ("disease", [
        "MATCH (m:Disease) WHERE m.name = $name "
        "RETURN m.name AS subject, m.prevent AS obj, '预防' AS rel",
    ]),
    "disease_lasttime": ("disease", [
        "MATCH (m:Disease) WHERE m.name = $name "
        "RETURN m.name AS subject, m.cure_lasttime AS obj, '治疗周期' AS rel",
    ]),
    "disease_cureprob": ("disease", [
        "MATCH (m:Disease) WHERE m.name = $name "
        "RETURN m.name AS subject, m.cured_prob AS obj, '治愈概率' AS rel",
    ]),
    "disease_cureway": ("disease", [
        "MATCH (m:Disease) WHERE m.name = $name "
        "RETURN m.name AS subject, m.cure_way AS obj, '治疗方式' AS rel",
    ]),
    "disease_easyget": ("disease", [
        "MATCH (m:Disease) WHERE m.name = $name "
        "RETURN m.name AS subject, m.easy_get AS obj, '易感人群' AS rel",
    ]),
    "disease_desc": ("disease", [
        "MATCH (m:Disease) WHERE m.name = $name "
        "RETURN m.name AS subject, m.desc AS obj, '简介' AS rel",
    ]),
    "disease_acompany": ("disease", [
        "MATCH (m:Disease)-[r:acompany_with]->(n:Disease) WHERE m.name = $name "
        "RETURN m.name AS subject, n.name AS obj, r.name AS rel",
        "MATCH (m:Disease)-[r:acompany_with]->(n:Disease) WHERE n.name = $name "
        "RETURN n.name AS subject, m.name AS obj, r.name AS rel",
    ]),
    "disease_not_food": ("disease", [
        "MATCH (m:Disease)-[r:no_eat]->(n:Food) WHERE m.name = $name "
        "RETURN m.name AS subject, n.name AS obj, r.name AS rel",
    ]),
    "disease_do_food": ("disease", [
        "MATCH (m:Disease)-[r:do_eat]->(n:Food) WHERE m.name = $name "
        "RETURN m.name AS subject, n.name AS obj, r.name AS rel",
        "MATCH (m:Disease)-[r:recommand_eat]->(n:Food) WHERE m.name = $name "
        "RETURN m.name AS subject, n.name AS obj, r.name AS rel",
    ]),
    "food_not_disease": ("food", [
        "MATCH (m:Disease)-[r:no_eat]->(n:Food) WHERE n.name = $name "
        "RETURN n.name AS subject, m.name AS obj, r.name AS rel",
    ]),
    "food_do_disease": ("food", [
        "MATCH (m:Disease)-[r:do_eat]->(n:Food) WHERE n.name = $name "
        "RETURN n.name AS subject, m.name AS obj, r.name AS rel",
        "MATCH (m:Disease)-[r:recommand_eat]->(n:Food) WHERE n.name = $name "
        "RETURN n.name AS subject, m.name AS obj, r.name AS rel",
    ]),
    "disease_drug": ("disease", [
        "MATCH (m:Disease)-[r:common_drug]->(n:Drug) WHERE m.name = $name "
        "RETURN m.name AS subject, n.name AS obj, r.name AS rel",
        "MATCH (m:Disease)-[r:recommand_drug]->(n:Drug) WHERE m.name = $name "
        "RETURN m.name AS subject, n.name AS obj, r.name AS rel",
    ]),
    "drug_disease": ("drug", [
        "MATCH (m:Disease)-[r:common_drug]->(n:Drug) WHERE n.name = $name "
        "RETURN n.name AS subject, m.name AS obj, r.name AS rel",
        "MATCH (m:Disease)-[r:recommand_drug]->(n:Drug) WHERE n.name = $name "
        "RETURN n.name AS subject, m.name AS obj, r.name AS rel",
    ]),
    "disease_check": ("disease", [
        "MATCH (m:Disease)-[r:need_check]->(n:Check) WHERE m.name = $name "
        "RETURN m.name AS subject, n.name AS obj, r.name AS rel",
    ]),
    "check_disease": ("check", [
        "MATCH (m:Disease)-[r:need_check]->(n:Check) WHERE n.name = $name "
        "RETURN n.name AS subject, m.name AS obj, r.name AS rel",
    ]),
    "disease_department": ("disease", [
        "MATCH (m:Disease)-[r:belongs_to]->(n:Department) WHERE m.name = $name "
        "RETURN m.name AS subject, n.name AS obj, r.name AS rel",
    ]),
}


class GraphQueryError(Exception):
    """图谱查询失败（连接 / 鉴权 / Cypher）"""


class GraphQuery:
    """Neo4j 查询封装：懒连接，线程安全由驱动负责"""

    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD):
        self.uri = uri
        self.user = user
        self.password = password
        self._driver = None

    # ---------- 连接 ----------
    def _get_driver(self):
        if self._driver is None:
            self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        return self._driver

    def verify(self) -> tuple[bool, str]:
        """检查数据库是否可用，返回 (ok, 消息)"""
        try:
            with self._get_driver().session() as s:
                s.run("RETURN 1").consume()
            return True, "Neo4j 连接正常"
        except AuthError:
            return False, "Neo4j 鉴权失败，请检查 NEO4J_USER / NEO4J_PASSWORD"
        except (ServiceUnavailable, OSError):
            return False, f"无法连接 Neo4j（{self.uri}），请确认数据库已启动"
        except Exception as e:  # noqa: BLE001
            return False, f"Neo4j 检查失败：{e}"

    def statistics(self) -> dict[str, Any]:
        """返回节点/关系总数与各标签统计"""
        cypher = """
            MATCH (n) WITH labels(n) AS ls, count(*) AS c
            UNWIND ls AS l
            RETURN l AS label, sum(c) AS count ORDER BY count DESC
        """
        try:
            with self._get_driver().session() as s:
                labels = [dict(r) for r in s.run(cypher)]
                total_rel = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
            return {"ok": True, "labels": labels, "relations": total_rel}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)}

    # ---------- 查询 ----------
    def run_intent(self, intent: str, name: str) -> list[dict[str, Any]]:
        """执行某个意图对应的全部 Cypher，返回扁平行列表"""
        entry = QUERY_MAP.get(intent)
        if not entry:
            return []
        _, templates = entry
        rows: list[dict[str, Any]] = []
        try:
            with self._get_driver().session() as s:
                for cypher in templates:
                    for rec in s.run(cypher, name=name):
                        rows.append(dict(rec))
        except (ServiceUnavailable, OSError) as e:
            raise GraphQueryError(f"数据库连接失败：{e}") from e
        except Neo4jError as e:
            raise GraphQueryError(f"查询执行失败：{e.message}") from e
        return rows

    def run_raw(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """执行任意参数化 Cypher（仅供调试/扩展）"""
        try:
            with self._get_driver().session() as s:
                return [dict(r) for r in s.run(cypher, **(params or {}))]
        except Exception as e:  # noqa: BLE001
            raise GraphQueryError(str(e)) from e

    def close(self):
        if self._driver is not None:
            self._driver.close()
            self._driver = None


if __name__ == "__main__":
    g = GraphQuery()
    print(g.verify())
    print(g.statistics())
    for row in g.run_intent("disease_symptom", "感冒"):
        print(row)
    g.close()
