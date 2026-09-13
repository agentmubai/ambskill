# -*- coding: utf-8 -*-
"""合并：把 status=done 的批次产物合成 work/kb/atoms.jsonl、units.jsonl；精确去重写 alias.json；无悬空校验；来源索引。
用法：python3 merge.py [--project P]
只合并 done 的批（failed / interrupted / pending 不进库）。精确去重 = 归一化 knowledge 相同 → 保留 confidence 高、original 长的那条，
被删 id 记进 alias.json（旧 id → 保留 id），下游按别名解析。语义重复留到 S5 由模型折叠。
产出：work/kb/{atoms.jsonl, units.jsonl, alias.json, sources.md}；meta 记 merge 阶段。"""
import os, sys, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

CONF = {"high": 3, "medium": 2, "low": 1}

def main():
    pos, o, f = C.parse_args(sys.argv[1:], usage="用法：merge.py [--project P]")
    if pos:
        C.die(f"多余的参数 {pos}；用法：merge.py [--project P]")
    P = C.project_root(o.get("--project"))
    bp = C.W(P, "batches.json"); C.need(bp, "S1 survey")
    bj = C.read_json(bp)
    done = [b for b in bj["batches"] if b["status"] == "done" and b.get("claimed_by") != "pilot"]
    unacc = [b["batch_id"] for b in bj["batches"] if b["status"] == "done" and b.get("claimed_by") == "pilot"]
    if unacc:
        print(f"提示：试点批 {unacc} 已 done 但未 `settle --pilot --accept`，不进库")
    if not done:
        C.die("没有可合并的 done 批次。先 settle（试点批要先 settle --pilot --accept）")
    atoms, units, inputs = [], [], []
    for b in done:
        ap, up = os.path.join(P, b["atoms_out"]), os.path.join(P, b["units_out"])
        inputs += [ap, up]
        atoms += [a for a in C.read_jsonl(ap) if "_bad_json" not in a]
        units += [u for u in C.read_jsonl(up) if "_bad_json" not in u]
    # 精确去重
    alias = C.load_alias(P); keep = {}; order = []
    for a in sorted(atoms, key=lambda x: x["id"]):
        key = re.sub(r"[\s，。、；：！？,.;:!?\"'“”‘’]", "", a.get("knowledge", ""))
        if key in keep:
            k = keep[key]
            better = (CONF.get(a.get("confidence"), 0), len(a.get("original", ""))) > (CONF.get(k.get("confidence"), 0), len(k.get("original", "")))
            if better:
                alias[k["id"]] = a["id"]; keep[key] = a; order[order.index(k["id"])] = a["id"]
            else:
                alias[a["id"]] = k["id"]
        else:
            keep[key] = a; order.append(a["id"])
    byid = {a["id"]: a for a in keep.values()}
    merged = [byid[i] for i in order]
    # 无悬空校验
    ids = set(byid); uids = {u["unit_id"] for u in units}; dangling = []
    for u in units:
        u["atom_ids"] = [C.resolve_id(alias, i) for i in u.get("atom_ids", [])]
        dangling += [f"{u['unit_id']} → {i}" for i in u["atom_ids"] if i not in ids]
    for a in merged:
        if a.get("unit_id") and a["unit_id"] not in uids:
            dangling.append(f"{a['id']} → {a['unit_id']}")
    C.write_jsonl(C.W(P, "kb", "atoms.jsonl"), merged)
    C.write_jsonl(C.W(P, "kb", "units.jsonl"), sorted(units, key=lambda u: u["unit_id"]))
    C.write_json(C.W(P, "kb", "alias.json"), alias)
    # 来源索引
    cat = C.load_catalog(P) or {"groups": []}
    per_g = collections.Counter(a["id"][1:3] for a in merged); per_gu = collections.Counter(u["unit_id"][1:3] for u in units)
    spk = collections.Counter((a.get("speaker", "未知"), a.get("role", "未知")) for a in merged)
    L = ["# 来源索引（merge 生成）", "", f"原子 {len(merged)}（去重前 {len(atoms)}，别名 {len(alias)}）| 单元 {len(units)} | 悬空引用 {len(dangling)}", "",
         "| 组 | 名称 | 形态 | 文件 | 原子 | 单元 |", "|---|---|---|---|---|---|"]
    for g in cat["groups"]:
        L.append(f"| {g['group_id']} | {g['name'][:40]} | {g['form']} | {g['n_files']} | {per_g.get(g['group_id'][1:], 0)} | {per_gu.get(g['group_id'][1:], 0)} |")
    L += ["", "## 说话人 × 角色（前 30）", "", "| 说话人 | 角色 | 原子 |", "|---|---|---|"] + [f"| {s} | {r} | {n} |" for (s, r), n in spk.most_common(30)]
    tp = collections.Counter(a.get("type") for a in merged); cf = collections.Counter(a.get("confidence") for a in merged)
    L += ["", "## 分布", "", "type：" + "，".join(f"{k} {v}" for k, v in tp.most_common()), "", "confidence：" + "，".join(f"{k} {v}" for k, v in cf.most_common()),
          "", "单元 type：" + "，".join(f"{k} {v}" for k, v in collections.Counter(u.get('type') for u in units).most_common())]
    if dangling:
        L += ["", "## 悬空引用（必须处理）", ""] + [f"- {d}" for d in dangling[:100]]
    C.write_text(C.W(P, "kb", "sources.md"), "\n".join(L) + "\n")
    C.record_stage(P, "merge", inputs, ok=not dangling, extra={"atoms": len(merged), "units": len(units), "alias": len(alias), "dangling": len(dangling)})
    print(f"原子 {len(merged)}（去重前 {len(atoms)}）| 单元 {len(units)} | 别名 {len(alias)} | 悬空 {len(dangling)}")
    print("high 占比 %.0f%%" % (100 * cf.get("high", 0) / max(1, len(merged))), "—— 偏高是通病，验收报告注明即可，不用规则降级")
    C.pipeline_log(P, "S3", f"merge：原子 {len(merged)} 单元 {len(units)} 悬空 {len(dangling)}")
    sys.exit(1 if dangling else 0)

if __name__ == "__main__":
    main()
