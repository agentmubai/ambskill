# -*- coding: utf-8 -*-
"""公共函数（被其余脚本 import，不单独运行）：
工程定位、JSON/JSONL 原子写、提示词填槽、阶段记录与过期判定、外部 CLI 适配、评分行解析、来源定位。
只依赖 Python 3.9+ 标准库。"""
import os, sys, io, re, json, glob, time, hashlib, datetime, subprocess, string, shlex

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ATOM_ID = r"c\d{2}_\d{3}_\d{3}"
UNIT_ID = r"u\d{2}_\d{3}_\d{2,3}"
ANY_ID = r"[cu]\d{2}_\d{3}_\d{2,3}"
TEXT_EXT = (".txt", ".md", ".srt", ".vtt", ".text", ".markdown")
STATUS_UNFINISHED = ("pending", "in_progress", "failed", "interrupted")
ORIGINAL_MAX = 200  # 原子 original 上限（字），与 extraction-rules.md 一致；settle 按它判
# 原子 / 单元的枚举（与 extraction-rules.md 1.1 / 1.2 一致；settle 校 schema 用）
ROLES = ("讲师", "嘉宾", "学员", "主持", "作品", "未知")
ATOM_TYPES = ("principle", "method", "case", "anti-pattern", "insight", "tool")
CLAIM_SCOPES = ("无条件主张", "有条件做法", "举例")
CONFIDENCES = ("high", "medium", "low")
UNIT_TYPES = ("case", "work", "sop", "argument")
FLAGS = ("platform", "conflict", "unverified", "title")  # title = original 抄的是文件名里的标题（正文里没有），引文核验按 catalog 的 title 核
SPEAKER_RX = re.compile(r"^\s*(Speaker\s*\d+|说话人\s*\d*|发言人\s*\d*|\[?\d{1,2}:\d{2}(?::\d{2})?\]?)\b", re.I)

# ---------- 命令行 ----------
def parse_args(argv, opts=(), flags=(), usage=""):
    """统一解析：opts 是带值参数（--x 值），flags 是布尔参数；--project 对所有脚本都可用。
    未知的 --xxx 直接报错退出（不静默忽略，免得把 --project 当成别的东西吞掉）。返回 (位置参数, 带值参数 dict, 布尔参数 set)。"""
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

# ---------- 工程定位 ----------
def project_root(explicit=None):
    """工程目录：--project > $BEIMING_PROJECT > 当前目录。工程的标志是 work/。"""
    p = explicit or os.environ.get("BEIMING_PROJECT") or os.getcwd()
    return os.path.abspath(p)

# ---------- 规则冻结 ----------
FROZEN_RX = re.compile(r"(?m)^\s*(?:版本[：:]\s*)?冻结\s*(v[\d.]+)\s*$")
VERSION_RX = re.compile(r"(?m)^\s*版本[：:]\s*(?:冻结\s*)?(v[\d.]+)")

def frozen_version(text):
    """规则是否冻结：只认独立成行的版本行「版本：冻结 vX.Y」（或「冻结 vX.Y」），说明句、引用块里的字样不算。返回版本号或 None。"""
    m = FROZEN_RX.search(text or "")
    return m.group(1) if m else None

def rules_version(text):
    """返回 (版本号, 是否冻结)。没有版本行时版本号为 'v?'。"""
    fz = frozen_version(text)
    if fz:
        return fz, True
    m = VERSION_RX.search(text or "")
    return (m.group(1) if m else "v?"), False

def freeze_hint(text):
    """未冻结时给出可懂的原因：版本行后带了尾注（括号说明等）、或根本没有版本行。"""
    m = re.search(r"(?m)^\s*(?:版本[：:]\s*)?冻结\s*v[\d.]+(\S.*|\s+\S.*)$", text or "")
    if m:
        return f"版本行后有多余内容「{m.group(1).strip()[:30]}」：整行只能是「版本：冻结 vX.Y」，说明放到别的行"
    if not VERSION_RX.search(text or ""):
        return "没有「版本：vX.Y」这一行"
    return "版本行没有「冻结」字样"

def W(P, *parts):
    return os.path.join(P, "work", *parts)

def ensure_project(P):
    for d in ("prompts", "reports", "pilot", "docs", "parts", "kb", "kb/pools", "kb/packs", "kb/layers_input", "draft/skills", "tests"):
        os.makedirs(W(P, d), exist_ok=True)
    os.makedirs(os.path.join(P, "product"), exist_ok=True)
    if not os.path.exists(W(P, "pipeline.md")):
        write_text(W(P, "pipeline.md"), "# pipeline\n\n每段结束追加一行：时间 | 段 | 做了什么 | 门槛结果 | 备注。\n\n")

