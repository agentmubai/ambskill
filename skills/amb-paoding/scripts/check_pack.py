# -*- coding: utf-8 -*-
"""P4 门槛：核一个「形态-类型」的写法书 pattern.md——章齐、魂有证据、三大段、每小段七项、引文与例块逐字、覆盖表、零引用篇处置。不过不许 compose。
用法：python3 check_pack.py <形态-类型,…|all> [--project P]
查（FAIL 项）：
  1 八章都在：怎么看事（魂）/ 读者账 / 要达成什么（暗线总览）/ 结构 / 劲儿 / 开头 / 中间 / 结尾
  2 魂：≥ 3 条，每条 ≥ 2 个不同原件编号作证据——只有一处证据的是那篇的选择，不是他的魂；一条证据都没有的是形容词
  2.5 读者账：五问都答（停下来 / 帮他什么 / 为什么看这个 / 为什么看我的 / 为什么种草），答案落到 ≥ 3 个原件
  3 三大段各 ≥ 1 个小段，中间 ≥ 2 个；小段编号连续；每小段有 明 / 暗 / 凭什么 / 你要有什么才能借 / 术 / 例 / 气口 七行；
    小段可加「可循环」行（直播讲品→互动→催单这种转几轮的），但要 ≥ 2 篇范文证据——循环是料里看出来的，不按形态预设
  4 每小段「例」≥ 1 个带编号的引用块（原文整段），或术里明写「候选无」且例里写明原因
  5 每条「原话」（编号）与每个例块都是所标原件正文的逐字子串（忽略空白与说话人行）；标错编号也算不符
  6 覆盖表：每个成员被引用几处；零引用篇每篇要有处置（dispose：并入 / 排除 / 补拆）
提醒（不拦）：例块引到本类型之外的原件；「凭什么」「你要有什么」写得太短（< 10 字，多半是敷衍）；魂条里没有「而不是」。
产出：<pack>/mismatch.md、<pack>/coverage.md；记录 check:<形态-类型>。
为什么有这一步：写法书是成品技能唯一读的参考。魂写成形容词、暗线没证据、例被改写，成品就只剩壳。"""
import os, sys, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

USAGE = "用法：check_pack.py <形态-类型,…|all> [--project P]"

