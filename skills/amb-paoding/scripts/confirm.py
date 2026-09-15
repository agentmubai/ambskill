# -*- coding: utf-8 -*-
"""P3 门槛：核 work/types/<形态>.json。使用者确认过的类型文件才算过；不过不许进 P4。
用法：python3 confirm.py <形态>|all [--project P]
查：confirmed_at 非空；每个类型 id 是 ASCII 短名且不重复；name / brief 非空；members 都是本形态存在的原件、且一篇只归一个类型；
    本形态每篇要么在某类型里、要么在 unassigned 里带理由（不许悄悄漏掉）；薄类型（篇数 < 参考线）只提醒不拦——出不出技能由使用者定，写在 thin_ok。
schema：
{"form": "短视频", "confirmed_at": "2026-…", "user_note": "使用者原话",
 "types": [{"id": "hook", "name": "反常识开头", "brief": "一句话说这类怎么写", "members": ["o01_001", …], "thin_ok": false, "exemplar": false}],
 "unassigned": {"o01_009": "为什么不归任何类型"}}
exemplar: true = 范文型：使用者点名一篇单独做成技能。members 必须恰好一篇，user_note 必须有他的原话；不算薄。
产出：记录 confirm:<形态>；status 据此判 P3 完成。"""
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

USAGE = "用法：confirm.py <形态>|all [--project P]"

def check(P, form, idx):
    T = C.load_types(P, form); errs, warns = [], []
    if T.get("form") != form:
        errs.append(f"form 字段是 {T.get('form')!r}，应为 {form}")
    if not T.get("confirmed_at"):
        errs.append("缺 confirmed_at：使用者没确认就不算（这是唯一参与点）")
    mine = {i for i, r in idx.items() if r["form"] == form}
    seen_ids, seen_members = set(), {}
    th = C.MIN_PIECES["long" if form in C.LONG_FORMS else "default"]
    for t in T.get("types", []):
        tid = t.get("id", "")
        if not re.fullmatch(r"[a-z][a-z0-9_-]{1,30}", tid):
            errs.append(f"类型 id {tid!r} 不是 ASCII 短名（小写字母开头，可含数字 _ -）")
        if tid in seen_ids:
            errs.append(f"类型 id 重复：{tid}")
        seen_ids.add(tid)
        if not t.get("name") or not t.get("brief"):
            errs.append(f"类型 {tid}：name / brief 要非空")
        ms = t.get("members", [])
        if not ms:
            errs.append(f"类型 {tid}：members 为空")
        if t.get("exemplar"):
            # 范文型：使用者点名一篇单独做。必须只有一篇，且 user_note 有他的原话——不许用它绕过薄类型提醒
            if len(ms) != 1:
                errs.append(f"类型 {tid} 标了 exemplar 却有 {len(ms)} 篇：范文型只能有一篇")
            if not str(T.get("user_note", "")).strip():
                errs.append(f"类型 {tid} 是范文型，user_note 必须记使用者点名这一篇的原话")
        for m in ms:
            if m not in idx:
                errs.append(f"类型 {tid}：成员 {m} 不在原件库")
            elif m not in mine:
                errs.append(f"类型 {tid}：成员 {m} 形态是 {idx[m]['form']}，不是 {form}")
            if m in seen_members:
                errs.append(f"原件 {m} 同时在 {seen_members[m]} 与 {tid}：一篇只归一个类型")
            seen_members[m] = tid
        if len(ms) < th and not t.get("thin_ok") and not t.get("exemplar"):
            warns.append(f"类型 {tid}（{t.get('name')}）只有 {len(ms)} 篇 < 参考线 {th}：出技能会薄。使用者同意仍出就标 thin_ok: true；他点名某一篇单独做就标 exemplar: true（范文型）；否则并入或只给表达样品")
    un = T.get("unassigned", {}) or {}
    for m, why in un.items():
        if m not in mine:
            errs.append(f"unassigned 里的 {m} 不是本形态原件")
        if not str(why).strip():
            errs.append(f"unassigned {m} 没写理由")
    missing = sorted(mine - set(seen_members) - set(un))
    if missing:
        errs.append(f"本形态有 {len(missing)} 篇既不在任何类型也不在 unassigned：{','.join(missing[:8])}{'…' if len(missing) > 8 else ''}")
    if not T.get("types"):
        errs.append("没有任何类型")
    return T, errs, warns

def main():
    pos, o, f = C.parse_args(sys.argv[1:], usage=USAGE)
    if len(pos) != 1:
        C.die(USAGE)
    P = C.project_root(o.get("--project")); idx = C.orig_index(P)
    forms = sorted({r["form"] for r in idx.values()}) if pos[0] == "all" else [pos[0]]
    total = 0
    for form in forms:
        if pos[0] == "all" and not os.path.exists(C.types_path(P, form)):
            print(f"{form}: 无 types 文件，跳过"); continue
        T, errs, warns = check(P, form, idx)
        for w in warns:
            print(f"提醒 {form}: {w}")
        for e in errs:
            print(f"FAIL {form}: {e}")
        ok = not errs; total += len(errs)
        C.record_stage(P, f"confirm:{form}", [C.types_path(P, form), C.W(P, "kb", "originals", "index.jsonl")], ok=ok,
                       extra={"types": [t["id"] for t in T.get("types", [])], "n_types": len(T.get("types", []))})
        print(f"{'PASS' if ok else 'FAIL'} {form}：{len(T.get('types', []))} 个类型，{sum(len(t.get('members', [])) for t in T.get('types', []))} 篇归类，{len(T.get('unassigned', {}) or {})} 篇未归")
        if ok:
            print("  接着：" + "；".join(f"paoding.py pattern {C.ft_key(form, t['id'])}" for t in T.get("types", [])[:3]) + ("…" if len(T.get("types", [])) > 3 else "") + f"（或 pattern all）")
        C.pipeline_log(P, "P3", f"confirm {form}：{'通过' if ok else str(len(errs)) + ' 项不过'}")
    sys.exit(1 if total else 0)

if __name__ == "__main__":
    main()
