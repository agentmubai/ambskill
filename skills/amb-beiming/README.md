# amb-beiming

把一位作者的真实语料（课程转写、访谈、作品、短分享）蒸馏成一套技能工具箱：一个路由器 + 若干任务技能，每条判断都能按原子 id 回到作者原话。使用者带着事实来，拿走成品。

这是一个 Agent Skill：给能读 `SKILL.md`、能跑 Python、最好能派子代理的 agent 宿主用。人只需要在三处出现——看预检结论、看加工样品、确认能力方案。

## 装

整仓安装见仓库根 README。只拿这一套时，把本目录整个放进宿主的技能目录，目录名保持 `amb-beiming`。只要 Python 3.9+ 标准库。

```
<宿主技能目录>/amb-beiming/
├── SKILL.md          执行 agent 读的调度表
├── README.md         本文件（给人）
├── LICENSE
├── references/       00 总纲、01–09 各段、extraction-rules 萃取规则、product-spec 成品规约、collaboration 协作协议
├── assets/           prompts/ 12 份提示词模板；product-readme.md 成品 README 模板；marketplace.json；fact_check.py 复制进每个任务技能的事实核对
├── evals/            触发查询与门槛用例（给 skill 评测框架；不随成品分发）
└── scripts/          beiming.py 入口 + 一功能一脚本
```

## 三分钟上手

准备一个语料目录（子目录 = 组；文本文件 .txt/.md/.srt/.vtt），然后在宿主里对 agent 说：

> 用 amb-beiming 把 `<语料目录>` 做成技能工具箱，工程放 `<项目>-workspace/`。

它会先跑（当前目录可以是任何地方；每个子命令都接受 `--project <工程目录>`，在工程目录里运行时可省略）：

```
cd <你的项目目录>
python3 <本目录>/scripts/beiming.py survey --corpus <语料目录> --project <项目>-workspace
python3 <本目录>/scripts/beiming.py status --project <项目>-workspace
```

`survey` 打印语料规模、每个批次的编号与工作量区间；`status` 打印批次状态与九段的完成情况、下一步命令。之后 agent 按 SKILL.md 的调度表推进；到 S1 结论、S2 样品、S4 方案时它会停下来让你看。

想自己一步步跑，`python3 scripts/beiming.py help` 列出全部子命令，每个脚本头部有用法与"为什么有这一步"。

## 你会得到什么

`<项目>-workspace/product/<工具箱名>/`：

- `skills/<前缀>/SKILL.md` 路由器：你说一句话，它告诉你归哪个技能、要带什么。
- `skills/<前缀>-<任务>/` 任务技能：SKILL.md + references（方法论、案例卡、六层）+ scripts/fact_check.py，运行时按编号定位读取；单独拷走一个技能目录也能工作。
- `scripts/fact_check.py`：与各技能自带的同一份，放在根目录方便单独调用（开放资产，不是运行依赖）。
- `kb/`（默认附）：原子库、单元库、各任务知识包与索引，每条判断都能回到原话；增量更新的输入（开放资产，技能运行不读它）。
- `README.md`：给拿到工具箱的人，写明目录布局与安装方式。

成品自包含，把 `skills/` 下的目录拷到任何宿主的技能目录即可用；不会自动装进任何地方。

## 派发方式

默认（`BEIMING_AGENT` 未设）：脚本生成提示词，执行 agent 一份派一个子代理，并发数按宿主上限；宿主不能派子代理时它自己逐份做，先告知使用者将串行处理再开始。

也可让脚本直接并发调用外部 CLI：`BEIMING_AGENT=codex`、`BEIMING_AGENT=claude`，或只设 `BEIMING_AGENT_CMD="<命令>"`（提示词从 stdin 进，回复到 stdout，非 0 算失败；`{out}` 会替换成回复文件路径，带空格的路径按 shell 规则加引号；只设它等于 `BEIMING_AGENT=custom`）。单次调用超过 `BEIMING_AGENT_TIMEOUT`（默认 1800 秒）会被终止并记 failed，不会永久占住 worker。首次用某个 CLI 前先拿 `calibrate` 这一份提示词跑一次 `run`，验证它接受 stdin 提示词。`work/STOP` 存在时不开新任务。

## 开发验证（维护者）

改了本目录任何文件后：

```
python3 scripts/beiming.py selfcheck [--corpus <某次真实语料目录>]
```

它查死链、外部路径、禁词、语料泄漏、提示词槽位契约、01–09 节序、编译、体积。然后拿一小批真实语料走一遍 S1–S3，确认 `settle`、`merge`、`audit` 的退出码与报告仍成立；有成品时跑 `lint`。`evals/` 下是给 skill 评测框架用的触发查询与门槛用例（不随成品分发）。

没有单元测试套件：这套流水线的验证是让真实语料走一遍并检查产物。

## 已知限制

- 技能更会走作者的路，成品可用有时低于裸模型；能交的部分仍应先交可拿走的成品。
- 使用者条件和作者主张冲突时，它会跟作者的方法，不会自行换路。
- 料薄的任务仍可能单开成一个技能。

## 许可

本技能（炉子：源码、脚本、提示词）采用 CC BY-NC 4.0，见 LICENSE。个人使用、学习、研究不必申请；公开发布衍生作品请注明来源；把本技能当产品卖或用它接付费代工，须另获授权。

炼出来的箱子：语料和判断归作者；作者用自己的工具箱做自己的生意可以。不能把炉子一并再分发。
