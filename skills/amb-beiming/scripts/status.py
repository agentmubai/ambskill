# -*- coding: utf-8 -*-
"""状态：只看文件与记录，不看任何人的口头汇报。判断每段是否"完成 = 产物存在 + 校验记录通过 + 输入未变"，并给出下一步命令。
用法：python3 status.py [--project P] [--json]
      python3 status.py --all <工程1> <工程2> …
任何时候接手一个工程（新会话、被打断、别人做过一半），先跑它。
S2 完成 = 版本行「版本：冻结 vX.Y」+ 全部试点批已 settle --accept + 加工样品在，三者同时成立。
S7 / S8 的"完成"按记录时的输入哈希判：评分或成品变了就显示 stale。"""
import os, sys, re, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

USAGE = "用法：status.py [--project P] [--json] | status.py --all <工程…>"

def has(p, pat=None):
    if not os.path.exists(p):
        return False
    return True if pat is None else bool(re.search(pat, C.read_text(p)))

def fmt_batches(bs):
    """按状态列批号：pending 2（b003,b004）"""
    by = collections.OrderedDict()
    for st in ("pending", "in_progress", "done", "failed", "interrupted", "excluded"):
        ids = [b["batch_id"] for b in bs if b["status"] == st]
        if ids:
            by[st] = ids
    return "；".join(f"{st} {len(ids)}（{','.join(ids[:8])}{'…' if len(ids) > 8 else ''}）" for st, ids in by.items()) or "无批次"

