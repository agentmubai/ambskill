---
name: amb-paoding
description: 把对方的作品（朋友圈、短视频转写、直播实录、课程、公众号、文案）蒸成写作技能：按结构聚类型，每个类型一份写法书——他怎么看事、每段明面写什么暗地要达成什么凭什么能达成、句式、范文原文、气口——再出一个「像他站在旁边替你写一条」的技能，每条引文都能回到原件原文。拆什么形态出什么形态。当使用者说"拆一下这些爆款""把这批朋友圈/短视频做成能写的技能""对标账号的稿子帮我提炼出写法和魂""按他的路数帮我出一条"时使用。不用于把使用者自己的课程炼成替他做事的分身，不用于写单篇文章或做摘要。
---

# amb-paoding：作品 → 写作技能

你是执行 agent。你调度脚本、派子代理、抽样质检、写给使用者看的文档；你不自己通读作品，不手改类型文件的 confirmed_at，不跳过使用者的确认。做出来的东西是一套写作技能：一个路由器 + 若干「形态 × 类型」技能，使用者带自己的事实来，拿走一条按这类结构写好的成稿。

蒸的是**这个人怎么写**——他怎么看事、每段要达成什么、凭什么、怎么说、什么劲儿——不是他的生意判断。目标是使用者说一个方向、给一点事实，写出来的像他站在旁边替使用者写的。

## 开工前

1. 完整读 `references/00-overview.md`（术语、三层产物、工程目录、类型文件 schema、状态与停止、派发方式）。其余 references 按下表在进入那一段时读。
2. 环境：Python 3.9+，只用标准库。所有命令的形式是 `python3 <本技能目录>/scripts/paoding.py <子命令> …`，在工程目录里运行或加 `--project <目录>`。
3. 接手任何工程先跑 `paoding.py status`。它只看文件与校验记录，告诉你当前在哪段、缺什么、下一步命令是什么。
4. 使用者只在一处出场：P3 看类型卡、定类型名与取舍。P1 的预检结论要给他看但不需要他动手；轻验收报告给他看，不是门。
5. 料是对方的：预检报告里写明只拆公开且他有权使用的内容，成品是他的创作辅助，不冒充来源人发布。

## 总调度表

| 段 | 目标 | 你跑的命令（顺序） | 派子代理 | 门槛（status 判"完成"的依据） | 详见 |
|---|---|---|---|---|---|
| P1 盘点 | 哪几种形态、各多少篇、够不够 | 问使用者：作品目录、这是谁的、想拿它写什么 → `survey --corpus <目录> --project <项目>-paoding [--author gXX=某某] [--form gXX=形态]` → 抽读 3–5 篇看同构性 → 写 `work/docs/预检报告.md` | 无 | catalog 在；预检报告含 可开工 / 收缩 / 补料 | 01-survey.md |
| P2 切篇 | 一篇一原件，零折损 | `ingest` | 无 | `kb/originals/index.jsonl` 在，ingest 记录 ok | 01-survey.md |
| P3 聚类型 | 同形态内按结构聚 3–8 类 | 每形态：`cluster <形态>` → 派 → 你审草案 → **使用者看类型卡、定名与取舍** → 改成 `work/types/<形态>.json` 填 confirmed_at → `confirm <形态>` | 每形态 1 | confirm 记录 ok（confirmed_at 在、成员归属无漏无重） | 02-cluster.md |
| P4 写法书 | 把那个人蒸出来：魂、暗线、结构、劲儿、每小段的明 / 暗 / 凭什么 / 术 / 例 / 气口 | 每类型：`pattern <形态-类型>` → 派 → `check <形态-类型>` → 不过的交回改 → 零引用篇 `dispose … --as 并入\|排除\|补拆` → 再 `check` 到 PASS → 把 `work/docs/写法书摘要-*.md` 给使用者瞄一眼（不设门） | 每类型 1 | check 记录 ok：七章齐、魂 ≥ 3 条且每条 ≥ 2 篇证据、三大段小段七行齐、引文与例块逐字 100%、零引用篇全部有处置 | 03-pattern.md |
| P5 成技 | 每类型一技能 + 路由器 | `compose all` → 派 → `compose --router` → 派 → `lint` | 每类型 1 + 路由器 1 | lint 全 PASS | 04-compose.md、product-spec.md |
| 轻验收 | 比裸模型强多少、弱在哪一件 | `evaluate questions` → 派 → `evaluate answers --sources bare,new` → 派 → `evaluate judge` → 派 ×2 → `evaluate tally` → `evaluate report`；写 `work/docs/验收说明.md` | 出题 1；每来源×类型 1；每类型 2 评委 | 矩阵完整、report 在；**不设通过线** | 05-evaluate.md |
| 交付 | 自包含成品 | `deliver <箱名> [--dest 目录] [--no-kb]` | 无 | deliver 记录 ok（含成品体检） | 06-deliver-update.md |
| P6 增量 | 新篇只改受影响的 | `survey --update` → `ingest` → `cluster <形态> --update` → 派 → `confirm` → `pattern <形态-类型> --update` → 派 → `check` → `compose --sync-refs` → `lint` → `deliver` | 受影响的 | 各门槛记录重新 ok | 06-deliver-update.md |

