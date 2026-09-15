# -*- coding: utf-8 -*-  (selfcheck-exempt：本文件含成品禁词的正则，自检时跳过禁词扫描)
"""P5 门槛（交付时复检）：查每个类型技能是否按 product-spec 的形态写、路由器是否完整、成品是否自包含。
用法：python3 lint_product.py [<skills 目录>] [--product <成品目录>] [--project P]
默认查 work/draft/skills/。--product 时额外查：README 存在、根 scripts/fact_check.py 存在、全目录无 work/ 路径与本机绝对路径。
体检过了不等于好（那要轻验收）；体检不过不进验收、不交付。退出码：有 FAIL 为 1。"""
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

BAD_PROCESS = re.compile(r"按需读取|本轮|待执行者|执行 agent|子代理|主会话|主代理|总控")
BAD_DISCLAIM = re.compile(r"此为编者|此为归纳|不冒充|非作者原话|编者判断|免责")
ABS_PATH = re.compile(r"(?:/Users/|/home/|[A-Za-z]:\\\\)")

def frontmatter(s):
    m = re.match(r"---\n(.*?)\n---", s, re.S)
    d = {}
    if m:
        for l in m.group(1).splitlines():
            if ":" in l and not l.startswith(" "):
                k, v = l.split(":", 1); d[k.strip()] = v.strip()
    return d

