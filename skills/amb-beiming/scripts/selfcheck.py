# -*- coding: utf-8 -*-
"""母技能开发检查（维护者用，接收方不需要跑）：检查 amb-beiming 自身是否自包含、可发布。
用法：python3 selfcheck.py [--corpus <语料目录>] [--skill <目录>]
检查项：
  1 死链       .md 里的相对链接都指向存在的文件
  2 外部路径   无本机绝对路径、无 workspace/ 引用（"<项目>-workspace/" 这种工程目录写法豁免）
  3 禁词       无工程代号、无过程角色词、无虚构人名；层名不用"心法/公理"
  4 语料泄漏   --corpus 给定时，references/assets 的 .md 里不出现语料的 30 字连续片段（抽样：每 120 字取一个 30 字窗口，不是逐字全扫）
  5 槽位契约   assets/prompts/*.md 的每个 ${槽位} 至少有一个脚本填它，且填它的脚本里出现该槽位名（不核脚本多填的槽位）
  6 节序       references/01–09 按 目标与产出 → 动作 → 规则 → 依据 → 常见失误 排（模板节可选）
  7 编译       scripts/*.py 与 assets/fact_check.py 都能 py_compile
  8 体积       总字节与各文件行数；SKILL.md > 300 行、总量 > 250KB 提醒（不算失败）
退出码：1–7 任一失败为 1。"""
import os, sys, re, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

BANNED = [r"[首二三四]炉", r"第[一二三四]炉", r"两炉", r"回炉", r"先例", r"炼成", r"炼器", r"练器", r"主代理", r"主会话", r"总控", r"马大个", r"老周", r"北冥", r"mubaiskill",
          r"(?m)^#+\s*(心法|公理)", r"(心法|公理)层", r"(?<![\w-])workspace/", r"/Users/", r"/home/", r"[A-Za-z]:\\\\"]
SECTIONS = ["目标与产出", "动作", "规则", "依据", "常见失误"]

def main():
    pos, o, f = C.parse_args(sys.argv[1:], opts=("--corpus", "--skill"), usage="用法：selfcheck.py [--corpus 语料目录] [--skill 目录]")
    if pos:
        C.die("用法：selfcheck.py [--corpus 语料目录] [--skill 目录]")
    skill = os.path.abspath(o["--skill"]) if o.get("--skill") else C.SKILL_DIR
    corpus = o.get("--corpus")
    fails = []; me = os.path.abspath(__file__)
    files = [p for p in glob.glob(os.path.join(skill, "**", "*"), recursive=True) if os.path.isfile(p) and "/.git/" not in p and "__pycache__" not in p]
    texts = {p: C.read_text(p) for p in files if p.endswith((".md", ".py", ".json", ".txt")) and os.path.abspath(p) != me}
    # 1 死链
    for p, t in texts.items():
        if not p.endswith(".md"):
            continue
        for link in re.findall(r"\]\(([^)\s]+)\)", t):
            if link.startswith(("http", "mailto", "#", "<")):
                continue
            tgt = os.path.normpath(os.path.join(os.path.dirname(p), link.split("#")[0]))
            if "<" in link or ">" in link or "${" in link:
                continue
            if not os.path.exists(tgt):
                fails.append(f"死链 {os.path.relpath(p, skill)} → {link}")
    # 2+3 外部路径与禁词（文件前三行含 selfcheck-exempt 的不扫：它们本身是扫禁词的脚本）
    for p, t in texts.items():
        if "selfcheck-exempt" in "\n".join(t.splitlines()[:3]):
            continue
        for rx in BANNED:
            for m in re.finditer(rx, t):
                line = t.count("\n", 0, m.start()) + 1
                fails.append(f"禁词/外部路径 {os.path.relpath(p, skill)}:{line} 「{m.group(0)}」")
    # 4 语料泄漏
    if corpus:
        big = ""
        for dp, dn, fn in os.walk(corpus):
            for f in fn:
                if f.lower().endswith(C.TEXT_EXT):
                    big += C.norm_ws(C.read_text(os.path.join(dp, f))) + "\n"
        for p, t in texts.items():
            if not p.endswith(".md") or "/scripts/" in p:
                continue
            n = C.norm_ws(t)
            for i in range(0, max(0, len(n) - 30), 120):  # 抽样：每 120 字一个 30 字窗口
                if n[i:i + 30] in big:
                    fails.append(f"语料泄漏（抽样命中）{os.path.relpath(p, skill)} 片段「{n[i:i+30]}」"); break
        print("语料泄漏检测：抽样（每 120 字取 30 字窗口），未命中不等于全文无泄漏")
    # 5 槽位契约
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
    # 6 节序
    for p in sorted(glob.glob(os.path.join(skill, "references", "0[1-9]-*.md"))):
        heads = [h.strip() for h in re.findall(r"(?m)^##\s+(.+)$", C.read_text(p))]
        idx = [next((i for i, h in enumerate(heads) if h.startswith(s)), -1) for s in SECTIONS]
        if -1 in idx or idx != sorted(idx):
            fails.append(f"节序 {os.path.basename(p)}：{heads}")
    # 7 编译
    for p in glob.glob(os.path.join(skill, "scripts", "*.py")) + [os.path.join(skill, "assets", "fact_check.py")]:
        try:
            compile(C.read_text(p), p, "exec")
        except Exception as e:
            fails.append(f"编译失败 {os.path.relpath(p, skill)}：{str(e)[:120]}")
    # 8 体积
    total = sum(os.path.getsize(p) for p in files)
    lines = {os.path.relpath(p, skill): texts[p].count("\n") + 1 for p in texts}
    print(f"文件 {len(files)} | 总字节 {total:,}（{total/1024:.0f} KB）")
    sk = lines.get("SKILL.md", 0)
    warn = []
    if sk > 300:
        warn.append(f"SKILL.md {sk} 行 > 300")
    if total > 250 * 1024:
        warn.append(f"总量 {total/1024:.0f} KB > 250 KB 提醒线（上一版约 312 KB；瘦身优先看 scripts 与 references 里的重复）")
    big = sorted(lines.items(), key=lambda kv: -kv[1])[:5]
    print("最长文件：" + "，".join(f"{k} {v} 行" for k, v in big))
    for w in warn:
        print("提醒：", w)
    for f in fails:
        print("FAIL", f)
    print("---", f"{'通过' if not fails else str(len(fails)) + ' 项失败'}")
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
