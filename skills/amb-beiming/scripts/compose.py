# -*- coding: utf-8 -*-
"""S6 成技派发：为每个任务建草稿目录、复制 references 三件、生成写技能的提示词；--router 生成路由器提示词。
用法：python3 compose.py <任务id,…|all> [--project P]
      python3 compose.py --router [--project P]
      python3 compose.py <任务id,…|all> --sync-refs [--project P]   只把知识包三件重新复制进草稿 references，不生成提示词（S9 增量改完知识包后用）
门槛：任务的 check-layers 记录为通过且未过期，否则不派（六层没核对过的不许进技能）。
产出：work/draft/skills/<前缀>-<任务>/references/{methods,cases,layers}.md（复制自知识包，不改内容）；work/prompts/compose-<任务>.md。
草稿技能自带 scripts/fact_check.py（复制自本技能 assets/），成品每个技能独立可装，不依赖工具箱根目录的共享脚本。"""
import os, sys, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

USAGE = "用法：compose.py <任务id,…|all> [--sync-refs] [--project P] | compose.py --router [--project P]"
REFS = (("methods.md", "methods.md"), ("cards.md", "cases.md"), ("layers.md", "layers.md"))

def sync_refs(P, tid, sd):
    """知识包 → 草稿 references 三件 + scripts/fact_check.py；返回复制的文件数。"""
    pack = C.W(P, "kb", "packs", tid); rd = os.path.join(sd, "references"); os.makedirs(rd, exist_ok=True); n = 0
    for src, dst in REFS:
        C.need(os.path.join(pack, src), f"distill {tid}（缺 {src}）")
        shutil.copy2(os.path.join(pack, src), os.path.join(rd, dst)); n += 1
    fc = os.path.join(C.SKILL_DIR, "assets", "fact_check.py")
    if os.path.exists(fc):
        os.makedirs(os.path.join(sd, "scripts"), exist_ok=True); shutil.copy2(fc, os.path.join(sd, "scripts", "fact_check.py")); n += 1
    return n

def main():
    pos, o, f = C.parse_args(sys.argv[1:], flags=("--router", "--sync-refs"), usage=USAGE)
    P = C.project_root(o.get("--project")); router = "--router" in f; sync = "--sync-refs" in f
    T = C.tasks(P); prefix = T.get("prefix") or C.die("tasks.json 缺 prefix"); spec = os.path.join(C.SKILL_DIR, "references", "product-spec.md")
    draft = C.W(P, "draft", "skills"); outs = []
    if router and (pos or sync):
        C.die(USAGE)
    if not router and len(pos) != 1:
        C.die(USAGE)
    if sync:
        for tid in C.split_names(pos[0], [t["id"] for t in T["tasks"]]):
            sd = os.path.join(draft, f"{prefix}-{tid}")
            C.need(os.path.join(sd, "SKILL.md"), f"compose {tid} 并派子代理（草稿还不存在，不是同步的场景）")
            n = sync_refs(P, tid, sd); print(f"{tid}: 已同步 {n} 个文件 → {os.path.relpath(sd, P)}/references/ 与 scripts/")
        C.pipeline_log(P, "S9", f"compose --sync-refs：{pos[0]}")
        print("同步后重新 `beiming.py lint`（引文核验会按新 references 重跑）")
        return
    C.stop_guard(P)
    if router:
        rows = []
        for t in T["tasks"]:
            d = os.path.join(draft, f"{prefix}-{t['id']}", "SKILL.md")
            C.need(d, f"compose {t['id']} 并派子代理（路由器最后写）")
            rows.append(f"- `{prefix}-{t['id']}`（{t.get('name','')}）：输入 {t.get('input','')}；判断 {t.get('judge','')}；交付 {t.get('deliver','')}")
        rd = os.path.join(draft, prefix); os.makedirs(rd, exist_ok=True)
        slots = {"project": P, "skill_dir": C.SKILL_DIR, "prefix": prefix, "router_dir": os.path.relpath(rd, P), "task_list": "\n".join(rows),
                 "spec_path": os.path.relpath(spec, P), "plan_path": "work/docs/能力方案.md", "report_out": "work/reports/compose-router.md"}
        outs.append(C.fill_prompt("compose-router", slots, "compose-router", P))
    else:
        for tid in C.split_names(pos[0], [t["id"] for t in T["tasks"]]):
            t = C.task_by_id(P, tid); pack = C.W(P, "kb", "packs", tid)
            st = C.stage_state(P, f"check_layers:{tid}", C.layers_inputs(P, tid))
            if st != "ok":
                C.die(f"{tid} 的六层核对状态是 {st}：先 `beiming.py check-layers {tid}` 通过再成技"
                      + ("（cards.md 在核对之后才写或又改过，卡里的引文还没核）" if st == "stale" else ""))
            sd = os.path.join(draft, f"{prefix}-{tid}"); sync_refs(P, tid, sd); rd = os.path.join(sd, "references")
            neighbors = "\n".join(f"- `../{prefix}-{x['id']}/SKILL.md`（{x.get('name','')}）：{x.get('judge','')}" for x in T["tasks"] if x["id"] != tid) or "- （只有这一个任务）"
            slots = {"project": P, "skill_dir": C.SKILL_DIR, "task": tid, "domain": t.get("domain", t.get("name", tid)), "prefix": prefix,
                     "skill_name": f"{prefix}-{tid}", "skill_dir_out": os.path.relpath(sd, P), "refs_dir": os.path.relpath(rd, P),
                     "pool_dir": os.path.relpath(C.W(P, "kb", "pools", tid), P), "spec_path": os.path.relpath(spec, P), "plan_path": "work/docs/能力方案.md",
                     "neighbors": neighbors, "report_out": f"work/reports/compose-{tid}.md"}
            outs.append(C.fill_prompt("compose-skill", slots, f"compose-{tid}", P))
    print(f"生成 {len(outs)} 份提示词：")
    for x in outs:
        print(" ", os.path.relpath(x, P))
    C.pipeline_log(P, "S6", f"compose{' --router' if router else ''}：{len(outs)} 份提示词")
    if C.agent_name() != "none":
        import run_stage; run_stage.run(P, [os.path.basename(x)[:-3] for x in outs])
    else:
        print("宿主子代理模式：每份提示词派一个子代理；全部回来后 `beiming.py lint`")

if __name__ == "__main__":
    main()