def check_skill(skills_dir, d, is_router, all_dirs, bodies, exemplar=False):
    p = os.path.join(skills_dir, d, "SKILL.md"); s = C.read_text(p); size = os.path.getsize(p); res = []
    fm = frontmatter(s)
    res.append(("frontmatter 有 name 与 description", bool(fm.get("name")) and bool(fm.get("description"))))
    res.append(("name 等于目录名", fm.get("name") == d))
    if is_router:
        links = re.findall(r"\]\(([^)#\s]+)\)", s)
        referenced = {os.path.basename(os.path.dirname(t.rstrip("/"))) if t.endswith("SKILL.md") else os.path.basename(t.rstrip("/")) for t in links if not t.startswith("http")}
        res.append(("路由器引用了全部类型技能", all(t in referenced for t in all_dirs if t != d)))
        res.append(("路由器无悬空引用", all(os.path.exists(os.path.normpath(os.path.join(skills_dir, d, t))) for t in links if not t.startswith("http"))))
        res.append(("先判形态再判类型（有形态一级与路由表）", bool(re.search(r"形态", s)) and bool(re.search(r"路由表|归哪个|归哪一个", s))))
        res.append(("有交付后导航", bool(re.search(r"导航|接着|下一步", s))))
    else:
        secs = re.split(r"(?m)^##\s+", s)
        def sec(name):
            return next((b for b in secs if re.match(r"[^\n]*" + name, b)), "")
        res.append(("开头有「警示：范文里的具体内容不能进稿」一行", bool(re.search(C.WARNING_RX, s))))
        res.append(("有「交付纪律」一节", bool(sec("交付纪律"))))
        disc = sec("交付纪律")
        res.append(("交付纪律写明先成为他再动笔", bool(re.search(r"先成为他|成为他再", disc or s))))
        res.append(("交付纪律写明默认只交一版", bool(re.search(r"默认只交一版|默认交一版|只交一版", disc or s))))
        res.append(("没把「并排两版」当默认动作", not re.search(r"(?<![不别])(?<!不要)(?:并排给两版|并列给两版|同时给出两版)", s)))
        res.append(("交付纪律写明事实不搬（只借句式与结构）", bool(re.search(r"不搬|只借(?:句式|结构)", disc or s))))
        soul = sec("先成为他")
        res.append(("有「先成为他」一节（Phase 0a）", bool(soul)))
        need_q = 1 if exemplar else 2  # 范文型只有一篇，魂条数可以少
        res.append((f"先成为他：≥ {need_q} 条带编号引文 + 动笔前三句", len(re.findall(C.ORIG_ID, soul)) >= need_q and bool(re.search(r"三句|先注意什么|替谁说话|带走哪一句", soul))))
        res.append(("先成为他：含读者账五问（停下来 / 帮他 / 为什么看 / 看我的 / 种草）", sum(bool(re.search(rx, soul)) for _, rx in C.READER_QS) >= 4))
        facts = sec("事实清单")
        res.append(("有「事实清单」（F01…）", bool(re.search(r"(?m)^##+\s*(?:器[·、]?\s*)?事实清单", s)) and bool(re.search(r"F0?1\b", s))))
        res.append(("事实清单含「凭什么」类的项（身份 / 领域 / 立场）", bool(re.search(r"凭什么|身份|年限|真懂|站哪", facts))))
        res.append(("有「骨架」一节（成品骨架表）", bool(re.search(r"(?m)^##+\s*(?:成品)?骨架", s))))
        phases = re.split(r"(?m)^##+\s*Phase\s*\d", s)[1:]
        res.append(("写法：Phase ≥ 2（每小段一个 Phase）", len(phases) >= 2))
        res.append(("每个 Phase 点名写法书小段（pattern.md 第 N 小段）", all(re.search(r"pattern\.md\s*第\s*\d+\s*小段", ph) for ph in phases) if phases else False))
        res.append(("每个 Phase 有「暗」行（这段要达成什么）", all(re.search(r"(?m)^\s*[-*]\s*暗[：:]", ph) for ph in phases) if phases else False))
        res.append(("每个 Phase 点名了句式引文「…」（编号）或写明「候选无」", all(re.search(C.ORIG_ID, ph) or "候选无" in ph for ph in phases) if phases else False))
        res.append(("Phase 里有槽位句或追问（信息不足不靠常识填）", any(re.search(r"〔|追问|先问|待补|可改", ph) for ph in phases) if phases else False))
        res.append(("有「不归这里」的交接一节", bool(re.search(r"(?m)^##+\s*不归", s))))
        res.append(("有「来源与边界」一节，写明是类型不是某人", bool(re.search(r"(?m)^##+\s*(?:来源|边界)", s)) and bool(re.search(r"不是某|不代表|不是.{0,6}本人", s))))
        if exemplar:
            res.append(("范文型：写明只有一篇范文", bool(re.search(r"只有一篇范文", s))))
        chk = sec("交付前自查") or sec("自查")
        res.append(("有「交付前自查」且写明不进正文、末尾留一行", bool(chk) and bool(re.search(r"不进(?:交给使用者的)?正文|不进正文", s)) and bool(re.search(r"需要(?:逐句)?核对来源就说一声|要核对来源就说一声", s))))
        res.append(("自查含魂四问（站错边 / 说破 / 任务 / 从不用）+ 读者一问（种草）", sum(bool(re.search(k, chk)) for k in (r"站错边|站.{0,3}边", r"说破|说教", r"任务", r"从不用|禁区")) >= 3 and bool(re.search(r"种草", chk))))
        n_ref = len(re.findall(r"references/pattern\.md", s))
        res.append((f"点名 references/pattern.md ≥ 3 处（现 {n_ref}）", n_ref >= 3))
        res.append(("写明 references 按小段定位读取", bool(re.search(r"按小段|按编号|定位读取|第\s*\d+\s*小段", s))))
        rd = os.path.join(skills_dir, d, "references")
        res.append(("自带 references/pattern.md", os.path.exists(os.path.join(rd, C.PATTERN))))
        res.append(("自带 scripts/fact_check.py", os.path.exists(os.path.join(skills_dir, d, "scripts", "fact_check.py"))))
        od_ = os.path.join(rd, "originals")
        res.append(("自带 references/originals/ 且非空（成品要重范文）", os.path.isdir(od_) and any(f.endswith(".md") for f in os.listdir(od_))))
        cited = set(re.findall(r"references/originals/(" + C.ORIG_ID + r")\.md", s))
        missing_o = [i for i in cited if not os.path.exists(os.path.join(od_, i + ".md"))]
        res.append((f"SKILL.md 点到的范文文件都在（缺 {len(missing_o)}）", not missing_o))
        # 引文逐字：优先按工程原件库核；没有工程时按技能自带的 originals 核；两者都没有则不算通过
        local = {}
        od = os.path.join(rd, "originals")
        if os.path.isdir(od):
            for fn in os.listdir(od):
                if fn.endswith(".md"):
                    local[fn[:-3]] = C.match_text(C.split_frontmatter(C.read_text(os.path.join(od, fn)))[1])
        pool = bodies or local
        if pool:
            n, bad = C.check_quotes(s, pool)
            fp = os.path.join(rd, C.PATTERN)
            if os.path.exists(fp):
                pt = C.read_text(fp); n2, bad2 = C.check_quotes(pt, pool); n += n2; bad += bad2
                for q, i in C.example_blocks(pt):
                    if i not in pool or C.norm_ws(q) not in pool[i]:
                        bad.append((q, i, "例块不是原件逐字子串"))
            res.append((f"SKILL.md 与 pattern.md 引文、例块逐字且编号正确（不符 {len(bad)} 条）", not bad))
        else:
            res.append(("引文核验：找不到原件库也没有自带 originals，无法核（不算通过）", False))
    body = "\n".join(l for l in s.splitlines() if not l.strip().startswith("原件依据"))
    res.append(("正文无过程用语", not BAD_PROCESS.search(body)))
    res.append(("正文无免责句", not BAD_DISCLAIM.search(body)))
    res.append(("无本机绝对路径", not ABS_PATH.search(s)))
    links = re.findall(r"\]\(([^)#\s]+)\)", s)
    res.append(("相对链接可解析", all(os.path.exists(os.path.normpath(os.path.join(skills_dir, d, t))) for t in links if not t.startswith(("http", "<")))))
    res.append(("正文 ≥ 1KB（路由器）/ 3KB（类型技能），空壳不算完成", size >= (1000 if is_router else 3000)))
    fails = [n for n, ok in res if not ok]
    print(f"{'FAIL' if fails else 'PASS'}  {d:<32} {size:>6}B  " + ("; ".join(fails) if fails else "全部通过"))
    if not is_router and size > C.SKILL_SIZE_WARN:
        print(f"      提醒：SKILL.md {size // 1024} KB > {C.SKILL_SIZE_WARN // 1024} KB。运行时读得越多越容易漏；Phase 里只留「读 / 暗 / 看 / 用 / 照 / 写实 / 气口 / 交」八行，解释性的话搬回写法书")
    return fails