def need(path, hint):
    if not os.path.exists(path):
        die(f"缺 {path}\n先做：{hint}")

def die(msg, code=2):
    print(msg, file=sys.stderr); sys.exit(code)

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
    """逐行解析；坏行以 {"_bad_json": ..., "_line": n} 返回，不中断。"""
    out = []
    if not os.path.exists(p):
        return out
    for n, line in enumerate(io.open(p, encoding="utf-8", errors="replace"), 1):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as e:
            out.append({"_bad_json": str(e), "_line": n})
    return out

def write_jsonl(p, rows):
    write_text(p, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))

def norm_ws(s):
    return re.sub(r"\s+", "", s or "")

DATE_PREFIX_RX = re.compile(r"^\s*\d{4}[-_.年]?\d{2}[-_.月]?\d{2}日?(?:[ _T\-]\d{2}[:：.\-时]\d{2}(?:[:：.\-分]\d{2}秒?)?)?[\s_\-–—.]*")

def file_title(fn):
    """文件名里的标题：去目录、去扩展名、去开头的日期 / 时间前缀（2026-05-11_12:13:11_、2026-05-11_、20260511- 等）、去末尾的短哈希（如 -a1b2c3d4）、去首尾空白。
    短视频 / 帖子的标题常常只在文件名里；标题原子按这个值核，catalog 另保留 file 原名。剥完为空就退回原主干。"""
    stem = os.path.splitext(os.path.basename(fn))[0]
    t = DATE_PREFIX_RX.sub("", stem, count=1)
    t = re.sub(r"[-_ ][0-9a-fA-F]{6,12}$", "", t).strip()
    return t or stem.strip()

def work_body(text, max_scan=40):
    """形态 D 的 work 单元正文：从第一个说话人段起（跳过平台导出的时间、时长、Keywords 等元数据行）；前 40 行内找不到说话人标签就取全文。"""
    lines = (text or "").splitlines()
    for i, l in enumerate(lines[:max_scan]):
        if SPEAKER_RX.match(l):
            return "\n".join(lines[i:]).strip()
    return (text or "").strip()

def group_of(catalog, gid):
    return next((g for g in (catalog or {}).get("groups", []) if g["group_id"] == gid), None)

def work_skeleton(batch, catalog):
    """形态 D 批的 work 单元骨架：一文件一单元，text 由脚本从文件正文（第一个说话人段起）生成，模型不抄。
    返回 [(unit dict)]；文件读不到的跳过。"""
    g = group_of(catalog, batch["group_id"]); out = []
    if not g:
        return out
    for fn in batch["files"]:
        p = os.path.join(batch["source_dir"], fn)
        if not os.path.isfile(p):
            continue
        no = batch["file_nos"][fn]; body = work_body(read_text(p))
        if not body:
            continue
        out.append({"unit_id": f"u{g['group_id'][1:]}_{no}_01", "type": "work", "title": file_title(fn), "text": body,
                    "source": {"group": g["name"], "file": fn, "title": file_title(fn)}, "speaker": "作者", "role": "作品",
                    "summary": "", "atom_ids": []})
    return out

def now():
    return datetime.datetime.now().isoformat(timespec="seconds")

def pipeline_log(P, stage, text):
    with io.open(W(P, "pipeline.md"), "a", encoding="utf-8") as f:
        f.write(f"- {now()} | {stage} | {text}\n")

# ---------- 阶段记录与过期 ----------
def sha_files(paths, root=None):
    """输入哈希 = 相对工程根的路径 + 内容。不混绝对路径：工程搬家、/tmp 与 /private/tmp、--project 与 cd 两种写法，哈希都不变。"""
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
    """返回 'ok' / 'stale' / 'failed' / 'missing'。stale = 记录时的输入哈希与现在不同。"""
    meta = read_json(W(P, "meta.json"), {})
    rec = meta.get(stage)
    if not rec:
        return "missing"
    if not rec.get("ok"):
        return "failed"
    return "ok" if rec.get("inputs_sha") == sha_files(inputs, P) else "stale"

# ---------- 提示词 ----------
class _Tpl(string.Template):
    idpattern = r"[a-z][a-z0-9_]*"

def fill_prompt(name, slots, out_name, P):
    """读 assets/prompts/<name>.md，填 ${槽位}，写到 work/prompts/<out_name>.md。缺槽位报错，不留空。"""
    tpl_path = os.path.join(SKILL_DIR, "assets", "prompts", name + ".md")
    need(tpl_path, "检查 amb-beiming/assets/prompts/ 是否完整")
    tpl = _Tpl(read_text(tpl_path))
    try:
        text = tpl.substitute({k: str(v) for k, v in slots.items()})
    except KeyError as e:
        die(f"提示词 {name}.md 缺槽位 {e}；脚本与模板不一致，先修脚本")
    out = W(P, "prompts", out_name + ".md")
    write_text(out, text)
    return out

