"""
医疗知识图谱 · 实体识别与意图分类（纯规则，无 LLM）

改造自原项目的 question_classifier.py：
  - 路径改用 pathlib（Windows 友好，不再用 '/'.join(split('/'))）
  - 去掉调试 print
  - 实体重叠去重写成清晰的 O(n²)（n 很小）
  - 意图判定保持原逻辑，另暴露 intent -> 实体类型 的映射给查询层
"""
from pathlib import Path

import ahocorasick

BASE_DIR = Path(__file__).resolve().parent
DICT_DIR = BASE_DIR / "dict"

ENTITY_FILES = {
    "disease": "disease.txt",
    "department": "department.txt",
    "check": "check.txt",
    "drug": "drug.txt",
    "food": "food.txt",
    "producer": "producer.txt",
    "symptom": "symptom.txt",
}

# 疑问词表，与原系统保持一致
QWDS = {
    "symptom": ["症状", "表征", "现象", "症候", "表现"],
    "cause": ["原因", "成因", "病因", "为什么", "怎么会", "怎样才", "咋样才", "怎样会", "如何会", "为啥", "为何",
              "如何才会", "怎么才会", "会导致", "会造成"],
    "acompany": ["并发症", "并发", "一起发生", "一并发生", "一起出现", "一并出现", "一同发生", "一同出现",
                 "伴随发生", "伴随", "共现"],
    "food": ["饮食", "饮用", "吃", "食", "伙食", "膳食", "喝", "菜", "忌口", "补品", "保健品", "食谱", "菜谱",
             "食用", "食物"],
    "drug": ["药", "药品", "用药", "胶囊", "口服液", "炎片"],
    "prevent": ["预防", "防范", "抵制", "抵御", "防止", "躲避", "逃避", "避开", "免得", "逃开", "避掉", "躲开",
                "躲掉", "绕开", "怎样才能不", "怎么才能不", "咋样才能不", "咋才能不", "如何才能不",
                "怎样才不", "怎么才不", "咋样才不", "咋才不", "如何才不"],
    "lasttime": ["周期", "多久", "多长时间", "多少时间", "几天", "几年", "多少天", "多少小时", "几个小时", "多少年"],
    "cureway": ["怎么治疗", "如何医治", "怎么医治", "怎么治", "怎么医", "如何治", "医治方式", "疗法", "咋治", "怎么办", "咋办"],
    "cureprob": ["多大概率能治好", "多大几率能治好", "治好希望大么", "几率", "几成", "比例", "可能性", "概率", "治愈率",
                 "能治", "可治", "可以治", "可以医"],
    "easyget": ["易感人群", "容易感染", "易发人群", "什么人", "哪些人", "感染", "染上", "得上"],
    "check": ["检查", "检查项目", "查出", "测出", "试出"],
    "belong": ["属于什么科", "属于", "什么科", "科室"],
    "cure": ["治疗什么", "治啥", "治疗啥", "医治啥", "治愈啥", "主治啥", "主治什么", "有什么用", "有何用", "用处",
             "用途", "有什么好处", "有什么益处", "有何益处", "用来", "用来做啥", "用来作甚", "需要", "要"],
}

# 意图 -> 主实体类型（查询层用它挑实体）
INTENT_ENTITY_TYPE = {
    "disease_symptom": "disease",
    "symptom_disease": "symptom",
    "disease_cause": "disease",
    "disease_acompany": "disease",
    "disease_not_food": "disease",
    "disease_do_food": "disease",
    "food_not_disease": "food",
    "food_do_disease": "food",
    "disease_drug": "disease",
    "drug_disease": "drug",
    "disease_check": "disease",
    "check_disease": "check",
    "disease_prevent": "disease",
    "disease_lasttime": "disease",
    "disease_cureway": "disease",
    "disease_cureprob": "disease",
    "disease_easyget": "disease",
    "disease_desc": "disease",
}


