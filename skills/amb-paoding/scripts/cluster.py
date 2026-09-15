# -*- coding: utf-8 -*-
"""P3 聚类型：为一个形态生成「按结构聚类型」的提示词；子代理读该形态全部原件，写类型卡（给使用者看）与类型草案 JSON（给执行者）。
用法：python3 cluster.py <形态> [--project P] [--update] [--parts N]
  --update  P6 增量：只把还没归进任何类型的新原件分进已有类型（或提议新类型），不重聚旧的
  --parts N 篇数多时切 N 块并发：生成 N 份分块提示词（各写 work/types/<形态>.partK.draft.json）+ 1 份合并提示词（cluster-<形态>-merge，读全部分块草案写最终草案与类型卡）。
            先并发跑分块，全部回来后再跑合并。一块 30 篇上下合适。
门槛：预检报告要有结论（可开工 / 收缩 / 补料），否则拒绝——第一个判断不能跳。
产出：work/prompts/cluster-<形态>.md；子代理写 work/docs/类型卡-<形态>.md 与 work/types/<形态>.draft.json。
使用者看类型卡、定类型名与取舍后，执行者把草案改成 work/types/<形态>.json 并填 confirmed_at，再跑 confirm。这是唯一参与点。"""
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

USAGE = "用法：cluster.py <形态> [--project P] [--update] [--parts N]"
SKELETON_HINT = {"朋友圈": "钩子 → 展开 → 收束（动作或留白）", "短视频": "前三秒 → 主体 → 结尾动作", "直播": "开场 → 留人 → 讲品 → 催单 → 下播",
                 "课程": "课纲 → 单节结构 → 开场 / 收束 / 作业", "公众号": "标题 → 开头 → 主体分节 → 结尾", "文案": "标题 → 痛点 → 方案 → 证明 → 行动", "其他": "（无起手模板，全从料里看）"}

