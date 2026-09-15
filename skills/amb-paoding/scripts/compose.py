# -*- coding: utf-8 -*-
"""P5 成技派发：为每个「形态-类型」建草稿目录、复制 references（写法书 + 范文全文）、生成写技能的提示词；--router 生成路由器提示词。
用法：python3 compose.py <形态-类型,…|all> [--project P]
      python3 compose.py --router [--project P]
      python3 compose.py <形态-类型,…|all> --sync-refs [--project P]   只重新复制 references，不生成提示词（P6 增量改完写法书后用）
门槛：该类型 check 记录为通过且未过期，否则不派（引文没核过、零引用没处置的不许进技能）。
产出：work/draft/skills/<前缀>-<形态>-<类型>/references/pattern.md + originals/<编号>.md + scripts/fact_check.py；work/prompts/compose-<形态-类型>.md。
范文全文按类型带：写法书「例」点到的篇永远带；本类型成员总量 ≤ 100KB（_core.BUNDLE_ALL_MAX）就全带；超了只带例篇，其余留成品根 kb/。
类型文件可用 "bundle": "all" | "samples" 强制。技能运行时读的就是这一份写法书：先过魂，再按小段的明 / 暗 / 凭什么 / 术 / 例 / 气口写。"""
import os, sys, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

USAGE = "用法：compose.py <形态-类型,…|all> [--sync-refs] [--project P] | compose.py --router [--project P]"

def skill_dirname(prefix, key):
    return f"{prefix}-{key}"

def sync_refs(P, key, sd, idx):
    """写法书 + 范文全文 + fact_check.py → 草稿。返回 (复制文件数, 带了哪些原件编号, 成员数, 是否只带样例篇)。
    按类型算：样例卡点到的篇永远带；成员总量 ≤ BUNDLE_ALL_MAX 全带；超了只带样例篇。类型的 bundle 字段可强制 all / samples。"""
    form, t = C.parse_ft(P, key); pk = C.pack_dir(P, key); rd = os.path.join(sd, "references"); os.makedirs(rd, exist_ok=True); n = 0
    pp = os.path.join(pk, C.PATTERN); C.need(pp, f"pattern {key}（缺写法书）")
    for stale in ("skeleton.md", "phrases.md", "samples.md"):  # 旧三件形态的残留不进技能
        if os.path.exists(os.path.join(rd, stale)):
            os.remove(os.path.join(rd, stale))
    shutil.copy2(pp, os.path.join(rd, C.PATTERN)); n += 1
    members = [m for m in t["members"] if m in idx]
    cited = {i for _, i in C.example_blocks(C.read_text(pp))}
    sample_ids = [m for m in members if m in cited] or members[:C.SAMPLES_MIN]
    total = sum(os.path.getsize(C.W(P, "kb", "originals", m + ".md")) for m in members if os.path.exists(C.W(P, "kb", "originals", m + ".md")))
    mode = t.get("bundle") or ("all" if total <= C.BUNDLE_ALL_MAX else "samples")
    if mode not in ("all", "samples"):
        C.die(f"类型 {key} 的 bundle 字段只能是 all / samples，现在是 {mode!r}")
    only_samples = mode == "samples"
    chosen = sample_ids if only_samples else members
    od = os.path.join(rd, "originals")
    if os.path.isdir(od):
        shutil.rmtree(od)
    os.makedirs(od, exist_ok=True)
    for m in chosen:
        p = C.W(P, "kb", "originals", m + ".md")
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(od, m + ".md")); n += 1
    fc = os.path.join(C.SKILL_DIR, "assets", "fact_check.py")
    os.makedirs(os.path.join(sd, "scripts"), exist_ok=True); shutil.copy2(fc, os.path.join(sd, "scripts", "fact_check.py")); n += 1
    return n, chosen, len(members), only_samples

