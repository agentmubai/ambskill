# -*- coding: utf-8 -*-
"""轻验收报告：读 tests/<题集>/scores.json → report.md：每类型每来源的总分与五维、新成品对裸模型的差距、扣分在哪一件。
用法：python3 eval_report.py [--testset 常备] [--project P]
不判 PASS / WEAK / FAIL。只做三件事：列差距；差距 < 1 分的标「不解读」；低于裸模型 ≥ 1 分的标「低于裸模型」并列出扣分件。
记录 evaluate:<题集>，ok = 矩阵完整（不是分数高低）。deliver 看到没有任何 evaluate 记录会提醒但不拦——轻验收是给人看的，不是门。"""
import os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

def mean(v):
    return sum(v) / len(v) if v else 0.0

def main():
    usage = "用法：eval_report.py [--testset 常备] [--project P]"
    pos, o, f = C.parse_args(sys.argv[1:], opts=("--testset",), usage=usage)
    if pos:
        C.die(usage)
    ts = o.get("--testset", "常备"); P = C.project_root(o.get("--project"))
    TS = C.W(P, "tests", ts); sj = os.path.join(TS, "scores.json"); C.need(sj, f"blind_eval tally --testset {ts}")
    tst = C.stage_state(P, f"tally:{ts}", C.tally_inputs(P, ts))
    if tst != "ok":
        C.die(f"tally:{ts} 的记录是 {tst}：" + {"stale": "评分 / key / 题集在 tally 之后改过，重跑 tally", "failed": "矩阵不完整（见 scores.json 的 problems）", "missing": "先跑 tally"}.get(tst, ""))
    S = C.read_json(sj); rows = S["rows"]
    if not S.get("complete"):
        C.die("scores.json 标记矩阵不完整，不出报告")
    import blind_eval
    qkind = {}
    for _k, _qs in blind_eval.parse_questions(os.path.join(TS, "questions.md"))[0].items():
        for _q, _kind, _t in _qs:
            qkind[(_k, _q)] = _kind
    keys = collections.OrderedDict(); srcs = []
    for r in rows:
        keys.setdefault(r["key"], []).append(r)
        if r["source"] not in srcs:
            srcs.append(r["source"])
    base, tgt = "bare", "new"
    L = [f"# 轻验收报告（{ts}）", "", f"评分行 {len(rows)}；来源：{', '.join(srcs)}；满分 25 = 五维（{' / '.join(C.DIMS)}）各 0–5。", "",
         "## 总表", "", "| 类型 | " + " | ".join(srcs) + f" | 差距（{tgt}−{base}） | 读法 | 扣分最多在 |", "|---|" + "---|" * (len(srcs) + 3)]
    flags = {}
    for k, rs in keys.items():
        bysrc = {s: [r for r in rs if r["source"] == s] for s in srcs}
        tot = {s: mean([r["total"] for r in v]) for s, v in bysrc.items()}
        tv = bysrc.get(tgt, []); bv = bysrc.get(base, [])
        if not tv or not bv:
            delta, read = 0.0, "缺对照来源"
        else:
            delta = tot[tgt] - tot[base]
            read = "差距 < 1 分，不解读" if abs(delta) < 1 else ("低于裸模型" if delta <= -1 else "高于裸模型")
        where = collections.Counter(r["where"] for r in tv if r["total"] <= 18).most_common(1)
        flags[k] = read
        L.append(f"| {k} | " + " | ".join(f"{tot.get(s, 0):.2f}" for s in srcs) + f" | {delta:+.2f} | {read} | {where[0][0] if where else '—'} |")
    L += ["", "## 五维均分（按来源）", "", "| 维度 | " + " | ".join(srcs) + " |", "|---|" + "---|" * len(srcs)]
    for i, d in enumerate(C.DIMS):
        L.append(f"| {d} | " + " | ".join(f"{mean([r['dims'][i] for r in rows if r['source'] == s]):.2f}" for s in srcs) + " |")
    L += ["", "## 按题型（新成品）", "", "| 题型 | 总分均值 | 结构对路 | 成品可用 |", "|---|---|---|---|"]
    kinds = collections.defaultdict(list)
    for r in rows:
        if r["source"] == tgt:
            kinds[qkind.get((r["key"], r["q"]), "?")].append(r)
    for kd, v in kinds.items():
        L.append(f"| {kd} | {mean([r['total'] for r in v]):.2f} | {mean([r['dims'][0] for r in v]):.2f} | {mean([r['dims'][1] for r in v]):.2f} |")
    low = collections.Counter(r["where"] for r in rows if r["source"] == tgt and r["total"] <= 18)
    L += ["", "## 扣分在哪一件（新成品总分 ≤ 18 的评分行）", ""] + ([f"- {k}：{v}" for k, v in low.most_common()] or ["- （无低分行）"])
    L += ["", "## 读分提醒", "", "- 评委有约 1 分波动；差距 < 1 分不解读。", "- 这是轻验收：不设通过线，只把差距和扣分件摊出来给你看。低于裸模型的类型，回去看它的骨架与句式是不是太少、或事实搬了。",
          "- 生成与评审都是模型；真正能不能发，要你用过才知道。", "",
          f"结论：{sum(1 for v in flags.values() if v == '高于裸模型')} 个类型高于裸模型 / {sum(1 for v in flags.values() if v.startswith('差距'))} 个不解读 / {sum(1 for v in flags.values() if v == '低于裸模型')} 个低于裸模型"]
    out = os.path.join(TS, "report.md"); C.write_text(out, "\n".join(L) + "\n")
    C.record_stage(P, f"evaluate:{ts}", C.eval_inputs(P, ts), ok=True, extra={"flags": flags})
    print(os.path.relpath(out, P)); print(L[-1])
    C.pipeline_log(P, "验收", f"report（{ts}）：" + L[-1])

if __name__ == "__main__":
    main()
