# -*- coding: utf-8 -*-
"""P2 切篇：按 catalog 把每个文件原模原样存成一个原件 → work/kb/originals/<oGG_FFF>.md + index.jsonl。
用法：python3 ingest.py [--project P] [--force]
  --force  重写已存在的原件（默认幂等：已有的不动，只补新的；P6 增量就是再跑一次）
原件 = 文件头（id / author / form / group / file / title / chars）+ 正文逐字。正文由脚本从文件生成，子代理不抄、不改字——原件层零折损。
短视频 / 直播 / 课程转写常带平台导出的元数据行（时间、时长、Keywords），正文从第一个说话人段起；前 40 行内找不到说话人标签就取全文。
为什么有这一步：拆解一压进提示词，原文就没了。原件在，引文才能核、覆盖才能算、新料才能对照。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

USAGE = "用法：ingest.py [--project P] [--force]"

def body_of(text, form):
    """长形态与短视频转写：从第一个说话人段起；朋友圈 / 公众号 / 文案：全文。"""
    if form in ("直播", "课程", "短视频"):
        lines = (text or "").splitlines()
        for i, l in enumerate(lines[:40]):
            if C.SPEAKER_RX.match(l):
                return "\n".join(lines[i:]).strip()
    return (text or "").strip()

def main():
    pos, o, f = C.parse_args(sys.argv[1:], flags=("--force",), usage=USAGE)
    if pos:
        C.die(USAGE)
    P = C.project_root(o.get("--project")); force = "--force" in f
    cat = C.catalog(P) or C.die("缺 work/catalog.json\n先做：paoding.py survey --corpus <作品目录>")
    od = C.W(P, "kb", "originals"); os.makedirs(od, exist_ok=True)
    idx = C.orig_index(P); new = kept = empty = 0
    for g in cat["groups"]:
        for fi in g["files"]:
            oid = f"o{g['group_id'][1:]}_{fi['no']}"; p = os.path.join(od, oid + ".md")
            if os.path.exists(p) and not force:
                kept += 1
                if oid not in idx:
                    idx[oid] = {"id": oid, "author": g["author"], "form": g["form"], "group_id": g["group_id"], "group": g["name"], "file": fi["file"], "title": fi["title"], "chars": fi["chars"], "path": os.path.relpath(p, P)}
                continue
            src = os.path.join(g["source_dir"], fi["file"])
            if not os.path.isfile(src):
                print(f"跳过 {oid}：来源文件不在 {src}"); continue
            body = body_of(C.read_text(src), g["form"])
            if not body:
                empty += 1; print(f"跳过 {oid}：正文为空（{fi['file']}）"); continue
            fm = "\n".join([f"id: {oid}", f"author: {g['author']}", f"form: {g['form']}", f"group: {g['group_id']} {g['name']}", f"file: {fi['file']}", f"title: {fi['title']}", f"chars: {len(C.norm_ws(body))}"])
            C.write_text(p, f"---\n{fm}\n---\n{body}\n")
            idx[oid] = {"id": oid, "author": g["author"], "form": g["form"], "group_id": g["group_id"], "group": g["name"], "file": fi["file"], "title": fi["title"], "chars": len(C.norm_ws(body)), "path": os.path.relpath(p, P)}
            new += 1
    # 形态 / 来源人以 catalog 为准（survey --form / --author 改过要跟上），文件头也同步
    for g in cat["groups"]:
        for fi in g["files"]:
            oid = f"o{g['group_id'][1:]}_{fi['no']}"
            if oid in idx and (idx[oid]["form"] != g["form"] or idx[oid]["author"] != g["author"]):
                idx[oid]["form"] = g["form"]; idx[oid]["author"] = g["author"]
                p = os.path.join(od, oid + ".md")
                if os.path.exists(p):
                    fm, body = C.split_frontmatter(C.read_text(p)); fm["form"] = g["form"]; fm["author"] = g["author"]
                    C.write_text(p, "---\n" + "\n".join(f"{k}: {v}" for k, v in fm.items()) + "\n---\n" + body)
    rows = [idx[k] for k in sorted(idx)]
    C.write_jsonl(os.path.join(od, "index.jsonl"), rows)
    by = {}
    for r in rows:
        by[r["form"]] = by.get(r["form"], 0) + 1
    print(f"原件库 {len(rows)} 篇（新写 {new}，已有 {kept}，空正文跳过 {empty}）：" + "，".join(f"{k} {v}" for k, v in by.items()))
    print(f"→ {os.path.relpath(od, P)}/<编号>.md，索引 index.jsonl。接着：写预检报告 → paoding.py cluster <形态>")
    C.record_stage(P, "ingest", [os.path.join(od, "index.jsonl"), C.W(P, "catalog.json")], extra={"originals": len(rows)})
    C.pipeline_log(P, "P2", f"ingest：原件 {len(rows)}（新 {new}）")

if __name__ == "__main__":
    main()
