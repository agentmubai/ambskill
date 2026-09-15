# -*- coding: utf-8 -*-
"""公共函数（被其余脚本 import，不单独运行）：
工程定位、读写、原件库读取、引文识别与逐字核、阶段记录与过期判定、提示词填槽、外部 CLI 适配、评分行解析。
只依赖 Python 3.9+ 标准库。零件来自同仓 amb-beiming 的 _core.py，按本技能的数据模型裁过：这里没有原子、没有批次，只有原件。"""
import os, sys, io, re, json, time, hashlib, datetime, subprocess, string, shlex

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIG_ID = r"o\d{2}_\d{3}"                       # 原件编号：o<组两位>_<文件三位>
TEXT_EXT = (".txt", ".md", ".srt", ".vtt", ".text", ".markdown")
FORMS = ("朋友圈", "短视频", "直播", "课程", "公众号", "文案", "其他")   # 形态枚举；survey 猜、--form 改
LONG_FORMS = ("直播", "课程")                    # 长形态：一篇是一场 / 一节，篇数门槛放宽
MIN_PIECES = {"default": 15, "long": 6}         # 一个类型出技能的最少篇数（参考值，不是硬线）
# 范文全文随技能带的规则按**类型**算，不按形态：写法书「例」里点到的篇永远带；本类型成员总量 ≤ BUNDLE_ALL_MAX 就全带；超了只带例篇。
# 类型文件可用 "bundle": "all" | "samples" 强制。成品要重范文；上限只防一类几十篇长转写读不完。
BUNDLE_ALL_MAX = 100 * 1024
SAMPLES_MIN, SAMPLES_MAX = 3, 5                 # 写法书选几篇范文（成员不足 3 篇时取成员数）
PATTERN = "pattern.md"                          # 一个类型的拆解层就是这一份写法书
# 写法书必有的章（## 级）与每小段（### N 名）必有的行。名字固定，check 按它查，成品 SKILL 按它点名。
PATTERN_CHAPTERS = {"soul": "怎么看事", "reader": "读者账", "hidden": "要达成什么", "shape": "结构", "voice": "劲儿", "open": "开头", "mid": "中间", "close": "结尾"}
SEGMENT_LINES = ("明", "暗", "凭什么", "你要有什么才能借", "术", "例", "气口")
MID_MIN_SEGMENTS = 2                            # 中间至少两个小段：不许一个「中间」包七成篇幅
LOOP_LINE = "可循环"                            # 小段可加一行「- 可循环：<证据>」：结构循环——同一小段的走法在一篇里转两轮以上、每轮内容不同；≥ 2 篇范文有证据才准标；形态不决定循环
SHORT_PIECE_CHARS = 40                          # 预检把 < 40 字的篇单列，问使用者收不收（几十个字没头没尾，多半拆不出结构）
# 警示：成品 SKILL.md 与写法书开头都要有这一行（lint / check 查关键词）。范文里的具体内容是来源人的，一个都不能进使用者的稿。
WARNING_LINE = "警示：范文里的人名、数字、行业、地名、案例、产品，全是来源人的，一个都不能进你的稿。写法书和范文只借他怎么看事、每段要达成什么、结构与句式。"
WARNING_RX = r"警示[：:].*(?:范文|原文).*(?:不能|不许|不得).*(?:进|写进).*稿"
SKILL_SIZE_WARN = 25 * 1024                     # 成品 SKILL.md 超过就提醒（不拦）：同仓实测超 22KB 后新题变差
QUOTE_MIN = 4                                   # 「」引文最短 4 字：「试试」「晚安」这种短句式也要核；「」只包原话，短的也不会是自己的话
SOUL_THIN_PIECES = 5                            # 类型成员少于这个数，写法书要标「魂只是轮廓」
# 读者账五问：任何内容背后都要答——读者为什么停下来 / 我能帮他什么 / 他为什么要看这个 / 为什么看我的不看别人的 / 看完为什么被种草。check 查五问关键词。
READER_QS = (("停", r"停下来|被吸引|停住|划走"), ("帮", r"帮他|帮到|能帮"), ("看这个", r"为什么要看|为什么看这个|想知道"), ("看我", r"看我的|不看别人|凭什么是我|为什么是我"), ("种草", r"种草|被说中|信了|想要|行动"))
DEFAULT_PREFIX = "pd"
ENV = "PAODING"                                 # 环境变量前缀：PAODING_PROJECT / PAODING_AGENT / PAODING_AGENT_CMD / PAODING_AGENT_TIMEOUT
DISPOSITIONS = ("并入", "排除", "补拆")          # 零引用篇的处置枚举
SPEAKER_RX = re.compile(r"^\s*(Speaker\s*\d+|说话人\s*\d*|发言人\s*\d*|\[?\d{1,2}:\d{2}(?::\d{2})?\]?)\b", re.I)

