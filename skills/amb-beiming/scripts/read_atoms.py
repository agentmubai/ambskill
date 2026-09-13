# -*- coding: utf-8 -*-
"""阅读版：把一批（或一个任务池、或全库）的原子与单元渲染成人能读的 Markdown，供执行 agent 抽样质检。
用法：python3 read_atoms.py <b001 | task:<任务id> | all> [--sample] [--project P]
  --sample  抽样模式：每批 2 条原子 + 风险文件（超长批、本组最短文件）各 1 条，外加全部单元的标题与摘要
产出：work/reports/read-<名>.md。抽样看什么见 references/03-extract.md 规则节。"""
import os, sys, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

def render_atom(a):
    return (f"### {a.get('id')}  [{a.get('type')} / {a.get('confidence')} / {a.get('claim_scope')}]  {a.get('speaker')}·{a.get('role')}\n"
            f"- **主张**：{a.get('knowledge')}\n- **原话**：{a.get('original')}\n- 来源：{a.get('source')}　topics {a.get('topics')}　skills {a.get('skills')}　flags {a.get('flags')}\n"
            + (f"- note：{a.get('note')}\n" if a.get("note") else ""))

def render_unit(u, full=False):
    s = f"### {u.get('unit_id')}  [{u.get('type')}]  {u.get('title')}\n- 摘要：{u.get('summary')}\n- 说话人：{u.get('speaker')}·{u.get('role')}　原子 {u.get('atom_ids')}\n"
    return s + (f"\n> {str(u.get('text'))[:1500]}\n" if full else "")

def main():
    pos, o, f = C.parse_args(sys.argv[1:], flags=("--sample",), usage="用法：read_atoms.py <bNNN | task:<id> | all> [--sample] [--project P]")
    sample = "--sample" in f; P = C.project_root(o.get("--project"))
    if len(pos) != 1:
        C.die("用法：read_atoms.py <bNNN | task:<id> | all> [--sample] [--project P]")
    target = pos[0]
    if target.startswith("b"):
        bj = C.read_json(C.W(P, "batches.json")); b = next((x for x in bj["batches"] if x["batch_id"] == target), None) or C.die("没有批次 " + target)
        atoms = [x for x in C.read_jsonl(os.path.join(P, b["atoms_out"])) if "_bad_json" not in x]; units = [x for x in C.read_jsonl(os.path.join(P, b["units_out"])) if "_bad_json" not in x]
        groups = {target: (b, atoms, units)}
    elif target.startswith("task:"):
        tid = target[5:]; d = C.W(P, "kb", "pools", tid); C.need(os.path.join(d, "atoms.jsonl"), "repool")
        groups = {tid: (None, C.read_jsonl(os.path.join(d, "atoms.jsonl")), C.read_jsonl(os.path.join(d, "units.jsonl")))}
    else:
        bj = C.read_json(C.W(P, "batches.json")); groups = {}
        for b in bj["batches"]:
            if b["status"] == "done":
                groups[b["batch_id"]] = (b, [x for x in C.read_jsonl(os.path.join(P, b["atoms_out"])) if "_bad_json" not in x], [x for x in C.read_jsonl(os.path.join(P, b["units_out"])) if "_bad_json" not in x])
    L = [f"# 阅读版：{target}" + ("（抽样）" if sample else ""), ""]
    for name, (b, atoms, units) in groups.items():
        L.append(f"## {name}  原子 {len(atoms)} 单元 {len(units)}" + (f"  形态 {b['form']}{' 超长批' if b.get('oversized') else ''}" if b else ""))
        pick = atoms
        if sample and atoms:
            random.seed(name); pick = random.sample(atoms, min(2, len(atoms)))
            if b:
                nos = sorted(b["file_nos"].items(), key=lambda kv: kv[1]); risk = [f"c{b['group_id'][1:]}_{nos[0][1]}_"] if b.get("oversized") else []
                shortest = min(b["files"], key=lambda f: len(C.read_text(os.path.join(b["source_dir"], f))))
                risk.append(f"c{b['group_id'][1:]}_{b['file_nos'][shortest]}_")
                for pre in risk:
                    c = [x for x in atoms if x["id"].startswith(pre) and x not in pick]
                    if c:
                        pick.append(c[0])
        L += [render_atom(x) for x in pick]
        L += [render_unit(u, full=not sample) for u in units]
    out = C.W(P, "reports", f"read-{target.replace(':', '-')}.md"); C.write_text(out, "\n".join(L))
    print("阅读版：", os.path.relpath(out, P), f"（{sum(len(g[1]) for g in groups.values())} 原子 / {sum(len(g[2]) for g in groups.values())} 单元）")

if __name__ == "__main__":
    main()