def assess(P):
    R = []; W = lambda *x: C.W(P, *x)
    def row(stage, state, note, nxt):
        R.append({"stage": stage, "state": state, "note": note, "next": nxt})
    if not os.path.isdir(W()):
        row("S1", "未开始", "没有 work/（若工程在别处，加 --project <目录>）", "beiming.py survey --corpus <语料目录> --project <工程目录>"); return R, {}
    bj = C.read_json(W("batches.json"), {"batches": []}); bs = bj["batches"]
    cnt = collections.Counter(b["status"] for b in bs)
    info = {"batches": dict(cnt), "batch_ids": {st: [b["batch_id"] for b in bs if b["status"] == st] for st in cnt}, "stop": os.path.exists(W("STOP"))}
    # S1
    pre = W("docs", "预检报告.md")
    if not has(W("catalog.json")):
        row("S1", "未开始", "无 catalog.json", "beiming.py survey --corpus <语料目录>")
    elif not has(pre, r"可开工|收缩范围|补料"):
        row("S1", "进行中", f"有盘点（{len(bs)} 批：{','.join(b['batch_id'] for b in bs[:6])}{'…' if len(bs) > 6 else ''}），缺预检报告结论（可开工 / 收缩范围 / 补料）", "按 references/01-survey.md 模板写 work/docs/预检报告.md，交使用者看")
    else:
        row("S1", "完成", f"{len(bs)} 批，结论已写", "")
    # S2
    rules = W("docs", "执行提示词.md")
    pil = [b for b in bs if b.get("claimed_by") == "pilot"]; acc = [b for b in bs if b.get("claimed_by") == "pilot-accepted"]
    sample = has(W("docs", "加工样品.md"))
    if not has(rules):
        row("S2", "未开始", "无执行提示词", f"beiming.py pilot <b001,bNNN>（选 2–3 批：最长文件所在批 + 一个别的形态；批号：{','.join(b['batch_id'] for b in bs[:6])}）")
    else:
        rtext = C.read_text(rules); ver, frozen = C.rules_version(rtext)
        miss = []
        if not frozen:
            miss.append(f"版本行是「{ver}」，未冻结（{C.freeze_hint(rtext)}）")
        if pil:
            miss.append("试点批未接纳 " + "、".join(f"{b['batch_id']}({b['status']})" for b in pil))
        if not pil and not acc:
            miss.append("没有试点批")
        if not sample:
            miss.append("缺加工样品（第二个参与点没走）")
        if miss:
            row("S2", "进行中", "；".join(miss),
                "settle --pilot → read <批> --sample → calibrate → 派子代理写加工样品 → 连续两批不改五项后把版本行改为「版本：冻结 vX.Y」→ settle --pilot --accept")
        else:
            row("S2", "完成", f"冻结 {ver}；试点批已接纳 {','.join(b['batch_id'] for b in acc)}；加工样品在", "")
    # S3
    active = [b for b in bs if b["status"] != "excluded"]
    unfinished = [b["batch_id"] for b in active if b["status"] in C.STATUS_UNFINISHED]
    unaccepted = [b["batch_id"] for b in pil if b["status"] == "done"]
    done_ok = [b for b in active if b["status"] == "done" and b.get("claimed_by") != "pilot"]
    inputs = [os.path.join(P, b[k]) for b in done_ok for k in ("atoms_out", "units_out")]
    ms = C.stage_state(P, "merge", inputs); au = C.stage_state(P, "audit", [W("kb", "atoms.jsonl"), W("kb", "units.jsonl")])
    loss = W("kb", "折损审计.md"); pending_dispo = 0
    if os.path.exists(loss):
        sec = C.read_text(loss).split("## 待处置", 1)[-1]
        pending_dispo = sum(1 for l in sec.splitlines() if l.startswith("|") and re.search(r"\|\s*\d+%\s*\|\s*\|\s*$", l))
    if not bs:
        row("S3", "未开始", "无批次", "beiming.py survey")
    elif unfinished or unaccepted:
        started = any(b.get("claimed_by") == "extract" for b in bs)
        note = f"未完成批 {len(unfinished)}：{','.join(unfinished[:10])}" if unfinished else ""
        if unaccepted:
            note += ("；" if note else "") + f"试点批 done 未接纳：{','.join(unaccepted)}"
        nxt = []
        if cnt.get("pending"):
            nxt.append("beiming.py extract → 派子代理 → settle")
        if cnt.get("in_progress"):
            nxt.append("in_progress → 等子代理写完后 settle")
        if cnt.get("interrupted"):
            nxt.append("interrupted → beiming.py recover")
        if cnt.get("failed"):
            nxt.append("failed → 看 batches.json note 修后 extract --batches <批> --regenerate")
        if unaccepted:
            nxt.append("试点批 → settle --pilot --accept（S2）")
        row("S3", "进行中" if started else "未开始", note or f"批次 {fmt_batches(bs)}", "；".join(nxt) or "beiming.py extract → 派子代理 → beiming.py settle")
    elif not done_ok:
        row("S3", "未开始", f"批次 {fmt_batches(bs)}", "beiming.py extract → 派子代理 → beiming.py settle")
    elif ms != "ok":
        row("S3", "进行中", f"批全 done（{len(done_ok)}），merge 状态 {ms}", "beiming.py merge → beiming.py audit")
    elif au != "ok" or pending_dispo:
        row("S3", "进行中", f"audit 状态 {au}；待处置低覆盖文件 {pending_dispo}", "beiming.py audit；在 work/kb/折损审计.md 处置列逐行填结论；疑漏读的批 `reset <批>` 后重抽")
    else:
        row("S3", "完成", f"原子 {C.read_json(W('meta.json'), {}).get('merge', {}).get('atoms')}，折损已处置", "")
    # S4
    tj = W("tasks.json"); plan = W("docs", "能力方案.md")
    if not has(plan):
        row("S4", "未开始", "无能力方案", "beiming.py plan → 派子代理/自己写 work/docs/能力方案.md → 使用者确认（第三个参与点）")
    elif not (has(tj) and C.read_json(tj, {}).get("confirmed_at") and C.read_json(tj, {}).get("tasks")):
        row("S4", "进行中", "能力方案已写，tasks.json 缺或未标 confirmed_at", "使用者确认后写 work/tasks.json（含 confirmed_at）→ beiming.py repool")
    elif C.stage_state(P, "repool", [tj, W("kb", "atoms.jsonl")]) != "ok":
        row("S4", "进行中", f"repool 状态 {C.stage_state(P, 'repool', [tj, W('kb', 'atoms.jsonl')])}（无处归原子也算未过）", "beiming.py repool；无处归的补进 match 后重跑")
    else:
        row("S4", "完成", f"{len(C.read_json(tj)['tasks'])} 任务已确认并分池", "")
    T = C.read_json(tj, {}).get("tasks", []) if has(tj) else []
    # S5
    if T:
        missing = []; bad = []
        for t in T:
            pk = W("kb", "packs", t["id"])
            for f in ("methods.md", "case_map.md", "layers.md", "cards.md"):
                if not has(os.path.join(pk, f)):
                    missing.append(f"{t['id']}/{f}")
            st = C.stage_state(P, f"check_layers:{t['id']}", [os.path.join(pk, "layers.md"), W("kb", "pools", t["id"], "atoms.jsonl")])
            if st != "ok":
                bad.append(f"{t['id']}:{st}")
        idx = C.stage_state(P, "index", [os.path.join(W("kb", "packs", t["id"]), f) for t in T for f in ("methods.md", "cards.md", "layers.md")])
        if missing and len(missing) == 4 * len(T):
            row("S5", "未开始", "无知识包", "beiming.py distill all --step pack → 派子代理 → caselib → screen → distill --step layers → check-layers → distill --step cards → index")
        elif missing or bad or idx != "ok":
            row("S5", "进行中", f"缺 {'、'.join(missing[:6]) or '无'}{'…' if len(missing) > 6 else ''}；六层核对 {'、'.join(bad) or '全过'}；index {idx}", "按缺的补：pack→caselib→screen→layers→check-layers→cards→index")
        else:
            row("S5", "完成", "各任务知识包齐、六层逐字核对通过、索引已建", "")
    # S6
    if T:
        prefix = C.read_json(tj).get("prefix", ""); draft = W("draft", "skills")
        dirs = [f"{prefix}-{t['id']}" for t in T] + [prefix]
        miss = [d for d in dirs if not has(os.path.join(draft, d, "SKILL.md"))]
        lint = C.stage_state(P, "lint", C.skill_inputs(draft, [d for d in dirs if d not in miss]))
        if len(miss) == len(dirs):
            row("S6", "未开始", "无草稿技能", "beiming.py compose all → 派子代理 → compose --router → 派子代理 → lint")
        elif miss or lint != "ok":
            row("S6", "进行中", f"缺 {'、'.join(miss) or '无'}；lint {lint}", "补写缺的技能；beiming.py lint 直到全 PASS")
        else:
            row("S6", "完成", f"{len(dirs)} 个技能体检通过", "")
    # S7
    meta = C.read_json(W("meta.json"), {})
    ev = {k.split(":", 1)[1]: v for k, v in meta.items() if k.startswith("evaluate:")}
    if T:
        states = {}
        for ts, v in ev.items():
            states[ts] = C.stage_state(P, f"evaluate:{ts}", C.eval_inputs(P, ts))
        passed = [ts for ts, st in states.items() if st == "ok"]
        if not ev:
            row("S7", "未开始", "无题集报告", "beiming.py evaluate questions → answers → judge → tally → report（--testset 常备）")
        elif not passed:
            row("S7", "进行中", "有报告但没有全 PASS 且未过期的题集：" + "；".join(f"{k}：{'/'.join(str(x) for x in v.get('verdicts', {}).values()) or '无判定'}（{states[k]}）" for k, v in ev.items()),
                "stale → 重跑 tally → report；WEAK/FAIL 回 S5 或 S6 修，修后只重答 new；再换一套题集")
        elif not has(W("docs", "验收报告.md")):
            row("S7", "进行中", f"PASS 题集：{'、'.join(passed)}；缺验收报告", "按 references/07-evaluate.md 模板写 work/docs/验收报告.md")
        else:
            row("S7", "完成", f"PASS 题集 {'、'.join(passed)}", "")
    # S8
    if T:
        dl = meta.get("deliver")
        if dl and dl.get("ok"):
            dest = dl.get("dest", "")
            dest = os.path.join(P, dest) if dest and not os.path.isabs(dest) else dest
            st = C.stage_state(P, "deliver", [os.path.join(dest, "README.md")]) if dest else "missing"
            if st == "ok" and os.path.isdir(dest):
                row("S8", "完成", f"成品 {dest}", "S9：新料 survey --update → extract → settle → merge → repool → update")
            else:
                row("S8", "进行中", f"deliver 记录 {st}（成品目录{'在' if os.path.isdir(dest) else '不在'}）", "重新 beiming.py deliver <工具箱名>")
        else:
            row("S8", "未开始", "未交付", "beiming.py deliver <工具箱名> [--plugin] [--no-kb]")
    return R, info

