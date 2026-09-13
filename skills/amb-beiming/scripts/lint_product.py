# -*- coding: utf-8 -*-  (selfcheck-exempt：本文件含成品禁词的正则，自检时跳过禁词扫描)
"""成品体检（S6 门槛；S8 复检）：查每个任务技能是否按 product-spec 的六层形态写、路由器是否完整、成品是否自包含。
用法：python3 lint_product.py [<skills 目录>] [--product <成品目录>] [--project P]
默认查 work/draft/skills/。--product 时额外查：README 存在、scripts/fact_check.py 存在、路由器引用的技能全部存在、全目录无 work/ 路径与本机绝对路径。
体检过了不等于好（那要 S7 盲评）；体检不过不进 S7。退出码：有 FAIL 为 1。"""
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

BAD_PROCESS = re.compile(r"按需读取|本轮|待执行者|执行 agent|子代理|主会话|主代理|总控")
BAD_DISCLAIM = re.compile(r"此为编者|此为归纳|不冒充|非作者原话|编者判断|免责")
ABS_PATH = re.compile(r"(?:/Users/|/home/|[A-Za-z]:\\\\)")

def frontmatter(s):
    m = re.match(r"---\n(.*?)\n---", s, re.S)
    if not m:
        return {}
    d = {}
    for l in m.group(1).splitlines():
        if ":" in l and not l.startswith(" "):
            k, v = l.split(":", 1); d[k.strip()] = v.strip()
    return d

def check_skill(skills_dir, d, is_router, all_dirs, P=None, tid=None):
    p = os.path.join(skills_dir, d, "SKILL.md"); s = C.read_text(p); size = os.path.getsize(p); res = []
    fm = frontmatter(s)
    res.append(("frontmatter 有 name 与 description", bool(fm.get("name")) and bool(fm.get("description"))))
    res.append(("name 等于目录名", fm.get("name") == d))
    if is_router:
        links = re.findall(r"\]\(([^)#\s]+)\)", s); referenced = {os.path.basename(os.path.dirname(t.rstrip("/"))) if t.endswith("SKILL.md") else os.path.basename(t.rstrip("/")) for t in links if not t.startswith("http")}
        tasks = [x for x in all_dirs if x != d]
        res.append(("路由器引用了全部任务技能", all(t in referenced for t in tasks)))
        res.append(("路由器无悬空引用", all(os.path.exists(os.path.normpath(os.path.join(skills_dir, d, t))) for t in links if not t.startswith("http"))))
        res.append(("有任务前路由与任务后导航两节", bool(re.search(r"任务前|路由表", s)) and bool(re.search(r"任务后|导航", s))))
    else:
        secs = re.split(r"(?m)^##\s+", s)
        dao_body = next((b for b in secs if b.startswith("道")), "")
        roots = [r for r in re.split(r"(?m)^###\s+", dao_body)[1:] if not re.match(r"^(外源|编排者|参考|说明)", r.strip())]
        res.append(("有 ## 道 且 ≥1 条根判断（参考 3–6，方法少可少）", len(roots) >= 1))
        res.append(("每条道有逐字原话引用块", all(re.search(r"(?m)^>\s*\S", r) for r in roots) if roots else False))
        res.append(("每条道标了原子 id", all(re.search(C.ATOM_ID, r) for r in roots) if roots else False))
        res.append(("每条道写了「它决定了什么」", all(("它决定了什么" in r or "用它判断" in r) for r in roots) if roots else False))
        res.append(("每条道写了语料没覆盖时怎么推", all(("怎么推" in r or "没覆盖" in r) for r in roots) if roots else False))
        phases = re.split(r"(?m)^##+\s*Phase\s*\d", s)[1:]
        res.append(("法：Phase ≥ 2", len(phases) >= 2))
        def branched(ph):
            n = len(re.findall(r"(?m)^\s*[-*]\s+.*(?:→|：|:)", ph))
            return ("成立" in ph and "不成立" in ph) or ("如果" in ph and re.search(r"否则|不成立|如果不", ph)) or n >= 3
        res.append(("每个 Phase 都按条件分支（成立/不成立、如果/否则、或 ≥3 条 条件→动作）", all(branched(ph) for ph in phases) if phases else False))
        res.append(("Phase 里有槽位句或追问（信息不足不靠常识填）", any(re.search(r"〔|问使用者|问用户|追问|先问|待补|可改", ph) for ph in phases) if phases else False))
        res.append(("Phase 里点名了 references 的模块号或案例卡 id", bool(re.search(r"references/methods\.md\s*M\d|references/cases\.md\s*u\d", s))))
        res.append(("器：有事实清单", bool(re.search(r"(?m)^##+\s*器?[·、]?\s*事实清单", s))))
        res.append(("器：有逐句来源表 / 事实核对", bool(re.search(r"逐句来源表|fact_check", s))))
        res.append(("交付纪律写明默认只交一版", bool(re.search(r"默认只交一版|默认交一版|只交一版", s))))
        # 前面加了"不/别/不要"的是正确表述（规约原话就是"不并排给两版"），不能算违规
        res.append(("没把「并排两版」当默认动作", not re.search(r"(?<![不别])(?<!不要)(?:并排给两版|并列给两版|同时给出两版)", s)))
        res.append(("器：核对写明是交付前自查、不进交给使用者的正文", bool(re.search(r"不进交给使用者的正文|不进正文|交付前自查", s))))
        res.append(("势：有一节（可写「无」）", bool(re.search(r"(?m)^##+\s*势", s))))
        res.append(("有「本任务不判的问题」一节", bool(re.search(r"(?m)^##+\s*本任务不判", s))))
        nj = next((b for b in secs if b.startswith("本任务不判")), "")
        res.append(("不判清单每条有 带什么去 / 作者判断 / 何时回来", bool(re.search(r"带什么|带.{0,20}去", nj)) and bool(re.search(C.ATOM_ID, nj)) and bool(re.search(r"回到本任务|回来|何时回", nj))))
        res.append(("有「说话风格」一节", bool(re.search(r"(?m)^##+\s*说话风格", s))))
        n_m = len(re.findall(r"methods\.md\s*M\d", s)); n_u = len(re.findall(r"cases\.md\s*u\d", s))
        res.append(("证：按 id 点名案例卡 ≥ 1 次", n_u >= 1))
        res.append((f"references 按编号点名合计 ≥ 3 处（methods M 号 {n_m} + cases u 号 {n_u}；与 06-compose 规则 3 一致）", n_m + n_u >= 3))
        res.append(("写明 references 按编号定位读取", bool(re.search(r"按编号|按模块号|定位读取", s))))
        rd = os.path.join(skills_dir, d, "references")
        res.append(("自带 references/{methods,cases,layers}.md", all(os.path.exists(os.path.join(rd, f)) for f in ("methods.md", "cases.md", "layers.md"))))
        res.append(("自带 scripts/fact_check.py（每个技能独立可装）", os.path.exists(os.path.join(skills_dir, d, "scripts", "fact_check.py"))))
        if P is not None and tid and os.path.exists(C.W(P, "kb", "pools", tid, "atoms.jsonl")):
            import check_layers as CK
            n, _ = CK.check(P, tid, p, require_layers=False, out_name="skill_mismatch.md")
            res.append((f"SKILL.md 引文逐字且与所标原子 id 一致（不符 {n} 条，见 work/kb/layers_input/{tid}/skill_mismatch.md）", n == 0))
        else:
            res.append(("SKILL.md 引文核验：找不到任务池，无法核（不算通过）", False))
    body = "\n".join(l for l in s.splitlines() if not l.strip().startswith("原子依据"))
    res.append(("正文无过程用语", not BAD_PROCESS.search(body)))
    res.append(("正文无免责句", not BAD_DISCLAIM.search(body)))
    res.append(("无本机绝对路径", not ABS_PATH.search(s)))
    links = re.findall(r"\]\(([^)#\s]+)\)", s)
    res.append(("相对链接可解析", all(os.path.exists(os.path.normpath(os.path.join(skills_dir, d, t))) for t in links if not t.startswith(("http", "<")))))
    res.append(("正文 ≥ 1KB（路由器）/ 3KB（任务技能），空壳不算完成", size >= (1000 if is_router else 3000)))
    fails = [n for n, ok in res if not ok]
    print(f"{'FAIL' if fails else 'PASS'}  {d:<24} {size:>6}B  " + ("; ".join(fails) if fails else "全部通过"))
    return fails

