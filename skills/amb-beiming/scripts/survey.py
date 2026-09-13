# -*- coding: utf-8 -*-
"""S1 盘点切批：递归盘点语料 → work/catalog.json（分组、稳定文件号、形态）+ work/batches.json（批次销账表）。
同时建好工程目录（init 兼任）。
用法：python3 survey.py --corpus <语料目录> [--project <工程目录>] [--form g01=A,g04=D] [--max-chars 100000] [--update]
  --form       按组号改形态（A 访谈 / B 单讲师课 / C 多讲师短分享 / D 作者作品）；重跑只改 form 字段，不动批次状态
  --max-chars  单批字符上限（默认 100000；按子代理上下文定，见 references/01-survey.md 规则节）
  --update     S9 增量：只追加新文件与新批次，已有文件号与批次不变
产出：work/catalog.json、work/batches.json（每文件记 title = 文件名标题：去扩展名、去开头的日期 / 时间前缀与末尾短哈希、去首尾空白；file 保留原名以便回溯；标题原子按 title 核）、控制台的规模表与批次表。"""
import os, sys, re, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

MAX_FILES = {"A": 12, "B": 12, "C": 12, "D": 30}
FORM_HINT = [("A", re.compile(r"访谈|对谈|对话|interview|podcast|播客", re.I)),
             ("D", re.compile(r"文案|朋友圈|推文|作品|公众号|短视频稿|销售信|posts?", re.I))]

def guess_form(name, files):
    for f, rx in FORM_HINT:
        if rx.search(name):
            return f
    if len(files) >= 10 and statistics.median([x["chars"] for x in files]) < 3000:
        return "C"
    return "B"

def scan(root):
    """根下一层子目录 = 一组；根下平铺文件 = g00 一组。返回 [(组名, 目录, [相对文件名])]。"""
    groups, nontext = [], []
    entries = sorted(os.listdir(root))
    flat = [e for e in entries if os.path.isfile(os.path.join(root, e)) and not e.startswith(".")]
    subs = [e for e in entries if os.path.isdir(os.path.join(root, e)) and not e.startswith(".")]
    if flat:
        groups.append(("(根目录)", root, flat))
    for s in subs:
        files = []
        for dp, dn, fn in os.walk(os.path.join(root, s)):
            dn[:] = sorted(d for d in dn if not d.startswith("."))
            for f in sorted(fn):
                if f.startswith("."):
                    continue
                files.append(os.path.relpath(os.path.join(dp, f), os.path.join(root, s)))
        groups.append((s, os.path.join(root, s), files))
    out = []
    for name, d, files in groups:
        txt = [f for f in files if f.lower().endswith(C.TEXT_EXT)]
        nontext += [os.path.join(name, f) for f in files if not f.lower().endswith(C.TEXT_EXT)]
        if txt:
            out.append((name, d, txt))
    return out, nontext

USAGE = "用法：survey.py --corpus <语料目录> [--project <工程目录>] [--form g01=A] [--max-chars N] [--update]"