# ---------- 停止 ----------
def stop_requested(P):
    return os.path.exists(W(P, "STOP"))

def stop_guard(P):
    """所有会生成提示词 / 派任务的脚本入口都调它：work/STOP 存在就拒绝。"""
    if stop_requested(P):
        die("work/STOP 存在：已收到停止指令，不派新任务、不生成新提示词。要继续先 `beiming.py recover`")

# ---------- 成品体检的输入集合 ----------
def skill_inputs(skills_dir, dirs):
    """lint 记录的输入哈希覆盖 SKILL.md 与 references/ 下全部文件（status 用同一函数算，才能判 stale）。"""
    out = []
    for d in dirs:
        sk = os.path.join(skills_dir, d, "SKILL.md")
        if os.path.exists(sk):
            out.append(sk)
        rd = os.path.join(skills_dir, d, "references")
        if os.path.isdir(rd):
            out += [os.path.join(rd, f) for f in sorted(os.listdir(rd))]
    return out

def score_files(P, ts):
    sd = W(P, "tests", ts, "scores")
    return [os.path.join(sd, x) for x in sorted(os.listdir(sd))] if os.path.isdir(sd) else []

def tally_inputs(P, ts):
    """tally:<题集> 记录的输入：key.json + questions.md + 每份评分文件。"""
    return [W(P, "tests", ts, "key.json"), W(P, "tests", ts, "questions.md")] + score_files(P, ts)

def eval_inputs(P, ts):
    """evaluate:<题集> 记录的输入：scores.json + 题集 + key + tasks.json + 每份评分文件；任一改动，旧 PASS 过期。"""
    return [W(P, "tests", ts, "scores.json"), W(P, "tests", ts, "questions.md"), W(P, "tests", ts, "key.json"), W(P, "tasks.json")] + score_files(P, ts)

# ---------- 外部 CLI 适配 ----------
def agent_name():
    """BEIMING_AGENT：none（默认，宿主子代理模式）/ codex / claude / custom。
    只设了 BEIMING_AGENT_CMD 而没设 BEIMING_AGENT 时按 custom 处理（自定义命令单独生效）。"""
    a = (os.environ.get("BEIMING_AGENT") or "").strip().lower()
    if a in ("", "none") and os.environ.get("BEIMING_AGENT_CMD"):
        return "custom"
    return a or "none"

def agent_cmd(out_path):
    """返回命令行列表。提示词从 stdin 进；最终回复写到 out_path（脚本负责把 stdout 存进去）。"""
    a = agent_name()
    custom = os.environ.get("BEIMING_AGENT_CMD")
    if custom:
        return shlex.split(custom.replace("{out}", shlex.quote(out_path)))
    if a == "codex":
        return ["codex", "exec", "--full-auto", "-"]
    if a == "claude":
        return ["claude", "-p", "--output-format", "text"]
    die(f"BEIMING_AGENT={a} 没有内置命令；设 BEIMING_AGENT_CMD（提示词从 stdin 进，输出到 stdout）")

def classify_output(rc, tail):
    t = tail.lower()
    if re.search(r"usage limit|purchase more credits|quota exceeded|insufficient credits|out of credits", t):
        return "quota"
    if rc != 0 and re.search(r"429|rate limit|too many requests|overloaded", t):
        return "rate"
    return "ok" if rc == 0 else "failed"

