# -*- coding: utf-8 -*-
"""六层逐字核对（S5 门槛）：layers.md 里 道 / 术 / 势 三节的每条「原话」必须在原子库 original 里逐字存在（忽略空白），
并且标了原子 id 的，原话必须属于那条 id（"原话曾存在"与"出处 id 正确"是两回事）。
也可直接核一份 SKILL.md（术多半折在 Phase 里：按他说的「……」（原子 id））。
任务模式下还核 packs/<任务>/cards.md：卡里带引号并标 unit_id 的句子必须是该单元 text 的逐字子串。
check_inline(P, path) 供 repool 核能力方案里给使用者看的原话（「……」（原子 id）），不落 layers_input。
用法：python3 check_layers.py <任务id,…|all> [--file <路径>] [--project P]
识别的原话写法：「> 引用块」「原话：…」、表格中表头含「原话」的列、行内「…」后跟原子 id。带〔槽位〕的句子是成品句式，不核。
产出：work/kb/layers_input/<任务>/mismatch.md；退出码 1 = 有不符或六层未完成（道 / 术 为 0 条不算通过），不许进 S6。
为什么要有这一步：归层的价值全在逐字；模型归层时会把原话改写成通顺句，不核对就全进技能了。"""
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

USAGE = "用法：check_layers.py <任务id,…|all> [--file 路径] [--project P]"

def quotes(sec):
    """返回 [(原话, 原子id或None)]。"""
    out, lines = [], sec.splitlines()
    for i, l in enumerate(lines):
        ids = re.findall(C.ATOM_ID, l)
        if l.startswith("> ") and len(l) > 10:
            q = re.sub(r"\s*[（(]\s*" + C.ATOM_ID + r"\s*[)）]\s*$", "", l[2:].strip()).strip("「」“”")
            out.append((q, ids[-1] if ids else None))
        m = re.match(r"[-*\s\d.]*\**原话\**[^：:]{0,8}[：:]\s*(.{8,})", l)
        if m:
            q = re.sub(r"\s*[（(]\s*" + C.ATOM_ID + r"\s*[)）]\s*$", "", m.group(1).strip()).strip("「」“”")
            out.append((q, ids[-1] if ids else None))
        if l.startswith("|") and ids:
            cells = [c.strip() for c in l.strip().strip("|").split("|")]
            hdr = next(([c.strip() for c in lines[k].strip().strip("|").split("|")] for k in range(i - 1, max(-1, i - 12), -1) if lines[k].startswith("|") and "原话" in lines[k]), None)
            if hdr:
                col = next((j for j, h in enumerate(hdr) if "原话" in h), None)
                if col is not None and col < len(cells) and len(cells[col]) >= 8:
                    out.append((cells[col].strip("「」“”"), ids[0]))
    for m in re.finditer(r"「([^」]{8,})」[^「\n]{0,40}?(" + C.ATOM_ID + ")", sec):
        out.append((m.group(1), m.group(2)))
    out = [(q, i) for q, i in out if "〔" not in q and "〕" not in q]
    seen, uniq = set(), []
    for q, i in out:
        if (q, i) not in seen:
            seen.add((q, i)); uniq.append((q, i))
    return uniq

def unit_quotes(text):
    """卡里的引文：「…」后 40 字内跟 unit id，或 > 引用块末尾带 unit id。返回 [(原话, unit_id)]。"""
    out = []
    for m in re.finditer(r"「([^」]{8,})」[^「\n]{0,40}?(" + C.UNIT_ID + ")", text):
        out.append((m.group(1), m.group(2)))
    for l in text.splitlines():
        if l.startswith("> ") and re.search(C.UNIT_ID, l):
            q = re.sub(r"\s*[（(]\s*" + C.UNIT_ID + r"\s*[)）]\s*$", "", l[2:].strip()).strip("「」“”")
            out.append((q, re.findall(C.UNIT_ID, l)[-1]))
    return [(q, i) for q, i in dict.fromkeys(out) if "〔" not in q]

def check_cards(P, tid):
    """核 packs/<任务>/cards.md 里标 unit_id 的引文。返回 (条数, 不符列表[(原话, why)])；没有 cards.md 返回 (0, [])。"""
    path = C.W(P, "kb", "packs", tid, "cards.md")
    if not os.path.exists(path):
        return 0, []
    units = {u["unit_id"]: C.norm_ws(u.get("text")) for f in (C.W(P, "kb", "pools", tid, "units.jsonl"), C.W(P, "kb", "units.jsonl")) if os.path.exists(f)
             for u in C.read_jsonl(f) if "_bad_json" not in u}
    qs = unit_quotes(C.read_text(path)); bad = []
    for q, i in qs:
        if i not in units:
            bad.append((q, f"单元 id {i} 不在单元库里"))
        elif C.norm_ws(q) not in units[i]:
            bad.append((q, f"不是单元 {i} text 的逐字子串（被改写）"))
    return len(qs), bad

