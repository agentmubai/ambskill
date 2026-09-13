# -*- coding: utf-8 -*-
"""S4 重建任务池：按使用者确认后的 work/tasks.json，把原子与单元重新分到 work/kb/pools/<任务>/{atoms,units}.jsonl。
用法：python3 repool.py [--project P]
映射规则（tasks.json 每个任务的 match 字段）：原子命中 skills ∩ match.skills、或 topics ∩ match.topics、或来源组 ∈ match.groups 即归入；
命中多个任务时按 tasks 顺序取第一个为主池，其余记为副本引用；单元跟随其原子的多数任务；无处归的列报告。
S5 的输入门槛是"该任务池已建"。产出：pools/、work/docs/S4重建任务池报告.md。"""
import os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C, check_layers as CK

def main():
    pos, o, f = C.parse_args(sys.argv[1:], usage="用法：repool.py [--project P]")
    if pos:
        C.die(f"多余的参数 {pos}；用法：repool.py [--project P]")
    P = C.project_root(o.get("--project"))
    T = C.tasks(P); C.need(C.W(P, "kb", "atoms.jsonl"), "merge")
    if not T.get("confirmed_at"):
        C.die("tasks.json 缺 confirmed_at：能力方案须经使用者确认后再 repool（把确认时间写进 tasks.json）")
    empty = [f"{t['id']}.{k}" for t in T["tasks"] for k in ("input", "judge", "deliver") if not str(t.get(k, "")).strip()]
    if empty:
        C.die("tasks.json 每个任务的 input / judge / deliver 三格都要非空（04-plan.md 内层 1）：缺 " + "、".join(empty))
    plan = C.W(P, "docs", "能力方案.md")
    if os.path.exists(plan):
        bad = CK.check_inline(P, plan)
        if bad:
            print("能力方案.md 里给使用者看的作者原话有不逐字 / id 不符的：")
            for q, why in bad[:10]:
                print(f"  - {q[:50]} ← {why}")
            C.die(f"共 {len(bad)} 条。这是第三个参与点使用者亲眼看的引文，先改成逐字原话并标对原子 id，再 repool", code=1)
    atoms = C.read_jsonl(C.W(P, "kb", "atoms.jsonl")); units = C.read_jsonl(C.W(P, "kb", "units.jsonl"))
    def hits(a):
        out = []
        for t in T["tasks"]:
            m = t.get("match", {})
            if (set(a.get("skills") or []) & set(m.get("skills", []))) or (set(a.get("topics") or []) & set(m.get("topics", []))) or ("g" + a["id"][1:3] in m.get("groups", [])):
                out.append(t["id"])
        return out
    pools = {t["id"]: {"atoms": [], "units": [], "copies": 0} for t in T["tasks"]}
    unmapped_a, primary = [], {}
    for a in atoms:
        h = hits(a)
        if not h:
            unmapped_a.append(a); continue
        primary[a["id"]] = h[0]; pools[h[0]]["atoms"].append(a)
        for extra in h[1:]:
            pools[extra]["atoms"].append({**a, "_copy_of": h[0]}); pools[extra]["copies"] += 1
    unmapped_u = []
    for u in units:
        c = collections.Counter(primary.get(i) for i in u.get("atom_ids", []) if primary.get(i))
        if c:
            pools[c.most_common(1)[0][0]]["units"].append(u)
        else:
            unmapped_u.append(u)
    for tid, p in pools.items():
        d = C.W(P, "kb", "pools", tid); os.makedirs(d, exist_ok=True)
        C.write_jsonl(os.path.join(d, "atoms.jsonl"), p["atoms"]); C.write_jsonl(os.path.join(d, "units.jsonl"), p["units"])
    L = ["# S4 重建任务池报告（repool 生成）", "", f"任务 {len(T['tasks'])} | 原子 {len(atoms)} | 单元 {len(units)} | 无处归原子 {len(unmapped_a)} | 无处归单元 {len(unmapped_u)}", "",
         "| 任务 | 名称 | 原子（含副本） | 副本 | 单元 | high | method+tool |", "|---|---|---|---|---|---|---|"]
    for t in T["tasks"]:
        p = pools[t["id"]]
        L.append(f"| {t['id']} | {t.get('name','')} | {len(p['atoms'])} | {p['copies']} | {len(p['units'])} | {sum(1 for a in p['atoms'] if a.get('confidence')=='high')} | {sum(1 for a in p['atoms'] if a.get('type') in ('method','tool'))} |")
    thin = [t["id"] for t in T["tasks"] if len(pools[t["id"]]["atoms"]) < 80]
    if thin:
        L += ["", f"池薄（< 80 条）的任务：{', '.join(thin)} —— 回能力方案并入邻居或补类目（参考值，不是硬线）"]
    dpool = [t["id"] for t in T["tasks"] if pools[t["id"]]["atoms"] and sum(1 for a in pools[t["id"]]["atoms"] if a.get("role") == "作品") / len(pools[t["id"]]["atoms"]) > 0.5]
    if dpool:
        L += ["", f"以作品层原子为主的任务：{', '.join(dpool)} —— 支撑看 method+tool 列，不看 high 列（作品层自述不自动 high，见 extraction-rules 第 4 节）"]
    if unmapped_a:
        L += ["", "## 无处归原子（前 60；先按 skills/topics 归到某任务的 match 或补任务，再重跑 repool）", ""]
        L += [f"- {a['id']} skills={a.get('skills')} topics={a.get('topics')} ｜ {a.get('knowledge','')[:60]}" for a in unmapped_a[:60]]
    if unmapped_u:
        L += ["", "## 无处归单元（前 30）", ""] + [f"- {u['unit_id']} [{u.get('type')}] {u.get('title','')[:50]}" for u in unmapped_u[:30]]
    out = C.W(P, "docs", "S4重建任务池报告.md"); C.write_text(out, "\n".join(L) + "\n")
    C.record_stage(P, "repool", [C.W(P, "tasks.json"), C.W(P, "kb", "atoms.jsonl")], ok=not unmapped_a, extra={"unmapped_atoms": len(unmapped_a), "unmapped_units": len(unmapped_u)})
    print(f"任务池 {len(pools)} 个已建 | 无处归原子 {len(unmapped_a)} 单元 {len(unmapped_u)} → {os.path.relpath(out, P)}")
    C.pipeline_log(P, "S4", f"repool：{len(pools)} 池，无处归原子 {len(unmapped_a)}")
    sys.exit(1 if unmapped_a else 0)

if __name__ == "__main__":
    main()