def run_prompt(prompt_path, out_path, log_path, cwd):
    """跑一份提示词。返回 (状态, 秒)。状态：ok / failed / quota / rate。"""
    t0 = time.time()
    cmd = agent_cmd(out_path)
    timeout = int(os.environ.get("BEIMING_AGENT_TIMEOUT", "1800"))  # 秒；一个挂住的 CLI 不能永久占住 worker
    try:
        with io.open(prompt_path, encoding="utf-8") as fin:
            proc = subprocess.run(cmd, stdin=fin, capture_output=True, text=True, cwd=cwd, timeout=timeout)
        rc, out = proc.returncode, (proc.stdout or "") + ("\n[stderr]\n" + proc.stderr if proc.stderr else "")
    except subprocess.TimeoutExpired as e:
        rc, out = 124, (e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")) + f"\n[timeout] 超过 BEIMING_AGENT_TIMEOUT={timeout}s 被终止\n"
    write_text(out_path, out)
    st = classify_output(rc, out[-2000:])
    with io.open(log_path, "a", encoding="utf-8") as f:
        f.write(f"{now()} {os.path.basename(prompt_path)} rc={rc} {st} {int(time.time()-t0)}s\n")
    return st, int(time.time() - t0)

# ---------- 评分行解析 ----------
DIMS = ["方法选择", "成品可用", "原法忠实", "材料贴合", "自检返工"]
LAYERS = ["道", "法", "术", "证", "器", "势", "无"]

def parse_score_rows(text):
    """评分行 = | 标签(甲乙丙丁) | 五维各 ≤5 | 总分 ≤25 | [扣分回哪一层] | ...。加粗与否都认。
    返回 (rows, bad)：rows = [(题号, 标签, [五维], 总分, 层)]；bad = [(题号, 标签, 原因)]，即以甲乙丙丁开头却不合格的行
    （数字不够、超量程、总分 ≠ 五维之和、题号缺）。不合格行不静默丢弃，调用方必须把 bad 报出来。题号取最近出现的 Qn；汇总表（题号为空）里的行不算评分行。"""
    rows, bad, q = [], [], None
    for line in text.splitlines():
        s = line.strip()
        if (s.startswith("#") and "汇总" in s) or (s.startswith("|") and "均分" in s and not re.search(r"\|\s*\**[甲乙丙丁]", s)):
            q = None  # 进入汇总表：后面的 甲/乙 行不是评分行
        m = re.search(r"\b(Q\d+)\b", line)
        if m and not s.startswith("|"):
            q = m.group(1)
        m2 = re.match(r"\|\s*\**([甲乙丙丁])\**\s*\|(.*)", line)
        if not m2:
            continue
        if q is None:
            continue  # 汇总表或题号之外的行
        cells = [c.strip() for c in m2.group(2).strip().strip("|").split("|")]
        nums, layer = [], "unmapped"
        for c in cells:
            mm = re.match(r"\**(\d+(?:\.\d+)?)\**\s*(?:/\s*\d+)?$", c)
            if mm and len(nums) < 6:
                nums.append(float(mm.group(1)))
        for c in cells:
            cc = c.strip("*` ")
            if cc in LAYERS:
                layer = cc; break
        lab = m2.group(1)
        if len(nums) < 6:
            bad.append((q, lab, f"数字列不足（读到 {len(nums)} 个，要五维 + 总分）")); continue
        if not all(0 <= x <= 5 for x in nums[:5]):
            bad.append((q, lab, f"五维超量程 {nums[:5]}")); continue
        if nums[5] > 25 or abs(sum(nums[:5]) - nums[5]) > 0.01:
            bad.append((q, lab, f"总分 {nums[5]} ≠ 五维之和 {sum(nums[:5])}")); continue
        rows.append((q, lab, nums[:5], nums[5], layer))
    return rows, bad

# ---------- 来源定位 ----------
def load_catalog(P):
    return read_json(W(P, "catalog.json"), None) if os.path.exists(W(P, "catalog.json")) else None

def locate_source(P, catalog, source, some_id=None):
    """按 id 前缀 cGG_FFF 在 catalog 里找来源文件；找不到再按 source.file 猜。"""
    if catalog and some_id:
        m = re.match(r"[cu](\d{2})_(\d{3})_", some_id)
        if m:
            g = "g" + m.group(1)
            for grp in catalog.get("groups", []):
                if grp["group_id"] == g:
                    for f in grp["files"]:
                        if f["no"] == m.group(2):
                            p = os.path.join(grp["source_dir"], f["file"])
                            if os.path.isfile(p):
                                return p
    src = source or {}
    root = (catalog or {}).get("corpus_root", "")
    for c in (os.path.join(root, src.get("group", ""), src.get("file", "")), os.path.join(root, src.get("file", ""))):
        if src.get("file") and os.path.isfile(c):
            return c
    base = os.path.basename(src.get("file", ""))
    if base and root:
        hits = glob.glob(os.path.join(root, "**", base), recursive=True)
        if len(hits) == 1:
            return hits[0]
    return None

def load_alias(P):
    return read_json(W(P, "kb", "alias.json"), {}) if os.path.exists(W(P, "kb", "alias.json")) else {}

def resolve_id(alias, i):
    seen = set()
    while i in alias and i not in seen:
        seen.add(i); i = alias[i]
    return i

def tasks(P):
    t = read_json(W(P, "tasks.json"), None) if os.path.exists(W(P, "tasks.json")) else None
    if not t or not t.get("tasks"):
        die("缺 work/tasks.json 或其中没有任务\n先做：S4 能力方案经使用者确认后写 tasks.json（schema 见 references/04-plan.md 模板节）")
    return t

def task_by_id(P, tid):
    for t in tasks(P)["tasks"]:
        if t["id"] == tid:
            return t
    die(f"tasks.json 里没有任务 {tid}")

def split_names(s, all_items):
    return list(all_items) if s in ("all", "*") else [x for x in s.split(",") if x]
