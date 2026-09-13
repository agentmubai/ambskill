# -*- coding: utf-8 -*-
"""S7 汇总报告：读 tests/<题集>/scores.json → report.md：每任务每来源的总分与五维、新版对裸模型的差距、PASS / WEAK / FAIL 判定、扣分回哪一层。
用法：python3 eval_report.py [--testset 常备] [--baseline bare] [--target new] [--project P]
判定（对 target 来源，按两位评委 × 各题平均；差距 = target − baseline）：
  FAIL  差距 ≤ −1；或 原法忠实 ≤ 2（只有通用常识）；或 反转题的方法选择 ≤ 1（条件变了结论不变）；或 材料贴合 ≤ 2（编了材料里没有的）
  WEAK  非 FAIL，且 |差距| < 1（不解读）、或 原法忠实 < 3.5、或 反转 / 近邻题的方法选择 < 3、或 成品可用 < 3
  PASS  其余：差距 ≥ 1 且 原法忠实 ≥ 3.5 且 反转与近邻的方法选择 ≥ 3 且 成品可用 ≥ 3
  路由器：每题方法选择均分 ≥ 4 为 PASS；有一题在 3–4 之间 WEAK；有一题 < 3 FAIL
只有一个来源时不判 PASS，只列分（无对照看不出增量）。"""
import os, sys, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

def mean(v):
    return sum(v) / len(v) if v else 0.0

