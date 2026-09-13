# -*- coding: utf-8 -*-
"""S4 数据表与拆合提示词：按原子真实分布出数据表，再生成能力方案的派发提示词。
用法：python3 plan.py [--project P]
产出：work/docs/S4数据表.md（topics / skills 标签 / type / role / confidence / 来源组 分布，skills×topics 交叉，单元按标签）、
      work/prompts/plan.md（执行 agent 自己写能力方案也读它）。
任务列表由数据 + 使用者任务清单决定，不预置；确认后写 work/tasks.json（schema 见 references/04-plan.md 模板节），再 repool。"""
import os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

def main():
    pos, o, f = C.parse_args(sys.argv[1:], usage="用法：plan.py [--project P]")
    if pos:
        C.die(f"多余的参数 {pos}；用法：plan.py [--project P]")
    P = C.project_root(o.get("--project"))
    C.stop_guard(P)
    C.need(C.W(P, "kb", "atoms.jsonl"), "merge")
    atoms = C.read_jsonl(C.W(P, "kb", "atoms.jsonl")); units = C.read_jsonl(C.W(P, "kb", "units.jsonl"))
    def cnt(key, multi=False):
        c = collections.Counter()
        for a in atoms:
            v = a.get(key)
            if multi:
                c.update(v or ["(空)"])
            else:
                c[v or "(空)"] += 1
        return c
    L = ["# S4 数据表（plan 生成，按原子真实分布）", "", f"原子 {len(atoms)} | 单元 {len(units)}", ""]
    def table(title, c, head):
        L.extend([f"## {title}", "", f"| {head} | 条数 | 占比 |", "|---|---|---|"] + [f"| {k} | {v} | {v/len(atoms)*100:.0f}% |" for k, v in c.most_common()] + [""])
    table("skills 标签（分池标签，不是最终任务）", cnt("skills", True), "标签")
    table("topics", cnt("topics", True), "主题")
    table("type", cnt("type"), "type"); table("role", cnt("role"), "role"); table("confidence", cnt("confidence"), "confidence"); table("claim_scope", cnt("claim_scope"), "claim_scope")
    table("来源组", collections.Counter("g" + a["id"][1:3] for a in atoms), "组")
    # 每个 skills 标签的质量画像
    L += ["## 每个 skills 标签的画像", "", "| 标签 | 原子 | 独占 | method+tool | high | case 原子 | 单元(case/work/sop/argument) | 主要来源组 |", "|---|---|---|---|---|---|---|---|"]
    tags = cnt("skills", True)
    unit_tags = collections.defaultdict(collections.Counter)
    aid2tags = {a["id"]: a.get("skills") or [] for a in atoms}
    for u in units:
        ts = collections.Counter(t for i in u.get("atom_ids", []) for t in aid2tags.get(i, []))
        if ts:
            unit_tags[ts.most_common(1)[0][0]][u.get("type")] += 1
    for t, n in tags.most_common():
        sub = [a for a in atoms if t in (a.get("skills") or [])]
        L.append(f"| {t} | {n} | {sum(1 for a in sub if len(a.get('skills') or []) == 1)} | {sum(1 for a in sub if a.get('type') in ('method', 'tool'))} | {sum(1 for a in sub if a.get('confidence') == 'high')} | {sum(1 for a in sub if a.get('type') == 'case')} | "
                 + "/".join(str(unit_tags[t].get(k, 0)) for k in ("case", "work", "sop", "argument")) + " | " + ",".join(k for k, _ in collections.Counter('g' + a['id'][1:3] for a in sub).most_common(3)) + " |")
    L += ["", "## skills × topics 交叉（前 40）", "", "| 标签 | 主题 | 条数 |", "|---|---|---|"]
    cross = collections.Counter((s, t) for a in atoms for s in (a.get("skills") or ["(空)"]) for t in (a.get("topics") or ["(空)"]))
    L += [f"| {s} | {t} | {n} |" for (s, t), n in cross.most_common(40)]
    out = C.W(P, "docs", "S4数据表.md"); C.write_text(out, "\n".join(L) + "\n")
    pre = C.W(P, "docs", "预检报告.md"); draft = C.W(P, "docs", "候选任务草案.md")
    slots = {"project": P, "skill_dir": C.SKILL_DIR, "data_table_path": os.path.relpath(out, P),
             "precheck_path": os.path.relpath(pre, P) if os.path.exists(pre) else "（缺预检报告：使用者任务清单请向使用者要）",
             "draft_path": os.path.relpath(draft, P) if os.path.exists(draft) else "（缺候选任务草案）", "plan_out": "work/docs/能力方案.md"}
    pp = C.fill_prompt("plan", slots, "plan", P)
    print("数据表：", os.path.relpath(out, P)); print("拆合提示词：", os.path.relpath(pp, P), "（派一个子代理，或你自己按它写 work/docs/能力方案.md；使用者确认后写 work/tasks.json 再 repool）")
    C.pipeline_log(P, "S4", "plan：数据表与拆合提示词已生成")

if __name__ == "__main__":
    main()
