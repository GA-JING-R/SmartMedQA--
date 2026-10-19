# 医疗知识图谱问答系统 · Web 版

基于 Neo4j 医疗知识图谱的中文问答应用，用 Flask 提供聊天式 Web 界面。

问答链路完全由**规则**驱动，不调用任何大模型：

> 词典实体识别 → 疑问词意图分类 → 参数化 Cypher 查图谱 → 模板拼成回答

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-000000?logo=flask&logoColor=white)
![Neo4j](https://img.shields.io/badge/Neo4j-5.x-4581C3?logo=neo4j&logoColor=white)
![LLM](https://img.shields.io/badge/LLM-none-6A5ACD)

> ⚠️ 演示数据只有 **20 个疾病**（以呼吸系统疾病和中毒类为主），全部清单见 [图谱数据](#图谱数据)。问这 20 个以外的病，会回答「图谱里没有查到相关信息」。

## 界面

页面是一个聊天窗口，包含四块：

- **顶部栏**：数据库连接状态灯、「图谱统计」按钮
- **聊天区**：用户气泡与回答气泡，回答下方附带命中的意图和识别出的实体（方便调试）
- **示例区**：首屏展示 8 个可点即问的示例问题
- **输入区**：文本框 + 发送按钮，回车提交

<!-- 截图：把界面截图放到 docs/screenshot.png，然后取消下一行注释 -->
<!-- ![界面截图](docs/screenshot.png) -->

## 功能特性

- **聊天式问答界面**：示例问题一键提问，回答附带 `intents` / `entities` 调试信息
- **7 类实体、18 类问答意图**：疾病、症状、药品、食物、检查、科室、厂商；症状、病因、并发症、忌口、宜吃、药品、检查、预防、周期、治愈率、易感人群等
- **图谱统计弹窗**：实时读取各标签节点数与关系总数
- **连接状态检测**：启动时终端打印数据库状态，页面右上角常驻指示灯
- **Cypher 全参数化**：统一用 `$name` 绑定，不拼接用户输入，从源头避免注入
- **配置外置**：数据库地址、账号、密码、端口都可用环境变量覆盖
- **异常兜底**：数据库连不上时返回可读提示（HTTP 503），页面不会白屏
- **零前端依赖**：模板 + 原生 JavaScript，不需要 npm 构建
- **一键建图**：`load_graph.py` 把 JSON 数据导入 Neo4j，幂等、可重复执行、支持 dry-run

## 工作原理

```
用户问题
   │
   ▼
classifier.py ── Aho-Corasick 词典匹配，找出问题里的实体
   │              （被更长实体包含的子串会被丢弃，如「肺气肿」优先于「肺」）
   ▼
classifier.py ── 疑问词表 + 实体类型 + 否定词，判定意图（可能多个）
   │              如「症状」+ disease → disease_symptom
   │                 「不能吃」中的「不能」命中否定词 → disease_not_food
   ▼
graph_query.py ─ 按意图取 Cypher 模板，$name 绑定实体名查 Neo4j
   │
   ▼
answer.py ────── 按意图套回答模板，拼成中文句子
```

同一句话命中多个意图时（例如「肺气肿吃什么药」同时命中 `disease_do_food` 和 `disease_drug`），会把多段回答依次拼接。

## 快速开始

### 环境要求

| 依赖 | 要求 | 实测版本 |
|---|---|---|
| Python | 3.10+ | 3.12.4 |
| Neo4j | 5.x | 5.27.0 Community |
| Flask | 3.x | 3.1.2 |
| neo4j 驱动 | 5.x+ | 6.1.0 |
| pyahocorasick | 2.x | 2.3.1 |

### 1. 安装依赖

```bat
pip install -r requirements.txt
```

### 2. 启动 Neo4j

```bat
:: Windows
<Neo4j 安装目录>\bin\neo4j.bat console
```

```bash
# Linux / macOS
<Neo4j 安装目录>/bin/neo4j console
```

浏览器打开 <http://localhost:7474> 能进入 Neo4j Browser 即就绪。

### 3. 导入图谱数据

仓库自带建图脚本 `load_graph.py` 和 20 条疾病的示例数据 `data_medical2.json`，先建图：

```bat
python load_graph.py
```

脚本会打印将要写入的节点与关系数量，建完后输出数据库统计（和本文档[图谱数据](#图谱数据)一节一致）。

- 只想看看数量、不写库：`python load_graph.py --dry-run`
- 换别的数据文件：`python load_graph.py --data 路径/文件.json`
- 脚本是幂等的：节点和关系都用 `MERGE`，反复执行不会产生重复数据
- 数据里指向未收录节点的关系（如并发症指向了图谱外的疾病）会被自动跳过

数据库为空时应用仍能启动，只是所有提问都会返回「图谱里没有查到相关信息」。

### 4. 启动 Web 服务

```bat
python app.py
```

终端出现下面的输出即成功：

```
==================================================
  医疗知识图谱问答系统 · Web
  数据库：Neo4j 连接正常
  访问：http://127.0.0.1:5000
==================================================
```

> 数据库没连上时第二行会变成「无法连接 Neo4j（bolt://localhost:7687），请确认数据库已启动」或「Neo4j 鉴权失败，请检查 NEO4J_USER / NEO4J_PASSWORD」，服务本身照常启动。

### 5. 打开页面

访问 <http://127.0.0.1:5000>，点击示例问题或直接输入。

## 配置

全部通过环境变量覆盖，不需要改源码：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j 连接地址 |
| `NEO4J_USER` | `neo4j` | 数据库用户名 |
| `NEO4J_PASSWORD` | `12345678` | 数据库密码（默认值仅供本地演示，**部署前务必改掉**） |
| `WEB_PORT` | `5000` | Web 服务端口 |

示例：

```bat
set NEO4J_PASSWORD=你的密码
set WEB_PORT=8000
python app.py
```

> 密码的默认值写在 `graph_query.py` 里，只是为了让本地演示开箱即用；生产环境请通过环境变量传入，或直接删掉默认值。

## 支持的问题

系统按「实体 + 疑问词」判定意图。下表每一行都已在默认的 20 条数据上验证过：

| 意图 | 示例问法 | 回答示例（节选） |
|---|---|---|
| `disease_symptom` | 肺气肿的症状有哪些 | 「肺气肿」的常见症状包括：小支气管粘膜水肿；桶状胸；胸闷…… |
| `symptom_disease` | 胸闷可能是什么病 | 出现「胸闷」这类症状，可能对应的疾病有：单纯性肺嗜酸粒细胞浸润症；肺大疱；肺气肿；百日咳 |
| `disease_cause` | 肺气肿的病因 | 「肺气肿」可能的成因：引起慢支的各种因素如感染，吸烟…… |
| `disease_acompany` | 肺气肿会引发什么并发症 | 「肺气肿」可能引发的并发症：放射性肺炎 |
| `disease_not_food` | 肺气肿不能吃什么 | 「肺气肿」忌食的食物：海虾；羊肉(瘦)；圆白菜；带鱼 |
| `disease_do_food` | 肺气肿吃什么好 | 「肺气肿」的饮食建议 —— 宜吃：鹿肉；杏仁……推荐食谱：山楂糕…… |
| `food_not_disease` | 海虾忌口什么 | 建议少吃「海虾」的人群/疾病：百日咳；苯中毒；喘息样支气管炎；肺气肿 |
| `food_do_disease` | 肺气肿能吃鹿肉吗 | 适合食用「鹿肉」的人群/疾病：肺气肿 |
| `disease_drug` | 肺气肿的常用药品 | 「肺气肿」的常用药品：氨茶碱片；噻托溴铵粉雾剂；茶碱缓释片…… |
| `drug_disease` | 氨茶碱片治疗什么 | 「氨茶碱片」主要用于治疗：肺气肿；喘息样支气管炎 |
| `disease_check` | 肺气肿要做什么检查 | 「肺气肿」通常需要做的检查：深吸气量（IC）；肺容量测定；心电图…… |
| `check_disease` | 血常规能检查出什么病 | 通过「血常规」可以检查出的疾病：百日咳；二硫化碳中毒；苯中毒…… |
| `disease_prevent` | 怎么预防肺气肿 | 「肺气肿」的预防措施：1、首先是戒烟…… |
| `disease_lasttime` | 肺气肿治疗周期多长 | 「肺气肿」的治疗周期大约为：120天 |
| `disease_cureway` | 肺气肿怎么治疗 | 「肺气肿」可以尝试的治疗方式：药物治疗、支持性治疗、手术治疗 |
| `disease_cureprob` | 肺气肿能治好吗 | 「肺气肿」的治愈概率（仅供参考）：0.5% |
| `disease_easyget` | 什么人容易得肺气肿 | 「肺气肿」的易感人群：长期接触有机或无机粉尘，有害气体者，吸烟者 |
| `disease_desc` | 肺气肿是什么病 | 「肺气肿」简介：肺气肿是指终末细支气管远端（呼吸细支气管……）的气道弹性减退…… |

注意三点：

1. **疾病名必须在图谱内**。词典收录了 8807 个病名（全量词表），图谱只导入 20 个；词典认得、图谱查不到时返回「图谱里没有查到相关信息」。
2. **药品要写全名**。词典里是药名全称（如「氨茶碱片」「噻托溴铵粉吸入剂」），写简称「氨茶碱」识别不到。
3. **疑问词决定意图**。「XX 能治什么病」不会命中任何意图（疑问词表里是「治疗什么」「主治什么」「有什么用」），换一种说法即可。

## 图谱数据

### 节点（7 类）

| 标签 | 含义 | 数量 |
|---|---|---|
| `Disease` | 疾病 | 20 |
| `Symptom` | 症状 | 77 |
| `Drug` | 药品 | 88 |
| `Food` | 食物 / 食谱 | 138 |
| `Check` | 检查项目 | 56 |
| `Department` | 科室 | 7 |
| `Producer` | 药品厂商 | 270 |

疾病节点同时带有文本属性：`name`、`desc`（简介）、`prevent`（预防）、`cause`（病因）、`easy_get`（易感人群）、`cure_way`（治疗方式）、`cure_lasttime`（治疗周期）、`cured_prob`（治愈概率）、`cure_department`（科室数组）。

### 关系（共 856 条）

| 关系类型 | `name` 属性 | 方向 | 数量 |
|---|---|---|---|
| `has_symptom` | 症状 | Disease → Symptom | 112 |
| `acompany_with` | 并发症 | Disease → Disease | 1 |
| `no_eat` | 忌吃 | Disease → Food | 56 |
| `do_eat` | 宜吃 | Disease → Food | 56 |
| `recommand_eat` | 推荐食谱 | Disease → Food | 104 |
| `common_drug` | 常用药品 | Disease → Drug | 32 |
| `recommand_drug` | 好评药品 | Disease → Drug | 111 |
| `need_check` | 诊断检查 | Disease → Check | 88 |
| `belongs_to` | 所属科室 | Disease → Department | 20 |
| `belongs_to` | 属于 | Department → Department | 3 |
| `drugs_of` | 生产药品 | Producer → Drug | 273 |

> `do_eat` 的 `name` 必须是「宜吃」、`recommand_eat` 的必须是「推荐食谱」，回答层靠这两个值把饮食建议分成两组。

### 疾病清单（20 个）

二硫化碳中毒、单纯性肺嗜酸粒细胞浸润症、喘息样支气管炎、大叶性肺炎、大楼病综合征、大量羊水吸入、成人呼吸窘迫综合征、放射性肺炎、百日咳、肺-胸膜阿米巴病、肺出血－肾炎综合征、肺大疱、肺念珠菌病、肺放线菌病、肺曲菌病、肺气肿、肺泡蛋白沉着症、肺泡蛋白质沉积症、肺炎球菌肺炎、苯中毒

### 建图脚本

`load_graph.py` 把 `data_medical2.json` 导入 Neo4j：

```bat
python load_graph.py              :: 建图 + 打印统计
python load_graph.py --dry-run    :: 只解析和统计，不连数据库
python load_graph.py --data x.json
```

连接信息沿用 `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` 三个环境变量。脚本按下面的映射建图，节点和关系都用 `MERGE`，所以可以反复执行。

| JSON 字段 | 去向 |
|---|---|
| `name` / `desc` / `prevent` / `cause` / `easy_get` / `cure_way` / `cure_lasttime` / `cured_prob` | Disease 节点属性 |
| `cure_department` | 拆成 `belongs_to`（疾病 → 科室），两级科室再建 `belongs_to`（小科室 → 大科室） |
| `symptom` | `has_symptom` → Symptom |
| `acompany` | `acompany_with` → Disease |
| `check` | `need_check` → Check |
| `common_drug` / `recommand_drug` | `common_drug` / `recommand_drug` → Drug |
| `drug_detail` | 「厂商(药品名)」拆开，建 `drugs_of`（Producer → Drug） |
| `not_eat` / `do_eat` / `recommand_eat` | `no_eat` / `do_eat` / `recommand_eat` → Food |

原始数据里有 23 条并发症记录，其中 22 条指向的词条不在本图谱内（例如「肺气肿」的并发表里混进了别的病），建图时会被跳过，所以并发症关系只剩 1 条。

数据文件是 **GBK 编码**（脚本会自动按 UTF-8 → GBK 的顺序尝试解码），手动读取时记得指定：

```python
with open("data_medical2.json", encoding="gbk") as f:
    for line in f:
        record = json.loads(line)
```

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 聊天界面 |
| POST | `/api/ask` | 问答，请求体 `{"question": "..."}` |
| GET | `/api/status` | 数据库连接状态 |
| GET | `/api/stats` | 节点 / 关系统计 |
| GET | `/api/examples` | 示例问题列表 |

### POST /api/ask

```bash
curl -X POST http://127.0.0.1:5000/api/ask \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"肺气肿的症状有哪些\"}"
```

命中并查到数据：

```json
{
  "ok": true,
  "matched": true,
  "answer": "「肺气肿」的常见症状包括：小支气管粘膜水肿；桶状胸；胸闷；……",
  "intents": ["disease_symptom"],
  "entities": { "肺气肿": ["disease"] }
}
```

认出实体但图谱里没有：

```json
{
  "ok": true,
  "matched": false,
  "answer": "图谱里没有查到相关信息，换个问法或换个实体试试。",
  "intents": ["disease_symptom"],
  "entities": { "肺癌": ["disease"] }
}
```

问题里没有词典实体（直接返回引导话术，带 `debug` 字段）：

```json
{
  "ok": true,
  "matched": false,
  "answer": "没能理解你的问题。\n试试这些问法：\n· 肺气肿的症状有哪些\n……",
  "debug": { "entities": {}, "types": [], "intents": [], "denied": false }
}
```

错误响应：

| 情况 | 状态码 | 响应体 |
|---|---|---|
| `question` 为空 | `400` | `{"ok": false, "error": "请输入问题"}` |
| 数据库连接 / 查询失败 | `503` | `{"ok": false, "error": "数据库连接失败：……"}` |

### GET /api/status

```json
{ "ok": true, "message": "Neo4j 连接正常" }
```

未连接时 `ok` 为 `false`，`message` 给出具体原因（连不上 / 鉴权失败）。

### GET /api/stats

```json
{
  "ok": true,
  "labels": [
    { "label": "Producer", "count": 270 },
    { "label": "Food", "count": 138 },
    { "label": "Disease", "count": 20 }
  ],
  "relations": 856
}
```

数据库异常时返回 `{"ok": false, "error": "..."}`（HTTP 状态码仍是 200）。

## 目录结构

```
医疗知识图谱问答系统_web/
├── app.py                 Flask 应用与 5 个路由
├── classifier.py          实体识别 + 意图分类（规则）
├── graph_query.py         Cypher 查询层（官方 neo4j 驱动，参数化）
├── answer.py              回答模板
├── load_graph.py          建图脚本：data_medical2.json → Neo4j
├── test_qa.py             冒烟测试：疾病清单 + 4 条问答链路
├── requirements.txt
├── .gitignore             排除 __pycache__、虚拟环境、日志等
├── dict/                  实体词典（全量）
│   ├── disease.txt        8807 条病名
│   ├── symptom.txt        5998 条症状
│   ├── drug.txt           3828 条药名
│   ├── food.txt           4870 条食物
│   ├── check.txt          3353 条检查项目
│   ├── department.txt     54 条科室
│   ├── producer.txt       17201 条厂商
│   └── deny.txt           37 个否定词（不、不能、忌、无……）
├── templates/
│   └── index.html         单页界面
├── static/
│   ├── style.css
│   └── app.js             原生 JS：提问、状态检测、统计弹窗
└── data_medical2.json     20 条疾病的原始数据（GBK）
```

## 测试

```bat
python test_qa.py
```

脚本会：

1. 打印图谱中的全部疾病名（数据库没数据时会提示先导入并返回退出码 1）
2. 取第一个疾病，构造「症状 / 不能吃什么 / 并发症」三条问句；再从库里取一个药品，构造一条「XX 治疗什么」
3. 逐条打印识别到的实体、命中的意图和最终回答

它只是冒烟脚本，不做断言。需要 Neo4j 在线。个别问句显示「（无结果）」是正常的——比如第一个疾病恰好没有并发症关系。

## 常见问题

**页面右上角显示「数据库未连接」**
Neo4j 没启动、地址或密码不对。先确认 <http://localhost:7474> 能打开，再核对 `NEO4J_URI` / `NEO4J_PASSWORD`。

**问什么都回答「图谱里没有查到相关信息」**
实体认出来了，但图谱里没有这个实体。对照[疾病清单](#疾病清单20-个)确认病名是否在内。

**问什么都回答「没能理解你的问题」**
问题里没有词典实体，或疑问词不在支持范围内。药品请写全名，疾病名请写完整。

**端口 5000 被占用**
`set WEB_PORT=8001` 换个端口后重启。

**读取 data_medical2.json 报 `UnicodeDecodeError`**
文件是 GBK 编码，打开时要指定 `encoding="gbk"`。

**`load_graph.py` 跑完的数量和文档不一样**
节点 / 关系数量是按默认的 20 条数据统计的。换了数据文件，或库里本来就有别的标签数据，数字都会变——脚本打印的是全库统计。


## 已知限制

1. **规则系统，不是大模型**。意图靠疑问词是否出现来判定，换个问法就可能落到别的意图，或者落到「没能理解」。这也是它不产生幻觉的原因。
2. **图谱只有 20 个疾病**，而词典是全量的 8807 个病名，所以「词典认得、图谱没有」是最常见的空回答。
3. **并发症数据只有 1 条**。原始数据里 23 条并发症记录中有 22 条指向图谱外的疾病，建图时被跳过；剩下这一条（肺气肿 → 放射性肺炎）语义上也可疑，属于原始数据问题。
4. **「属于什么科」没有接入**。查询层里有 `disease_department` 模板，但分类器不产出这个意图，问「XX 属于什么科」会被兜底成疾病简介。
5. **药品必须写全名**，简称无法识别。
6. **否定词表偏宽**。`deny.txt` 里单字「不、无、没、少」等都会命中，个别问句可能被误判成「忌吃」类意图。
7. **Flask 开发服务器**。`app.run(debug=False)` 只适合本地使用，且只监听 `127.0.0.1`；对外部署请套 WSGI。
8. **无鉴权**。接口不校验身份，不要直接暴露到公网。
9. `data_medical2.json` 是 GBK 编码，不是 UTF-8。

## 免责声明

本项目用于学习与演示。图谱数据来自公开网络采集，可能存在错误、过时或不严谨之处；回答由模板拼接，仅供参考，**不构成任何医疗建议**。如有身体不适，请及时就医。

## 数据来源

图谱数据为公开医疗问答数据集。本版重写了查询与问答链路（官方驱动、参数化 Cypher、规则分类 + 模板作答），并附带基于官方驱动的建图脚本 `load_graph.py`。
