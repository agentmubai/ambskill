# -*- coding: utf-8 -*-
"""六层粗筛：从任务池筛出交给归层子代理的候选；模型只在候选里选，脚本事后逐字核对（check_layers）。
用法：python3 screen_layers.py <任务id,…|all> [--project P]
输入：pools/<任务>/{atoms,units}.jsonl；packs/<任务>/methods.md（模块标题 M01…）与 case_map.md（可缺，缺则退化为全池）。
产出 work/kb/layers_input/<任务>/：
  hit_units.jsonl        对照表命中的单元全文（案例卡子代理的输入）
  dao_shu_candidates.md  道/术候选：作者原话里的判断句（绝对词 / 数字 / 跨来源重复 / 原则-方法类型加分，例句特征减分），去近似重复，最多 60 条
  principle_hints.md     原话里出现经典原理名词的句子（外源原理用）
  shi_candidates.md      原话里提到平台 / 规则 / 年份的句子（势层用）
  zheng.md               法 → 案例单元 表（证层，直接贴进六层）"""
import os, sys, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C, case_library as CL

ABS = re.compile(r"一定|必须|只有|只要|永远|从来|没有第二|就是|叫做|本质|核心|第一步|先.{1,12}再|不要|别去|不能|不是.{1,10}是|凡是|所有|任何|100%|一律|默认|前提"
                 r"|一般都|往往|大多|通常|很难|几乎|反常识|底层|真正的|说白了|归根|最重要|千万")  # 后一行是软绝对词：口语作者常用"一般都""很难"表达判断；通用启发式，按语料补词
NUM = re.compile(r"\d+\s*[%秒天条个次倍块元人段句年万分]|[一二三四五六七八九十百千]+[个条秒天次倍块元人段句年]")
EX = re.compile(r"^(我在|我们家|我的|有人说|比如|例如|当你说|举个|像我|我这个|我有个|他说|你看这个)")
NAMES = ["定位", "心智", "漏斗", "二八", "复利", "峰终", "锚定", "损失厌恶", "从众", "稀缺", "互惠", "马斯洛", "供需", "LTV", "飞轮", "第一性", "MVP", "精益", "长尾", "框架效应", "禀赋", "杠杆", "规模效应", "边际", "沉没成本", "机会成本", "心流", "刻意练习", "复盘", "最小可行", "金字塔", "SCQA", "AIDA", "4P", "SWOT", "OKR", "PDCA"]
SHI = re.compile(r"平台|规则|限流|违禁|违规|封号|投放|投流|算法|推荐机制|流量池|权重|20[12]\d|去年|今年|现在.{0,6}(改|变|新)|以前|新规|审核|团购|小店|千川|巨量|dou\+|抖\+")

def grams(s):
    s = re.sub(r"[^一-龥A-Za-z0-9]", "", s); return {s[i:i + 2] for i in range(len(s) - 1)}

