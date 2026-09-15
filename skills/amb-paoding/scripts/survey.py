# -*- coding: utf-8 -*-
"""P1 盘点：递归盘点作品目录 → work/catalog.json（按形态分组、稳定文件号、来源人、篇数）。同时建好工程目录。
用法：python3 survey.py --corpus <作品目录> [--project <工程目录>] [--form g01=短视频,g02=朋友圈] [--author g01=某某] [--update]
  --form    按组号改形态（朋友圈 / 短视频 / 直播 / 课程 / 公众号 / 文案 / 其他）；重跑只改 form 字段，不动文件号
  --author  按组号标来源人（对方是谁；多人料必标，成品会写明「类型，不是某人」）
  --update  P6 增量：只追加新文件，已有文件号不变；并出 work/docs/增量报告.md，把新料分三档——
            ① 形态已有且有已确认类型 → 正常增量（cluster --update 只给新篇分类，不动旧的）
            ② 新形态、篇数够 → 不是同一批次，不并进旧类型；建议当新形态聚类型、出新技能，放同一个箱子（路由器先判形态）
            ③ 新形态、篇数不够 → 不是同一批次也不够出技能：只入原件库标待补料，不出技能、不动旧的
            同形态但来源人是新的 → 提醒写法可能不同，建议单独聚、不并入
一篇的单位按形态定：朋友圈一条、短视频一条、直播一场、课程一节、公众号一篇——都是一文件一篇。
产出：work/catalog.json、控制台的规模表（每形态多少篇、够不够出技能）；--update 时另出 work/docs/增量报告.md。"""
import os, sys, re, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

FORM_HINT = [("朋友圈", re.compile(r"朋友圈|moments?", re.I)),
             ("短视频", re.compile(r"短视频|抖音|视频号|快手|tiktok|douyin|reels|shorts|小红书|xhs|红书", re.I)),
             ("直播", re.compile(r"直播|live", re.I)),
             ("课程", re.compile(r"课程|课|lesson|course|训练营|录播", re.I)),
             ("公众号", re.compile(r"公众号|文章|article|blog|长文", re.I)),
             ("文案", re.compile(r"文案|海报|销售信|详情页|copy", re.I))]

def guess_form(name, files):
    for f, rx in FORM_HINT:
        if rx.search(name):
            return f
    if files:
        med = statistics.median([x["chars"] for x in files])
        if med < 600:
            return "朋友圈"
        if med < 3000:
            return "短视频"
        if med > 15000:
            return "课程"
    return "其他"

def scan(root):
    """根下一层子目录 = 一组；根下平铺文件 = 一组。返回 ([(组名, 目录, [相对文件名])], 非文本)。"""
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
                if not f.startswith("."):
                    files.append(os.path.relpath(os.path.join(dp, f), os.path.join(root, s)))
        groups.append((s, os.path.join(root, s), files))
    out = []
    for name, d, files in groups:
        txt = [f for f in files if f.lower().endswith(C.TEXT_EXT)]
        nontext += [os.path.join(name, f) for f in files if not f.lower().endswith(C.TEXT_EXT)]
        if txt:
            out.append((name, d, txt))
    return out, nontext

USAGE = "用法：survey.py --corpus <作品目录> [--project P] [--form g01=短视频] [--author g01=某某] [--update]"