def check_one(P, key, idx):
    form, t = C.parse_ft(P, key); pk = C.pack_dir(P, key); members = [m for m in t["members"] if m in idx]
    bodies = C.load_bodies(P, list(idx.keys()))
    errs, warns, mism = [], [], []
    p = os.path.join(pk, C.PATTERN)
    if not os.path.exists(p):
        errs.append(f"缺 {C.PATTERN}")
        C.record_stage(P, f"check:{key}", C.pack_inputs(P, form, key), ok=False, extra={"missing": True})
        print(f"FAIL {key}: 缺 {C.PATTERN}（先 paoding.py pattern {key} 并派子代理）"); return False
    s = C.read_text(p)
    # 0 警示行：写法书开头要有「范文里的具体内容不能进稿」
    if not re.search(C.WARNING_RX, s):
        errs.append("缺开头警示行（「警示：范文里的人名、数字、行业、地名、案例、产品……一个都不能进你的稿」）")
    # 1 八章
    for k, kw in C.PATTERN_CHAPTERS.items():
        if C.chapter(s, k) is None:
            errs.append(f"缺章「{kw}」（## 标题里要含这几个字）")
    # 2 魂
    soul = C.chapter(s, "soul") or ""
    bullets = [b for b in re.findall(r"(?m)^- (.+)$", soul) if not b.startswith(("写之前", "每条写成"))]
    bullets = [b for b in bullets if "禁区" not in b[:6]]
    exemplar = bool(t.get("exemplar"))
    # 范文型只有一篇：魂从一篇里能看出多少写多少，证据 ≥ 1 处即可、≥ 1 条即可；其余类型 ≥ 3 条、每条 ≥ 2 篇
    min_bullets, min_ev = (1, 1) if exemplar else (3, 2)
    if len(bullets) < min_bullets:
        errs.append(f"魂只有 {len(bullets)} 条（要 ≥ {min_bullets}）")
    for b in bullets:
        ids = set(C.id_mentions(b))
        if len(ids) < min_ev:
            errs.append(f"魂条证据不足（要 ≥ {min_ev} 个不同原件{'；成员只有一篇又不是范文型，先并入或标 exemplar' if len(members) < 2 and not exemplar else ''}）：{b[:40]}…")
        if "而不是" not in b and "不是" not in b:
            warns.append(f"魂条没写成「他会…而不是…」的选择句：{b[:30]}…")
    # 2.5 读者账五问：每问至少出现一次关键词，且这一章至少 3 个原件编号作证据
    reader = C.chapter(s, "reader") or ""
    missing_q = [name for name, rx in C.READER_QS if not re.search(rx, reader)]
    if reader and missing_q:
        errs.append(f"读者账缺问：{'、'.join(missing_q)}（五问：停下来 / 帮他什么 / 为什么看这个 / 为什么看我的 / 为什么种草）")
    need_r = 1 if exemplar else min(3, max(1, len(members)))
    if reader and len(set(C.id_mentions(reader))) < need_r:
        errs.append(f"读者账证据不足：五问的答案要落到原件（≥ {need_r} 个不同编号）")
    # 3 三大段与小段
    segs = C.segments(s)
    for big, kw in (("open", "开头"), ("mid", "中间"), ("close", "结尾")):
        if not any(x[3] == big for x in segs):
            errs.append(f"「{kw}」下没有小段（### N 名）")
    nums = [x[0] for x in segs]
    if nums != list(range(1, len(nums) + 1)):
        errs.append(f"小段编号不连续：{nums}")
    n_mid = sum(1 for x in segs if x[3] == "mid")
    if segs and n_mid < C.MID_MIN_SEGMENTS:
        errs.append(f"「中间」只有 {n_mid} 个小段（要 ≥ {C.MID_MIN_SEGMENTS}）：三大段定位置，小段定功能，中间不能一个小段包七成篇幅")
    for n, name, body, big in segs:
        if big is None:
            errs.append(f"小段 {n} {name} 不在 开头 / 中间 / 结尾 任一章下")
        m = re.search(r"(?m)^- " + C.LOOP_LINE + r"[：:](.*)$", body)
        if m:
            ev = set(C.id_mentions(m.group(1)))
            if len(ev) < (1 if exemplar else 2):
                errs.append(f"小段 {n} {name} 标了「{C.LOOP_LINE}」但证据不足（要 ≥ 2 篇范文里这一段的结构转了两轮以上、每轮内容不同；循环是料里看出来的，不是形态给的）")
        missing = [l for l in C.SEGMENT_LINES if not re.search(r"(?m)^- " + re.escape(l) + r"[：:]", body)]
        if missing:
            errs.append(f"小段 {n} {name} 缺行：{'、'.join(missing)}")
        for l in ("凭什么", "你要有什么才能借"):
            m = re.search(r"(?m)^- " + l + r"[：:](.*)$", body)
            if m and len(m.group(1).strip()) < 10:
                warns.append(f"小段 {n}「{l}」只有 {len(m.group(1).strip())} 字，多半是敷衍")
        ex = C.example_blocks(body)
        if not ex and "候选无" not in body:
            errs.append(f"小段 {n} {name}「例」没有带编号的引用块，也没写「候选无」")
    # 5 逐字（「」引文 + 例块）
    n_q, bad = C.check_quotes(s, bodies); mism += [(q, i, why) for q, i, why in bad]
    for q, i in C.example_blocks(s):
        if i not in bodies:
            mism.append((q, i, f"原件 {i} 不在原件库")); continue
        if C.norm_ws(q) not in bodies[i]:
            mism.append((q, i, f"例块不是原件 {i} 的逐字子串（被改写或拼接）"))
    mism = list(dict.fromkeys(mism))
    if mism:
        errs.append(f"引文 / 例块不符 {len(mism)} 条（见 mismatch.md）")
    outside = {i for _, i in C.example_blocks(s) if i in bodies and i not in members}
    if outside:
        warns.append(f"例块引了本类型之外的原件 {','.join(sorted(outside)[:4])}：通过但提示")
    # 6 覆盖
    cnt = collections.Counter(C.id_mentions(s))
    zero = [m for m in members if cnt.get(m, 0) == 0]
    disp = C.read_json(os.path.join(pk, "dispositions.json"), {})
    undisposed = [m for m in zero if m not in disp]
    rows = ["# 覆盖表：" + key, "", f"成员 {len(members)} 篇；被引用 {len(members) - len(zero)} 篇；零引用 {len(zero)} 篇（每篇要有处置，`paoding.py dispose {key} <编号> --as 并入|排除|补拆`）", "",
            "| 编号 | 标题 | 字数 | 被引处数 | 处置 |", "|---|---|---|---|---|"]
    for m in members:
        d = disp.get(m, {})
        rows.append(f"| {m} | {idx[m]['title'][:30]} | {idx[m]['chars']} | {cnt.get(m, 0)} | {(d.get('as', '') + ('：' + d['note'] if d.get('note') else '')) if d else ('**待处置**' if m in zero else '')} |")
    ex_ids = {i for _, i in C.example_blocks(s)}
    rows += ["", f"进了「例」的范文 {len(ex_ids)} 篇：{'、'.join(sorted(ex_ids)) or '（无）'}", f"「」引文 {n_q} 条，例块 {len(C.example_blocks(s))} 个", ""]
    C.write_text(os.path.join(pk, "coverage.md"), "\n".join(rows) + "\n")
    if undisposed:
        errs.append(f"零引用篇 {len(undisposed)} 篇没有处置：{','.join(undisposed[:6])}{'…' if len(undisposed) > 6 else ''}")
    want = min(C.SAMPLES_MIN, len(members))
    if len(ex_ids) < want:
        warns.append(f"进「例」的范文只有 {len(ex_ids)} 篇，建议 {want}–{min(C.SAMPLES_MAX, len(members))} 篇")
    C.write_text(os.path.join(pk, "mismatch.md"), "# 以下引文 / 例块不是所标原件的逐字子串，必须换成逐字原话 / 改对编号 / 删除\n\n" + ("\n".join(f"- {q[:80]}{'…' if len(q) > 80 else ''}　← {why}" for q, i, why in mism) or "（无）") + "\n")
    # 篇数少的类型，魂只是轮廓：写法书开头要写明（不拦，提醒）
    if len(members) < C.SOUL_THIN_PIECES and not exemplar and not re.search(r"轮廓|不是定论|只是.{0,4}(?:轮廓|参考)", s[:1500]):
        warns.append(f"成员只有 {len(members)} 篇（< {C.SOUL_THIN_PIECES}），魂拆不准：写法书开头写一句「基于 {len(members)} 篇，魂只是轮廓」，成品的边界节也带上")
    ok = not errs
    C.record_stage(P, f"check:{key}", C.pack_inputs(P, form, key), ok=ok, extra={"quotes": n_q, "examples": len(C.example_blocks(s)), "mismatch": len(mism), "segments": len(segs), "zero_ref": len(zero), "members": len(members)})
    if ok:
        digest_for_user(P, key, form, t, s, segs, bullets, members)
    for w in warns:
        print(f"提醒 {key}: {w}")
    for e in errs:
        print(f"FAIL {key}: {e}")
    print(f"{'PASS' if ok else 'FAIL'} {key}：小段 {len(segs)}，魂 {len(bullets)} 条，引文 {n_q} + 例块 {len(C.example_blocks(s))}，不符 {len(mism)}；成员 {len(members)}，零引用 {len(zero)}（已处置 {len(zero) - len(undisposed)}）→ {os.path.relpath(pk, P)}/coverage.md")
    return ok

