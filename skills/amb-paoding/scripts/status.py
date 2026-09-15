# -*- coding: utf-8 -*-
"""状态：只看文件与记录，不看任何人的口头汇报。每段"完成 = 产物存在 + 校验记录通过 + 输入未变"，并给出下一步命令。
用法：python3 status.py [--project P] [--json]
接手任何工程（新会话、被打断、别人做过一半）先跑它。"""
import os, sys, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

USAGE = "用法：status.py [--project P] [--json]"

def assess(P):
    R = []; W = lambda *x: C.W(P, *x)
    def row(stage, state, note, nxt):
        R.append({"stage": stage, "state": state, "note": note, "next": nxt})
    if not os.path.isdir(W()):
        row("P1", "未开始", "没有 work/（若工程在别处，加 --project <目录>）", "paoding.py survey --corpus <作品目录> --project <工程目录>"); return R
    cat = C.catalog(P); idx = C.orig_index(P)
    pre = W("docs", "预检报告.md"); has_pre = os.path.exists(pre) and bool(re.search(r"可开工|收缩|补料", C.read_text(pre)))
    # P1
    if not cat:
        row("P1", "未开始", "无 catalog.json", "paoding.py survey --corpus <作品目录>")
    elif not has_pre:
        row("P1", "进行中", f"已盘点 {cat.get('total_files', 0)} 篇 / {len(cat.get('groups', []))} 组，缺预检报告结论（可开工 / 收缩 / 补料）", "按 references/01-survey.md 模板写 work/docs/预检报告.md，交使用者看")
    else:
        row("P1", "完成", f"{cat.get('total_files', 0)} 篇，结论已写", "")
    # P2
    ing = C.stage_state(P, "ingest", [W("kb", "originals", "index.jsonl"), W("catalog.json")])
    if not idx:
        row("P2", "未开始", "原件库为空", "paoding.py ingest")
    elif ing != "ok":
        row("P2", "进行中", f"原件 {len(idx)}；ingest 记录 {ing}（catalog 改过就重跑）", "paoding.py ingest")
    else:
        row("P2", "完成", f"原件 {len(idx)} 篇", "")
    # P3
    forms = sorted({r["form"] for r in idx.values()}) if idx else []
    if forms:
        done, doing, todo = [], [], []
        for fm in forms:
            tp = C.types_path(P, fm)
            if not os.path.exists(tp):
                todo.append(fm); continue
            st = C.stage_state(P, f"confirm:{fm}", [tp, W("kb", "originals", "index.jsonl")])
            (done if st == "ok" else doing).append(f"{fm}({st})" if st != "ok" else fm)
        if not done and not doing:
            row("P3", "未开始", f"形态 {'、'.join(forms)} 都没有类型文件", f"paoding.py cluster {forms[0]} → 派子代理 → 使用者看类型卡 → 写 work/types/<形态>.json（confirmed_at）→ paoding.py confirm <形态>")
        elif doing or todo:
            row("P3", "进行中", f"已确认 {'、'.join(done) or '无'}；未过 {'、'.join(doing) or '无'}；未开始 {'、'.join(todo) or '无'}", "cluster / confirm 补齐；不想做的形态在预检报告写「收缩」即可")
        else:
            row("P3", "完成", f"{len(C.all_confirmed_types(P))} 个类型已确认（形态 {'、'.join(done)}）", "")
    pairs = C.all_confirmed_types(P); keys = [C.ft_key(fm, t["id"]) for fm, t in pairs]
    # P4
    if keys:
        miss, bad = [], []
        for fm, t in pairs:
            k = C.ft_key(fm, t["id"]); pk = C.pack_dir(P, k)
            if not os.path.exists(os.path.join(pk, C.PATTERN)):
                miss.append(k); continue
            st = C.stage_state(P, f"check:{k}", C.pack_inputs(P, fm, k))
            if st != "ok":
                bad.append(f"{k}:{st}")
        if len(miss) == len(keys):
            row("P4", "未开始", "无写法书", "paoding.py pattern all → 派子代理 → paoding.py check all → dispose 零引用篇 → 再 check")
        elif miss or bad:
            row("P4", "进行中", f"缺写法书 {'、'.join(miss) or '无'}；check 未过 {'、'.join(bad) or '无'}", "补 pattern；check 不过看 <pack>/mismatch.md 与 coverage.md；零引用篇 dispose")
        else:
            row("P4", "完成", f"{len(keys)} 个类型写法书齐、魂有证据、引文逐字、零引用已处置", "")
    # P5
    if keys:
        prefix = C.project_meta(P).get("prefix") or C.DEFAULT_PREFIX; draft = W("draft", "skills")
        dirs = [f"{prefix}-{k}" for k in keys] + [prefix]
        miss = [d for d in dirs if not os.path.exists(os.path.join(draft, d, "SKILL.md"))]
        lint = C.stage_state(P, "lint", C.skill_inputs(draft, [d for d in dirs if d not in miss]))
        if len(miss) == len(dirs):
            row("P5", "未开始", "无草稿技能", "paoding.py compose all → 派子代理 → compose --router → 派 → paoding.py lint")
        elif miss or lint != "ok":
            row("P5", "进行中", f"缺 {'、'.join(miss) or '无'}；lint {lint}", "补写缺的技能；paoding.py lint 直到全 PASS")
        else:
            row("P5", "完成", f"{len(dirs)} 个技能体检通过", "")
    # 验收
    meta = C.read_json(W("meta.json"), {})
    ev = {k.split(":", 1)[1]: v for k, v in meta.items() if k.startswith("evaluate:")}
    if keys:
        if not ev:
            row("验收", "未开始", "无轻验收报告（不是门；建议至少一套）", "paoding.py evaluate questions → answers → judge → tally → report")
        else:
            states = {ts: C.stage_state(P, f"evaluate:{ts}", C.eval_inputs(P, ts)) for ts in ev}
            fresh = [ts for ts, st in states.items() if st == "ok"]
            if fresh:
                row("验收", "完成", "报告：" + "；".join(f"{ts}（{'/'.join(str(x) for x in ev[ts].get('flags', {}).values()) or '有报告'}）" for ts in fresh), "")
            else:
                row("验收", "进行中", "报告已过期：" + "、".join(f"{ts}({st})" for ts, st in states.items()), "重跑 tally → report")
    # 交付
    if keys:
        dl = meta.get("deliver")
        if dl and dl.get("ok"):
            dest = dl.get("dest", ""); dest = os.path.join(P, dest) if dest and not os.path.isabs(dest) else dest
            st = C.stage_state(P, "deliver", [os.path.join(dest, "README.md")]) if dest else "missing"
            if st == "ok" and os.path.isdir(dest):
                row("交付", "完成", f"成品 {dest}", "P6 增量：survey --update → ingest → cluster <形态> --update → confirm → pattern --update → check → compose --sync-refs → lint → deliver")
            else:
                row("交付", "进行中", f"deliver 记录 {st}", "重新 paoding.py deliver <箱名>")
        else:
            row("交付", "未开始", "未交付", "paoding.py deliver <箱名> [--no-kb]")
    return R

def main():
    pos, o, f = C.parse_args(sys.argv[1:], flags=("--json",), usage=USAGE)
    if pos:
        C.die(USAGE)
    P = C.project_root(o.get("--project")); R = assess(P)
    if "--json" in f:
        print(json.dumps({"project": P, "rows": R, "stop": C.stop_requested(P)}, ensure_ascii=False, indent=1)); return
    print(f"工程：{P}" + ("   ** work/STOP 存在：停止中，不派新任务 **" if C.stop_requested(P) else ""))
    print("| 段 | 状态 | 说明 | 下一步 |\n|---|---|---|---|")
    for r in R:
        print(f"| {r['stage']} | {r['state']} | {r['note']} | {r['next']} |")
    cur = next((r for r in R if r["state"] != "完成"), None)
    print("\n当前：" + (f"{cur['stage']} {cur['state']} → {cur['next']}" if cur else "P1–交付 全部完成"))

if __name__ == "__main__":
    main()