# ---------- 命令行 ----------
def parse_args(argv, opts=(), flags=(), usage=""):
    """统一解析：opts 带值，flags 布尔；--project 对所有脚本可用。未知 --xxx 直接报错。返回 (位置参数, 带值 dict, 布尔 set)。"""
    opts = set(opts) | {"--project"}; flags = set(flags)
    pos, o, f = [], {}, set(); a = list(argv); i = 0
    while i < len(a):
        x = a[i]
        if x.startswith("--"):
            if x in opts:
                if i + 1 >= len(a) or a[i + 1].startswith("--"):
                    die(f"参数 {x} 缺值\n{usage}".rstrip())
                o[x] = a[i + 1]; i += 2; continue
            if x in flags:
                f.add(x); i += 1; continue
            die(f"未知参数 {x}\n{usage}".rstrip())
        pos.append(x); i += 1
    return pos, o, f

def die(msg, code=2):
    print(msg, file=sys.stderr); sys.exit(code)

def need(path, hint):
    if not os.path.exists(path):
        die(f"缺 {path}\n先做：{hint}")

# ---------- 工程定位 ----------
def project_root(explicit=None):
    """工程目录：--project > $PAODING_PROJECT > 当前目录。工程的标志是 work/。"""
    return os.path.abspath(explicit or os.environ.get(ENV + "_PROJECT") or os.getcwd())

def W(P, *parts):
    return os.path.join(P, "work", *parts)

def ensure_project(P):
    for d in ("prompts", "reports", "docs", "types", "kb/originals", "kb/packs", "draft/skills", "tests"):
        os.makedirs(W(P, d), exist_ok=True)
    os.makedirs(os.path.join(P, "product"), exist_ok=True)
    if not os.path.exists(W(P, "pipeline.md")):
        write_text(W(P, "pipeline.md"), "# pipeline\n\n每段结束追加一行：时间 | 段 | 做了什么 | 门槛结果 | 备注。\n\n")
    if not os.path.exists(W(P, "project.json")):
        write_json(W(P, "project.json"), {"prefix": DEFAULT_PREFIX, "toolbox": "", "note": "prefix 是技能目录前缀（ASCII 短名）；toolbox 是成品箱名，deliver 时也可给"})

def project_meta(P):
    return read_json(W(P, "project.json"), {"prefix": DEFAULT_PREFIX, "toolbox": ""})

# ---------- 读写 ----------
def read_text(p):
    return io.open(p, encoding="utf-8", errors="replace").read()

def write_text(p, s):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    tmp = p + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        f.write(s)
    os.replace(tmp, p)

def read_json(p, default=None):
    if not os.path.exists(p):
        if default is not None:
            return default
        die(f"缺 {p}")
    return json.loads(read_text(p))

def write_json(p, obj):
    write_text(p, json.dumps(obj, ensure_ascii=False, indent=1) + "\n")

def read_jsonl(p):
    out = []
    if not os.path.exists(p):
        return out
    for n, line in enumerate(io.open(p, encoding="utf-8", errors="replace"), 1):
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                out.append({"_bad_json": str(e), "_line": n})
    return out

def write_jsonl(p, rows):
    write_text(p, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))

def norm_ws(s):
    return re.sub(r"\s+", "", s or "")

def now():
    return datetime.datetime.now().isoformat(timespec="seconds")

def pipeline_log(P, stage, text):
    with io.open(W(P, "pipeline.md"), "a", encoding="utf-8") as f:
        f.write(f"- {now()} | {stage} | {text}\n")