def digest_for_user(P, key, form, t, s, segs, bullets, members):
    """写法书通过后，顺手给使用者一页摘要：他怎么看事、读者账、结构。不设门、不加参与点——但魂是「他怎么看事」，使用者该瞄一眼。
    去掉编号，保留「」原话（那是给人看的证据）。"""
    L = [f"# 写法书摘要：{t['name']}（{form}）", "", f"基于 {len(members)} 篇。" + ("篇数少，下面的「怎么看事」只是轮廓，不是定论。" if len(members) < C.SOUL_THIN_PIECES else ""), "",
         "## 他是怎么看事的", ""]
    for b in bullets:
        L.append("- " + re.sub(r"\s*[（(]" + C.ORIG_ID + r"[)）]", "", b).strip())
    ban = re.search(r"(?m)^- \*\*禁区[^*]*\*\*[：:]?\s*(.+)$", C.chapter(s, "soul") or "")
    if ban:
        L += ["", f"**他从不做的：** {ban.group(1).strip()}"]
    reader = C.chapter(s, "reader") or ""
    L += ["", "## 读者为什么会看、为什么会被种草", ""] + [("- " + re.sub(r"\s*[（(]" + C.ORIG_ID + r"[)）]", "", b).strip()) for b in re.findall(r"(?m)^- (.+)$", reader)]
    L += ["", "## 这一类怎么排", "", "| 大段 | 小段 |", "|---|---|"] + [f"| {{'open': '开头', 'mid': '中间', 'close': '结尾'}}[big] if big else '?' | {n} {name} |".replace("{{", "{").replace("}}", "}") for n, name, _, big in segs]
    L += ["", "如果你觉得哪一条「怎么看事」不像他，或者缺了一条，说一声：改写法书，不用重拆。"]
    out = C.W(P, "docs", f"写法书摘要-{key}.md"); C.write_text(out, "\n".join(L) + "\n")
    print(f"  给使用者看的摘要 → {os.path.relpath(out, P)}")

def main():
    pos, o, f = C.parse_args(sys.argv[1:], usage=USAGE)
    if len(pos) != 1:
        C.die(USAGE)
    P = C.project_root(o.get("--project")); idx = C.orig_index(P)
    keys = [C.ft_key(fm, t["id"]) for fm, t in C.all_confirmed_types(P)]
    bad = 0
    for key in C.split_names(pos[0], keys):
        if pos[0] == "all" and not os.path.exists(os.path.join(C.pack_dir(P, key), C.PATTERN)):
            print(f"{key}: 无写法书，跳过（先 pattern）"); continue
        bad += 0 if check_one(P, key, idx) else 1
    C.pipeline_log(P, "P4", f"check {pos[0]}：{'全过' if not bad else str(bad) + ' 个类型不过'}")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