def main():
    pos, o, f = C.parse_args(sys.argv[1:], opts=("--corpus", "--form", "--author"), flags=("--update",), usage=USAGE)
    if pos:
        C.die(f"多余的参数 {pos}\n{USAGE}")
    corpus = o.get("--corpus"); P = C.project_root(o.get("--project")); update = "--update" in f
    form_over = dict(kv.split("=", 1) for kv in o.get("--form", "").split(",") if "=" in kv)
    author_over = dict(kv.split("=", 1) for kv in o.get("--author", "").split(",") if "=" in kv)
    for v in form_over.values():
        if v not in C.FORMS:
            C.die(f"形态 {v} 不在枚举里：{' / '.join(C.FORMS)}")
    if not corpus:
        C.die(USAGE)
    corpus = os.path.abspath(corpus)
    if not os.path.isdir(corpus):
        C.die(f"作品目录不存在：{corpus}")
    C.ensure_project(P)
    old = C.catalog(P) if (update or form_over or author_over) else None
    if os.path.exists(C.W(P, "catalog.json")) and not (update or form_over or author_over):
        C.die("work/catalog.json 已存在。改形态用 --form，标来源人用 --author，加新料用 --update；要重来先删掉 work/catalog.json 与 work/kb/originals/")
    groups_raw, nontext = scan(corpus)
    old_groups = {g["name"]: g for g in (old or {}).get("groups", [])}
    cat = {"corpus_root": corpus, "created": (old or {}).get("created") or C.now(), "updated": C.now(), "groups": [], "nontext": nontext}
    used = {g["group_id"] for g in old_groups.values()}
    next_g = max([int(g[1:]) for g in used] + [0]) + 1
    new_files = 0
    for name, d, files in groups_raw:
        og = old_groups.get(name)
        if og:
            gid = og["group_id"]; known = {x["file"]: x for x in og["files"]}; nxt = max([int(x["no"]) for x in og["files"]] + [0]) + 1
        else:
            gid = "g%02d" % next_g; next_g += 1; known = {}; nxt = 1
        flist = []
        for fn in files:
            chars = len(C.norm_ws(C.read_text(os.path.join(d, fn))))
            if fn in known:
                flist.append({**known[fn], "title": known[fn].get("title") or C.file_title(fn), "chars": chars})
            else:
                flist.append({"no": "%03d" % nxt, "file": fn, "title": C.file_title(fn), "chars": chars, "added": C.now()[:10]}); nxt += 1; new_files += 1
        form = form_over.get(gid) or (og or {}).get("form") or guess_form(name, flist)
        author = author_over.get(gid) or (og or {}).get("author") or "(未标)"
        cat["groups"].append({"group_id": gid, "name": name, "form": form, "author": author, "source_dir": d, "files": flist,
                              "n_files": len(flist), "total_chars": sum(x["chars"] for x in flist)})
    cat["total_files"] = sum(g["n_files"] for g in cat["groups"]); cat["total_chars"] = sum(g["total_chars"] for g in cat["groups"])
    C.write_json(C.W(P, "catalog.json"), cat)
    # 规模表：按形态汇总篇数，对着门槛说够不够
    by_form = {}
    for g in cat["groups"]:
        by_form.setdefault(g["form"], {"pieces": 0, "chars": 0, "groups": [], "authors": set()})
        by_form[g["form"]]["pieces"] += g["n_files"]; by_form[g["form"]]["chars"] += g["total_chars"]
        by_form[g["form"]]["groups"].append(g["group_id"]); by_form[g["form"]]["authors"].add(g["author"])
    print(f"组 {len(cat['groups'])} | 文本文件 {cat['total_files']} | 字符 {cat['total_chars']:,} | 非文本 {len(nontext)}（列在 catalog.nontext，转文字后 --update）" + (f" | 本次新增 {new_files}" if update else ""))
    print("| 组 | 名称 | 形态 | 来源人 | 篇 | 字符 |\n|---|---|---|---|---|---|")
    for g in cat["groups"]:
        print(f"| {g['group_id']} | {g['name'][:24]} | {g['form']} | {g['author']} | {g['n_files']} | {g['total_chars']:,} |")
    print("\n| 形态 | 篇 | 字符 | 来源人 | 够不够（一个类型的参考线） |\n|---|---|---|---|---|")
    for form, v in by_form.items():
        th = C.MIN_PIECES["long" if form in C.LONG_FORMS else "default"]
        verdict = f"篇数够聚类型（单类型 ≥ {th} 篇才出技能）" if v["pieces"] >= th * 2 else (f"偏薄：{v['pieces']} 篇，可能只够 1 个类型或只给表达样品" if v["pieces"] >= th else f"不够：{v['pieces']} 篇 < {th}，只给表达样品")
        print(f"| {form} | {v['pieces']} | {v['chars']:,} | {'、'.join(sorted(v['authors']))} | {verdict} |")
    unl = [g["group_id"] for g in cat["groups"] if g["author"] == "(未标)"]
    if unl:
        print(f"\n提醒：{','.join(unl)} 未标来源人。拆对方的料要标 `--author {unl[0]}=某某`；多人料混在一起时成品只能写「类型，不是某人」。")
    long_forms = [fm for fm in by_form if fm in C.LONG_FORMS]
    if long_forms:
        print(f"\n**先问使用者要什么**（料里有 {'、'.join(long_forms)}）：想学他讲课 / 直播的那个感觉、照他的结构做自己的 → 本技能；想让它替自己判断、做事 → 推荐同仓 amb-beiming（那是用自己的料炼分身）。答案写进预检报告。")
    shorts = [(g["group_id"], f["file"], f["chars"]) for g in cat["groups"] for f in g["files"] if f["chars"] < C.SHORT_PIECE_CHARS]
    if shorts:
        print(f"\n提醒：{len(shorts)} 篇不到 {C.SHORT_PIECE_CHARS} 字（{'；'.join(f'{g} {fn[:20]}（{c} 字）' for g, fn, c in shorts[:4])}{'…' if len(shorts) > 4 else ''}）。几十个字没头没尾，多半拆不出开头 / 中间 / 结尾。问使用者收不收：收，写法书里这类篇的结尾可与开头合并、但会拉低这一类的结构清晰度；不收，用 --form 之外的办法——把它们移出作品目录再 survey。")
    if any(g["form"] == "其他" for g in cat["groups"]):
        print("提醒：有组形态猜成「其他」，用 `--form gXX=<形态>` 改（形态决定一篇的单位与起手骨架）。")
    if update:
        update_report(P, cat, old)
    else:
        print("\n接着：paoding.py ingest（一篇一原件进原件库）→ 写 work/docs/预检报告.md（结论：可开工 / 收缩到某几个形态 / 补料）")
    C.pipeline_log(P, "P1", f"survey：{cat['total_files']} 篇 / {cat['total_chars']:,} 字符 / {len(by_form)} 种形态" + ("（--update）" if update else ""))

