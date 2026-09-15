# -*- coding: utf-8 -*-
"""P4 写法书：为每个「形态-类型」生成提示词；子代理读该类型全部原件，写一份 pattern.md 到 work/kb/packs/<形态-类型>/。
用法：python3 pattern.py <形态-类型,…|all> [--project P] [--update]
  --update  P6 增量：写法书已在时不重写，只把新成员补进去（提示词列出旧写法书与新成员）
门槛：该形态 confirm 记录为通过且未过期，否则不派。
写法书是什么：不是拆结构，是把那个人蒸出来——他怎么看事（魂）、每段明面写什么 / 暗地要达成什么 / 凭什么能达成、读起来什么劲儿，
每小段带范文该段的原文整段。章名与每小段七行固定（_core.PATTERN_CHAPTERS / SEGMENT_LINES），check 按它核。详见 references/03-pattern.md。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C
from cluster import SKELETON_HINT

USAGE = "用法：pattern.py <形态-类型,…|all> [--project P] [--update]"

def main():
    pos, o, f = C.parse_args(sys.argv[1:], flags=("--update",), usage=USAGE)
    if len(pos) != 1:
        C.die(USAGE)
    P = C.project_root(o.get("--project")); update = "--update" in f; C.stop_guard(P)
    idx = C.orig_index(P); all_keys = [C.ft_key(fm, t["id"]) for fm, t in C.all_confirmed_types(P)]
    if not all_keys:
        C.die("没有已确认的类型：先 cluster → 使用者确认 → confirm")
    outs = []
    for key in C.split_names(pos[0], all_keys):
        form, t = C.parse_ft(P, key)
        st = C.stage_state(P, f"confirm:{form}", [C.types_path(P, form), C.W(P, "kb", "originals", "index.jsonl")])
        if st != "ok":
            C.die(f"{form} 的 confirm 记录是 {st}：先 `paoding.py confirm {form}` 通过再写写法书")
        pk = C.pack_dir(P, key); os.makedirs(pk, exist_ok=True)
        members = [idx[m] for m in t["members"] if m in idx]
        pp = os.path.join(pk, C.PATTERN)
        if update and os.path.exists(pp):
            old_ids = set(C.id_mentions(C.read_text(pp)))
            new_members = [m for m in members if m["id"] not in old_ids]
            if not new_members:
                print(f"{key}: 写法书已在且没有未引用的新成员，跳过"); continue
            mode = (f"**增量模式**：写法书已在（`{os.path.relpath(pp, P)}`）。只读新成员，把它们补进现有写法书：魂与暗线若有新证据就在原条目后加编号，不改旧措辞；"
                    f"能归进已有小段的在该小段「例」下加它的原文整段、「术」下加它的句式；确实是新小段再加条目并重排编号。不删旧内容。新成员：\n"
                    + "\n".join(f"- `{m['path']}`　{m['id']}　{m['title'][:40]}" for m in new_members))
        elif t.get("exemplar"):
            mode = "**范文型**：这个类型只有一篇，是使用者点名单独做的。魂从这一篇里能看出多少写多少，写不满三条就如实标「只有一篇，魂只能到这」；每小段的「例」都是它；「术」都是它的句子。不往外找别的篇凑。"
        else:
            mode = "**首次**：读完全部成员再动手。先记每篇的三大段边界与每段第一句，再看跨篇重复的选择。"
        n_samples = min(C.SAMPLES_MAX, max(C.SAMPLES_MIN, 1), len(members))
        listing = "\n".join(f"- `{m['path']}`　{m['id']}　{m['author']}　{m['title'][:40]}　{m['chars']} 字" for m in members)
        slots = {"project": P, "form": form, "type_id": t["id"], "type_name": t["name"], "brief": t.get("brief", ""), "n": len(members), "n_samples": n_samples,
                 "authors": "、".join(sorted({m["author"] for m in members})), "skeleton_hint": SKELETON_HINT.get(form, ""), "listing": listing, "mode_block": mode,
                 "pattern_out": os.path.relpath(pp, P), "rules_path": os.path.join(C.SKILL_DIR, "references", "03-pattern.md"), "report_out": f"work/reports/pattern-{key}.md"}
        outs.append(C.fill_prompt("pattern", slots, f"pattern-{key}", P))
    print(f"生成 {len(outs)} 份提示词（一份一个子代理）：")
    for x in outs:
        print(" ", os.path.relpath(x, P))
    print("回来后：paoding.py check <形态-类型|all>（章齐、魂有证据、例逐字、覆盖表）；零引用篇用 paoding.py dispose 写处置")
    C.pipeline_log(P, "P4", f"pattern：{len(outs)} 份提示词" + ("（--update）" if update else ""))
    if outs and C.agent_name() != "none":
        import run_stage; run_stage.run(P, [os.path.basename(x)[:-3] for x in outs])

if __name__ == "__main__":
    main()