def main():
    pos, o, f = C.parse_args(sys.argv[1:], flags=("--router", "--sync-refs"), usage=USAGE)
    P = C.project_root(o.get("--project")); router = "--router" in f; sync = "--sync-refs" in f
    meta = C.project_meta(P); prefix = meta.get("prefix") or C.DEFAULT_PREFIX; idx = C.orig_index(P)
    spec = os.path.join(C.SKILL_DIR, "references", "product-spec.md"); draft = C.W(P, "draft", "skills"); outs = []  # 技能自身的文件用绝对路径
    pairs = C.all_confirmed_types(P); keys = [C.ft_key(fm, t["id"]) for fm, t in pairs]
    if not keys:
        C.die("没有已确认的类型：先 cluster → confirm → pattern → check")
    if router and (pos or sync):
        C.die(USAGE)
    if not router and len(pos) != 1:
        C.die(USAGE)
    if sync:
        for key in C.split_names(pos[0], keys):
            sd = os.path.join(draft, skill_dirname(prefix, key)); C.need(os.path.join(sd, "SKILL.md"), f"compose {key} 并派子代理（草稿还不存在，不是同步的场景）")
            n, chosen, nm, only_s = sync_refs(P, key, sd, idx); print(f"{key}: 同步 {n} 个文件（范文全文 {len(chosen)}/{nm} 篇{'，超上限只带样例篇' if only_s else ''}）")
        C.pipeline_log(P, "P6", f"compose --sync-refs：{pos[0]}"); print("同步后重新 `paoding.py lint`"); return
    C.stop_guard(P)
    if router:
        rows = []
        for fm, t in pairs:
            key = C.ft_key(fm, t["id"]); d = os.path.join(draft, skill_dirname(prefix, key), "SKILL.md")
            C.need(d, f"compose {key} 并派子代理（路由器最后写）")
            rows.append(f"- `{skill_dirname(prefix, key)}`（形态 {fm}｜类型 {t['name']}）：{t.get('brief','')}")
        rd = os.path.join(draft, prefix); os.makedirs(rd, exist_ok=True)
        forms = sorted({fm for fm, _ in pairs})
        slots = {"project": P, "prefix": prefix, "router_dir": os.path.relpath(rd, P), "skill_list": "\n".join(rows), "forms": "、".join(forms),
                 "spec_path": spec, "report_out": "work/reports/compose-router.md"}
        outs.append(C.fill_prompt("compose-router", slots, "compose-router", P))
    else:
        for key in C.split_names(pos[0], keys):
            form, t = C.parse_ft(P, key)
            st = C.stage_state(P, f"check:{key}", C.pack_inputs(P, form, key))
            if st != "ok":
                C.die(f"{key} 的 check 记录是 {st}：先 `paoding.py check {key}` 通过再成技")
            sd = os.path.join(draft, skill_dirname(prefix, key)); n, chosen, nm, only_s = sync_refs(P, key, sd, idx); rd = os.path.join(sd, "references")
            neighbors = "\n".join(f"- `../{skill_dirname(prefix, C.ft_key(fm2, t2['id']))}/SKILL.md`（{fm2}｜{t2['name']}）：{t2.get('brief','')}" for fm2, t2 in pairs if C.ft_key(fm2, t2["id"]) != key) or "- （只有这一个类型）"
            authors = sorted({idx[m]["author"] for m in t["members"] if m in idx})
            segs = C.segments(C.read_text(os.path.join(C.pack_dir(P, key), C.PATTERN)))
            seg_list = "\n".join(f"- 第 {n_} 小段「{name}」（{ {'open': '开头', 'mid': '中间', 'close': '结尾'}.get(big, '?') }）" for n_, name, _, big in segs) or "- （写法书里没解析出小段：先 check）"
            orig_note = (f"范文全文已随技能带在 `{os.path.relpath(rd, P)}/originals/<编号>.md`，共 {len(chosen)} 篇"
                         + (f"（本类型 {nm} 篇总量超上限，只带写法书「例」点到的这几篇，其余在生成它的工程 kb/ 里）" if only_s else f"（本类型全部 {nm} 篇成员）")
                         + "。技能里每个 Phase 对应写法书一个小段，写法书的「例」已经是范文该段的整段原文；要看整篇再按编号读 originals。")
            ex_note = ("\n\n**范文型**：这个类型只有一篇范文，是使用者点名单独做的。写法直接是「照着这一篇的每一段写」；「来源与边界」必须写明「只有一篇范文，写出来会很像它，结构之外的变化没有依据」。"
                       if t.get("exemplar") else "")
            slots = {"project": P, "form": form, "type_id": t["id"], "type_name": t["name"], "brief": t.get("brief", ""), "prefix": prefix,
                     "skill_name": skill_dirname(prefix, key), "skill_dir_out": os.path.relpath(sd, P), "refs_dir": os.path.relpath(rd, P),
                     "originals_note": orig_note, "exemplar_note": ex_note, "segment_list": seg_list, "n_segments": len(segs),
                     "authors": "、".join(authors), "n_authors": len(authors), "spec_path": spec, "neighbors": neighbors, "report_out": f"work/reports/compose-{key}.md"}
            outs.append(C.fill_prompt("compose-skill", slots, f"compose-{key}", P))
    print(f"生成 {len(outs)} 份提示词：")
    for x in outs:
        print(" ", os.path.relpath(x, P))
    C.pipeline_log(P, "P5", f"compose{' --router' if router else ''}：{len(outs)} 份提示词")
    if C.agent_name() != "none":
        import run_stage; run_stage.run(P, [os.path.basename(x)[:-3] for x in outs])
    else:
        print("宿主子代理模式：每份提示词派一个子代理；全部回来后 `paoding.py lint`")

if __name__ == "__main__":
    main()