DATE_PREFIX_RX = re.compile(r"^\s*\d{4}[-_.年]?\d{2}[-_.月]?\d{2}日?(?:[ _T\-]\d{2}[:：.\-时]\d{2}(?:[:：.\-分]\d{2}秒?)?)?[\s_\-–—.]*")

def file_title(fn):
    """文件名里的标题：去目录、扩展名、开头日期 / 时间前缀、末尾短哈希。短视频 / 帖子的标题常常只在文件名里。"""
    stem = os.path.splitext(os.path.basename(fn))[0]
    t = DATE_PREFIX_RX.sub("", stem, count=1)
    t = re.sub(r"[-_ ][0-9a-fA-F]{6,12}$", "", t).strip()
    return t or stem.strip()

# ---------- 原件库 ----------
def catalog(P):
    return read_json(W(P, "catalog.json"), None) if os.path.exists(W(P, "catalog.json")) else None

def orig_index(P):
    """kb/originals/index.jsonl → {id: row}。row = {id, author, form, group_id, group, file, title, chars, path}。"""
    return {r["id"]: r for r in read_jsonl(W(P, "kb", "originals", "index.jsonl")) if "_bad_json" not in r}

FM_RX = re.compile(r"\A---\n(.*?)\n---\n", re.S)

def split_frontmatter(text):
    """返回 (frontmatter dict, 正文)。原件文件头是 key: value 行。"""
    m = FM_RX.match(text)
    if not m:
        return {}, text
    d = {}
    for l in m.group(1).splitlines():
        if ":" in l:
            k, v = l.split(":", 1); d[k.strip()] = v.strip()
    return d, text[m.end():]

def orig_body(P, oid):
    p = W(P, "kb", "originals", oid + ".md")
    if not os.path.isfile(p):
        return None
    return split_frontmatter(read_text(p))[1]

def match_text(body):
    """逐字核用的正文形态：去掉说话人 / 时间戳行（Speaker 1 00:00:30、说话人 1 …），再去全部空白。
    转写每隔几句一行标签，一段引文跨过标签就对不上；原件文件本身原样保留，只有核对时跳过。"""
    keep = [l for l in (body or "").splitlines() if not SPEAKER_RX.match(l)]
    return norm_ws("\n".join(keep))

def load_bodies(P, ids):
    """{id: match_text(正文)}，供逐字核。"""
    out = {}
    for i in ids:
        b = orig_body(P, i)
        if b is not None:
            out[i] = match_text(b)
    return out

# ---------- 类型 ----------
def types_path(P, form):
    return W(P, "types", form + ".json")

def load_types(P, form, must=True):
    p = types_path(P, form)
    if not os.path.exists(p):
        if must:
            die(f"缺 {p}\n先做：paoding.py cluster {form} → 派子代理 → 使用者确认 → 写 work/types/{form}.json（含 confirmed_at）→ paoding.py confirm {form}")
        return None
    return read_json(p)

def all_confirmed_types(P):
    """返回 [(form, type dict)]，只含 confirmed_at 非空的形态文件。"""
    out = []
    td = W(P, "types")
    if not os.path.isdir(td):
        return out
    for f in sorted(os.listdir(td)):
        if f.endswith(".json") and not f.endswith(".draft.json"):
            t = read_json(os.path.join(td, f))
            if t.get("confirmed_at"):
                out += [(t["form"], x) for x in t.get("types", [])]
    return out

def ft_key(form, tid):
    return f"{form}-{tid}"

def parse_ft(P, key):
    """'短视频-hook' → (form, type dict)。"""
    for form, t in all_confirmed_types(P):
        if ft_key(form, t["id"]) == key:
            return form, t
    die(f"没有已确认的类型 {key}；已确认的：{', '.join(ft_key(f, t['id']) for f, t in all_confirmed_types(P)) or '（无）'}")

def split_names(s, all_items):
    return list(all_items) if s in ("all", "*") else [x for x in s.split(",") if x]