def main():
    usage = "用法：lint_product.py [<skills 目录>] [--product <成品目录>] [--project P]"
    pos, o, f = C.parse_args(sys.argv[1:], opts=("--product",), usage=usage)
    P = C.project_root(o.get("--project")); product = o.get("--product")
    if len(pos) > 1:
        C.die(usage)
    skills_dir = os.path.join(product, "skills") if product else (pos[0] if pos else C.W(P, "draft", "skills"))
    if not os.path.isdir(skills_dir):
        C.die(f"没有技能目录：{skills_dir}\n先做：S6 compose 并派子代理")
    dirs = sorted(d for d in os.listdir(skills_dir) if os.path.exists(os.path.join(skills_dir, d, "SKILL.md")))
    if not dirs:
        C.die("技能目录里没有 SKILL.md")
    T = C.read_json(C.W(P, "tasks.json"), {}) if os.path.exists(C.W(P, "tasks.json")) else {}
    prefix = T.get("prefix") or min(dirs, key=len)
    total = 0
    for d in dirs:
        tid = d[len(prefix) + 1:] if d.startswith(prefix + "-") else None
        total += len(check_skill(skills_dir, d, d == prefix, dirs, P, tid))
    if product:
        extra = []
        extra.append(("成品有 README.md", os.path.exists(os.path.join(product, "README.md"))))
        extra.append(("成品根有开放资产 scripts/fact_check.py（各技能自带的一份才是运行依赖）", os.path.exists(os.path.join(product, "scripts", "fact_check.py"))))
        bad = []
        for dp, dn, fn in os.walk(product):
            for f in fn:
                if f.endswith((".md", ".json", ".py")):
                    t = C.read_text(os.path.join(dp, f))
                    if re.search(r"(?<![\w/-])work/", t) or ABS_PATH.search(t):
                        bad.append(os.path.relpath(os.path.join(dp, f), product))
        extra.append(("成品内无 work/ 路径与本机绝对路径", not bad))
        for n, ok in extra:
            print(("PASS  " if ok else "FAIL  ") + n + ("" if ok else "：" + ", ".join(bad[:5])))
        total += sum(1 for _, ok in extra if not ok)
    # 记录的输入含 references/ 全部文件：S9 增量改了 references 而没重跑 lint，status 会判 stale
    C.record_stage(P, "lint_product" if product else "lint", C.skill_inputs(skills_dir, dirs), ok=(total == 0), extra={"fails": total})
    print("---", "有 FAIL" if total else "全部通过", f"（{len(dirs)} 个技能）")
    sys.exit(1 if total else 0)

if __name__ == "__main__":
    main()