def main():
    usage = "用法：eval_report.py [--testset 常备] [--baseline bare] [--target new] [--project P]"
    pos, o, f = C.parse_args(sys.argv[1:], opts=("--testset", "--baseline", "--target"), usage=usage)
    if pos:
        C.die(usage)
    ts = o.get("--testset", "常备"); base = o.get("--baseline", "bare"); tgt = o.get("--target", "new"); P = C.project_root(o.get("--project"))
    TS = C.W(P, "tests", ts); sj = os.path.join(TS, "scores.json"); C.need(sj, f"blind_eval tally --testset {ts}")
    qp = os.path.join(TS, "questions.md")
    tst = C.stage_state(P, f"tally:{ts}", C.tally_inputs(P, ts))
    if tst != "ok":
        C.die(f"tally:{ts} 的记录是 {tst}：" + {"stale": "评分文件 / key / 题集在 tally 之后改过，先重跑 `blind_eval tally`", "failed": "矩阵不完整（见 scores.json 的 problems），补齐后重跑 tally", "missing": "先跑 `blind_eval tally`"}.get(tst, ""))
    S = C.read_json(sj); rows = S["rows"]
    if not S.get("complete", False) or S.get("problems"):
        C.die("scores.json 标记矩阵不完整：\n" + "\n".join(f"- {p}" for p in S.get("problems", [])) + "\n不出判定；补齐后重跑 tally")
    qkind = {}
    for block in C.read_text(qp).split("\n## ")[1:]:
        for q, k in re.findall(r"(?m)^- (Q\d+)\s+([^：:\n]+)[：:]", block):
            qkind[q] = k.strip()
    tasks = collections.OrderedDict(); srcs = []
    for r in rows:
        tasks.setdefault(r["task"], []).append(r)
        if r["source"] not in srcs:
            srcs.append(r["source"])
    L = [f"# 盲评报告（{ts}）", "", f"评分行 {len(rows)}；来源：{', '.join(srcs)}；满分 25 = 五维（{' / '.join(C.DIMS)}）各 0–5。", ""]
    if S.get("problems"):
        L += ["**解析问题（先处理再信分数）**：", ""] + [f"- {p}" for p in S["problems"]] + [""]
    L += ["## 总表", "", "| 任务 | " + " | ".join(srcs) + f" | 差距（{tgt}−{base}） | 判定 | 主因 |", "|---|" + "---|" * (len(srcs) + 3)]
    verdicts = {}
    for tid, rs in tasks.items():
        bysrc = {s: [r for r in rs if r["source"] == s] for s in srcs}
        tot = {s: mean([r["total"] for r in v]) for s, v in bysrc.items()}
        tv = bysrc.get(tgt, []); bv = bysrc.get(base, [])
        if not tv or not bv:
            verdict, why, delta = "—", "缺对照来源", 0.0
        else:
            delta = tot[tgt] - tot[base]; dims = {d: mean([r["dims"][i] for r in tv]) for i, d in enumerate(C.DIMS)}
            def kind_dim(kinds, d):
                v = [r["dims"][C.DIMS.index(d)] for r in tv if any(k in qkind.get(r["q"], "") for k in kinds)]; return mean(v) if v else None
            if tid == "router":
                per_q = [mean([r["dims"][0] for r in tv if r["q"] == q]) for q in sorted({r["q"] for r in tv})]
                verdict = "PASS" if all(x >= 4 for x in per_q) else ("FAIL" if any(x < 3 for x in per_q) else "WEAK"); why = f"各题方法选择 {', '.join(f'{x:.1f}' for x in per_q)}"
            else:
                flip = kind_dim(("反转",), "方法选择"); nb = kind_dim(("近邻",), "方法选择"); reasons = []
                if delta <= -1: reasons.append(f"低于对照 {delta:.2f}")
                if dims["原法忠实"] <= 2: reasons.append("原法忠实 ≤ 2")
                if flip is not None and flip <= 1: reasons.append("反转题方法选择 ≤ 1")
                if dims["材料贴合"] <= 2: reasons.append("材料贴合 ≤ 2")
                if reasons:
                    verdict = "FAIL"
                else:
                    if abs(delta) < 1: reasons.append(f"差距 {delta:.2f} < 1 不解读")
                    if dims["原法忠实"] < 3.5: reasons.append(f"原法忠实 {dims['原法忠实']:.2f} < 3.5")
                    if flip is not None and flip < 3: reasons.append(f"反转题方法选择 {flip:.2f} < 3")
                    if nb is not None and nb < 3: reasons.append(f"近邻题方法选择 {nb:.2f} < 3")
                    if dims["成品可用"] < 3: reasons.append(f"成品可用 {dims['成品可用']:.2f} < 3")
                    verdict = "WEAK" if reasons else "PASS"
                why = "；".join(reasons) or "五项门槛全过"
        verdicts[tid] = verdict
        L.append(f"| {tid} | " + " | ".join(f"{tot.get(s, 0):.2f}" for s in srcs) + f" | {delta:+.2f} | {verdict} | {why} |")
    L += ["", "## 五维均分（按来源）", "", "| 维度 | " + " | ".join(srcs) + " |", "|---|" + "---|" * len(srcs)]
    for i, d in enumerate(C.DIMS):
        L.append(f"| {d} | " + " | ".join(f"{mean([r['dims'][i] for r in rows if r['source'] == s]):.2f}" for s in srcs) + " |")
    L += ["", "## 按题型（target）", "", "| 题型 | 总分均值 | 方法选择 | 成品可用 |", "|---|---|---|---|"]
    kinds = collections.defaultdict(list)
    for r in rows:
        if r["source"] == tgt:
            kinds[qkind.get(r["q"], "?")].append(r)
    for k, v in kinds.items():
        L.append(f"| {k} | {mean([r['total'] for r in v]):.2f} | {mean([r['dims'][0] for r in v]):.2f} | {mean([r['dims'][1] for r in v]):.2f} |")
    lay = collections.Counter(r["layer"] for r in rows if r["source"] == tgt and r["total"] <= 18)
    L += ["", "## 扣分回哪一层（target 总分 ≤ 18 的评分行，评委标注的层）", ""] + ([f"- {k}：{v}" for k, v in lay.most_common()] or ["- （无低分行）"])
    L += ["", "## 读分提醒", "", "- 评委有约 1 分波动；差距 < 1 分不解读，看分维度与题型变化。", "- 评委打的是相对分：同一盲评包里几份回答互相衬托，写差距走势，不拿对照的绝对分说它退步。",
          "- 修订几轮后必须换一套没见过的题（泛化 / 暴力）；掉回去就是过拟合。", "- 生成与评审都是模型；真正的效果要使用者用过才知道，验收报告写明这一点。", "",
          f"结论：{sum(1 for v in verdicts.values() if v == 'PASS')} PASS / {sum(1 for v in verdicts.values() if v == 'WEAK')} WEAK / {sum(1 for v in verdicts.values() if v == 'FAIL')} FAIL" + ("；**全部 PASS**" if verdicts and all(v == "PASS" for v in verdicts.values()) else "；WEAK/FAIL 的任务回 S5（知识包里没有）或 S6（有但技能没调用）")]
    out = os.path.join(TS, "report.md"); C.write_text(out, "\n".join(L) + "\n")
    # 记录的输入含 scores.json / 题集 / key / 每份评分文件 / tasks.json：任何一个再改，S7 的 PASS 就过期（status 判 stale）
    C.record_stage(P, f"evaluate:{ts}", C.eval_inputs(P, ts), ok=bool(verdicts) and all(v == "PASS" for v in verdicts.values()), extra={"verdicts": verdicts})
    print(os.path.relpath(out, P)); print(L[-1])
    C.pipeline_log(P, "S7", f"evaluate report（{ts}）：" + L[-1])

if __name__ == "__main__":
    main()
