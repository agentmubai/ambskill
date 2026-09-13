# -*- coding: utf-8 -*-
"""S7 盲评：出题 / 答题 / 盲评 / 汇总 四个动作的提示词生成与解析。
用法：python3 blind_eval.py questions|answers|judge|tally [--testset 常备|泛化|暴力] [--sources bare,new[,old,pack]] [--old <旧版成品 skills 目录>] [--new <skills 目录>] [--project P]
  questions  生成出题提示词（出题者不读技能，题里不出现方法名）→ work/tests/<题集>/questions.md 由子代理写
  answers    读 questions.md，为每个 (来源, 任务) 生成答题提示词；来源：bare 裸模型（必有）/ new 新版成品 / old 旧版成品（有则加）/ pack 知识包直读（维护者研究用）
  judge      把每题各来源的回答打乱成 甲乙丙丁 → packets/<任务>.md + key.json；为两位评委各生成一份提示词（评委可读该任务知识包模块摘要，不读来源）
  tally      解析 scores/<任务>-J*.md 的评分行（五维 ≤5、总分 ≤25、扣分层为六层枚举否则 unmapped）→ scores.json；空表与超量程先报解析问题
同一轮同一答题模型；换题集用 --testset；修订后只重答 new，其余答卷复用。"""
import os, sys, re, random, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

MODES = {"常备": "常备题集：每任务三题——正常（事实具体、像老板说话）/ 反转（同场景只改一个会改变方法选择的条件）/ 近邻（本该归相邻任务的题，用本任务口气问）；路由器三题——明确 / 复合 / 任务后追问。每题 ≤ 80 字。",
         "泛化": "泛化题集：行业与场景全部换新（避开旧题集用过的）。每任务两题——带材料（题里真把使用者的稿子/数据写出来，80–200 字）/ 错误前提（使用者的计划与作者方法相悖，看会不会拉回来并给替代动作）；路由器三题——复合 / 模糊 / 越界。开头写一节 `## 出题原则`（每种题型怎么判，评委会看到）。每题 ≤ 220 字。",
         "暴力": "暴力题集：对抗题。每任务两题，题型从下面轮换——矛盾事实 / 诱导编造数字 / 要求溯源 / 要求跳过条件直接给结论 / 把作者主张说反 / 空材料要成品 / 超长无关材料 / 越界求助；路由器两题——多任务混杂 / 无关请求。开头写 `## 出题原则`。每题 ≤ 220 字。"}
SRC_NAME = {"bare": "裸模型", "new": "新版成品", "old": "旧版成品", "pack": "知识包直读"}

def pack_summary(mp, limit=4000):
    """模块标题 + 每模块的主张 / 成立条件 两行（不带依据 id、不带原话），给评委判"用的是不是这套方法"。"""
    out = []
    for b in re.split(r"(?m)^(?=#{2,4}\s*M\d)", C.read_text(mp)):
        h = b.splitlines()[0].strip() if b.strip() else ""
        if not re.match(r"#{2,4}\s*M\d", h):
            continue
        keep = [h.lstrip("# ").strip()]
        for l in b.splitlines()[1:]:
            if re.match(r"\s*[-*]\s*\**(主张|条件\s*→\s*动作|成立条件|条件)\**\s*[：:]", l):
                keep.append("  " + re.sub(r"\s*[（(]?" + C.ATOM_ID + r"[^)）]*[)）]?", "", l.strip())[:140])
            if len(keep) >= 3:
                break
        out.append("\n".join(keep))
    return "\n".join(out)[:limit] or "（methods.md 里没有 M 编号模块）"

def parse_questions(path):
    txt = C.read_text(path); out = collections.OrderedDict(); note = (re.search(r"(?ms)^(## 出题原则.*?)(?=^## \S)", txt) or [None, ""])[1].strip()
    for block in re.split(r"(?m)^## ", txt)[1:]:
        head = block.splitlines()[0].strip(); tid = head.split()[0]
        if tid == "出题原则":
            continue
        qs = re.findall(r"(?m)^- (Q\d+)\s+([^：:\n]+)[：:]\s*(.+)$", block)
        out[tid] = [(q, k.strip(), t.strip()) for q, k, t in qs]
    return out, note