def main():
    pos, o, f = C.parse_args(sys.argv[1:], opts=("--parts",), flags=("--update",), usage=USAGE)
    if len(pos) != 1:
        C.die(USAGE)
    form = pos[0]; P = C.project_root(o.get("--project")); update = "--update" in f; parts = int(o.get("--parts", "1"))
    if parts > 1 and update:
        C.die("--parts 与 --update 不同时用：增量新篇通常不多，一份就够")
    if form not in C.FORMS:
        C.die(f"形态 {form} 不在枚举里：{' / '.join(C.FORMS)}")
    C.stop_guard(P)
    pre = C.W(P, "docs", "预检报告.md")
    if not (os.path.exists(pre) and re.search(r"可开工|收缩|补料", C.read_text(pre))):
        C.die("work/docs/预检报告.md 缺或没有结论（可开工 / 收缩到某几个形态 / 补料）：先把预检结论交使用者看，再聚类型")
    idx = C.orig_index(P)
    mine = [r for r in idx.values() if r["form"] == form]
    if not mine:
        C.die(f"原件库里没有形态为 {form} 的原件（有：{', '.join(sorted({r['form'] for r in idx.values()}))}）；先 survey --form 改形态或 ingest")
    existing = C.load_types(P, form, must=False) if update else None
    assigned = {m for t in (existing or {}).get("types", []) for m in t.get("members", [])} | set((existing or {}).get("unassigned", {}).keys())
    todo = [r for r in mine if r["id"] not in assigned] if update else mine
    if update and not todo:
        C.die(f"{form} 没有未归类的新原件；不用 --update 重聚")
    if update and not existing:
        C.die(f"--update 需要已确认的 work/types/{form}.json；没有就不加 --update")
    th = C.MIN_PIECES["long" if form in C.LONG_FORMS else "default"]
    authors = sorted({r["author"] for r in mine})
    listing = "\n".join(f"- `{r['path']}`　{r['id']}　{r['author']}　{r['title'][:40]}　{r['chars']} 字" for r in todo)
    # 速览：每篇开头 / 结尾各 120 字逐字（跳过说话人行）。几十上百篇时子代理先看它形成假设，再逐篇读全文确认；不替代读全文
    brief = [f"# {form} 速览（每篇开头 / 结尾各 120 字，逐字；只用来形成假设，归属要读全文确认）", ""]
    for r in todo:
        body = C.orig_body(P, r["id"]) or ""
        txt = "".join(l.strip() for l in body.splitlines() if l.strip() and not C.SPEAKER_RX.match(l))
        brief.append(f"## {r['id']}　{r['title'][:40]}　{r['chars']} 字\n开头：{txt[:120]}\n结尾：{txt[-120:]}\n")
    brief_path = C.W(P, "docs", f"速览-{form}{'-update' if update else ''}.md"); C.write_text(brief_path, "\n".join(brief))
    if parts > 1:
        # 分块：每块只做自己那些篇的归类假设，写 partK 草案；合并那一份读全部草案 + 速览，统一类型、写最终草案与类型卡
        size = -(-len(todo) // parts); outs = []
        for k in range(parts):
            chunk = todo[k * size:(k + 1) * size]
            if not chunk:
                break
            slots = {"project": P, "form": form, "n": len(chunk), "n_all": len(mine), "authors": "、".join(authors), "threshold": th,
                     "skeleton_hint": SKELETON_HINT.get(form, ""), "brief_path": os.path.relpath(brief_path, P),
                     "listing": "\n".join(f"- `{r['path']}`　{r['id']}　{r['author']}　{r['title'][:40]}　{r['chars']} 字" for r in chunk),
                     "mode_block": (f"**分块模式：第 {k + 1} / {parts} 块**，你只负责上面这 {len(chunk)} 篇。别的块由别人读，最后有一份合并。所以：类型名先用**结构描述**（「反问起 → 三分法 → 回到反问」这种），不急着取好听的名字；每篇都要归进某个假设或写进未归类并说明；速览里别的块的篇可以看，用来判断你的假设是不是全局常见的，但不要给它们归类。"
                                    f"草案 JSON 写到 `work/types/{form}.part{k + 1}.draft.json`，类型卡写到 `work/docs/类型卡-{form}-part{k + 1}.md`（简版：每类一段，结构描述 + 两句原话 + 篇数）。"),
                     "card_out": f"work/docs/类型卡-{form}-part{k + 1}.md", "draft_out": f"work/types/{form}.part{k + 1}.draft.json", "report_out": f"work/reports/cluster-{form}-part{k + 1}.md"}
            outs.append(C.fill_prompt("cluster", slots, f"cluster-{form}-part{k + 1}", P))
        mslots = {"project": P, "form": form, "n_all": len(mine), "parts": len(outs), "threshold": th, "brief_path": os.path.relpath(brief_path, P),
                  "part_drafts": "\n".join(f"- `work/types/{form}.part{k + 1}.draft.json`（类型卡 `work/docs/类型卡-{form}-part{k + 1}.md`）" for k in range(len(outs))),
                  "card_out": f"work/docs/类型卡-{form}.md", "draft_out": f"work/types/{form}.draft.json", "report_out": f"work/reports/cluster-{form}-merge.md"}
        merge = C.fill_prompt("cluster-merge", mslots, f"cluster-{form}-merge", P)
        print(f"分块 {len(outs)} 份 + 合并 1 份：")
        for x in outs + [merge]:
            print(" ", os.path.relpath(x, P))
        print(f"先并发跑分块：paoding.py run {','.join(os.path.basename(x)[:-3] for x in outs)} --workers {len(outs)}；全部回来后 paoding.py run cluster-{form}-merge；再走 confirm。")
        C.pipeline_log(P, "P3", f"cluster {form} --parts {len(outs)}：{len(todo)} 篇")
        if C.agent_name() != "none":
            import run_stage; run_stage.run(P, [os.path.basename(x)[:-3] for x in outs], workers=len(outs))
            print(f"分块跑完。接着：paoding.py run cluster-{form}-merge")
        return
    exist_block = ""
    if existing:
        exist_block = "\n".join(f"- `{t['id']}` {t['name']}：{t.get('brief','')}（现有 {len(t.get('members', []))} 篇）" for t in existing.get("types", [])) or "- （无）"
    slots = {"project": P, "form": form, "n": len(todo), "n_all": len(mine), "authors": "、".join(authors), "threshold": th,
             "skeleton_hint": SKELETON_HINT.get(form, ""), "listing": listing, "brief_path": os.path.relpath(brief_path, P),
             "mode_block": ("**增量模式**：下面列的是还没归类的新原件。只做两件事：把它们分进已有类型；实在不像任何一类的提议新类型（写清为什么）。不重聚、不改旧类型的成员。已有类型：\n" + exist_block) if update else "**首次聚类型**：读完全部原件再动手。",
             "card_out": f"work/docs/类型卡-{form}.md", "draft_out": f"work/types/{form}.draft.json", "report_out": f"work/reports/cluster-{form}.md"}
    out = C.fill_prompt("cluster", slots, f"cluster-{form}" + ("-update" if update else ""), P)
    print(os.path.relpath(out, P), f"（派一个子代理；{form} {len(todo)} 篇，来源人 {'、'.join(authors)}）")
    print(f"回来后：使用者看 work/docs/类型卡-{form}.md 定类型名与取舍 → 把 {form}.draft.json 改成 work/types/{form}.json、填 confirmed_at 与 user_note → paoding.py confirm {form}")
    C.pipeline_log(P, "P3", f"cluster {form}{' --update' if update else ''}：{len(todo)} 篇")
    if C.agent_name() != "none":
        import run_stage; run_stage.run(P, [os.path.basename(out)[:-3]])

if __name__ == "__main__":
    main()
