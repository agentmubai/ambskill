# -*- coding: utf-8 -*-
"""轻验收：出题 / 答题 / 盲评 / 汇总 四个动作的提示词生成与解析。
用法：python3 blind_eval.py questions|answers|judge|tally [--testset 常备] [--sources bare,new] [--new <skills 目录>] [--project P]
  questions  出题提示词（出题者不读技能，题里不出现类型名、句式）→ work/tests/<题集>/questions.md 由子代理写；每类型 2 题，路由器 2 题
  answers    每个 (来源, 类型) 一份答题提示词；来源：bare 裸模型 / new 新成品
  judge      每题各来源回答打乱成 甲乙 → packets/<类型>.md + key.json；两位评委各一份提示词
  tally      解析 scores/<类型>-J*.md 的评分行 → scores.json；矩阵缺格显式列出
轻验收 = 不设 PASS / WEAK 硬门，只出差距报告；但矩阵必须完整，缺格不许用均分掩盖。"""
import os, sys, re, random, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

SRC_NAME = {"bare": "裸模型", "new": "新成品"}

def parse_questions(path):
    txt = C.read_text(path); out = collections.OrderedDict(); note = (re.search(r"(?ms)^(## 出题原则.*?)(?=^## \S)", txt) or [None, ""])[1].strip()
    for block in re.split(r"(?m)^## ", txt)[1:]:
        head = block.splitlines()[0].strip(); key = head.split()[0]
        if key == "出题原则":
            continue
        qs = re.findall(r"(?m)^- (Q\d+)\s+([^：:\n]+)[：:]\s*(.+)$", block)
        out[key] = [(q, k.strip(), t.strip()) for q, k, t in qs]
    return out, note