# ---------- 引文识别与逐字核 ----------
def quotes(text):
    """从 markdown 里找带原件编号的引文：「…」后 40 字内跟 oGG_FFF；> 引用块末尾带编号；表格里表头含「原话」的列且行内有编号。
    带〔〕的句子是成品句式槽位，不核。返回 [(原话, 编号)]，去重。"""
    out, lines = [], text.splitlines()
    for m in re.finditer(r"「([^」]{" + str(QUOTE_MIN) + r",})」[^「\n]{0,40}?(" + ORIG_ID + ")", text):
        out.append((m.group(1), m.group(2)))
    for i, l in enumerate(lines):
        ids = re.findall(ORIG_ID, l); ls = l.lstrip()
        if ls.startswith("> ") and ids and len(ls) > 10:  # 引用块允许缩进（写在列表项下面）
            q = re.sub(r"\s*[（(]\s*" + ORIG_ID + r"\s*[)）]\s*$", "", ls[2:].strip()).strip("「」“”")
            out.append((q, ids[-1]))
        if l.startswith("|") and ids:
            cells = [c.strip() for c in l.strip().strip("|").split("|")]
            hdr = next(([c.strip() for c in lines[k].strip().strip("|").split("|")] for k in range(i - 1, max(-1, i - 12), -1) if lines[k].startswith("|") and "原话" in lines[k]), None)
            if hdr:
                col = next((j for j, h in enumerate(hdr) if "原话" in h), None)
                if col is not None and col < len(cells) and len(cells[col]) >= QUOTE_MIN:
                    out.append((cells[col].strip("「」“”"), ids[0]))
    out = [(q, i) for q, i in out if "〔" not in q and "〕" not in q]
    seen, uniq = set(), []
    for q, i in out:
        if (q, i) not in seen:
            seen.add((q, i)); uniq.append((q, i))
    return uniq

def check_quotes(text, bodies):
    """bodies = {id: norm_ws(正文)}。返回 (引文数, 不符列表[(原话, 编号, 原因)])。"""
    qs = quotes(text); bad = []
    for q, i in qs:
        if i not in bodies:
            bad.append((q, i, f"原件 {i} 不在原件库里")); continue
        if norm_ws(q) not in bodies[i]:
            bad.append((q, i, f"不是原件 {i} 的逐字子串（被改写或拼接）"))
    return len(qs), bad

def id_mentions(text):
    """文本里出现的全部原件编号（含没带引文的），用来算覆盖。"""
    return re.findall(ORIG_ID, text)

# ---------- 写法书解析 ----------
def chapters(text):
    """按 `## ` 切章 → [(标题, 正文)]。"""
    out = []
    for b in re.split(r"(?m)^##\s+(?!#)", text)[1:]:
        head, _, body = b.partition("\n")
        out.append((head.strip(), body))
    return out

def chapter(text, key):
    """按 PATTERN_CHAPTERS 的关键词找章（标题含关键词即命中）。返回正文或 None。"""
    kw = PATTERN_CHAPTERS[key]
    for h, b in chapters(text):
        if kw in h:
            return b
    return None

def segments(text):
    """写法书里的小段：`### <序号> <名>` → [(序号, 名, 正文, 所属大段 open/mid/close/None)]。所属大段 = 它上面最近的 ## 开头 / 中间 / 结尾。"""
    out = []
    for head, body in chapters(text):
        big = next((k for k in ("open", "mid", "close") if head.strip() == PATTERN_CHAPTERS[k]), None)
        for sb in re.split(r"(?m)^(?=###\s)", body)[1:]:
            first, _, rest = sb.partition("\n")
            m = re.match(r"###\s+(\d+)\s+(.+)", first)
            if m:
                out.append((int(m.group(1)), m.group(2).strip(), rest, big))
    return out

def example_blocks(text):
    """「例」的引用块：缩进或不缩进的 `> 原文（编号）` → [(原文, 编号)]。"""
    out = []
    for l in text.splitlines():
        ls = l.lstrip(); ids = re.findall(ORIG_ID, ls)
        if ls.startswith("> ") and ids:
            out.append((re.sub(r"\s*[（(]\s*" + ORIG_ID + r"\s*[)）]\s*$", "", ls[2:].strip()), ids[-1]))
    return out