def main():
    pos, o_, f_ = C.parse_args(sys.argv[1:], usage="用法：screen_layers.py <任务id,…|all> [--project P]")
    P = C.project_root(o_.get("--project"))
    if len(pos) != 1:
        C.die("用法：screen_layers.py <任务id,…|all> [--project P]")
    T = C.tasks(P)
    for tid in C.split_names(pos[0], [t["id"] for t in T["tasks"]]):
        pool = C.W(P, "kb", "pools", tid); pack = C.W(P, "kb", "packs", tid); out = C.W(P, "kb", "layers_input", tid); os.makedirs(out, exist_ok=True)
        C.need(os.path.join(pool, "atoms.jsonl"), "repool")
        atoms = [x for x in C.read_jsonl(os.path.join(pool, "atoms.jsonl")) if "_bad_json" not in x]
        units = [x for x in C.read_jsonl(os.path.join(pool, "units.jsonl")) if "_bad_json" not in x]
        mapping = CL.read_map(os.path.join(pack, "case_map.md"))
        # 一个单元对多个模块：modules 保留全部对照，不覆盖
        sel = [dict(u, modules=[{"module": m, "why": w} for m, w in mapping[u["unit_id"]] if m and m != "—"]) for u in units if CL.mapped(mapping, u["unit_id"])]
        C.write_jsonl(os.path.join(out, "hit_units.jsonl"), sel)
        bymod = collections.defaultdict(list)
        for u in sel:
            for mw in u["modules"]:
                bymod[mw["module"].split(" ")[0].split("：")[0]].append((u["unit_id"], mw["why"]))
        Z = ["## 四、证（脚本从案例对照表生成；原样贴进六层）", "", "> 证只用来选法和说明为什么，永远不进使用者的稿。每条：法 → 案例卡 unit_id → 它证明什么。卡在 cards.md。", ""]
        Z += [f"- **{m}**：" + "；".join(f"`{u}`（{w[:40]}）" for u, w in items[:4]) for m, items in sorted(bymod.items())] or ["- （对照表为空：pack 子代理写完 case_map.md 再跑一次 screen）"]
        C.write_text(os.path.join(out, "zheng.md"), "\n".join(Z) + "\n")
        # 道/术候选
        byid = {x["id"]: x for x in atoms}; G = {i: grams(x.get("knowledge", "")) for i, x in byid.items()}
        cands = {}
        mp = os.path.join(pack, "methods.md")
        if os.path.exists(mp):
            for b in re.split(r"(?m)^(?=#{2,4}\s)", C.read_text(mp)):
                h = re.match(r"#{2,4}\s*(.+)", b)
                if not h or not re.match(r"M\d{1,3}\b", h.group(1).strip()):
                    continue
                mod = h.group(1).strip().split("：")[0].split(" ")[0]
                for i in re.findall(C.ATOM_ID, "\n".join(l for l in b.splitlines() if "依据" in l)):
                    x = byid.get(i)
                    if x and x.get("role") not in ("学员", "主持", "未知") and 10 <= len(x.get("original", "")) <= 160 and i not in cands:
                        cands[i] = mod
        if not cands:
            cands = {x["id"]: "" for x in atoms if x.get("role") not in ("学员", "主持", "未知") and 10 <= len(x.get("original", "")) <= 160}
        scored = []
        for i, mod in cands.items():
            x = byid[i]; o = re.sub(r"\s*\n\s*", " ", x["original"].strip()); g = G[i]; groups = set()
            for j, gj in G.items():
                if j != i and len(g & gj) and len(g & gj) / max(1, min(len(g), len(gj))) >= 0.5:
                    groups.add(j[1:3])
            rep = len(groups - {i[1:3]})
            if not (ABS.search(o) or NUM.search(o)):
                continue
            sc = (2 if x.get("type") in ("principle", "method") else 0) + (2 if x.get("claim_scope") == "无条件主张" else 0) + (2 if ABS.search(o) else 0) + min(rep, 3) + (1 if NUM.search(o) else 0) + (1 if x.get("confidence") == "high" else 0) - (3 if EX.search(o) else 0)
            scored.append((-sc, len(o), i, mod, rep, o, x))
        scored.sort(); rows = [f"# {tid} 道/术候选（脚本粗筛，作者原话逐字；模型只在此选道与术）", "", "| # | 原子 id | 模块 | claim_scope | 跨组重复 | 置信 | 原话 | 书面陈述 |", "|---|---|---|---|---|---|---|---|"]
        seen, n = [], 0
        for _, _, i, mod, rep, o, x in scored:
            g = grams(o)
            if any(len(g & s) / max(1, min(len(g), len(s))) >= 0.6 for s in seen):
                continue
            seen.append(g); n += 1
            rows.append(f"| {n} | {i} | {mod} | {x.get('claim_scope','')} | {rep} | {x.get('confidence')} | {o.replace('|','｜')} | {x.get('knowledge','').strip().replace('|','｜')} |")
            if n >= 60:
                break
        C.write_text(os.path.join(out, "dao_shu_candidates.md"), "\n".join(rows) + "\n")
        pr = ["| 原子 id | 命中词 | 原话 | 书面陈述 |", "|---|---|---|---|"]; sh = ["| 原子 id | 来源 | 时间 | 原话 |", "|---|---|---|---|"]
        for x in atoms:
            if x.get("role") in ("学员", "主持", "未知") or not (10 <= len(x.get("original", "")) <= 200):
                continue
            o = re.sub(r"\s*\n\s*", " ", x["original"].strip()).replace("|", "｜"); ns = [w for w in NAMES if w in o]
            if ns and len(pr) < 82:
                pr.append(f"| {x['id']} | {','.join(ns)} | {o} | {x.get('knowledge','').strip().replace('|','｜')} |")
            if SHI.search(o) and len(sh) < 72:
                s = x.get("source", {}); sh.append(f"| {x['id']} | {s.get('group','')[:30]} | {s.get('timestamp','')} | {o} |")
        C.write_text(os.path.join(out, "principle_hints.md"), "\n".join(pr) + "\n"); C.write_text(os.path.join(out, "shi_candidates.md"), "\n".join(sh) + "\n")
        print(f"{tid}: 命中单元 {len(sel)} | 道/术候选 {n}（法 {len(set(cands.values()) - {''})}）| 原理线索 {len(pr)-2} | 势候选 {len(sh)-2} → work/kb/layers_input/{tid}/")

if __name__ == "__main__":
    main()
