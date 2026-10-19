"""
医疗知识图谱 · 回答模板层

查询层统一返回 subject / obj / rel 三列，这里按意图套模板拼成人话。
保留原项目的说法，只把错别字和不通顺的句子修了一下。
"""
from typing import Any

RESULT_LIMIT = 20


def _uniq(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        if v is None:
            continue
        if isinstance(v, (list, tuple)):
            text = "、".join(str(x) for x in v if x)
        else:
            text = str(v).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out[:RESULT_LIMIT]


def _join(values: list[str], sep: str = "；") -> str:
    return sep.join(values) if values else "（暂无数据）"


def format_answer(intent: str, rows: list[dict[str, Any]]) -> str:
    """把查询结果拼成中文回答；查不到时返回空串（调用方决定兜底话术）"""
    if not rows:
        return ""

    subject = str(rows[0].get("subject") or "")
    objs = _uniq([r.get("obj") for r in rows])

    if intent == "disease_symptom":
        return f"「{subject}」的常见症状包括：{_join(objs)}"

    if intent == "symptom_disease":
        return f"出现「{subject}」这类症状，可能对应的疾病有：{_join(objs)}"

    if intent == "disease_cause":
        return f"「{subject}」可能的成因：{_join(objs)}"

    if intent == "disease_prevent":
        return f"「{subject}」的预防措施：{_join(objs)}"

    if intent == "disease_lasttime":
        return f"「{subject}」的治疗周期大约为：{_join(objs)}"

    if intent == "disease_cureway":
        return f"「{subject}」可以尝试的治疗方式：{_join(objs)}"

    if intent == "disease_cureprob":
        return f"「{subject}」的治愈概率（仅供参考）：{_join(objs)}"

    if intent == "disease_easyget":
        return f"「{subject}」的易感人群：{_join(objs)}"

    if intent == "disease_desc":
        return f"「{subject}」简介：{_join(objs, ' ')}"

    if intent == "disease_acompany":
        return f"「{subject}」可能引发的并发症：{_join(objs)}"

    if intent == "disease_not_food":
        return f"「{subject}」忌食的食物：{_join(objs)}"

    if intent == "disease_do_food":
        do_eat = _uniq([r.get("obj") for r in rows if r.get("rel") == "宜吃"])
        recipes = _uniq([r.get("obj") for r in rows if r.get("rel") == "推荐食谱"])
        parts = []
        if do_eat:
            parts.append(f"宜吃：{_join(do_eat)}")
        if recipes:
            parts.append(f"推荐食谱：{_join(recipes)}")
        return f"「{subject}」的饮食建议 —— " + ("；".join(parts) if parts else "（暂无数据）")

    if intent == "food_not_disease":
        return f"建议少吃「{subject}」的人群/疾病：{_join(objs)}"

    if intent == "food_do_disease":
        return f"适合食用「{subject}」的人群/疾病：{_join(objs)}"

    if intent == "disease_drug":
        return f"「{subject}」的常用药品：{_join(objs)}"

    if intent == "drug_disease":
        return f"「{subject}」主要用于治疗：{_join(objs)}"

    if intent == "disease_check":
        return f"「{subject}」通常需要做的检查：{_join(objs)}"

    if intent == "check_disease":
        return f"通过「{subject}」可以检查出的疾病：{_join(objs)}"

    if intent == "disease_department":
        return f"「{subject}」建议就诊科室：{_join(objs)}"

    # 未登记的意图，退化成通用输出
    return f"「{subject}」相关结果：{_join(objs)}"