def main():
    pos, o, f = C.parse_args(sys.argv[1:], flags=("--json", "--all"), usage=USAGE)
    if "--all" in f:
        Ps = [os.path.abspath(x) for x in pos]
        if not Ps:
            C.die(USAGE)
        for P in Ps:
            R, info = assess(P); cur = next((r for r in R if r["state"] != "完成"), None)
            bb = "，".join(f"{k} {v}" for k, v in info.get("batches", {}).items()) or "无批次"
            print(f"{os.path.basename(P):<30} {(cur or {}).get('stage', 'S8')} {(cur or {}).get('state', '完成')}  {(cur or {}).get('note', '')[:70]}  批次：{bb}" + ("  [STOP]" if info.get("stop") else ""))
        return
    if pos:
        C.die(f"多余的参数 {' '.join(pos)}\n{USAGE}")
    P = C.project_root(o.get("--project"))
    R, info = assess(P)
    if "--json" in f:
        print(json.dumps({"project": P, "rows": R, **info}, ensure_ascii=False, indent=1)); return
    print(f"工程：{P}" + ("   ** work/STOP 存在：停止中，不派新任务 **" if info.get("stop") else ""))
    if info.get("batches") is not None and os.path.isdir(C.W(P)):
        print("批次：" + fmt_batches(C.read_json(C.W(P, "batches.json"), {"batches": []})["batches"]))
    print("| 段 | 状态 | 说明 | 下一步 |\n|---|---|---|---|")
    for r in R:
        print(f"| {r['stage']} | {r['state']} | {r['note']} | {r['next']} |")
    cur = next((r for r in R if r["state"] != "完成"), None)
    print("\n当前：" + (f"{cur['stage']} {cur['state']} → {cur['next']}" if cur else "S1–S8 全部完成"))

if __name__ == "__main__":
    main()
