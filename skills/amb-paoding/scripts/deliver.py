# -*- coding: utf-8 -*-
"""交付：把 work/draft/skills 装配成成品目录 product/<箱名>/，写 README、放 fact_check.py、默认附原件库与拆解层，再跑成品体检。
用法：python3 deliver.py <箱名> [--dest <目录>] [--no-kb] [--project P]
  --dest   成品放到别处（默认 product/<箱名>/）。只允许覆盖空目录或上一次交付的成品（同时有 README.md 与 skills/），别的一律拒绝——不替使用者删来历不明的目录
  --no-kb  不附 kb/（默认附 kb/originals/ 全部原件 + kb/packs/ 写法书与覆盖表，让接收方能溯源、能增量）
门槛：lint 记录为通过且未过期。轻验收没有记录只提醒不拦（它是给人看的，不是门）。"""
import os, sys, shutil, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

def main():
    usage = "用法：deliver.py <箱名> [--dest 目录] [--no-kb] [--project P]"
    pos, o, f = C.parse_args(sys.argv[1:], opts=("--dest",), flags=("--no-kb",), usage=usage)
    dest = o.get("--dest"); P = C.project_root(o.get("--project")); nokb = "--no-kb" in f
    if len(pos) != 1:
        C.die(usage)
    box = pos[0]; meta = C.project_meta(P); prefix = meta.get("prefix") or C.DEFAULT_PREFIX; draft = C.W(P, "draft", "skills")
    dirs = sorted(d for d in os.listdir(draft) if os.path.exists(os.path.join(draft, d, "SKILL.md"))) if os.path.isdir(draft) else []
    if not dirs:
        C.die("work/draft/skills 为空。先 P5")
    if prefix not in dirs:
        C.die(f"缺路由器 {prefix}/SKILL.md：先 `paoding.py compose --router` 并派子代理")
    if C.stage_state(P, "lint", C.skill_inputs(draft, dirs)) != "ok":
        C.die("成品体检未通过或已过期（SKILL.md 或 references 改过）：先 `paoding.py lint`")
    mj = C.read_json(C.W(P, "meta.json"), {})
    evals = [k.split(":", 1)[1] for k, v in mj.items() if k.startswith("evaluate:") and v.get("ok")]
    if not evals:
        print("提醒：没有任何轻验收报告。可以交付，但成品 README 会写明「未对裸模型盲评」。")
    out = dest or os.path.join(P, "product", box)
    if os.path.exists(out):
        if not os.path.isdir(out):
            C.die(f"--dest 指向的不是目录：{out}")
        rest = [e for e in os.listdir(out) if e != ".DS_Store"]
        looks_product = os.path.isdir(os.path.join(out, "skills")) and os.path.isfile(os.path.join(out, "README.md"))
        if rest and not looks_product:
            C.die(f"{out} 已有内容，且不像上一次交付的成品（缺 README.md 或 skills/）。换一个空目录，或自己先清空——deliver 不替你删来历不明的目录。")
        shutil.rmtree(out)
    shutil.copytree(draft, os.path.join(out, "skills"))
    fc = os.path.join(C.SKILL_DIR, "assets", "fact_check.py")
    os.makedirs(os.path.join(out, "scripts"), exist_ok=True); shutil.copy2(fc, os.path.join(out, "scripts", "fact_check.py"))
    for d in dirs:
        if d != prefix:
            os.makedirs(os.path.join(out, "skills", d, "scripts"), exist_ok=True); shutil.copy2(fc, os.path.join(out, "skills", d, "scripts", "fact_check.py"))
    idx = C.orig_index(P); n_orig = len(idx)
    if not nokb:
        kb = C.W(P, "kb"); ok = os.path.join(out, "kb")
        shutil.copytree(os.path.join(kb, "originals"), os.path.join(ok, "originals"))
        if os.path.isdir(os.path.join(kb, "packs")):
            shutil.copytree(os.path.join(kb, "packs"), os.path.join(ok, "packs"), ignore=shutil.ignore_patterns("mismatch.md"))
    pairs = C.all_confirmed_types(P); cat = C.catalog(P) or {}
    authors = sorted({r["author"] for r in idx.values()}); forms = sorted({fm for fm, _ in pairs})
    rows = "\n".join(f"| `{prefix}-{C.ft_key(fm, t['id'])}` | {fm} | {t['name']} | {t.get('brief','')} | {len(t.get('members', []))} |" for fm, t in pairs)
    tpl = C.read_text(os.path.join(C.SKILL_DIR, "assets", "product-readme.md"))
    readme = C._Tpl(tpl).substitute(
        toolbox=box, prefix=prefix, n_types=len(pairs), forms="、".join(forms), type_table=rows, n_files=cat.get("total_files", 0), n_chars=f"{cat.get('total_chars', 0):,}",
        n_originals=n_orig, authors="、".join(authors), date=datetime.date.today().isoformat(),
        eval_note=(f"已对裸模型做轻验收（题集：{'、'.join(evals)}），差距报告随生产工程留存。" if evals else "本次交付未对裸模型盲评；效果以你实际用过为准。"),
        kb_note=("本目录 `kb/originals/` 是全部原件（逐字、带编号），`kb/packs/` 是每个类型的骨架、句式、样例与覆盖表：技能里每条引文都能按编号回到原文；增量更新时把它交回 amb-paoding。技能运行不读 kb/，不装进宿主也不影响。" if not nokb else "本次交付不附 kb/；增量更新需回到生产工程。"),
        author_note=(f"这套技能拆的是 {len(authors)} 位来源人的作品，炼出来的是**类型**的写法，不是任何一个人的判断，也不代表任何一个人。" if len(authors) > 1 else f"这套技能拆的是「{authors[0] if authors else '（未标）'}」的作品，炼出来的是这类内容的写法，不是他的判断，也不代表他本人。"))
    C.write_text(os.path.join(out, "README.md"), readme)
    print(f"成品：{out}\n技能 {len(dirs)}（含路由器）| 原件 {n_orig} | kb {'附' if not nokb else '不附'} | 轻验收 {'、'.join(evals) or '无'}")
    import lint_product
    sys.argv = ["lint_product.py", "--product", out, "--project", P]
    C.pipeline_log(P, "交付", f"deliver：{box} → {os.path.relpath(out, P)}")
    try:
        lint_product.main()
    except SystemExit as e:
        if e.code:
            print("成品体检有 FAIL：修完重新 deliver"); sys.exit(1)
    dest_rec = os.path.relpath(out, P) if not os.path.relpath(out, P).startswith("..") else out
    C.record_stage(P, "deliver", [os.path.join(out, "README.md")], extra={"toolbox": box, "dest": dest_rec})

if __name__ == "__main__":
    main()