# ---------- 阶段记录与过期 ----------
def sha_files(paths, root=None):
    """输入哈希 = 相对工程根的路径 + 内容。工程搬家、/tmp 与 /private/tmp、--project 与 cd 两种写法都不变。"""
    h = hashlib.sha256()
    for p in sorted(paths):
        if os.path.isfile(p):
            rel = os.path.relpath(os.path.realpath(p), os.path.realpath(root)) if root else os.path.basename(p)
            h.update(rel.replace(os.sep, "/").encode("utf-8")); h.update(open(p, "rb").read())
    return h.hexdigest()[:16]

def record_stage(P, stage, inputs, ok=True, extra=None):
    meta = read_json(W(P, "meta.json"), {})
    meta[stage] = {"at": now(), "ok": bool(ok), "inputs_sha": sha_files(inputs, P), **(extra or {})}
    write_json(W(P, "meta.json"), meta)

def stage_state(P, stage, inputs):
    """'ok' / 'stale' / 'failed' / 'missing'。stale = 记录时的输入哈希与现在不同。"""
    rec = read_json(W(P, "meta.json"), {}).get(stage)
    if not rec:
        return "missing"
    if not rec.get("ok"):
        return "failed"
    return "ok" if rec.get("inputs_sha") == sha_files(inputs, P) else "stale"

def pack_dir(P, key):
    return W(P, "kb", "packs", key)

def pack_inputs(P, form, key):
    """check:<key> 的输入清单：写法书 + 处置 + 该形态的类型文件。check / compose / status 共用。"""
    pk = pack_dir(P, key)
    return [os.path.join(pk, PATTERN), os.path.join(pk, "dispositions.json"), types_path(P, form)]

def skill_inputs(skills_dir, dirs):
    """lint 记录的输入：SKILL.md 与 references/ 下全部文件（含 originals/）。"""
    out = []
    for d in dirs:
        sk = os.path.join(skills_dir, d, "SKILL.md")
        if os.path.exists(sk):
            out.append(sk)
        rd = os.path.join(skills_dir, d, "references")
        for dp, dn, fn in os.walk(rd) if os.path.isdir(rd) else []:
            out += [os.path.join(dp, f) for f in sorted(fn)]
    return out

def score_files(P, ts):
    sd = W(P, "tests", ts, "scores")
    return [os.path.join(sd, x) for x in sorted(os.listdir(sd))] if os.path.isdir(sd) else []

def tally_inputs(P, ts):
    return [W(P, "tests", ts, "key.json"), W(P, "tests", ts, "questions.md")] + score_files(P, ts)

def eval_inputs(P, ts):
    return [W(P, "tests", ts, "scores.json"), W(P, "tests", ts, "questions.md"), W(P, "tests", ts, "key.json")] + score_files(P, ts)

# ---------- 提示词 ----------
class _Tpl(string.Template):
    idpattern = r"[a-z][a-z0-9_]*"

def fill_prompt(name, slots, out_name, P):
    """读 assets/prompts/<name>.md，填 ${槽位}，写 work/prompts/<out_name>.md。缺槽位报错。"""
    tpl_path = os.path.join(SKILL_DIR, "assets", "prompts", name + ".md")
    need(tpl_path, "检查 amb-paoding/assets/prompts/ 是否完整")
    try:
        text = _Tpl(read_text(tpl_path)).substitute({k: str(v) for k, v in slots.items()})
    except KeyError as e:
        die(f"提示词 {name}.md 缺槽位 {e}；脚本与模板不一致，先修脚本")
    out = W(P, "prompts", out_name + ".md")
    write_text(out, text)
    return out

# ---------- 停止 ----------
def stop_requested(P):
    return os.path.exists(W(P, "STOP"))

def stop_guard(P):
    if stop_requested(P):
        die("work/STOP 存在：已收到停止指令，不派新任务、不生成新提示词。要继续先 `paoding.py recover`")

# ---------- 外部 CLI 适配 ----------
def agent_name():
    a = (os.environ.get(ENV + "_AGENT") or "").strip().lower()
    if a in ("", "none") and os.environ.get(ENV + "_AGENT_CMD"):
        return "custom"
    return a or "none"

