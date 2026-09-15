# 工作空间约定

- 本项目根目录为 `ambskill`。文件操作与命令执行默认以仓库根为工作目录。
- 本对话产生的材料、记录、代码、文档均保存在项目内；用户另行指定位置时，以用户要求为准。
- 任务按项目集中在 `workspace/<项目名>/`；不再在根目录创建 inputs、outputs、tests 或 tmp。
- 每轮回复结束前，将用户输入、最终回复及重要产出路径追加至 `workspace/仓库维护/对话记录.md`。
- 继续工作时先读本文件，再按需查阅对话记录和项目说明。

## 目录与 Git 维护

- 仅项目根维护 Git；技能子目录不建独立仓库，不使用未明确要求的子模块。
- `skills/` 只放本仓库维护、准备公开的技能源码。当前公开技能两套：`skills/amb-beiming/`（语料 → 任务技能工具箱）与 `skills/amb-paoding/`（作品 → 写作技能）。每套 `SKILL.md` 的 `name`、目录名、插件名一致。
- 客户语料、蒸馏过程、测试和成品留在 `workspace/<项目名>/`，不自动升为根 `skills/` 里的源码，也不自动装进任何宿主发现目录。
- `README.md`、`AGENTS.md`、`.gitignore`、`.claude-plugin/marketplace.json` 随仓库进入 Git。
- `workspace/` 整个目录不进 Git（`.gitignore` 里是 `/workspace/`），一个文件都不传。干净克隆里没有这个目录，用的人自己建。
- 本机缓存、虚拟环境、凭据和本地发现入口不进入 Git。
- 改 `amb-beiming` 或 `amb-paoding` 源码前，设计层先给用户看方案，机械改动直接做。改完跑对应的 selfcheck：`python3 skills/amb-beiming/scripts/beiming.py selfcheck` / `python3 skills/amb-paoding/scripts/paoding.py selfcheck`。
- 两套技能互不依赖、各自可单独安装；成品前缀不同，装进同一宿主目录不撞名。配合方式（北冥交付步骤可选读庖丁写法书、一个总路由器分「要判断 / 要成稿」）尚未实现，设计记在 `workspace/vikki/工作过程/北冥与庖丁成品对照.md`。
- 未经用户明确要求，不向根 `skills/` 或任何宿主技能目录复制、链接生成物。
