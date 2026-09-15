# -*- coding: utf-8 -*-
"""母技能开发检查（维护者用，接收方不需要跑）：检查 amb-paoding 自身是否自包含、可发布。
用法：python3 selfcheck.py [--corpus <作品目录>] [--skill <目录>]
检查项：
  1 死链       .md 里的相对链接都指向存在的文件
  2 外部路径   无本机绝对路径、无 workspace/ 引用（"<项目>-paoding/" 这种工程目录写法豁免）
  3 禁词       无中文技能名、无客户 / 工程代号、无过程角色词
  4 语料泄漏   --corpus 给定时，references/assets 的 .md 里不出现语料的 30 字连续片段（抽样）
  5 槽位契约   assets/prompts/*.md 的每个 ${槽位} 至少有一个脚本填它，且脚本里出现该槽位名
  6 节序       references/01–06 按 目标与产出 → 动作 → 规则 → 依据 → 常见失误 排
  7 编译       scripts/*.py 与 assets/fact_check.py 都能编译
  8 体积       总字节与各文件行数；SKILL.md > 300 行、总量 > 250KB 提醒（不算失败）
退出码：1–7 任一失败为 1。"""
import os, sys, re, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

# 公开文件里不出现：中文技能名（只对人用）、上一版与同仓技能的中文名、客户与工程代号、过程角色词、本机路径
BANNED = [r"庖丁", r"北冥", r"南冥", r"mubaiskill", r"董十一", r"安先生", r"马大个", r"vikki", r"陈幸", r"王义", r"陈晶", r"鹤老师", r"老周",
          r"[首二三四]炉", r"第[一二三四]炉", r"主代理", r"主会话", r"总控", r"(?<![\w-])workspace/", r"/Users/", r"/home/", r"[A-Za-z]:\\\\"]
SECTIONS = ["目标与产出", "动作", "规则", "依据", "常见失误"]

def main():
    pos, o, f = C.parse_args(sys.argv[1:], opts=("--corpus", "--skill"), usage="用法：selfcheck.py [--corpus 作品目录] [--skill 目录]")
    if pos:
        C.die("用法：selfcheck.py [--corpus 作品目录] [--skill 目录]")
    skill = os.path.abspath(o["--skill"]) if o.get("--skill") else C.SKILL_DIR; corpus = o.get("--corpus")
    fails = []; me = os.path.abspath(__file__)
    files = [p for p in glob.glob(os.path.join(skill, "**", "*"), recursive=True) if os.path.isfile(p) and "/.git/" not in p and "__pycache__" not in p]
    texts = {p: C.read_text(p) for p in files if p.endswith((".md", ".py", ".json", ".txt")) and os.path.abspath(p) != me}
    for p, t in texts.items():
        if not p.endswith(".md"):
            continue
        for link in re.findall(r"\]\(([^)\s]+)\)", t):
            if link.startswith(("http", "mailto", "#", "<")) or "<" in link or "${" in link:
                continue
            if not os.path.exists(os.path.normpath(os.path.join(os.path.dirname(p), link.split("#")[0]))):
                fails.append(f"死链 {os.path.relpath(p, skill)} → {link}")
    for p, t in texts.items():
        if "selfcheck-exempt" in "\n".join(t.splitlines()[:3]):
            continue
        for rx in BANNED:
            for m in re.finditer(rx, t):
                fails.append(f"禁词/外部路径 {os.path.relpath(p, skill)}:{t.count(chr(10), 0, m.start()) + 1} 「{m.group(0)}」")
    if corpus:
        big = ""
        for dp, dn, fn in os.walk(corpus):
            for x in fn:
                if x.lower().endswith(C.TEXT_EXT):
                    big += C.norm_ws(C.read_text(os.path.join(dp, x))) + "\n"
        for p, t in texts.items():
            if not p.endswith(".md") or "/scripts/" in p:
                continue
            n = C.norm_ws(t)
            for i in range(0, max(0, len(n) - 30), 120):
                if n[i:i + 30] in big:
                    fails.append(f"语料泄漏（抽样命中）{os.path.relpath(p, skill)} 片段「{n[i:i+30]}」"); break
        print("语料泄漏检测：抽样（每 120 字取 30 字窗口），未命中不等于全文无泄漏")
    scripts = {p: t for p, t in texts.items() if p.endswith(".py")}
    for tpl in glob.glob(os.path.join(skill, "assets", "prompts", "*.md")):
        name = os.path.basename(tpl)[:-3]; slots = set(re.findall(r"\$\{([a-z][a-z0-9_]*)\}", texts.get(tpl, C.read_text(tpl))))
        users = [p for p, t in scripts.items() if f'fill_prompt("{name}"' in t]
        if not users:
            fails.append(f"槽位 {name}.md 没有脚本填它"); continue
        for u in users:
            for s in slots:
                if f'"{s}"' not in scripts[u]:
                    fails.append(f"槽位 {name}.md 的 ${{{s}}} 在 {os.path.basename(u)} 里没赋值")
    rd = os.path.join(skill, "assets", "product-readme.md")
    if os.path.exists(rd):
        for s in set(re.findall(r"\$\{([a-z][a-z0-9_]*)\}", C.read_text(rd))):
            if s + "=" not in scripts.get(os.path.join(skill, "scripts", "deliver.py"), ""):
                fails.append(f"槽位 product-readme.md 的 ${{{s}}} deliver.py 没赋值")
    for p in sorted(glob.glob(os.path.join(skill, "references", "0[1-9]-*.md"))):
        heads = [h.strip() for h in re.findall(r"(?m)^##\s+(.+)$", C.read_text(p))]
        idx = [next((i for i, h in enumerate(heads) if h.startswith(s)), -1) for s in SECTIONS]
        if -1 in idx or idx != sorted(idx):
            fails.append(f"节序 {os.path.basename(p)}：{heads}")
    for p in glob.glob(os.path.join(skill, "scripts", "*.py")) + [os.path.join(skill, "assets", "fact_check.py")]:
        try:
            compile(C.read_text(p), p, "exec")
        except Exception as e:
            fails.append(f"编译失败 {os.path.relpath(p, skill)}：{str(e)[:120]}")
    total = sum(os.path.getsize(p) for p in files); lines = {os.path.relpath(p, skill): texts[p].count("\n") + 1 for p in texts}
    print(f"文件 {len(files)} | 总字节 {total:,}（{total/1024:.0f} KB）")
    if lines.get("SKILL.md", 0) > 300:
        print("提醒：SKILL.md", lines["SKILL.md"], "行 > 300")
    if total > 250 * 1024:
        print(f"提醒：总量 {total/1024:.0f} KB > 250 KB")
    print("最长文件：" + "，".join(f"{k} {v} 行" for k, v in sorted(lines.items(), key=lambda kv: -kv[1])[:5]))
    for x in fails:
        print("FAIL", x)
    print("---", "通过" if not fails else f"{len(fails)} 项失败")
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
