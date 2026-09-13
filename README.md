# ambskill

把一位作者的成批语料（课程转写、访谈、作品、短分享）做成一套可溯源的 Agent 技能工具箱。

可在 Claude Code、Codex、Cursor、ZCode、Grok CLI 等能读 `SKILL.md` 的 Agent 上使用。WorkBuddy 把技能目录放到 `~/.workbuddy/skills/` 即可。

**作者**：[GitHub](https://github.com/agentmubai)

---

## 如何安装

#### Claude Code

```bash
claude plugin marketplace add agentmubai/ambskill
claude plugin install amb-beiming@ambskill
```

#### 通用安装方式（适用于 Codex / Claude Code / Cursor / ZCode / Grok）

```bash
npx -y skills add agentmubai/ambskill -g --all
```

只要 Python 3.9+ 标准库。装好后新开会话，说「用 amb-beiming 把这批语料做成技能工具箱」。

只装这一套：

```bash
npx -y skills add agentmubai/ambskill --skill amb-beiming
```

## 如何更新

#### Claude Code 插件市场安装的用户

```bash
claude plugin marketplace update ambskill
claude plugin update amb-beiming@ambskill
```

#### 通过 `npx skills add` 安装的用户

再跑一次同样的命令。

```bash
npx -y skills add agentmubai/ambskill -g --all
```

---

## 工具箱

| Skill | 做什么 |
|---|---|
| `amb-beiming` | 语料 → 路由器 + 若干任务技能。每条判断能按原子 id 回到作者原话。人只在预检、加工样品、能力方案三处出场。 |

怎么跑见 [skills/amb-beiming/README.md](skills/amb-beiming/README.md)。

本机蒸馏工程在 `workspace/`，不进 Git。干净克隆带不走客户语料和成品。

## 许可证

本仓库源码采用 [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) 许可证。

- 个人使用、学习、研究、非商业项目：不需要署名，不需要申请
- 公开发布衍生作品（文章、工具、课程等）：请注明来源
- 商业用途（把本技能当产品卖，或用它接付费代工）：需要单独授权，请联系作者

由 `amb-beiming` 生成的工具箱：语料和判断归语料作者；作者用自己的工具箱做自己的生意可以。不能把本仓库源码一并再分发。