def _load_words(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [w.strip() for w in path.read_text(encoding="utf-8").splitlines() if w.strip()]


class QuestionClassifier:
    """实体识别 + 意图分类"""

    def __init__(self, dict_dir: Path | str | None = None):
        self.dict_dir = Path(dict_dir) if dict_dir else DICT_DIR
        self.entity_words = {k: _load_words(self.dict_dir / f) for k, f in ENTITY_FILES.items()}
        self.deny_words = _load_words(self.dict_dir / "deny.txt")

        self.wdtype: dict[str, list[str]] = {}
        all_words: set[str] = set()
        for etype, words in self.entity_words.items():
            for w in words:
                all_words.add(w)
                self.wdtype.setdefault(w, []).append(etype)

        self.tree = ahocorasick.Automaton()
        for idx, w in enumerate(sorted(all_words)):
            self.tree.add_word(w, (idx, w))
        self.tree.make_automaton()

    def extract_entities(self, question: str) -> dict[str, list[str]]:
        """识别实体并去掉被更长实体包含的子串，返回 {词: [类型...]}"""
        hits = [item[1][1] for item in self.tree.iter(question)]
        if not hits:
            return {}
        kept: list[str] = []
        for a in hits:
            if a in kept:
                continue
            if any(a != b and a in b for b in hits):
                continue
            kept.append(a)
        return {w: self.wdtype.get(w, []) for w in kept}

    def _has(self, key: str, question: str) -> bool:
        return any(w in question for w in QWDS[key])

    def classify(self, question: str) -> dict:
        """
        返回:
          {
            "entities": {词: [类型...]},
            "types":    集合里的类型名列表,
            "intents":  [意图...],          # 可能多个
            "denied":   bool                # 是否含"忌口/不能"类否定词
          }
        """
        entities = self.extract_entities(question)
        if not entities:
            return {"entities": {}, "types": [], "intents": [], "denied": False}

        types = {t for ts in entities.values() for t in ts}
        intents: list[str] = []
        denied = any(w in question for w in self.deny_words)

        if self._has("symptom", question) and "disease" in types:
            intents.append("disease_symptom")
        if self._has("symptom", question) and "symptom" in types:
            intents.append("symptom_disease")
        if self._has("cause", question) and "disease" in types:
            intents.append("disease_cause")
        if self._has("acompany", question) and "disease" in types:
            intents.append("disease_acompany")

        if self._has("food", question) and "disease" in types:
            intents.append("disease_not_food" if denied else "disease_do_food")
        if (self._has("food", question) or self._has("cure", question)) and "food" in types:
            intents.append("food_not_disease" if denied else "food_do_disease")

        if self._has("drug", question) and "disease" in types:
            intents.append("disease_drug")
        if self._has("cure", question) and "drug" in types:
            intents.append("drug_disease")
        if self._has("check", question) and "disease" in types:
            intents.append("disease_check")
        if (self._has("check", question) or self._has("cure", question)) and "check" in types:
            intents.append("check_disease")
        if self._has("prevent", question) and "disease" in types:
            intents.append("disease_prevent")
        if self._has("lasttime", question) and "disease" in types:
            intents.append("disease_lasttime")
        if self._has("cureway", question) and "disease" in types:
            intents.append("disease_cureway")
        if self._has("cureprob", question) and "disease" in types:
            intents.append("disease_cureprob")
        if self._has("easyget", question) and "disease" in types:
            intents.append("disease_easyget")

        # 兜底：有实体但没命中具体疑问词
        if not intents:
            if "disease" in types:
                intents = ["disease_desc"]
            elif "symptom" in types:
                intents = ["symptom_disease"]

        # 去重且保持顺序
        seen: set[str] = set()
        intents = [i for i in intents if not (i in seen or seen.add(i))]

        return {"entities": entities, "types": sorted(types), "intents": intents, "denied": denied}


if __name__ == "__main__":
    clf = QuestionClassifier()
    for q in ["感冒的症状有哪些", "高血压不能吃什么", "阿莫西林能治什么病", "糖尿病会引发什么并发症"]:
        print(q, "->", clf.classify(q))
