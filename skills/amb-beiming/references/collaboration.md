# 协作协议：执行 agent、子代理、脚本各做什么

## 1 分工

| 谁 | 做 | 不做 |
|---|---|---|
| 脚本（scripts/） | 一切确定性的事：盘点切批、填提示词、核验引文、销账、合并去重、粗筛、逐字核对、体检、打乱评分、解析分数、装配成品、报状态 | 任何需要读懂语料的判断 |
| 子代理 | 读语料写原子与单元；写知识包、六层、案例卡；写技能；出题、答题、评分；增量对照。一份提示词一个子代理，只读只写提示词指定的文件 | 改 batches.json、改别人的文件、口头汇报代替写文件 |
| 执行 agent（你） | 调度脚本、派子代理、抽样质检、写给使用者看的文档、定冻结、判 PASS 之外的取舍、处理失败与停止 | 自己通读语料（读不完，而且读了也是一次性的）、手改状态、跳过使用者的三个参与点 |
| 使用者 | 看预检结论、看加工样品、确认能力方案；最后拿工具箱 | 不需要懂任何术语 |

## 2 派发

- 脚本为每个工作单位生成一份填好的提示词到 `work/prompts/`，文件名即任务名（`extract-b003`、`distill-pack-<任务>`、`compose-<任务>`、`evaluate-judge-常备-<任务>-J1`）。
- 宿主能派子代理：一份提示词一个子代理，把提示词全文作为子代理的任务；并发数按宿主上限，不设下限。子代理不需要读 amb-beiming 的 SKILL.md，提示词里已指明它要读的规则文件。
- 宿主不能派子代理：你自己逐份做，做一份写一份文件；开工前告知使用者将串行处理再开始。
- `BEIMING_AGENT=codex|claude` 或 `BEIMING_AGENT_CMD=<命令>`：派发脚本生成后直接并发调用外部 CLI；回复存 `work/reports/<名>.reply.md`，产物仍以提示词指定的文件为准。
- 自定义命令契约：提示词从 stdin 进；回复写 stdout；非 0 退出码算失败；输出含 usage limit / quota exceeded / insufficient credits 类字样算额度用尽（整批停）；含 429 / rate limit / overloaded 歇 120 秒重试最多 3 次；`{out}` 占位会被替换为回复文件路径。

## 3 销账

- `work/batches.json` 是批次的唯一真相源。状态只由 extract（→ in_progress）、settle（→ done / failed；`--pilot --accept` 把 claimed_by 改 pilot-accepted）、stop（→ interrupted）、recover（interrupted → pending）、reset（任意 → pending，供返工）、exclude（→ excluded，`--reason` 必填）改。你不手改。
- settle 只认文件：原子文件与批次报告都还不存在的 in_progress 批算"未返回"（不改状态，等子代理写完；不要重派）；recover / reset 过还没重新 extract 的批不核；其余批：三个文件（原子、单元、批次报告）都存在、JSONL 合法、必填字段、枚举值合法（role / type / claim_scope / confidence / 单元 type / flags）、id 合规不重复、原子↔单元互指都在本批、original ≤ 200 字、引文逐字命中、原子 > 0。任一不过 → failed 并在 note 写原因；检出即拒，不是没检出即过。
- 非批次类工作（知识包、六层、技能、答卷）没有销账表，靠对应的核验脚本记录（check-layers、lint、tally）与 `status` 判完成。
- 子代理"已完成"的口头汇报不进任何记录。

## 4 失败与续跑

- failed 批：看 note；引文未命中让原子代理修（把 note 里的 id 给它）；空文件重派；连续两次同批失败 → 你读阅读版判断是不是语料问题，是则 `beiming.py exclude <批> --reason "<问题>"`。done 批要返工用 `reset <批>`。
- 会话中断：新会话先 `status`，它告诉你当前在哪段、缺什么；in_progress 但子代理已不在的批，`stop` 再 `recover` 后重派。
- 输入变了（改了规则、重抽了批）：依赖它的阶段在 status 里显示 stale，重跑那一步即可，脚本按输入哈希判断。
- 试产（换个模型试试）的产物不进 parts，放 `work/tmp/`。

## 5 停止

见 00 第 7 节。要点：`beiming.py stop` → 不再派 → 已派出的等返回但不 settle → `status` 核实 → 报告 完成 / 中断 / 续点。宿主子代理若能取消就取消。恢复 `recover`。

## 6 边界

- 授权不外推：使用者说"样品可以，全量跑"只授权 S3，不等于能自行定能力方案；跨会话交接时范围以使用者原话为准，不加他没说过的条件。
- 报告进度区分"做了"和"声称做了"：脚本核验通过才写"完成"；子代理说读完了要抽查。
- 吸收使用者反馈先分类：通用规则 → 报给维护者改 amb-beiming；项目偏好 → 写进工程 pipeline.md；已有规则没执行 → 检讨执行，不加新条款。
- 被质疑时回到整体重审（重跑 status、重读该段 references），不局部撤项了事。

## 7 给使用者的文档

预检报告、加工样品、能力方案、验收报告、成品 README 用第二人称"你"，不出现流水线段号、脚本名、schema 字段名。要让不懂技术的人在五分钟内看完并做出决定。
