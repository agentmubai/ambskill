# -*- coding: utf-8 -*-
"""S5 蒸馏派发：为任务生成三种提示词之一（每任务一份，派一个子代理）。
用法：python3 distill.py <任务id,… | all> --step pack|layers|cards [--project P]
  pack    知识包：读任务池 → work/kb/packs/<任务>/methods.md（方法论）+ case_map.md（案例对照表）
  layers  六层归层：先跑 screen 与 caselib，读候选 → packs/<任务>/layers.md
  cards   案例卡：读 layers_input/<任务>/hit_units.jsonl → packs/<任务>/cards.md
顺序：pack → caselib → screen → layers → cards → check-layers → index。缺前置文件即停并告诉你先做哪一步。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

def main():
    usage = "用法：distill.py <任务id,…|all> --step pack|layers|cards [--project P]"
    pos, o, f = C.parse_args(sys.argv[1:], opts=("--step",), usage=usage)
    step = o.get("--step"); P = C.project_root(o.get("--project"))
    if len(pos) != 1 or step not in ("pack", "layers", "cards"):
        C.die(usage)
    C.stop_guard(P)
    T = C.tasks(P); ids = C.split_names(pos[0], [t["id"] for t in T["tasks"]])
    outs = []
    for tid in ids:
        t = C.task_by_id(P, tid); pool = C.W(P, "kb", "pools", tid); pack = C.W(P, "kb", "packs", tid); li = C.W(P, "kb", "layers_input", tid)
        os.makedirs(pack, exist_ok=True)
        base = {"project": P, "skill_dir": C.SKILL_DIR, "task": tid, "domain": t.get("domain", t.get("name", tid)),
                "pool_dir": os.path.relpath(pool, P), "pack_dir": os.path.relpath(pack, P), "plan_path": "work/docs/能力方案.md",
                "report_out": f"work/reports/distill-{step}-{tid}.md"}
        if step == "pack":
            C.need(os.path.join(pool, "atoms.jsonl"), "repool")
            size = sum(os.path.getsize(os.path.join(pool, x)) for x in ("atoms.jsonl", "units.jsonl") if os.path.exists(os.path.join(pool, x)))
            outs.append(C.fill_prompt("distill-pack", base, f"distill-pack-{tid}", P))
            print(f"  {tid} 池体量约 {size // 1000:,} KB（原子 + 单元 JSONL）" + ("——超过 400 KB（约 15 万字）：子代理一次读不完，把 atoms.jsonl 按 id 前缀（文件）拆成两半分两次派，第二次带上第一次的 methods.md 续写" if size > 400_000 else ""))
        elif step == "layers":
            C.need(os.path.join(pack, "methods.md"), f"distill {tid} --step pack 并派子代理")
            C.need(os.path.join(li, "dao_shu_candidates.md"), f"beiming.py screen {tid}（先 caselib 再 screen）")
            outs.append(C.fill_prompt("distill-layers", {**base, "layers_input_dir": os.path.relpath(li, P), "layers_out": os.path.relpath(os.path.join(pack, "layers.md"), P)}, f"distill-layers-{tid}", P))
        else:
            C.need(os.path.join(li, "hit_units.jsonl"), f"beiming.py screen {tid}")
            outs.append(C.fill_prompt("distill-cards", {**base, "hit_units": os.path.relpath(os.path.join(li, "hit_units.jsonl"), P), "cards_out": os.path.relpath(os.path.join(pack, "cards.md"), P)}, f"distill-cards-{tid}", P))
    print(f"生成 {len(outs)} 份 {step} 提示词：")
    for o in outs:
        print(" ", os.path.relpath(o, P))
    C.pipeline_log(P, "S5", f"distill --step {step}：{len(outs)} 份提示词（{','.join(ids)}）")
    if C.agent_name() != "none":
        import run_stage; run_stage.run(P, [os.path.basename(o)[:-3] for o in outs])
    else:
        print("宿主子代理模式：每份提示词派一个子代理；" + {"pack": "回来后 `beiming.py caselib <任务>` 与 `beiming.py screen <任务>`", "layers": "回来后 `beiming.py check-layers <任务>`", "cards": "回来后 `beiming.py index`"}[step])

if __name__ == "__main__":
    main()
