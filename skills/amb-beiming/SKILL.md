---
name: amb-beiming
description: 把一位作者的真实语料（课程转写、访谈、作品、短分享）蒸馏成一套能替使用者做具体任务的技能工具箱，每条判断都能回到原话。当使用者说"把这些课/文章做成 skill""从语料里萃取方法论做成工具""给我的内容做一套 agent 技能""给已有的工具箱加新料"时使用；也用于把别人的现成 skill 改造成可溯源的形态。不用于写单篇文章、做笔记摘要或不需要溯源的泛化提示词。
---

# amb-beiming：语料 → 技能工具箱

你是执行 agent。你调度脚本、派子代理、抽样质检、写给使用者看的文档；你不自己通读语料，不手改状态文件（批次状态只经 settle / stop / recover / reset / exclude 改），不跳过使用者的三个参与点。做出来的东西叫工具箱：一个路由器 + 若干任务技能，使用者带着事实来，拿走成品。

## 开工前

1. 完整读 `references/00-overview.md`（术语、两层产物、工程目录、schema、状态与停止、派发方式）。其余 references 按下表在进入那一段时读。
2. 环境：Python 3.9+，只用标准库。所有命令的形式是 `python3 <本技能目录>/scripts/beiming.py <子命令> …`，在工程目录里运行或加 `--project <目录>`。
3. 接手任何工程先跑 `beiming.py status`。它只看文件与校验记录，告诉你当前在哪段、缺什么、下一步命令是什么。新会话、被打断、别人做过一半，都从它开始。
4. 使用者只在三处出现：S1 看预检结论、S2 看加工样品、S4 确认能力方案。其余判断你做，并留下文件作证据。
5. 语料少于约 50 个文件且不到 8 万字时不用本技能：读完直接手写一个技能更便宜；S1 预检报告里把这一点告诉使用者。

## 总调度表

| 段 | 目标 | 你跑的命令（顺序） | 派子代理 | 门槛（status 判"完成"的依据） | 详见 |
|---|---|---|---|---|---|
| S1 盘点 | 能开工吗、做出什么 | 向使用者要语料目录，并问一句"你想拿它具体做什么"（粗方向即可，**不要求清单**）→ `survey --corpus <目录> --project <项目>-workspace`（建工程）→ 核形态 → 写 `work/docs/预检报告.md` 与 `候选任务草案.md` | 无 | catalog / batches 在；预检报告含 可开工 / 收缩范围 / 补料 | 01-survey.md |
| S2 试点 | 规则调到连续两批不改，冻结 | `pilot <b,b>`（要求预检报告已有三选一结论，否则拒绝；首次生成 `work/docs/执行提示词.md`，先填它第 6 节的白名单）→ 派 → `settle --pilot` → `read <b> --sample` → `calibrate` → 派 → 再试或冻结：把执行提示词第 3 行的版本行整行改成「版本：冻结 vX.Y」→ `settle --pilot --accept`（把 done 的试点批搬进 parts） | 每批 1；校准 1 | 执行提示词有独立成行的「版本：冻结 vX.Y」（说明句不算）；试点批全部 pilot-accepted；加工样品在 | 02-pilot.md |
| S3 萃取 | 全量抽成档案层 | `extract`（未冻结 / 缺加工样品 / 试点批未接纳 都会被拒，退出码 2；`--force` 越过并记 pipeline）→ 派 → `settle` → `read all --sample` → `merge` → `audit` → 处置低覆盖；要返工的批 `reset <b>` 后重抽，语料本身坏的 `exclude <b> --reason` | 每批 1 | 无未完成批；merge / audit 通过且未过期；折损待处置为 0 | 03-extract.md |
| S4 方案 | 定任务，分池 | `plan` → 派（或自写）→ **使用者确认** → 写 `work/tasks.json` → `repool` | 1 | tasks.json 含 confirmed_at；repool 无无处归 | 04-plan.md |
| S5 蒸馏 | 每任务知识包 + 六层 + 卡 | 每任务：`distill --step pack` → 派 → `caselib` → `screen` → `distill --step layers` → 派 → `check-layers` → `distill --step cards` → 派 → **再跑一次 `check-layers`**（卡是这时才有的，不再核一次，卡里的引文永不核验）；最后 `index` | 每任务 3 | 四件齐；每任务 check-layers 通过；index 在 | 05-distill.md |
| S6 成技 | 任务技能 + 路由器 | `compose all` → 派 → `compose --router` → 派 → `lint` | 每任务 1 + 路由器 1 | lint 全 PASS | 06-compose.md、product-spec.md |
| S7 验收 | 比裸模型强多少、弱在哪层 | `evaluate questions` → 派 → `evaluate answers --sources bare,new[,old]` → 派 → `evaluate judge` → 派 ×2 → `evaluate tally`（任务 × 题 × 来源 × 两评委缺一格即拒）→ `evaluate report`；写 `work/docs/验收报告.md` | 出题 1；每来源×任务 1；每任务 2 评委（含路由器） | 默认至少一套题集全部 PASS 且评测依赖未变；带 WEAK 交付须 `--force`，验收报告与成品 README 写明弱项（不写工程路径） | 07-evaluate.md |
| S8 交付 | 自包含成品 | `deliver <工具箱名> [--plugin] [--no-kb]` | 无 | deliver 记录通过（含 `lint --product`）且成品目录在 | 08-deliver.md |
| S9 增量 | 新料局部更新 | `survey --update` → S3 命令 → `repool` → `update all --groups gXX` → 派（只改知识包）→ `check-layers all` → `compose all --sync-refs` → `lint` → S7 回归 → `deliver` | 每任务 1 | 回归无任务掉到 WEAK | 09-update.md |