def main():
    usage = "用法：blind_eval.py questions|answers|judge|tally [--testset 常备] [--sources bare,new] [--new 目录] [--project P]"
    pos, o, f = C.parse_args(sys.argv[1:], opts=("--testset", "--sources", "--new"), usage=usage)
    ts = o.get("--testset", "常备"); srcs = o.get("--sources", "bare,new").split(","); P = C.project_root(o.get("--project"))
    new = o.get("--new") or C.W(P, "draft", "skills"); act = pos[0] if len(pos) == 1 else None
    if act not in ("questions", "answers", "judge", "tally"):
        C.die(usage)
    if act != "tally":
        C.stop_guard(P)
    prefix = C.project_meta(P).get("prefix") or C.DEFAULT_PREFIX; pairs = C.all_confirmed_types(P)
    if not pairs:
        C.die("没有已确认的类型")
    keys = [C.ft_key(fm, t["id"]) for fm, t in pairs]
    TS = C.W(P, "tests", ts); os.makedirs(TS, exist_ok=True); rel = os.path.relpath(TS, P)
    if act == "questions":
        listing = "\n".join(f"- {C.ft_key(fm, t['id'])}　形态 {fm}｜类型 {t['name']}：{t.get('brief','')}" for fm, t in pairs) + "\n- router 路由器（先判形态再判类型）"
        slots = {"project": P, "testset": ts, "type_list": listing, "questions_out": f"{rel}/questions.md", "precheck_path": "work/docs/预检报告.md",
                 "cards": "\n".join(f"- work/docs/类型卡-{fm}.md" for fm in sorted({fm for fm, _ in pairs}))}
        print(os.path.relpath(C.fill_prompt("evaluate-questions", slots, f"evaluate-questions-{ts}", P), P), "（派一个子代理出题）"); return
    qpath = os.path.join(TS, "questions.md"); C.need(qpath, f"blind_eval questions --testset {ts} 并派子代理")
    Q, note = parse_questions(qpath)
    if act == "answers":
        outs = []
        for key, qs in Q.items():
            skill = prefix if key == "router" else f"{prefix}-{key}"
            qtext = "\n".join(f"- {q} {k}：{t}" for q, k, t in qs)
            for s in srcs:
                if s == "bare":
                    role = "你是一位常年替人写这类内容的老手，只凭自己的经验回答。不读任何文件。"
                elif s == "new":
                    role = f"你要扮演技能 `{os.path.relpath(new, P)}/{skill}/SKILL.md`：先完整读它，再按它写明的方式读它的 references（按编号定位），然后严格按它的流程逐题回答，像真被调用一样。不读原件库、不读其他来源的回答。"
                else:
                    C.die(f"来源 {s} 不认识（bare / new）")
                slots = {"project": P, "role_block": role, "source": s, "key": key, "testset_dir": rel, "questions": qtext, "answer_out": f"{rel}/answers/{s}/{key}.md"}
                outs.append(C.fill_prompt("evaluate-answer", slots, f"evaluate-answer-{ts}-{s}-{key}", P))
        print(f"生成 {len(outs)} 份答题提示词（{','.join(srcs)} × {len(Q)}）。同一轮所有来源用同一个答题模型。")
        for x in outs:
            print(" ", os.path.relpath(x, P))
        return
    if act == "judge":
        key = {"testset": ts, "judges": [1, 2], "tasks": {}, "skipped": {}}; outs = []; random.seed(ts)
        for k, qs in Q.items():
            avail = [s for s in srcs if os.path.exists(os.path.join(TS, "answers", s, f"{k}.md"))]
            if len(avail) < 2:
                print(f"{k}: 回答不足两方（有 {avail}），跳过——tally 会记为缺格"); key["skipped"][k] = avail; continue
            texts = {s: C.read_text(os.path.join(TS, "answers", s, f"{k}.md")) for s in avail}
            L = [f"# 盲评包 {k}（{ts}）", ""]; key["tasks"][k] = {}
            for q, kind, t in qs:
                order = avail[:]; random.shuffle(order); labels = "甲乙丙丁"[:len(order)]; key["tasks"][k][q] = dict(zip(labels, order))
                L += [f"## {q} {kind}：{t}", ""]
                for lab, s in zip(labels, order):
                    m = re.search(r"(?ms)^#+\s*" + q + r"\b.*?(?=^#+\s*Q\d+\b|\Z)", texts[s]); ans = m.group(0) if m else f"（{q} 未在回答文件里找到独立小节）"
                    ans = re.sub(r"(?m)^#+\s*" + q + r"[^\n]*\n", "", ans).strip()
                    L += [f"### 回答{lab}", "", ans, ""]
            C.write_text(os.path.join(TS, "packets", f"{k}.md"), "\n".join(L))
            # 评委只看结构摘要（小段名），不看魂、句式与例——防止按“像不像原文”打分而不是按“成品能不能用”
            summary = "（路由器题：只看归对没归对）"
            if k != "router":
                sk = os.path.join(C.pack_dir(P, k), C.PATTERN)
                if os.path.exists(sk):
                    pt = C.read_text(sk)
                    heads = [f"第 {n} 小段 {name}（{ {'open': '开头', 'mid': '中间', 'close': '结尾'}.get(big, '') }）" for n, name, _, big in C.segments(pt)]
                    # 路数：魂条的选择句（去掉「」原话与编号，评委不该看到范文）+ 禁区
                    soul = C.chapter(pt, "soul") or ""
                    picks = []
                    for b in re.findall(r"(?m)^- \*\*(.+?)\*\*", soul):
                        picks.append(re.sub(r"「[^」]*」|[（(]" + C.ORIG_ID + r"[)）]", "", b).strip("。 "))
                    ban = re.search(r"(?m)^- \*\*禁区[^*]*\*\*[：:]?\s*(.+)$", soul)
                    summary = "结构：\n" + ("\n".join(f"- {h}" for h in heads[:12]) or "- （写法书里没解析出小段）")
                    summary += "\n路数：\n" + ("\n".join(f"- {p}" for p in picks[:8]) or "- （无）") + (f"\n禁区：{ban.group(1).strip()}" if ban else "")
            for j in (1, 2):
                slots = {"project": P, "judge_no": j, "key": k, "testset_dir": rel, "packet_path": f"{rel}/packets/{k}.md", "skeleton_summary": summary, "notes": note or "（题集无附加说明）", "score_out": f"{rel}/scores/{k}-J{j}.md"}
                outs.append(C.fill_prompt("evaluate-judge", slots, f"evaluate-judge-{ts}-{k}-J{j}", P))
        C.write_json(os.path.join(TS, "key.json"), key)
        print(f"盲评包 {len(key['tasks'])} 个，评委提示词 {len(outs)} 份（两位评委）。评委不读 key.json、不读 answers/。")
        for x in outs:
            print(" ", os.path.relpath(x, P))
        return
    # tally
    kp = os.path.join(TS, "key.json"); C.need(kp, f"blind_eval judge --testset {ts}")
    key = C.read_json(kp); sd = os.path.join(TS, "scores"); rows = []; problems = []
    judges = key.get("judges", [1, 2])
    for k, avail in key.get("skipped", {}).items():
        problems.append(f"{k}：judge 时回答不足两方（有 {avail}）")
    for k in Q:
        if k not in key["tasks"] and k not in key.get("skipped", {}):
            problems.append(f"{k}：题集里有它，key.json 里没有（judge 后题集改过？重跑 judge）")
    for k, qmap in key["tasks"].items():
        for j in judges:
            fpath = os.path.join(sd, f"{k}-J{j}.md")
            if not os.path.exists(fpath):
                problems.append(f"{k}-J{j}.md：评委 {j} 的评分文件缺失"); continue
            parsed, bad = C.parse_score_rows(C.read_text(fpath))
            for b in bad:
                problems.append(f"{k}-J{j}.md：非法评分行 {' '.join(str(x) for x in b)}（五维各 0–5、总分 = 五维之和）")
            seen = collections.Counter()
            for q, lab, dims, total, where in parsed:
                if q not in qmap:
                    problems.append(f"{k}-J{j}.md {q}：题号不在盲评包里"); continue
                src = qmap[q].get(lab)
                if not src:
                    problems.append(f"{k}-J{j}.md {q} 标签 {lab}：这题只有 {''.join(qmap[q])}"); continue
                seen[(q, lab)] += 1
                if seen[(q, lab)] > 1:
                    problems.append(f"{k}-J{j}.md {q} {lab}：重复评分"); continue
                rows.append({"key": k, "judge": j, "q": q, "label": lab, "source": src, "dims": dims, "total": total, "where": where})
            for q, labs in qmap.items():
                for lab, src in labs.items():
                    if (q, lab) not in seen:
                        problems.append(f"{k}-J{j}.md {q} 回答{lab}（{SRC_NAME.get(src, src)}）：缺格")
    complete = not problems
    C.write_json(os.path.join(TS, "scores.json"), {"testset": ts, "complete": complete, "judges": judges, "rows": rows, "problems": problems})
    by = collections.defaultdict(list)
    for r in rows:
        by[r["source"]].append(r["total"])
    exp = sum(len(labs) for qmap in key["tasks"].values() for labs in qmap.values()) * len(judges)
    print(f"评分格 {len(rows)}/{exp} | " + " | ".join(f"{SRC_NAME.get(s, s)} 均分 {sum(v)/len(v):.2f}（n={len(v)}）" for s, v in by.items()))
    for p in problems:
        print("缺/错：", p)
    C.record_stage(P, f"tally:{ts}", C.tally_inputs(P, ts), ok=complete, extra={"problems": len(problems), "cells": len(rows), "expected": exp})
    if not complete:
        print("矩阵不完整：补齐每一格再重跑 tally（不许用均分掩盖缺格）"); sys.exit(1)
    print(f"矩阵完整；接着 `paoding.py evaluate report --testset {ts}`")

if __name__ == "__main__":
    main()