def check_inline(P, path):
    """核一份任意 markdown 里「……」（原子 id）/ > 引用块 的原话，按全库原子 original 逐字 + id 绑定。返回 [(原话, why)]。"""
    full = C.W(P, "kb", "atoms.jsonl"); alias = C.load_alias(P)
    by = {x["id"]: C.norm_ws(x.get("original")) for x in C.read_jsonl(full) if "_bad_json" not in x}
    bad = []
    for q, i in quotes(C.read_text(path)):
        nq = C.norm_ws(q)
        if not i:
            if nq not in "\n".join(by.values()):
                bad.append((q, "原子库里找不到逐字对应，且没标原子 id"))
            continue
        rid = C.resolve_id(alias, i)
        if rid not in by:
            bad.append((q, f"原子 id {i} 不在原子库里"))
        elif nq not in by[rid]:
            bad.append((q, f"原话不属于所标 id {i}"))
    return bad

def check(P, tid, path, require_layers=True, out_name="mismatch.md"):
    """返回 (不符条数, 未完成说明列表)。require_layers=False 时只核引文（lint 核 SKILL.md 用）。"""
    pool = C.W(P, "kb", "pools", tid, "atoms.jsonl"); full = C.W(P, "kb", "atoms.jsonl"); alias = C.load_alias(P)
    pool_rows = [x for x in C.read_jsonl(pool) if "_bad_json" not in x] if os.path.exists(pool) else []
    full_rows = [x for x in C.read_jsonl(full) if "_bad_json" not in x] if os.path.exists(full) else pool_rows
    pool_by = {x["id"]: C.norm_ws(x.get("original")) for x in pool_rows}; full_by = {x["id"]: C.norm_ws(x.get("original")) for x in full_rows}
    allpool = "\n".join(pool_by.values()); allfull = "\n".join(full_by.values()) or allpool
    s = C.read_text(path); secs = re.split(r"(?m)^##\s+", s); names = ["道", "术", "势"]
    if os.path.basename(path) == "SKILL.md":
        secs.append("全文行内引文\n" + s); names.append("全文行内引文")
    report, bad_all, total, incomplete = [], [], 0, []
    for name in names:
        sec = next((x for x in secs if re.match(r"[一二三四五六1-6]?[、.\s]*" + name, x)), "")
        qs = quotes(sec); bad = []; outside = 0
        for q, i in qs:
            nq = C.norm_ws(q)
            if i:
                rid = C.resolve_id(alias, i)
                if rid in pool_by:
                    if nq not in pool_by[rid]:
                        bad.append((q, f"原话不属于所标 id {i}（该原子的 original 里没有这句）"))
                elif rid in full_by:
                    if nq in full_by[rid]:
                        outside += 1
                    else:
                        bad.append((q, f"原话不属于所标 id {i}"))
                else:
                    bad.append((q, f"原子 id {i} 不在原子库里"))
            else:
                if nq in allpool:
                    pass
                elif nq in allfull:
                    outside += 1
                else:
                    bad.append((q, "原子库里找不到逐字对应（被改写或拼接）"))
        total += len(bad); bad_all += [(name, q, why) for q, why in bad]
        if require_layers and name in ("道", "术") and sec and not qs:
            incomplete.append(f"{name} 0 条原话：六层未完成（空节不算通过）")
        if require_layers and name in ("道", "术") and not sec:
            incomplete.append(f"缺「{name}」节")
        report.append(f"{name} {len(qs)} 条，不符 {len(bad)}" + (f"（另 {outside} 条来自本任务池外，通过但提示）" if outside else ""))
    if require_layers and not pool_rows:
        incomplete.append("任务池为空（work/kb/pools/<任务>/atoms.jsonl 无原子）")
    if require_layers:
        n_c, bad_c = check_cards(P, tid)
        if n_c or bad_c:
            total += len(bad_c); bad_all += [("案例卡", q, why) for q, why in bad_c]
            report.append(f"案例卡引文 {n_c} 条，不符 {len(bad_c)}")
    out = C.W(P, "kb", "layers_input", tid, out_name); os.makedirs(os.path.dirname(out), exist_ok=True)
    C.write_text(out, "# 以下「原话」在原子库里找不到逐字对应或不属于所标 id，必须换成逐字原话 / 改对 id 或删除\n\n"
                 + "\n".join(f"- [{n}] {q}　← {why}" for n, q, why in bad_all) + ("\n\n# 未完成\n\n" + "\n".join(f"- {x}" for x in incomplete) if incomplete else "") + "\n")
    print(f"{tid}: " + " | ".join(report) + ("" if not (total or incomplete) else f" → {os.path.relpath(out, P)}"))
    for x in incomplete:
        print(f"  未完成：{x}")
    return total, incomplete

def main():
    pos, o, fl = C.parse_args(sys.argv[1:], opts=("--file",), usage=USAGE)
    P = C.project_root(o.get("--project")); f = o.get("--file")
    if len(pos) != 1:
        C.die(USAGE)
    T = C.tasks(P); bad = 0; inc = 0
    for tid in C.split_names(pos[0], [t["id"] for t in T["tasks"]]):
        path = f or C.W(P, "kb", "packs", tid, "layers.md")
        C.need(path, f"distill {tid} --step layers 并派子代理")
        n, incomplete = check(P, tid, path, require_layers=not f); bad += n; inc += len(incomplete)
        if not f:
            C.record_stage(P, f"check_layers:{tid}", C.layers_inputs(P, tid), ok=(n == 0 and not incomplete), extra={"mismatch": n, "incomplete": incomplete})
    sys.exit(1 if (bad or inc) else 0)

if __name__ == "__main__":
    main()
