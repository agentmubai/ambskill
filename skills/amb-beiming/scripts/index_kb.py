# -*- coding: utf-8 -*-
"""知识库索引：汇总每个任务的方法模块与案例卡 → work/kb/index.md。S6 写技能、S7 评委核"原法忠实"、S9 覆盖对照都从它进。
用法：python3 index_kb.py [--project P]
读 packs/<任务>/methods.md 的模块标题（M01…）、cards.md 的卡（unit_id + 首行）、layers.md 的道条数。"""
import os, sys, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

def modules(path):
    out = []
    if not os.path.exists(path):
        return out
    for l in C.read_text(path).splitlines():
        m = re.match(r"#{2,4}\s*(M\d{1,3})\b[：:\s]*(.*)", l)
        if m:
            out.append((m.group(1), m.group(2).strip()))
    return out

def cards(path):
    out = []
    if not os.path.exists(path):
        return out
    for l in C.read_text(path).splitlines():
        m = re.match(r"#{2,4}\s*(" + C.UNIT_ID + r")\b[：:\s|｜]*(.*)", l)
        if m:
            out.append((m.group(1), m.group(2).strip()))
    return out

def main():
    pos, o, f = C.parse_args(sys.argv[1:], usage="用法：index_kb.py [--project P]")
    if pos:
        C.die(f"多余的参数 {pos}；用法：index_kb.py [--project P]")
    P = C.project_root(o.get("--project"))
    T = C.tasks(P); L = ["# 知识库索引（index_kb 生成）", "", "| 任务 | 名称 | 方法模块 | 案例卡 | 道 | 池原子 |", "|---|---|---|---|---|---|"]
    body, inputs, problems = [], [], []
    for t in T["tasks"]:
        pack = C.W(P, "kb", "packs", t["id"]); ms = modules(os.path.join(pack, "methods.md")); cs = cards(os.path.join(pack, "cards.md"))
        lay = os.path.join(pack, "layers.md"); dao = len(re.findall(r"(?m)^###\s", re.split(r"(?m)^##\s+", C.read_text(lay))[1] if os.path.exists(lay) and len(re.split(r"(?m)^##\s+", C.read_text(lay))) > 1 else ""))
        pool = C.W(P, "kb", "pools", t["id"], "atoms.jsonl"); n = len(C.read_jsonl(pool)) if os.path.exists(pool) else 0
        inputs += [os.path.join(pack, f) for f in ("methods.md", "cards.md", "layers.md")]
        cl = C.stage_state(P, f"check_layers:{t['id']}", [lay, pool])
        for cond, msg in ((not ms, "methods.md 没有 M 编号模块"), (not cs, "cards.md 没有案例卡"), (dao == 0, "layers.md 道为 0 条"), (n == 0, "任务池为空"), (cl != "ok", f"check-layers 记录 {cl}")):
            if cond:
                problems.append(f"{t['id']}: {msg}")
        L.append(f"| {t['id']} | {t.get('name','')} | {len(ms)} | {len(cs)} | {dao} | {n} |")
        body += [f"\n## {t['id']} {t.get('name','')}", "", f"知识包：`packs/{t['id']}/`（相对本索引所在的 kb 目录；含 methods.md / case_map.md / case_library.md / layers.md / cards.md）", "", "### 方法模块", ""]
        body += [f"- {m} {title}" for m, title in ms] or ["- （methods.md 还没有 M 编号模块）"]
        body += ["", "### 案例卡", ""] + ([f"- {u} {title}" for u, title in cs] or ["- （cards.md 未生成）"])
    C.write_text(C.W(P, "kb", "index.md"), "\n".join(L + body) + "\n")
    C.record_stage(P, "index", inputs, ok=not problems, extra={"problems": problems})
    print("索引：work/kb/index.md", f"（{len(T['tasks'])} 任务）")
    for p in problems:
        print("未完成：", p)
    C.pipeline_log(P, "S5", "index：知识库索引已生成" + (f"；未完成 {len(problems)} 项" if problems else ""))
    if problems:
        print("索引已写，但 S5 不算完成（空知识包 / 空六层 / 核对未过不算通过）")
        sys.exit(1)

if __name__ == "__main__":
    main()
