# 03 S3 全量萃取、销账、合并与折损审计

## 目标与产出

把全部批次按冻结的规则抽成原子与单元，机械核验后合并成档案层。

产出：`work/parts/atoms_bNNN.jsonl`、`units_bNNN.jsonl`、`work/reports/bNNN.md`（子代理）；`work/kb/{atoms,units}.jsonl`、`alias.json`、`sources.md`、`折损审计.md`（脚本）。完成 = 无 pending / in_progress / failed / interrupted 批；merge 与 audit 记录通过且输入未变；折损审计"待处置"每行有结论。

## 动作

1. `beiming.py extract`：为全部 pending 批生成提示词并标 in_progress。规则未冻结（执行提示词没有独立成行的「版本：冻结 vX.Y」）、或缺 `work/docs/加工样品.md`、或还有 `claimed_by=pilot` 未接纳的试点批 → 退出码 2、不改任何批状态（`--force` 越过并记 pipeline.md，验收报告要交代）；形态 D 的批脚本先把 work 单元骨架写进 units 文件（一文件一单元、text = 正文），子代理只补 summary / atom_ids；没有可派的批（pending 为 0）→ 退出码 1 并说明其余批各是什么状态。它打印每个批号。
2. 派子代理，一份提示词一个。宿主能并发就并发（并发数按宿主上限）；不能并发就先告知使用者将串行处理再开始。设了 `BEIMING_AGENT` 的，脚本自己并发跑。
3. 全部返回后 `beiming.py settle`。原子文件与批次报告都还不存在的 in_progress 批算"未返回"：状态不改、退出码 1、不是失败，等它写完再 settle，不要 `--regenerate` 重派（会有两个子代理写同一批）。done / failed 各多少一眼可见；failed 的 note 写了原因（引文未命中、字段缺或枚举外、id 格式错、原子↔单元互指不在本批、空文件、缺批次报告）。
4. failed 的处理：引文未命中 → 让原子代理按 note 修（或 `extract --batches bNNN --regenerate` 重派）；空文件 / 未写 → 重派；连续两次同批失败 → 你自己读该批的阅读版看是不是语料本身有问题（乱码、二手笔记），是则 `beiming.py exclude bNNN --reason "<问题>"`（不手改 batches.json）。
5. 抽样质检（不是可选）：`beiming.py read all --sample`。每批看 2 条 + 风险文件 1 条，对照下面"抽样看什么"。发现系统性问题（不是个别条）→ 这是规则问题，回 S2 升版本，受影响批 `reset bNNN` 后重抽（done 的批也能 reset；recover 只管 interrupted）。
6. `beiming.py merge`：只合并 done 且已接纳的批（试点批要先 `settle --pilot --accept`）；精确去重写 alias.json；有悬空引用退出码 1，先修。
7. `beiming.py audit`：低于 30% 覆盖的文件列在"待处置"，你逐行填：合理排除（闲聊、重复课）/ 纯观点（无可执行判断）/ 缺完整体（该做单元没做，回该批补）/ 疑漏读（该批 `reset` 后重抽）。全填完 S3 才算完。
8. 在 `work/pipeline.md` 追加一行。

## 规则

- 分配在先、各写各的、集中销账：批次只由 extract 分配，子代理只写自己批的三个文件（原子、单元、批次报告），状态只由 settle / stop / recover / reset / exclude 改。任何人不手改 batches.json 的 status。
- 子代理的回复不是产物；settle 只认文件。settle 的校验是"检出即拒"而不是"没检出即过"：枚举外的值、超长 original、假 id、指向别批的互指，都算 failed。
- failed 不算完成；interrupted 的产物不可信：`recover` 把旧产物改名 `.stale-<时间>`（留证据）并给批打 `needs_reextract`，没重新 `extract` 之前 `settle` 不核这批——这条由脚本保证，不靠纪律。done 的批要返工用 `reset`（退回 pending，旧产物同样改名 .stale，note 记原状态），不删文件不手改。
- 形态 D 的 work 单元 text 以脚本从文件生成的为准：settle 把模型改动的按文件覆盖、漏掉的补回，记在 note，不判失败——整篇逐字抄是机械活，不交给模型。
- 标题只在文件名里的原子（flags 含 `title`）按文件名标题核逐字，不按正文核；其余原子仍按正文核。
- 抽样看什么：主张脱离上下文能懂吗；role 对吗（学员提问被抽成主张是最常见的错）；claim_scope 把举例当无条件主张了吗；数字有没有变形；最长文件的中段有原子吗；该成单元的（完整案例、作者的稿）是不是被拆碎了。
- 精确去重只做归一化后完全相同的 knowledge；语义重复留给 S5 的模型做，因为脚本分不清"同义"与"条件不同"。
- 覆盖率证明的是"原文有多少逐字进了档案"，不是质量；低覆盖不一定错，但必须有处置结论。
- 试产不并入：任何"试试这个模型行不行"的产物不进 parts，另放 `work/tmp/`。

## 依据

外层：Map-Reduce 式的"分配在先、各写各的、集中归并"——用预分配代替锁；可复现性——每条引文能回到原文，是唯一机械的保真手段。

内层（可观察）：
1. 全部批 done 或 excluded，failed 为 0。
2. settle 的引文命中 100%（原子 original 与单元 text）。
3. merge 悬空引用 0；折损审计的低覆盖文件全部有处置。

为什么这样定：
- 集中销账：多个写者改同一份状态文件必然互相覆盖；子代理只写自己的三个文件，状态只由 settle 改。
- settle 只认文件：子代理的回复是自述，文件才是产物。
- 抽样必做：引文命中只证明"原话是真的"，证明不了"归属对、判断对"——学员的话被抽成作者主张，命中率照样 100%。
- 低覆盖要处置：覆盖率低的文件要么该排除，要么被漏读；不处置就永久缺失。

实测参照（上一版记录）：并发子代理各自改状态文件出现过写冲突，改为子代理只写自己的产出、集中销账后消失；用 jq 统计中文字段曾把讲者占比完全报错（多字节排序），改 Python 统计后才对。

## 模板

`work/reports/bNNN.md` 由子代理按 extract 提示词写；你在 pipeline.md 追加的一行：

```
- <时间> | S3 | extract N 批 / settle done X failed Y / merge 原子 A 单元 U 悬空 0 / audit 覆盖 P% 低覆盖 L 已处置 | 门槛：通过 | 备注：bNNN excluded（乱码）
```

## 常见失误

- 全量后改规则不升版本、不重抽：档案里同一字段两种口径，S5 折叠时把不同条件的主张合成一条。
- 用 jq 之类工具在命令行里改或统计 JSONL：中文与转义容易坏行，jq 的 `sort|uniq` 对中文有多字节排序问题会报出完全错误的分布（上一版实测曾据此误判讲者占比）；一律用 `read --sample` 或 Python 统计。
- 早松晚紧：前几批规则还松、打补丁后偏紧，全局平均正常但两头偏。merge 后抽首尾各一批对照；接受则在验收报告注明。
- merge 时把 failed 批也合进去："反正大部分是对的"——一条改写过的引文进了道层，整条道失真。
- 只看覆盖率不抽读：覆盖高但 role 全错的批照样能过机械核验。
- 抽样发现问题只修那几条：系统性问题要回规则，不然其余批里同样的错还在。
