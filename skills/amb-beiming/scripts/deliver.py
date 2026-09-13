# -*- coding: utf-8 -*-
"""S8 交付：把 work/draft/skills 装配成成品目录 product/<工具箱名>/，写 README、放 fact_check.py、默认附知识库，再跑成品体检。
用法：python3 deliver.py <工具箱名> [--dest <目录>] [--plugin] [--no-kb] [--project P]
  --dest    成品放到别处（默认 product/<工具箱名>/）
  --plugin  生成 .claude-plugin/marketplace.json（宿主用市场装的场景）
  --no-kb   不附知识库（默认附 kb/{atoms,units}.jsonl、packs/、index.md，让接收方能溯源与增量）
门槛：lint 记录为通过且未过期，且 S7 至少一套题集报告 PASS。"""
import os, sys, shutil, json, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

def main():
    usage = "用法：deliver.py <工具箱名> [--dest 目录] [--plugin] [--no-kb] [--force] [--project P]"
    pos, o, f = C.parse_args(sys.argv[1:], opts=("--dest",), flags=("--plugin", "--no-kb", "--force"), usage=usage)
    dest = o.get("--dest"); P = C.project_root(o.get("--project")); plugin = "--plugin" in f; nokb = "--no-kb" in f
    if len(pos) != 1:
        C.die(usage)
    box = pos[0]; T = C.tasks(P); prefix = T["prefix"]; draft = C.W(P, "draft", "skills")
    dirs = sorted(d for d in os.listdir(draft) if os.path.exists(os.path.join(draft, d, "SKILL.md"))) if os.path.isdir(draft) else []
    if not dirs:
        C.die("work/draft/skills 为空。先 S6")
    if C.stage_state(P, "lint", C.skill_inputs(draft, dirs)) != "ok":
        C.die("成品体检未通过或已过期（SKILL.md 或 references 改过）：先 `beiming.py lint`")
    meta = C.read_json(C.W(P, "meta.json"), {})
    # 只认"记录 ok 且输入未变"的题集：评分文件 / 题集 / key / tasks.json 任一改过，旧 PASS 过期
    passed = [k for k, v in meta.items() if k.startswith("evaluate:") and v.get("ok") and C.stage_state(P, k, C.eval_inputs(P, k.split(":", 1)[1])) == "ok"]
    stale = [k for k, v in meta.items() if k.startswith("evaluate:") and v.get("ok") and k not in passed]
    if stale:
        print(f"提示：{stale} 的 PASS 已过期（评测依赖改过），不算")
    if not passed and "--force" not in f:
        C.die("S7 没有一套题集全部 PASS 且未过期。先验收（stale 的重跑 tally → report）；确需带 WEAK 交付，在验收报告写明后加 --force")
    if not passed:
        print("警告：带 WEAK/FAIL 交付（--force）；验收报告与成品 README 须写明")
    out = dest or os.path.join(P, "product", box)
    if os.path.exists(out):
        shutil.rmtree(out)
    shutil.copytree(draft, os.path.join(out, "skills"))
    fc = os.path.join(C.SKILL_DIR, "assets", "fact_check.py")
    os.makedirs(os.path.join(out, "scripts"), exist_ok=True); shutil.copy2(fc, os.path.join(out, "scripts", "fact_check.py"))  # 根目录一份是开放资产
    for d in dirs:  # 每个任务技能自带一份：单独拷走一个技能目录也能跑器层核对
        if d != prefix:
            os.makedirs(os.path.join(out, "skills", d, "scripts"), exist_ok=True); shutil.copy2(fc, os.path.join(out, "skills", d, "scripts", "fact_check.py"))
    n_atoms = n_units = 0
    if not nokb:
        kb = C.W(P, "kb"); ok = os.path.join(out, "kb"); os.makedirs(ok, exist_ok=True)
        for f in ("atoms.jsonl", "units.jsonl", "alias.json", "index.md", "sources.md"):
            if os.path.exists(os.path.join(kb, f)):
                shutil.copy2(os.path.join(kb, f), os.path.join(ok, f))
        if os.path.isdir(os.path.join(kb, "packs")):
            shutil.copytree(os.path.join(kb, "packs"), os.path.join(ok, "packs"), ignore=shutil.ignore_patterns("case_library_full.md"))
        n_atoms = len(C.read_jsonl(os.path.join(kb, "atoms.jsonl"))); n_units = len(C.read_jsonl(os.path.join(kb, "units.jsonl")))
    cat = C.load_catalog(P) or {}
    rows = "\n".join(f"| `{prefix}-{t['id']}` | {t.get('name','')} | {t.get('input','')} | {t.get('deliver','')} |" for t in T["tasks"])
    tpl = C.read_text(os.path.join(C.SKILL_DIR, "assets", "product-readme.md"))
    weak_note = "" if passed else "本次带弱项交付：尚无一套题集全部 PASS。剩余弱项见验收报告，成品不写工程路径。"
    readme = C._Tpl(tpl).substitute(toolbox=box, prefix=prefix, n_tasks=len(T["tasks"]), task_table=rows, n_files=cat.get("total_files", 0), n_chars=f"{cat.get('total_chars', 0):,}",
                                    n_atoms=n_atoms, n_units=n_units, date=datetime.date.today().isoformat(), testsets="、".join(k.split(":", 1)[1] for k in passed),
                                    weak_note=weak_note,
                                    kb_note=("本目录 `kb/` 附带原子库、单元库与各任务知识包：每条判断都能按原子 id 回到原话；增量更新时把它交给 amb-beiming。知识库是开放的：`kb/atoms.jsonl` 可直接做检索或 RAG，`kb/packs/<任务>/methods.md` 可粘进任何 system prompt，案例可按 unit_id 单独取，不装技能也能用。" if not nokb else "本次交付不附知识库；增量更新需回到生产工程。"))
    C.write_text(os.path.join(out, "README.md"), readme)
    if plugin:
        mp = json.loads(C.read_text(os.path.join(C.SKILL_DIR, "assets", "marketplace.json")))
        mp["name"] = box; mp["plugins"] = [{"name": d, "source": f"./skills/{d}", "description": next((t.get("judge", "") for t in T["tasks"] if d == f"{prefix}-{t['id']}"), "路由器：按任务分发")} for d in dirs]
        C.write_json(os.path.join(out, ".claude-plugin", "marketplace.json"), mp)
    print(f"成品：{out}\n技能 {len(dirs)} | 知识库 {'附' if not nokb else '不附'}（原子 {n_atoms} 单元 {n_units}）| 市场文件 {'有' if plugin else '无'}")
    import lint_product
    sys.argv = ["lint_product.py", "--product", out, "--project", P]
    C.pipeline_log(P, "S8", f"deliver：{box} → {os.path.relpath(out, P)}")
    try:
        lint_product.main()
    except SystemExit as e:
        if e.code:
            print("成品体检有 FAIL：修完重新 deliver"); sys.exit(1)
    # dest 记相对工程根的路径（成品在工程外时才是绝对路径）：工程搬家后 status 仍能找到成品，不假过期
    dest_rec = os.path.relpath(out, P) if not os.path.relpath(out, P).startswith("..") else out
    C.record_stage(P, "deliver", [os.path.join(out, "README.md")], extra={"toolbox": box, "dest": dest_rec})

if __name__ == "__main__":
    main()
