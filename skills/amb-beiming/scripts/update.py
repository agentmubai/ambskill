# -*- coding: utf-8 -*-
"""S9 增量派发：新料走完 survey --update → extract → settle → merge → repool 后，为每个任务生成"覆盖对照 + 冲突表 + 应用改动"的提示词。
用法：python3 update.py <任务id,…|all> --groups g05,g06 [--project P]
  --groups  本次新增的来源组（新原子按 id 前缀识别；只对照这些，不重写全包）
产出：work/prompts/update-<任务>.md；子代理写 work/docs/更新对照-<任务>.md、work/docs/冲突表-<任务>.md（每任务一份，多任务并行不共写），并改知识包。
子代理只改知识包（packs/），不直接改草稿技能的 references：改完由 `compose <任务> --sync-refs` 复制过去，保证知识包与技能一致。
改完必须重跑 check-layers → compose --sync-refs → lint → 常备题集回归；WEAK 掉回去就回滚。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

USAGE = "用法：update.py <任务id,…|all> --groups g05,g06 [--project P]"

def main():
    pos, o, f = C.parse_args(sys.argv[1:], opts=("--groups",), usage=USAGE)
    groups = o["--groups"].split(",") if o.get("--groups") else None
    P = C.project_root(o.get("--project"))
    if len(pos) != 1 or not groups:
        C.die(USAGE)
    C.stop_guard(P)
    T = C.tasks(P); prefix = T["prefix"]; outs = []
    for tid in C.split_names(pos[0], [t["id"] for t in T["tasks"]]):
        t = C.task_by_id(P, tid); pool = C.W(P, "kb", "pools", tid, "atoms.jsonl"); C.need(pool, "repool（新料合并后重建任务池）")
        new_ids = [x["id"] for x in C.read_jsonl(pool) if "_bad_json" not in x and ("g" + x["id"][1:3]) in groups]
        if not new_ids:
            print(f"{tid}: 新组里没有归到本任务的原子，跳过"); continue
        slots = {"project": P, "skill_dir": C.SKILL_DIR, "task": tid, "domain": t.get("domain", t.get("name", tid)), "pool_dir": os.path.relpath(os.path.dirname(pool), P),
                 "pack_dir": f"work/kb/packs/{tid}", "skill_dir_out": f"work/draft/skills/{prefix}-{tid}", "new_ids": f"{len(new_ids)} 条：" + ", ".join(new_ids[:400]) + (" …" if len(new_ids) > 400 else ""),
                 "compare_out": f"work/docs/更新对照-{tid}.md", "conflict_out": f"work/docs/冲突表-{tid}.md", "report_out": f"work/reports/update-{tid}.md"}
        outs.append(C.fill_prompt("update", slots, f"update-{tid}", P))
    print(f"生成 {len(outs)} 份增量提示词：")
    for x in outs:
        print(" ", os.path.relpath(x, P))
    C.pipeline_log(P, "S9", f"update：{len(outs)} 份提示词，新组 {','.join(groups)}")
    if C.agent_name() != "none":
        import run_stage; run_stage.run(P, [os.path.basename(x)[:-3] for x in outs])
    else:
        print("宿主子代理模式：每份提示词派一个子代理；回来后 check-layers <任务> → compose <任务> --sync-refs → lint → evaluate（常备题集回归）")

if __name__ == "__main__":
    main()