子代理怎么派：脚本把填好的提示词写到 `work/prompts/`，一份一个子代理，把提示词全文交给它；并发数按宿主上限。设了 `BEIMING_AGENT`（codex / claude / 自定义命令）脚本会自己并发调用。子代理的回复不算产物，它写的文件才算，随后的核验命令（settle / check-layers / lint / tally）才是"完成"。宿主不能派子代理时，你逐份自己做，先告知使用者将串行处理再开始。细则在 `references/collaboration.md`。

## 原则

1. **逐字或没有。** 原子的 original、单元的 text、六层的原话、技能里引用的作者句子，都必须是来源文件的逐字子串；脚本核，不过不进下一步。改写过的引文比没有更糟，它让使用者以为那是作者说的。
2. **完成只认文件与校验记录。** 产物存在 + 核验通过 + 输入未变，三者缺一不算完成。口头汇报、"应该写好了"、进度条，都不是。
3. **规则冻结再全量。** S2 连续两批不改 schema、白名单、confidence 判据、去重、保真五项才冻结；冻结后要改就升版本、标生效批次、受影响批重抽。
4. **两层分开。** 档案层最大化还原（能回到每句原话），工作集最小化激活（技能运行时按编号只读当下要判的几条）。不把档案塞进技能，也不为了瘦身丢档案。
5. **使用者的三个参与点不跳。** 预检结论、加工样品、能力方案——三处都有脚本硬门：`pilot` 查预检结论，`extract` 查加工样品与试点接纳，`repool` 查 confirmed_at；`--force` 越过会写进 pipeline.md，验收报告要交代。给他看的文档用"你"，不出现段号、脚本名、字段名。三处之外唯一会再找他的情形：S9 增量里新料与旧主张相反而作者自己没说明取舍（冲突表里"交使用者"的行），这是既有能力，不算新参与点。
6. **作者的方法就是方法。** 不评判对错、不加提醒、不用行业通则补作者没讲的步骤；作者自己说的条件与"慎用"连同方法保留。
7. **对照才有意义。** 验收必比裸模型；同一轮同一答题模型；两位评委盲评；差距小于 1 分不解读；修订两轮后换没见过的题集。

## 停止

收到停止指令（使用者说停、额度用尽、宿主要求）时：

1. 立刻 `beiming.py stop`：写 `work/STOP`，in_progress 批标 interrupted；此后所有派发命令（pilot / extract / calibrate / plan / distill / compose / evaluate / update / run）拒绝生成新提示词，退出码 2。
2. 不再派任何子代理。已派出的：宿主能取消就取消；不能就等它返回，但**不 settle、不合并、不把它的产物当完成**。
3. `beiming.py status` 核实存量，向使用者报告三件事：完成了什么（有校验记录的）、什么被中断（interrupted 批、未核对的六层、未体检的技能）、下一步从哪里续。
4. 恢复时 `beiming.py recover`：删 STOP，interrupted 退回 pending，旧产物改名 `.stale-<时间>` 留证据；没重新 `extract` 之前 `settle` 不会核这些批（中断前的半截产物不可能被判 done）。再跑 `status` 续。

设了 `BEIMING_AGENT` 时 `run_stage` 读到 STOP 自动不开新任务，正在跑的那几份跑完即止；碰到 429 睡 120 秒醒来后也先看 STOP。

## 命令速查

所有子命令都接受 `--project <工程目录>`，未知参数报错不忽略。

```
status [--json] | status --all <工程…>   接手先跑；--all 一行一个工程
survey --corpus <目录> [--form g01=A] [--max-chars N] [--update]   （init 是别名）
pilot <b001,b004> [--force]       S2 试点（要求预检报告有结论；首次运行建 work/docs/执行提示词.md v1.0）
calibrate                         S2 校准提示词
settle [all|b,b] [--pilot] [--accept] [--force]   --accept 需已冻结；把 done 的试点批搬进 parts
extract [--batches all|b,b] [--regenerate] [--workers N] [--force]   未冻结 / 缺加工样品 / 试点未接纳 / 无可派批 → 退出非 0；形态 D 批预写 work 单元
run <名,名> [--workers N]         BEIMING_AGENT 非 none 时手动重跑某些提示词
read <bNNN|task:<id>|all> [--sample]
merge / audit [--threshold 0.30]
plan / repool
distill <任务|all> --step pack|layers|cards
caselib <任务|all> / screen <任务|all> / check-layers <任务|all> [--file 路径] / index
compose <任务|all> / compose --router / compose <任务|all> --sync-refs / lint [--product <成品目录>]
evaluate questions|answers|judge|tally|report [--testset 常备|泛化|暴力] [--sources bare,new,old,pack] [--old <目录>]
deliver <工具箱名> [--dest 目录] [--plugin] [--no-kb] [--force]
update <任务|all> --groups g05,g06
stop / recover / reset <b,b> [--reason 文] / exclude <b,b> --reason 文   recover 与 reset 都把旧产物改名 .stale
selfcheck [--corpus <目录>]      维护者检查本技能自身
```

每个脚本文件头部都有用法与"为什么有这一步"；子命令与脚本的对应见 `scripts/beiming.py help`。

## 你不做的事

- 不把语料拷进工程，不把成品装进任何宿主的技能目录（安装是接收方的动作）。
- 不在 references 或成品里写虚构语料；开源版不附真实工程摘录。
- 不用 jq 之类命令行工具改 JSONL；用脚本。
- 不在同一工程里让两个执行 agent 同时派发；要并行就分工程。