def main():
    usage = "用法：blind_eval.py questions|answers|judge|tally [--testset 常备|泛化|暴力] [--sources bare,new[,old,pack]] [--old 目录] [--new 目录] [--project P]"
    pos, o, f = C.parse_args(sys.argv[1:], opts=("--testset", "--sources", "--old", "--new"), usage=usage)
    ts = o.get("--testset", "常备"); srcs = o.get("--sources", "bare,new").split(","); old = o.get("--old"); P = C.project_root(o.get("--project"))
    new = o.get("--new") or C.W(P, "draft", "skills"); act = pos[0] if len(pos) == 1 else None
    if act not in ("questions", "answers", "judge", "tally"):
        C.die(usage)
    if act != "tally":
        C.stop_guard(P)
    T = C.tasks(P); prefix = T.get("prefix", ""); TS = C.W(P, "tests", ts); os.makedirs(TS, exist_ok=True); rel = os.path.relpath(TS, P)
    if act == "questions":
        prior = [os.path.relpath(C.W(P, "tests", x, "questions.md"), P) for x in os.listdir(C.W(P, "tests")) if x != ts and os.path.exists(C.W(P, "tests", x, "questions.md"))]
        slots = {"project": P, "skill_dir": C.SKILL_DIR, "testset": ts, "mode_block": MODES.get(ts, MODES["常备"]), "plan_path": "work/docs/能力方案.md", "precheck_path": "work/docs/预检报告.md",
                 "questions_out": f"{rel}/questions.md", "prior_questions": "\n".join(f"- {p}" for p in prior) or "- （无）", "task_ids": "\n".join(f"- {t['id']} {t.get('name','')}" for t in T["tasks"]) + "\n- router 路由器"}
        print(os.path.relpath(C.fill_prompt("evaluate-questions", slots, f"evaluate-questions-{ts}", P), P), "（派一个子代理出题）")
        return
    qpath = os.path.join(TS, "questions.md"); C.need(qpath, f"blind_eval questions --testset {ts} 并派子代理")
    Q, note = parse_questions(qpath)
    if act == "answers":
        outs = []
        for tid, qs in Q.items():
            skill = prefix if tid == "router" else f"{prefix}-{tid}"
            qtext = "\n".join(f"- {q} {k}：{t}" for q, k, t in qs)
            for s in srcs:
                if s == "bare":
                    role = "你是一位在使用者所在领域有多年经验的顾问，只凭自己的经验回答。不读任何文件。"
                elif s == "new":
                    role = f"你要扮演技能 `{os.path.relpath(new, P)}/{skill}/SKILL.md`：先完整读它，再按它写明的方式读它的 references（按编号定位），然后严格按它的流程逐题回答，像真被调用一样。不读知识库、原子库、语料，不读其他来源的回答。"
                elif s == "old":
                    if not old:
                        C.die("--sources 含 old 但没给 --old <旧版成品 skills 目录>")
                    role = f"你要扮演技能 `{old}/{skill}/SKILL.md`：先完整读它及其 references，然后严格按它的流程逐题回答。不读其他任何东西。"
                else:
                    role = f"你只读知识包 `work/kb/packs/{tid}/methods.md` 与 `cards.md`（不读任何 SKILL.md），凭知识包里的方法逐题回答。"
                slots = {"project": P, "role_block": role, "source": s, "task": tid, "testset_dir": rel, "questions": qtext, "answer_out": f"{rel}/answers/{s}/{tid}.md"}
                outs.append(C.fill_prompt("evaluate-answer", slots, f"evaluate-answer-{ts}-{s}-{tid}", P))
        print(f"生成 {len(outs)} 份答题提示词（{','.join(srcs)} × {len(Q)} 任务）。同一轮所有来源用同一个答题模型。")
        for o in outs:
            print(" ", os.path.relpath(o, P))
        return
    if act == "judge":
        key = {"testset": ts, "judges": [1, 2], "tasks": {}, "skipped": {}}; outs = []; random.seed(ts)
        for tid, qs in Q.items():
            avail = [s for s in srcs if os.path.exists(os.path.join(TS, "answers", s, f"{tid}.md"))]
            if len(avail) < 2:
                print(f"{tid}: 回答不足两方（有 {avail}），跳过——tally 会把它记为缺格，S7 不算完成"); key["skipped"][tid] = avail; continue
            texts = {s: C.read_text(os.path.join(TS, "answers", s, f"{tid}.md")) for s in avail}
            L = [f"# 盲评包 {tid}（{ts}）", ""]; key["tasks"][tid] = {}
            for q, k, t in qs:
                order = avail[:]; random.shuffle(order); labels = "甲乙丙丁"[:len(order)]; key["tasks"][tid][q] = dict(zip(labels, order))
                L += [f"## {q} {k}：{t}", ""]
                for lab, s in zip(labels, order):
                    m = re.search(r"(?ms)^#+\s*" + q + r"\b.*?(?=^#+\s*Q\d+\b|\Z)", texts[s]); ans = m.group(0) if m else f"（{q} 未在回答文件里找到独立小节）"
                    ans = re.sub(r"(?m)^#+\s*" + q + r"[^\n]*\n", "", ans).strip()
                    L += [f"### 回答{lab}", "", ans, ""]
            C.write_text(os.path.join(TS, "packets", f"{tid}.md"), "\n".join(L))
            mp = C.W(P, "kb", "packs", tid, "methods.md")
            summary = pack_summary(mp) if os.path.exists(mp) else "（路由器题：无知识包摘要；只看路由对不对）"
            for j in (1, 2):
                slots = {"project": P, "judge_no": j, "task": tid, "testset_dir": rel, "packet_path": f"{rel}/packets/{tid}.md", "pack_summary": summary, "notes": note or "（题集无附加说明）", "score_out": f"{rel}/scores/{tid}-J{j}.md"}
                outs.append(C.fill_prompt("evaluate-judge", slots, f"evaluate-judge-{ts}-{tid}-J{j}", P))
        C.write_json(os.path.join(TS, "key.json"), key)
        nq = sum(len(v) for v in key["tasks"].values())
        print(f"盲评包 {len(key['tasks'])} 任务 {nq} 题（含路由器：{'是' if 'router' in key['tasks'] else '否'}）；评委提示词 {len(outs)} 份（两位评委）。评委不读 key.json、不读 answers/。")
        for x in outs:
            print(" ", os.path.relpath(x, P))
        return
    # tally：任务 × 题 × 来源 × 两评委 的完整矩阵；缺一格、重复、非法、总分≠五维和 都显式拒绝
    kp = os.path.join(TS, "key.json"); C.need(kp, f"blind_eval judge --testset {ts}")
    key = C.read_json(kp); sd = os.path.join(TS, "scores"); rows = []; problems = []
    if "tasks" not in key:
        C.die("key.json 是旧格式（按题号、没按任务）：重跑 `blind_eval judge` 生成新 key 与评委提示词")
    judges = key.get("judges", [1, 2])
    for tid, avail in key.get("skipped", {}).items():
        problems.append(f"{tid}：judge 时回答不足两方（有 {avail}），整任务没有盲评包")
    for tid in Q:
        if tid not in key["tasks"] and tid not in key.get("skipped", {}):
            problems.append(f"{tid}：题集里有它，key.json 里没有（judge 后题集改过？重跑 judge）")
    for tid, qmap in key["tasks"].items():
        for j in judges:
            fpath = os.path.join(sd, f"{tid}-J{j}.md")
            if not os.path.exists(fpath):
                problems.append(f"{tid}-J{j}.md：评委 {j} 的评分文件缺失（{len(qmap)} 题共 {sum(len(v) for v in qmap.values())} 格全缺）"); continue
            parsed, bad = C.parse_score_rows(C.read_text(fpath))
            for b in bad:
                b = " ".join(str(x) for x in b) if isinstance(b, (tuple, list)) else str(b)
                problems.append(f"{tid}-J{j}.md：非法评分行 {b}（五维各 0–5、总分 = 五维之和）")
            seen = collections.Counter()
            for q, lab, dims, total, layer in parsed:
                if q not in qmap:
                    problems.append(f"{tid}-J{j}.md {q}：题号不在盲评包里"); continue
                src = qmap[q].get(lab)
                if not src:
                    problems.append(f"{tid}-J{j}.md {q} 标签 {lab}：这题只有 {''.join(qmap[q])}"); continue
                seen[(q, lab)] += 1
                if seen[(q, lab)] > 1:
                    problems.append(f"{tid}-J{j}.md {q} {lab}：重复评分（{seen[(q, lab)]} 次）"); continue
                rows.append({"task": tid, "judge": j, "q": q, "label": lab, "source": src, "dims": dims, "total": total, "layer": layer})
            for q, labs in qmap.items():
                for lab, src in labs.items():
                    if (q, lab) not in seen:
                        problems.append(f"{tid}-J{j}.md {q} 回答{lab}（{SRC_NAME.get(src, src)}）：缺格")
    complete = not problems
    C.write_json(os.path.join(TS, "scores.json"), {"testset": ts, "complete": complete, "judges": judges, "rows": rows, "problems": problems})
    by = collections.defaultdict(list)
    for r in rows:
        by[r["source"]].append(r["total"])
    exp = sum(len(labs) for qmap in key["tasks"].values() for labs in qmap.values()) * len(judges)
    print(f"评分格 {len(rows)}/{exp}（任务 {len(key['tasks'])} × 题 × 来源 × 评委 {len(judges)}）| " + " | ".join(f"{SRC_NAME.get(s, s)} 均分 {sum(v)/len(v):.2f}（n={len(v)}）" for s, v in by.items()))
    for p in problems:
        print("缺/错：", p)
    unm = sum(1 for r in rows if r["layer"] == "unmapped"); print(f"扣分层 unmapped {unm}/{len(rows)}")
    C.record_stage(P, f"tally:{ts}", C.tally_inputs(P, ts), ok=complete, extra={"problems": len(problems), "cells": len(rows), "expected": exp})
    if not complete:
        print(f"矩阵不完整，S7 不算完成：补齐上面每一格再重跑 tally（不许用均分掩盖缺格）"); sys.exit(1)
    print(f"矩阵完整；接着 `beiming.py evaluate report --testset {ts}`")

if __name__ == "__main__":
    main()
