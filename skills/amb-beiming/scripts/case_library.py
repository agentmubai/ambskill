# -*- coding: utf-8 -*-
"""案例库：从任务池的单元层逐字生成案例库全文（脚本保证逐字，模型只负责"哪个案例解释哪条判断"）。
用法：python3 case_library.py <任务id,…|all> [--project P]
输入：work/kb/pools/<任务>/units.jsonl；packs/<任务>/case_map.md（子代理写的对照表 | unit_id | 模块 | 为什么 |，可缺）。
产出：packs/<任务>/case_library_full.md（全部 case/work 单元全文）、case_library.md（对照表命中的精选，编号与全量一致）。
精选进成品的知识库附加包；全量只在工程与知识库里，不进技能运行时（整读会卡死模型）。"""
import os, sys, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

def read_map(path):
    """case_map.md → {unit_id: [(模块, 为什么), …]}。一个单元可对多个模块（分多行），全部保留，不覆盖。"""
    m = collections.OrderedDict()
    if not os.path.exists(path):
        return m
    for l in C.read_text(path).splitlines():
        cells = [c.strip().strip("`") for c in l.strip().strip("|").split("|")]
        if len(cells) >= 2 and re.fullmatch(C.UNIT_ID, cells[0]):
            m.setdefault(cells[0], []).append((cells[1], cells[2] if len(cells) > 2 else ""))
    return m

def render(u, maps, atoms_by_id=None):
    """maps = [(模块, 为什么), …]，可空。"""
    src = u.get("source", {})
    L = [f"### {u['unit_id']}　{u.get('title','')}", f"- 类型：{u.get('type')}{'（作者自己的稿）' if u.get('type')=='work' else ''}｜说话人：{u.get('speaker')}·{u.get('role')}｜来源：{src.get('group','')} / {src.get('file','')} {src.get('timestamp_start','')}–{src.get('timestamp_end','')}",
         f"- 摘要：{u.get('summary','')}", f"- 原子依据：{', '.join(u.get('atom_ids', [])) or '（无）'}"]
    for mod, why in maps or []:
        if mod and mod != "—":
            L.append(f"- 解释哪条判断：{mod}｜{why}")
    L += ["", "<details><summary>单元全文（逐字）</summary>", "", str(u.get("text", "")), "", "</details>", ""]
    return "\n".join(L)

def mapped(mapping, uid):
    """该单元是否被对照到至少一个真实模块（模块 `—` 表示放不进任何模块，不算精选）。"""
    return any(mod and mod != "—" for mod, _ in mapping.get(uid, []))

def main():
    pos, o, f = C.parse_args(sys.argv[1:], usage="用法：case_library.py <任务id,…|all> [--project P]")
    P = C.project_root(o.get("--project"))
    if len(pos) != 1:
        C.die("用法：case_library.py <任务id,…|all> [--project P]")
    T = C.tasks(P)
    for tid in C.split_names(pos[0], [t["id"] for t in T["tasks"]]):
        pool = C.W(P, "kb", "pools", tid); pack = C.W(P, "kb", "packs", tid); os.makedirs(pack, exist_ok=True)
        C.need(os.path.join(pool, "units.jsonl"), "repool")
        units = [u for u in C.read_jsonl(os.path.join(pool, "units.jsonl")) if u.get("type") in ("case", "work")]
        mapping = read_map(os.path.join(pack, "case_map.md"))
        head = f"# {tid} 案例库（case_library 生成，单元全文逐字）\n\n> 案例只用来选法和解释为什么，卡里与文里的具体事实不进使用者的稿。全文只在知识库里，技能运行时读的是 cards.md。\n\n"
        by_group = collections.defaultdict(list)
        for u in units:
            by_group[u.get("source", {}).get("group", "")].append(u)
        full = [head + f"单元 {len(units)}（work {sum(1 for u in units if u.get('type')=='work')}）\n"]
        n_sel = len([u for u in units if mapped(mapping, u["unit_id"])])
        multi = sum(1 for u in units if len([1 for m, _ in mapping.get(u["unit_id"], []) if m and m != "—"]) > 1)
        sel = [head.replace("案例库", "案例库·精选") + f"精选 {n_sel} / {len(units)}（对照表 case_map.md 命中的；一个单元对多个模块的保留全部对照）\n"]
        for g, us in sorted(by_group.items()):
            full.append(f"\n## 来源组 {g}\n"); sel.append(f"\n## 来源组 {g}\n")
            for u in us:
                r = render(u, mapping.get(u["unit_id"], [])); full.append(r)
                if mapped(mapping, u["unit_id"]):
                    sel.append(r)
        C.write_text(os.path.join(pack, "case_library_full.md"), "\n".join(full)); C.write_text(os.path.join(pack, "case_library.md"), "\n".join(sel))
        miss = [k for k in mapping if k not in {u["unit_id"] for u in units}]
        print(f"{tid}: 单元 {len(units)} | 精选 {n_sel}（对多模块 {multi}）" + (f" | 对照表里有 {len(miss)} 个 unit_id 不在池中：{miss[:5]}" if miss else "") + ("" if mapping else " | 还没有 case_map.md，精选为空（pack 子代理写完再跑一次）"))

if __name__ == "__main__":
    main()