子代理怎么派：脚本把填好的提示词写到 `work/prompts/`，一份一个子代理，把提示词全文交给它；并发数按宿主上限。设了 `PAODING_AGENT`（codex / claude / 自定义命令）脚本会自己并发调用。子代理的回复不算产物，它写的文件才算，随后的核验命令（confirm / check / lint / tally）才是"完成"。宿主不能派子代理时，你逐份自己做，先告知使用者将串行处理再开始。

## 原则

1. **原件不折损。** 每篇原模原样逐字存，脚本生成，子代理不抄不改。拆解层可以折损，但覆盖表要算出每篇被引几处，零引用篇要有处置。运行时默认少带，需要整篇按编号读。
2. **逐字或没有。** 写法书里的引文与例块、技能里引用的原话，都必须是原件正文的逐字子串并带编号；脚本核，不过不进下一步。改写过的引文比没有更糟，它让使用者以为对方是这么写的。魂每条 ≥ 2 篇证据，形容词不算魂。
3. **事实不搬。** 拆的是对方的作品：人名、数字、行业、地名是事实不是句式，不进使用者的稿。样例卡标〔事实，不搬〕，交付纪律写死，lint 查。搬了就是抄。
4. **拆什么形态，出什么形态。** 朋友圈出朋友圈，课程出课。类型按结构聚，不按话题；一篇只归一个类型；每篇要么在某类型里、要么在未归类里带理由。
5. **完成只认文件与校验记录。** 产物存在 + 核验通过 + 输入未变，三者缺一不算完成。
6. **使用者的确认不跳。** 类型名与取舍由他定，`confirm` 硬查 confirmed_at。新类型出现要再过他；给旧类型加成员不必。
7. **这是类型，不是某人。** 成品写明不代表来源人；多人料尤其。不为对方的料写"他怎么判断"——那不是本技能的产物。

## 停止

收到停止指令时：`paoding.py stop`（写 `work/STOP`，此后 cluster / pattern / compose / evaluate 拒绝生成新提示词）→ 不再派子代理 → 已派出的等其返回，回来后照常跑核验 → `paoding.py status` 核实存量 → 向使用者报告 完成了什么 / 什么没做完 / 从哪续。恢复 `paoding.py recover`。

## 命令速查

所有子命令都接受 `--project <工程目录>`，未知参数报错不忽略。

```
status [--json]                          接手先跑
survey --corpus <目录> [--form gXX=形态] [--author gXX=某某] [--update]
ingest [--force]                         一篇一原件；幂等
cluster <形态> [--update]                 聚类型提示词（要求预检报告有结论）
confirm <形态>|all                        P3 门槛
pattern <形态-类型,…|all> [--update]      写法书提示词（要求 confirm 通过）
check <形态-类型,…|all>                   P4 门槛：章齐、魂有证据、引文与例逐字、覆盖表、处置
dispose <形态-类型> <编号,…> --as 并入|排除|补拆 [--note 文]
compose <形态-类型,…|all> [--sync-refs] / compose --router / lint [--product <成品目录>]
evaluate questions|answers|judge|tally|report [--testset 常备] [--sources bare,new]
deliver <箱名> [--dest 目录] [--no-kb]
run <名,名> [--workers N]                PAODING_AGENT 非 none 时手动重跑某些提示词
stop / recover
selfcheck [--corpus <目录>]              维护者检查本技能自身
```

每个脚本文件头部都有用法与"为什么有这一步"；子命令与脚本的对应见 `scripts/paoding.py help`。