def agent_cmd(out_path):
    a = agent_name(); custom = os.environ.get(ENV + "_AGENT_CMD")
    if custom:
        return shlex.split(custom.replace("{out}", shlex.quote(out_path)))
    if a == "codex":
        return ["codex", "exec", "--full-auto", "-"]
    if a == "claude":
        return ["claude", "-p", "--output-format", "text"]
    die(f"{ENV}_AGENT={a} 没有内置命令；设 {ENV}_AGENT_CMD（提示词从 stdin 进，输出到 stdout）")

def classify_output(rc, tail):
    t = tail.lower()
    if re.search(r"usage limit|purchase more credits|quota exceeded|insufficient credits|out of credits", t):
        return "quota"
    if rc != 0 and re.search(r"429|rate limit|too many requests|overloaded", t):
        return "rate"
    return "ok" if rc == 0 else "failed"

def run_prompt(prompt_path, out_path, log_path, cwd):
    t0 = time.time(); cmd = agent_cmd(out_path)
    timeout = int(os.environ.get(ENV + "_AGENT_TIMEOUT", "1800"))
    try:
        with io.open(prompt_path, encoding="utf-8") as fin:
            proc = subprocess.run(cmd, stdin=fin, capture_output=True, text=True, cwd=cwd, timeout=timeout)
        rc, out = proc.returncode, (proc.stdout or "") + ("\n[stderr]\n" + proc.stderr if proc.stderr else "")
    except subprocess.TimeoutExpired as e:
        rc, out = 124, (e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")) + f"\n[timeout] 超过 {ENV}_AGENT_TIMEOUT={timeout}s 被终止\n"
    write_text(out_path, out)
    st = classify_output(rc, out[-2000:])
    with io.open(log_path, "a", encoding="utf-8") as f:
        f.write(f"{now()} {os.path.basename(prompt_path)} rc={rc} {st} {int(time.time()-t0)}s\n")
    return st, int(time.time() - t0)

# ---------- 评分行解析 ----------
DIMS = ["结构对路", "成品可用", "写法像", "事实贴合", "自检返工"]
WHERE = ["骨架", "句式", "样例", "事实", "无"]   # 扣分在哪一件

def parse_score_rows(text):
    """评分行 = | 标签(甲乙丙丁) | 五维各 ≤5 | 总分 ≤25 | [扣分在哪一件] | …。返回 (rows, bad)。
    rows = [(题号, 标签, [五维], 总分, 扣分件)]；bad = 以甲乙丙丁开头却不合格的行。题号取最近的 Qn；汇总表里的行不算。"""
    rows, bad, q = [], [], None
    for line in text.splitlines():
        s = line.strip()
        if (s.startswith("#") and "汇总" in s) or (s.startswith("|") and "均分" in s and not re.search(r"\|\s*\**[甲乙丙丁]", s)):
            q = None
        m = re.search(r"\b(Q\d+)\b", line)
        if m and not s.startswith("|"):
            q = m.group(1)
        m2 = re.match(r"\|\s*\**([甲乙丙丁])\**\s*\|(.*)", line)
        if not m2 or q is None:
            continue
        cells = [c.strip() for c in m2.group(2).strip().strip("|").split("|")]
        nums, where = [], "unmapped"
        for c in cells:
            mm = re.match(r"\**(\d+(?:\.\d+)?)\**\s*(?:/\s*\d+)?$", c)
            if mm and len(nums) < 6:
                nums.append(float(mm.group(1)))
        for c in cells:
            cc = c.strip("*` ")
            if cc in WHERE:
                where = cc; break
        lab = m2.group(1)
        if len(nums) < 6:
            bad.append((q, lab, f"数字列不足（读到 {len(nums)} 个，要五维 + 总分）")); continue
        if not all(0 <= x <= 5 for x in nums[:5]):
            bad.append((q, lab, f"五维超量程 {nums[:5]}")); continue
        if nums[5] > 25 or abs(sum(nums[:5]) - nums[5]) > 0.01:
            bad.append((q, lab, f"总分 {nums[5]} ≠ 五维之和 {sum(nums[:5])}")); continue
        rows.append((q, lab, nums[:5], nums[5], where))
    return rows, bad
