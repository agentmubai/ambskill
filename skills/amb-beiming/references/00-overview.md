# 00 总纲：这套流水线是什么、产什么、怎么记状态

SKILL.md 是调度表，本文件是它背后的契约：术语、两层产物、工程目录、数据 schema、状态与停止、派发方式。执行任何一段之前先把本文件读完一遍；之后按 SKILL.md 调度表定位到 01–09。

## 1 目标

输入一批某位作者的真实语料（课程转写、访谈、作品、短分享），输出一套能替使用者做具体任务的技能工具箱：每个任务技能里的每条判断都能按原子 id 回到作者原话；使用者带着事实来，拿走成品，而不是拿走"建议"。

## 2 术语

| 词 | 指 |
|---|---|
| 执行 agent | 读 SKILL.md、调度脚本、派子代理、做判断的那个 agent（你） |
| 子代理 | 执行 agent 派出去读语料、写知识包、写技能、答题、评分的 agent；一份提示词一个子代理 |
| 使用者 | 提供语料、确认预检结论、看加工样品、确认能力方案、最终用工具箱的人 |
| 接收方 | 拿到工具箱并装进自己宿主的人（可能就是使用者） |
| 维护者 | 改 amb-beiming 自身的人 |
| 工程 | 一次生产的全部中间物与成品所在目录 `<项目>-workspace/` |
| 成品 / 工具箱 | `product/<工具箱名>/`：路由器 + 任务技能 + 共享脚本 + 可选知识库 |
| 原子 | 一条作者主张 + 逐字原话 + 出处 + 标签 |
| 单元 | 完整案例 / 作者作品 / 成套步骤 / 完整论证的逐字全文 |
| 知识包 | 一个任务的方法论、案例对照、六层、案例卡 |
| 实测参照 | 上一版工具在几次真实工程里留下的记录（各段"依据"节末尾的"实测参照"段）；只说明规则的来历，不是承诺，也不是同一次工程 |

## 3 两层产物

- **档案层**（`work/kb/`）：最大化还原。原子库、单元库、案例库全文、折损审计。目标是"作者说过的都在、都能回到原话"。
- **工作集**（`product/`）：最小化激活。技能运行时只读它自己的 `references/{methods,cases,layers}.md`，按编号定位；不整读知识库。目标是"调用时只装进当下要判的那几条"。

两层分开，是因为把档案直接塞进技能会让模型整读几十 KB 后什么都记不住，而只做工作集又会在增量与追溯时丢证据。

## 4 九段一览

| 段 | 做什么 | 完成的定义 | 使用者参与 |
|---|---|---|---|
| S1 盘点 | 盘语料、切批、写预检报告 | catalog / batches 在，预检报告有结论（`pilot` 查它） | **看预检结论** |
| S2 试点 | 2–3 批试萃取，校准规则，冻结 | 执行提示词有独立成行的「版本：冻结 vX.Y」，试点批全部 pilot-accepted，加工样品在（`extract` 查这三条） | **看加工样品** |
| S3 萃取 | 全量派发、销账、合并、折损审计 | 无未完成批，merge/audit 记录通过，低覆盖已处置 | 无 |
| S4 方案 | 数据表 → 能力方案 → tasks.json → 任务池 | tasks.json 含 confirmed_at，repool 无无处归 | **确认能力方案** |
| S5 蒸馏 | 每任务：知识包 → 案例库 → 粗筛 → 六层 → 案例卡 → 索引 | 四件齐，六层逐字核对通过，索引在 | 无 |
| S6 成技 | 写任务技能与路由器，体检 | lint 全 PASS | 无 |
| S7 验收 | 出题、多方答题、双评委盲评、汇总 | 至少一套题集全部 PASS，验收报告在 | 无（结果给使用者看） |
| S8 交付 | 装配成品目录，复检 | deliver 记录通过 | 拿走 |
| S9 增量 | 新料对照、冲突表、局部改、回归 | 回归不掉 WEAK | 作者未说明取舍的冲突交使用者决定 |

使用者只在三处出现（S1 / S2 / S4）。S9 的冲突行是这三处之外唯一会再找他的情形——只在新料与旧主张相反且作者自己没说明时；不算新参与点。其余所有判断由执行 agent 做并留证据（文件）。

两种运行模式：**协作**（默认）在三处都等使用者；**全自动**（使用者一开始就说"别等我，做完给我看"）只在 S4 停一次——预检、试点、验收照做不省，S1 结论非"可开工"即停下报告，不硬做；S2 的样品判断由校准子代理做并落盘，使用者事后看。

## 5 工程目录