def main():
    usage = "用法：lint_product.py [<skills 目录>] [--product <成品目录>] [--project P]"
    pos, o, f = C.parse_args(sys.argv[1:], opts=("--product",), usage=usage)
    P = C.project_root(o.get("--project")); product = o.get("--product")
    if len(pos) > 1:
        C.die(usage)
    skills_dir = os.path.join(product, "skills") if product else (pos[0] if pos else C.W(P, "draft", "skills"))
    if not os.path.isdir(skills_dir):
        C.die(f"没有技能目录：{skills_dir}\n先做：P5 compose 并派子代理")
    dirs = sorted(d for d in os.listdir(skills_dir) if os.path.exists(os.path.join(skills_dir, d, "SKILL.md")))
    if not dirs:
        C.die("技能目录里没有 SKILL.md")
    prefix = C.project_meta(P).get("prefix") if os.path.exists(C.W(P, "project.json")) else min(dirs, key=len)
    idx = C.orig_index(P); bodies = C.load_bodies(P, list(idx.keys())) if idx else {}
    exemplars = {f"{prefix}-{C.ft_key(fm, t['id'])}" for fm, t in C.all_confirmed_types(P) if t.get("exemplar")} if idx else set()
    total = 0
    for d in dirs:
        total += len(check_skill(skills_dir, d, d == prefix, dirs, bodies, exemplar=d in exemplars))
    if product:
        extra = [("成品有 README.md", os.path.exists(os.path.join(product, "README.md"))),
                 ("成品根有开放资产 scripts/fact_check.py", os.path.exists(os.path.join(product, "scripts", "fact_check.py")))]
        bad = []
        for dp, dn, fn in os.walk(product):
            for x in fn:
                if x.endswith((".md", ".json", ".py")):
                    t = C.read_text(os.path.join(dp, x))
                    if re.search(r"(?<![\w/-])work/", t) or ABS_PATH.search(t):
                        bad.append(os.path.relpath(os.path.join(dp, x), product))
        extra.append(("成品内无 work/ 路径与本机绝对路径", not bad))
        for n, ok in extra:
            print(("PASS  " if ok else "FAIL  ") + n + ("" if ok else "：" + ", ".join(bad[:5])))
        total += sum(1 for _, ok in extra if not ok)
    C.record_stage(P, "lint_product" if product else "lint", C.skill_inputs(skills_dir, dirs), ok=(total == 0), extra={"fails": total})
    print("---", "有 FAIL" if total else "全部通过", f"（{len(dirs)} 个技能）")
    sys.exit(1 if total else 0)

if __name__ == "__main__":
    main()
