# -*- coding: utf-8 -*-
"""S2 校准提示词：试点产物核验通过后，生成"对照规则逐条审读试点原子、提出校准补丁"的提示词（派一个子代理或执行 agent 自己做）。
用法：python3 calibrate.py [--project P]
输入：work/pilot/ 的试点产物、work/reports/pilot-*.md、work/docs/执行提示词.md。
产出：work/prompts/calibrate.md → 子代理写 work/docs/加工样品.md（给使用者看的样品：原子 10 条 + 单元 2 个 + 覆盖率 + 补丁建议）并把补丁追加到执行提示词。
补丁纪律：只加条目，不改 schema、白名单、confidence 定义、去重规则、保真红线；连续两批不改这五项即可冻结。"""
import os, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

def main():
    pos, o, f = C.parse_args(sys.argv[1:], usage="用法：calibrate.py [--project P]")
    if pos:
        C.die(f"多余的参数 {pos}；用法：calibrate.py [--project P]")
    P = C.project_root(o.get("--project"))
    C.stop_guard(P)
    rules = C.W(P, "docs", "执行提示词.md"); C.need(rules, "pilot")
    outs = sorted(glob.glob(C.W(P, "pilot", "atoms_*.jsonl")))
    if not outs:
        C.die("work/pilot/ 里没有试点产物。先 pilot 并等子代理写完，再 settle --pilot")
    bj = C.read_json(C.W(P, "batches.json")); pilots = [b for b in bj["batches"] if b.get("claimed_by") == "pilot"]
    unsettled = [b["batch_id"] for b in pilots if b["status"] != "done"]
    if unsettled:
        print(f"提示：试点批 {unsettled} 还没 settle 为 done；校准应在核验通过后做")
    slots = {"project": P, "skill_dir": C.SKILL_DIR, "rules_path": os.path.relpath(rules, P), "pilot_dir": "work/pilot",
             "pilot_files": "\n".join(f"- {os.path.relpath(o, P)}（单元：{os.path.relpath(o, P).replace('atoms_', 'units_')}）" for o in outs),
             "reports": "\n".join(f"- {os.path.relpath(r, P)}" for r in sorted(glob.glob(C.W(P, "reports", "pilot-*.md")))) or "- （无试点报告）",
             "sample_out": "work/docs/加工样品.md"}
    out = C.fill_prompt("calibrate", slots, "calibrate", P)
    print(os.path.relpath(out, P), "（派一个子代理；它写 work/docs/加工样品.md 并追加补丁到执行提示词。样品给使用者看，是第二个参与点）")
    C.pipeline_log(P, "S2", "calibrate：校准提示词已生成")

if __name__ == "__main__":
    main()
