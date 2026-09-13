# -*- coding: utf-8 -*-
"""事实核对（器）：技能交付前跑一遍——成品里出现的数字、年限、价格、人数，必须来自「事实清单」或写成〔槽位〕，否则报出来。
生产工具箱时，本文件复制进每个任务技能的 scripts/fact_check.py（技能目录单独拷走也能跑）；工具箱根目录 scripts/ 另放一份作开放资产。
用法：python3 <技能目录>/scripts/fact_check.py <回答.md> [<技能目录>]     退出码 0 = 无可疑；1 = 有可疑事实；2 = 没找到事实清单 / 用法错
给了技能目录时，出现在其 SKILL.md / references 里的数字视为"方法数字"（作者的阈值、秒数），单独列出不算可疑。
识别方式：回答里以「事实清单」为题的一节（或 F01 / F1. 编号行）当作清单；逐句来源表与清单本身不检查；正文里带数字或单位的片段若不在清单里、又不在〔〕里，视为可疑。
这是启发式检查，不判对错，只把"清单外的具体事实"摊出来让写稿的人自己看。只依赖标准库。"""
import io, re, sys, os, glob

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help") or not os.path.isfile(sys.argv[1]):
        print(__doc__); sys.exit(2)
    p = sys.argv[1]; s = io.open(p, encoding="utf-8", errors="replace").read()
    method_norm = ""
    if len(sys.argv) > 2 and os.path.isdir(sys.argv[2]):
        files = [os.path.join(sys.argv[2], "SKILL.md")] + glob.glob(os.path.join(sys.argv[2], "references", "*.md"))
        method_norm = re.sub(r"\s", "", "\n".join(io.open(f, encoding="utf-8", errors="replace").read() for f in files if os.path.exists(f)))
    m = re.search(r"(?ms)^#{1,4}[^\n]*事实清单[^\n]*\n(.*?)(?=^#{1,4}\s|\Z)", s)
    fact_txt = m.group(1) if m else "\n".join(l for l in s.splitlines() if re.match(r"^\s*[-*]?\s*F\d{1,2}[.．:：、\s]", l))
    if not fact_txt.strip():
        print("未找到事实清单（没有「事实清单」一节或 F01 编号行）"); sys.exit(2)
    facts_norm = re.sub(r"\s", "", fact_txt)
    body = s
    for title in ("事实清单", "逐句来源表", "来源表", "待补"):
        body = re.sub(r"(?ms)^#{1,4}[^\n]*" + title + r"[^\n]*\n.*?(?=^#{1,4}\s|\Z)", "", body)
    body = re.sub(r"〔[^〕]*〕|\[[^\]]*\]", "", body)
    pat = re.compile(r"(\d+(?:\.\d+)?\s*(?:元|块|万|千|年|个月|天|人|位|条|单|次|倍|折|%|秒|分钟|小时|平|公里|米|双|套|份|款|台|家|张))|([一二三四五六七八九十两几]+(?:年|个月|天|人|位|条|单|次|倍|折|秒|分钟|双|套|份|款|台|家|张))")
    suspects, methodish = [], []
    for sent in re.split(r"[。！？\n]", body):
        for mm in pat.finditer(sent):
            tok = re.sub(r"\s", "", mm.group(0))
            if tok in facts_norm or not re.sub(r"\s", "", sent).strip():
                continue
            (methodish if (method_norm and tok in method_norm) else suspects).append((tok, sent.strip()[:80]))
    seen, out = set(), []
    for tok, sent in suspects:
        if (tok, sent) in seen:
            continue
        seen.add((tok, sent)); out.append(f"- 「{tok}」 不在事实清单：{sent}")
    print(f"事实清单 {len(fact_txt.strip().splitlines())} 行；正文可疑具体事实 {len(out)} 处；方法数字（作者阈值，不算可疑）{len({t for t, _ in methodish})} 种")
    print("\n".join(out[:40]))
    sys.exit(1 if out else 0)

if __name__ == "__main__":
    main()