def main():
    pos, o, f = C.parse_args(sys.argv[1:], opts=("--corpus", "--form", "--max-chars"), flags=("--update",), usage=USAGE)
    if pos:
        C.die(f"多余的参数 {pos}\n{USAGE}")
    corpus = o.get("--corpus"); P = C.project_root(o.get("--project"))
    form_over = dict(kv.split("=") for kv in o.get("--form", "").split(",") if "=" in kv)
    mc = o.get("--max-chars"); update = "--update" in f
    if not corpus:
        C.die(USAGE)
    corpus = os.path.abspath(corpus)
    if not os.path.isdir(corpus):
        C.die(f"语料目录不存在：{corpus}")
    C.ensure_project(P)
    old = C.load_catalog(P) if (update or form_over) else None
    if os.path.exists(C.W(P, "catalog.json")) and not update and not form_over:
        C.die("work/catalog.json 已存在。改形态用 --form，加新料用 --update；要重来请先删掉 work/catalog.json 与 work/batches.json")
    groups_raw, nontext = scan(corpus)
    old_groups = {g["name"]: g for g in (old or {}).get("groups", [])}
    catalog = {"corpus_root": corpus, "created": (old or {}).get("created") or C.now(), "updated": C.now(), "groups": [], "nontext": nontext}
    used_gids = {g["group_id"] for g in old_groups.values()}
    next_g = max([int(g[1:]) for g in used_gids] + [0]) + 1
    for name, d, files in groups_raw:
        og = old_groups.get(name)
        if og:
            gid = og["group_id"]; known = {f["file"]: f for f in og["files"]}
            nxt = max([int(f["no"]) for f in og["files"]] + [0]) + 1
        else:
            gid = "g%02d" % next_g; next_g += 1; known = {}; nxt = 1
        flist = []
        for f in files:
            chars = len(C.norm_ws(C.read_text(os.path.join(d, f))))
            if f in known:
                flist.append({**known[f], "title": known[f].get("title") or C.file_title(f), "chars": chars})
            else:
                flist.append({"no": "%03d" % nxt, "file": f, "title": C.file_title(f), "chars": chars, "added": C.now()[:10]}); nxt += 1
        form = form_over.get(gid) or (og or {}).get("form") or guess_form(name, flist)
        catalog["groups"].append({"group_id": gid, "name": name, "form": form, "source_dir": d, "files": flist,
                                  "n_files": len(flist), "total_chars": sum(x["chars"] for x in flist)})
    catalog["total_files"] = sum(g["n_files"] for g in catalog["groups"])
    catalog["total_chars"] = sum(g["total_chars"] for g in catalog["groups"])
    C.write_json(C.W(P, "catalog.json"), catalog)

    # 批次：已有的保留（只更新 form），新文件成新批
    bpath = C.W(P, "batches.json")
    bj = C.read_json(bpath, {"rules_version": "v1.0", "max_chars": 100000, "batches": []})
    max_chars = int(mc) if mc else int(bj.get("max_chars", 100000))
    assigned = {(b["group_id"], fn) for b in bj["batches"] for fn in b["files"]}  # 组 + 文件名：不同组的同名文件是不同文件
    gform = {g["group_id"]: g["form"] for g in catalog["groups"]}
    for b in bj["batches"]:
        b["form"] = gform.get(b["group_id"], b["form"])
    n = len(bj["batches"])
    def new_batch(g, files):
        nonlocal n
        n += 1; bid = "b%03d" % n
        fn = {f["file"]: f["no"] for f in g["files"]}
        return {"batch_id": bid, "status": "pending", "group_id": g["group_id"], "form": g["form"], "source_dir": g["source_dir"],
                "files": [f["file"] for f in files], "file_nos": {f["file"]: fn[f["file"]] for f in files},
                "chars": sum(f["chars"] for f in files), "oversized": len(files) == 1 and files[0]["chars"] > max_chars,
                "atoms_out": f"work/parts/atoms_{bid}.jsonl", "units_out": f"work/parts/units_{bid}.jsonl",
                "report_out": f"work/reports/{bid}.md", "claimed_by": "", "atoms": 0, "units": 0, "note": ""}
    for g in catalog["groups"]:
        pending = [f for f in g["files"] if (g["group_id"], f["file"]) not in assigned]
        cur, cur_chars = [], 0
        for f in pending:
            if f["chars"] > max_chars:
                if cur:
                    bj["batches"].append(new_batch(g, cur)); cur, cur_chars = [], 0
                bj["batches"].append(new_batch(g, [f])); continue
            if cur and (cur_chars + f["chars"] > max_chars or len(cur) >= MAX_FILES.get(g["form"], 12)):
                bj["batches"].append(new_batch(g, cur)); cur, cur_chars = [], 0
            cur.append(f); cur_chars += f["chars"]
        if cur:
            bj["batches"].append(new_batch(g, cur))
    bj["max_chars"] = max_chars
    C.write_json(bpath, bj)
    catalog_chars = {(g["group_id"], f["file"]): f["chars"] for g in catalog["groups"] for f in g["files"]}

    tc = catalog["total_chars"]
    print(f"组 {len(catalog['groups'])} | 文本文件 {catalog['total_files']} | 字符 {tc:,} | 非文本 {len(nontext)}（列在 catalog.nontext，转文本后 --update）")
    print("| 组 | 名称 | 形态 | 文件 | 字符 |\n|---|---|---|---|---|")
    for g in catalog["groups"]:
        print(f"| {g['group_id']} | {g['name'][:30]} | {g['form']} | {g['n_files']} | {g['total_chars']:,} |")
    print(f"批次 {len(bj['batches'])}（单批 ≤ {max_chars:,} 字符；超长单文件独立成批 {sum(1 for b in bj['batches'] if b['oversized'])} 个）")
    print("| 批 | 组 | 形态 | 文件 | 字符 | 状态 |\n|---|---|---|---|---|---|")
    for b in bj["batches"]:
        print(f"| {b['batch_id']} | {b['group_id']} | {b['form']} | {len(b['files'])}{'（超长）' if b.get('oversized') else ''} | {b['chars']:,} | {b['status']} |")
    longest = max(bj["batches"], key=lambda b: max(catalog_chars.get((b["group_id"], fn), 0) for fn in b["files"])) if bj["batches"] else None
    if longest:
        print(f"最长文件所在批：{longest['batch_id']}（S2 试点必选它 + 一个别的形态的批：`beiming.py pilot {longest['batch_id']},bNNN`）")
    big = [b for b in bj["batches"] if b["chars"] > 100000]
    if big:
        print(f"提醒：{len(big)} 批超过 10 万字符（{','.join(b['batch_id'] for b in big[:6])}）。子代理是 256K 级上下文时建议 `--max-chars 80000`（references/01-survey.md 规则节）。")
    C.pipeline_log(P, "S1", f"survey：{catalog['total_files']} 文件 / {tc:,} 字符 / {len(bj['batches'])} 批" + ("（--update）" if update else ""))

if __name__ == "__main__":
    main()