```
<项目>-workspace/
├── work/
│   ├── catalog.json        S1 语料盘点：组、稳定文件号、形态
│   ├── batches.json        S1–S3 批次销账表（唯一真相源）
│   ├── tasks.json          S4 使用者确认后的任务定义（schema 见 04）
│   ├── meta.json           各阶段校验记录（时间、通过、输入哈希）；status 据此判"完成"
│   ├── pipeline.md         流水账：每段结束追加一行
│   ├── STOP                存在即"停止中"
│   ├── prompts/            脚本填好的提示词，一份一个子代理
│   ├── reports/            子代理写的批次报告 / 阶段报告；外部 CLI 的回复
│   ├── pilot/              S2 试点产物
│   ├── parts/              S3 各批原子 / 单元 JSONL
│   ├── docs/               给使用者看的：预检报告、加工样品、候选任务草案、S4数据表、能力方案、验收报告、执行提示词、冲突表
│   ├── kb/                 档案层：atoms.jsonl units.jsonl alias.json sources.md 折损审计.md index.md
│   │   ├── pools/<任务>/   任务池
│   │   ├── packs/<任务>/   知识包：methods.md case_map.md case_library(.full).md layers.md cards.md
│   │   └── layers_input/<任务>/  粗筛候选与核对结果
│   ├── draft/skills/       S6 草稿技能
│   └── tests/<题集>/       S7：questions.md answers/ packets/ key.json scores/ scores.json report.md
└── product/<工具箱名>/     S8 成品：README.md skills/ scripts/fact_check.py [kb/] [.claude-plugin/]
```

`survey` 第一次运行时建好全部目录（不需要单独的 init）。语料不拷进工程，catalog 记录来源路径。

## 6 数据 schema 摘要

原子（`atoms.jsonl` 一行一条）：

```json
{"id": "c01_003_012", "knowledge": "书面主张一句", "original": "逐字原话 ≤200 字", 
 "source": {"group": "组名", "file": "文件名", "timestamp": "可选"}, "speaker": "谁", "role": "讲师|嘉宾|学员|主持|作品|未知",
 "topics": ["主题"], "skills": ["分池标签"], "type": "principle|method|case|anti-pattern|insight|tool",
 "claim_scope": "无条件主张|有条件做法|举例", "confidence": "high|medium|low", "flags": ["platform|conflict|unverified"], "unit_id": "可选", "note": "可选"}
```

单元（`units.jsonl`）：

```json
{"unit_id": "u01_003_02", "type": "case|work|sop|argument", "title": "…", "text": "原文连续子串，可长", 
 "source": {"group": "…", "file": "…", "timestamp_start": "", "timestamp_end": ""}, "speaker": "…", "role": "…", "summary": "…", "atom_ids": ["c01_003_012"]}
```

id 里的组号与文件号来自 catalog，S9 加新文件只追加号码不重排，所以 id 终身稳定。完整 schema、红线、判据在 extraction-rules.md。

## 7 状态、完成与停止

- **完成** = 产物文件存在 + 对应校验脚本记录通过（meta.json）+ 记录时的输入哈希与现在一致。三者缺一，`status` 都不显示"完成"。子代理的口头汇报不算数。输入哈希只含相对工程根的路径与内容：工程搬家、拷副本、`/tmp` 与 `/private/tmp`、`--project` 与 `cd` 两种写法，记录都不会假过期；成品位置也按相对路径记。
- 批次状态：pending → in_progress →（settle）→ done | failed；stop 把 in_progress 改 interrupted；recover 把 interrupted 退回 pending；`reset <批>` 把任意状态（含 done）退回 pending 供重抽；两者都把旧产物改名 `.stale-<时间>` 并给批打 `needs_reextract`，`extract` 生成新提示词时清掉，没清掉之前 `settle` 不核这批（退出码 1）；`exclude <批> --reason` 标 excluded（语料本身的问题，不再抽）。failed 与 interrupted 都不算完成，产物不进库；excluded 不计入未完成。批次状态只经这五个命令改，不手改 batches.json。
- 试点批的 `claimed_by`：pilot（试点中或 done 未接纳）→ pilot-accepted（`settle --pilot --accept` 后，产物已在 parts）。done 但仍是 pilot 的批不进 merge，status 会指出。
- **停止**：`beiming.py stop` 写 `work/STOP`，所有派发脚本（pilot / extract / calibrate / plan / distill / compose / evaluate 的 questions·answers·judge / update / run）读到它就拒绝生成新提示词，`run_stage` 不开新任务、429 睡醒后先看 STOP。宿主子代理模式下你收到停止指令后：立刻跑 stop → 不再派子代理 → 已派出的若宿主能取消就取消，不能就等它返回但**不 settle** → 跑 status 核实存量 → 向使用者报告"完成了什么 / 什么被中断 / 下一步从哪里续"。恢复用 `recover`。
- 接手任何工程先跑 `status`；它只看文件与记录。

## 8 派发方式两轴

| | 宿主能派子代理 | 宿主不能派子代理 |
|---|---|---|
| `BEIMING_AGENT=none`（默认） | 脚本生成提示词，你一份派一个子代理，并发数按宿主上限 | 你自己按提示词逐份做；先告知使用者将串行处理再开始 |
| `BEIMING_AGENT=codex\|claude\|custom`（只设 `BEIMING_AGENT_CMD` 等于 custom） | 脚本生成后直接并发调用外部 CLI（`--workers`） | 同左 |

自定义命令契约：提示词从 stdin 进，回复写 stdout（脚本存为 `work/reports/<名>.reply.md`），非 0 退出码算失败；输出里出现 usage limit / quota 类字样算额度用尽，出现 429 / rate limit 歇两分钟重试。回复不是产物，提示词里指定的文件才是。