def update_report(P, cat, old):
    """增量三档 + 来源人提醒 → work/docs/增量报告.md。新料 = catalog 里 added 为今天、且旧 catalog 没有的文件。"""
    old_files = {(g["group_id"], f["file"]) for g in (old or {}).get("groups", []) for f in g["files"]}
    new = {}  # form -> [(group, file dict)]
    for g in cat["groups"]:
        for f in g["files"]:
            if (g["group_id"], f["file"]) not in old_files:
                new.setdefault(g["form"], []).append((g, f))
    if not new:
        print("\n增量：没有新文件。"); return
    confirmed = {}  # form -> types dict
    for fm in set(new):
        t = C.load_types(P, fm, must=False)
        if t and t.get("confirmed_at"):
            confirmed[fm] = t
    idx = C.orig_index(P)
    L = [f"# 增量报告（{C.now()[:16]}）", "", "新料按「是不是同一批次、够不够」分三档。新形态的料**不并进旧类型**——不同形态硬并会做成垃圾；够料就当新形态在同一个箱子里出新技能（路由器先判形态），不够就只入原件库。", ""]
    L += ["| 形态 | 新篇 | 来源人 | 档 | 结论 | 下一步 |", "|---|---|---|---|---|---|"]
    for fm, items in new.items():
        n = len(items); authors = sorted({g["author"] for g, _ in items})
        th = C.MIN_PIECES["long" if fm in C.LONG_FORMS else "default"]
        if fm in confirmed:
            old_authors = {idx[m]["author"] for t in confirmed[fm].get("types", []) for m in t.get("members", []) if m in idx}
            newcomers = [a for a in authors if a not in old_authors]
            tier, verdict = "①", f"形态已有、类型已确认：正常增量，只给这 {n} 篇分类，旧类型不动"
            nxt = f"paoding.py ingest → cluster {fm} --update → 使用者看新增/变动 → confirm {fm} → 受影响类型 pattern --update → check"
            if newcomers:
                verdict += f"。**但来源人 {'、'.join(newcomers)} 是新的**，写法可能与旧类型不同：建议让聚类型的子代理单独判像不像，像才并入，不像就提新类型（要再过使用者）"
        elif n >= th:
            tier, verdict = "②", f"**新形态，不是同一批次**；{n} 篇 ≥ 参考线 {th}，够聚类型。不并进旧类型；当新形态走一遍聚类型，在同一个箱子里出新技能"
            nxt = f"paoding.py ingest → 在预检报告补一行「{fm} 可开工」→ cluster {fm} → 使用者确认 → confirm → pattern → check → compose → 路由器重写（compose --router）"
        else:
            tier, verdict = "③", f"**新形态，不是同一批次，也不够**：{n} 篇 < 参考线 {th}。只入原件库标待补料，不出技能、不动旧的"
            nxt = f"paoding.py ingest（只存原件）；补到 ≥ {th} 篇再 cluster {fm}；或使用者点名其中一篇做范文型（exemplar）"
        L.append(f"| {fm} | {n} | {'、'.join(authors)} | {tier} | {verdict} | {nxt} |")
    L += ["", "## 新文件", ""] + [f"- {fm}｜{g['group_id']} {g['name']}｜{f['file']}（{f['chars']} 字）" for fm, items in new.items() for g, f in items]
    L += ["", "旧类型、旧写法书、旧技能在这一步一个字没动；只有 cluster --update 之后被分进去的新篇会让对应类型的 check / lint 变 stale。"]
    out = C.W(P, "docs", "增量报告.md"); C.write_text(out, "\n".join(L) + "\n")
    print(f"\n增量报告 → {os.path.relpath(out, P)}")
    for l in L[5:5 + len(new)]:
        print(l)

if __name__ == "__main__":
    main()
