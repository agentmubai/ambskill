# -*- coding: utf-8 -*-
"""引文逐字核验：每条原子的 original、每个单元的 text，去空白后必须是来源文件的连续子串。
例外只有一种：原子 flags 含 "title"（标题只在文件名里）时，original 按来源文件名里的标题核（去空白后须是标题的子串）。
这是防"编造引文 / 改写原话"的唯一机械手段；S2 试点后、S3 每批销账前、merge 后各跑一次。
用法：python3 quote_check.py <jsonl 文件或目录> [--project <工程目录>] [--report <路径> | --no-report]
来源定位：按 id 前缀 cGG_FFF / uGG_FFF 查 work/catalog.json 的组与文件号；找不到再按 source.file 猜。
退出码：有未命中或坏行为 1。"""
import os, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

def check_file(path, P, catalog=None, cache=None):
    """返回 (total, ok, misses)。misses 每条 {file, line?, id, reason, snippet}。"""
    catalog = catalog or C.load_catalog(P); cache = cache if cache is not None else {}
    total = ok = 0; misses = []
    for r in C.read_jsonl(path):
        total += 1
        if "_bad_json" in r:
            misses.append({"file": path, "line": r["_line"], "reason": "JSON 非法：" + r["_bad_json"]}); continue
        is_unit = "unit_id" in r and "text" in r
        rid = r.get("unit_id") if is_unit else r.get("id")
        q = C.norm_ws(r.get("text") if is_unit else r.get("original"))
        if not q:
            misses.append({"file": path, "id": rid, "reason": "original/text 为空"}); continue
        if not is_unit and "title" in (r.get("flags") or []):
            src = C.locate_source(P, catalog, r.get("source"), rid)
            title = C.norm_ws(C.file_title(src) if src else (r.get("source") or {}).get("title", ""))
            if title and q in title:
                ok += 1
            else:
                misses.append({"file": path, "id": rid, "reason": "标了 title 但 original 不是文件名标题的逐字子串", "snippet": (r.get("original") or "")[:80], "title": title[:60]})
            continue
        src = C.locate_source(P, catalog, r.get("source"), rid)
        if not src:
            misses.append({"file": path, "id": rid, "reason": "定位不到来源文件（检查 catalog 与 source）", "source": r.get("source")}); continue
        if src not in cache:
            cache[src] = C.norm_ws(C.read_text(src))
        if q in cache[src]:
            ok += 1
        else:
            misses.append({"file": path, "id": rid, "reason": "不是来源文件的逐字子串", "snippet": (r.get("text") if is_unit else r.get("original"))[:80]})
    return total, ok, misses

def main():
    pos, o, f = C.parse_args(sys.argv[1:], opts=("--report",), flags=("--no-report",), usage="用法：quote_check.py <jsonl|目录> [--project P] [--report 路径 | --no-report]")
    rep = "NONE" if "--no-report" in f else o.get("--report")
    P = C.project_root(o.get("--project"))
    if len(pos) != 1:
        C.die("用法：quote_check.py <jsonl|目录> [--project P] [--report 路径 | --no-report]")
    target = pos[0]
    files = [target] if os.path.isfile(target) else sorted(glob.glob(os.path.join(target, "**", "*.jsonl"), recursive=True))
    T = O = 0; M = []; cache = {}; cat = C.load_catalog(P)
    for f in files:
        t, o, m = check_file(f, P, cat, cache); T += t; O += o; M += m
    print(f"条目 {T} | 逐字命中 {O} | 未命中 {len(M)}")
    for m in M[:20]:
        print(" -", m.get("id"), m["reason"], (m.get("snippet") or "")[:40])
    if rep != "NONE":
        rep = rep or (target.rstrip("/") + ".quote_check.json")
        C.write_json(rep, {"total": T, "ok": O, "misses": M})
        print("报告：", rep)
    sys.exit(1 if M else 0)

if __name__ == "__main__":
    main()
