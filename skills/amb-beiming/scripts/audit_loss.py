# -*- coding: utf-8 -*-
"""折损审计：每个来源文件被单元 text 与原子 original 覆盖的字符比例；低于阈值的文件列出来让执行 agent 逐个写处置。
用法：python3 audit_loss.py [--threshold 0.30] [--project P]
产出：work/kb/折损审计.md（表 + 待处置清单，处置列由执行 agent 填：合理排除 / 纯观点 / 缺完整体 / 疑漏读）。
覆盖率的分母是去空白后的原文字符；同一段被多条引用只算一次。"""
import os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

def main():
    pos, o, f = C.parse_args(sys.argv[1:], opts=("--threshold",), usage="用法：audit_loss.py [--threshold 0.30] [--project P]")
    if pos:
        C.die(f"多余的参数 {pos}；用法：audit_loss.py [--threshold 0.30] [--project P]")
    th = float(o.get("--threshold", "0.30")); P = C.project_root(o.get("--project"))
    cat = C.load_catalog(P); C.need(C.W(P, "kb", "atoms.jsonl"), "merge")
    atoms = C.read_jsonl(C.W(P, "kb", "atoms.jsonl")); units = C.read_jsonl(C.W(P, "kb", "units.jsonl"))
    spans = collections.defaultdict(list); texts = {}
    def add(rid, q):
        src = C.locate_source(P, cat, None, rid)
        if not src or not q:
            return
        if src not in texts:
            texts[src] = C.norm_ws(C.read_text(src))
        i = texts[src].find(q)
        if i >= 0:
            spans[src].append((i, i + len(q)))
    for u in units:
        add(u.get("unit_id"), C.norm_ws(u.get("text")))
    for x in atoms:
        add(x.get("id"), C.norm_ws(x.get("original")))
    rows = []
    for g in cat["groups"]:
        for f in g["files"]:
            src = os.path.join(g["source_dir"], f["file"])
            if src not in texts:
                texts[src] = C.norm_ws(C.read_text(src)) if os.path.isfile(src) else ""
            L = len(texts[src]) or 1
            cov = 0; last = -1
            for s, e in sorted(spans.get(src, [])):
                s = max(s, last)
                if e > s:
                    cov += e - s; last = e
            rows.append((g["group_id"], f["no"], f["file"], L, cov / L, sum(1 for x in atoms if x["id"].startswith(f"c{g['group_id'][1:]}_{f['no']}_")), sum(1 for u in units if u["unit_id"].startswith(f"u{g['group_id'][1:]}_{f['no']}_"))))
    total = sum(r[3] for r in rows); covered = sum(r[3] * r[4] for r in rows)
    low = [r for r in rows if r[4] < th]
    L = ["# 折损审计（audit_loss 生成）", "", f"文件 {len(rows)} | 总字符 {total:,} | 覆盖 {covered/total*100:.1f}% | 低于 {int(th*100)}% 的文件 {len(low)}", "",
         "覆盖率证明的是\"原文有多少被逐字带进档案\"，不是质量；低覆盖文件必须有处置结论才算 S3 完成。", "",
         "| 组 | 文件号 | 文件 | 字符 | 覆盖 | 原子 | 单元 |", "|---|---|---|---|---|---|---|"]
    L += [f"| {g} | {n} | {f[:50]} | {c:,} | {p*100:.0f}% | {na} | {nu} |" for g, n, f, c, p, na, nu in rows]
    # audit 会被反复重跑：reset 重抽后要重跑、S9 增量后要重跑，status 的下一步文案也是让你重跑它。
    # 整文件重写会把执行 agent 已填的处置结论抹掉，而 S3 的完成门槛正是"待处置为 0"——先把上一轮读回来。
    ap = C.W(P, "kb", "折损审计.md"); prev = {}
    if os.path.isfile(ap):
        in_sec = False
        for line in C.read_text(ap).splitlines():
            if line.startswith("## 待处置"):
                in_sec = True; continue
            if in_sec and line.startswith("|"):
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) == 5 and cells[0] not in ("组", "") and set(cells[0]) != {"-"} and cells[4]:
                    prev[(cells[0], cells[1])] = cells[4]
    L += ["", f"## 待处置（覆盖 < {int(th*100)}%）", "", "每行填处置：合理排除 / 纯观点 / 缺完整体 / 疑漏读（疑漏读 → 该批 `reset <批>` 后重新 extract；其余进 S9 输入）", "",
          "重跑 audit 会按 组 + 文件号 把已填的处置带过来；文件若不再低覆盖，它那行连同处置一起消失。", "",
          "| 组 | 文件号 | 文件 | 覆盖 | 处置 |", "|---|---|---|---|---|"]
    L += [f"| {g} | {n} | {f[:50]} | {p*100:.0f}% | {prev.get((str(g), str(n)), '')} |" for g, n, f, c, p, na, nu in low]
    carried = sum(1 for g, n, _f, _c, _p, _na, _nu in low if prev.get((str(g), str(n))))
    C.write_text(ap, "\n".join(L) + "\n")
    C.record_stage(P, "audit", [C.W(P, "kb", "atoms.jsonl"), C.W(P, "kb", "units.jsonl")], extra={"coverage": round(covered / total, 3), "low": len(low)})
    print(f"覆盖 {covered/total*100:.1f}% | 低覆盖文件 {len(low)}（沿用上轮处置 {carried}，待填 {len(low)-carried}）→ work/kb/折损审计.md 待处置列")
    C.pipeline_log(P, "S3", f"audit：覆盖 {covered/total*100:.1f}%，低覆盖 {len(low)} 文件待处置")

if __name__ == "__main__":
    main()
