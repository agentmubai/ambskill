# -*- coding: utf-8 -*-
"""销账：核验批次产出（三个文件存在、JSONL 每行可解析、schema（必填字段、枚举、字段类型、id 格式、original ≤200 字）、
引文逐字命中），过的标 done、不过标 failed。子代理的口头摘要不算数，只有这一步算数。
用法：python3 settle.py [all | b001,b002] [--pilot] [--accept] [--force] [--project P]
  --pilot   只核试点批（claimed_by=pilot）；默认核 in_progress / failed 的，已 done 的要重核请点名批号
  --accept  冻结后接纳试点：把试点批（含已 done 的）核一遍并搬进 work/parts/，claimed_by 改 pilot-accepted；要求版本行「版本：冻结 vX.Y」
  --force   连 interrupted 的批也核；默认 interrupted 不核（被中断的产物不可信，先 recover 重抽）
选不到任何批时退出码 1 并说明原因，不打印"done 0 / failed 0"当成功。
三个产物文件全不存在的 in_progress 批算"未返回"，不改状态（子代理还没写完，不是失败）；有部分文件才按失败处理。
recover / reset 过、还没重新 extract 的批（needs_reextract）不核，退出码 1：中断前的半截产物不可信。
形态 D 批的 work 单元：text 由脚本按文件正文恢复（模型改动的按文件覆盖，缺的补回），记在 note，不判失败。"""
import os, sys, re, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C, quote_check as Q

USAGE = "用法：settle.py [all | b001,b002] [--pilot] [--accept] [--force] [--project P]"
REQ_ATOM = ("id", "knowledge", "original", "source", "speaker", "role", "topics", "skills", "type", "claim_scope", "confidence")
REQ_UNIT = ("unit_id", "type", "title", "text", "source", "speaker", "role", "summary", "atom_ids")

def _is_strlist(v):
    return isinstance(v, list) and all(isinstance(x, str) for x in v)

def schema_errors(rows, kind):
    """kind = 'atom' | 'unit'。返回错误列表（每条含 id）。"""
    errs = []; seen = set()
    req, idkey, idrx = (REQ_ATOM, "id", C.ATOM_ID) if kind == "atom" else (REQ_UNIT, "unit_id", C.UNIT_ID)
    for r in rows:
        if "_bad_json" in r:
            errs.append(f"第 {r['_line']} 行 JSON 非法"); continue
        rid = r.get(idkey, "")
        miss = [k for k in req if k not in r]
        if miss:
            errs.append(f"{rid} 缺字段 {miss}")
        if not isinstance(rid, str) or not re.fullmatch(idrx, rid):
            errs.append(f"id 不合规：{rid}")
        if rid in seen:
            errs.append(f"id 重复：{rid}")
        seen.add(rid)
        src = r.get("source")
        if not (isinstance(src, dict) and isinstance(src.get("group"), str) and isinstance(src.get("file"), str)):
            errs.append(f"{rid} source 须是含 group/file 的对象")
        if r.get("role") not in C.ROLES:
            errs.append(f"{rid} role 不在枚举 {C.ROLES}：{r.get('role')}")
        if kind == "atom":
            if r.get("type") not in C.ATOM_TYPES:
                errs.append(f"{rid} type 不在枚举：{r.get('type')}")
            if r.get("claim_scope") not in C.CLAIM_SCOPES:
                errs.append(f"{rid} claim_scope 不在枚举：{r.get('claim_scope')}")
            if r.get("confidence") not in C.CONFIDENCES:
                errs.append(f"{rid} confidence 不在枚举：{r.get('confidence')}")
            for k in ("topics", "skills"):
                if not _is_strlist(r.get(k)):
                    errs.append(f"{rid} {k} 须是字符串列表")
            if "flags" in r and not (_is_strlist(r["flags"]) and all(x in C.FLAGS for x in r["flags"])):
                errs.append(f"{rid} flags 只能是 {C.FLAGS} 的子集")
            if not isinstance(r.get("knowledge"), str) or not r.get("knowledge", "").strip():
                errs.append(f"{rid} knowledge 为空")
            o = r.get("original")
            if not isinstance(o, str) or not o.strip():
                errs.append(f"{rid} original 为空")
            elif len(o) > C.ORIGINAL_MAX:
                errs.append(f"{rid} original 超 {C.ORIGINAL_MAX} 字（{len(o)}）")
            if "unit_id" in r and r["unit_id"] and not (isinstance(r["unit_id"], str) and re.fullmatch(C.UNIT_ID, r["unit_id"])):
                errs.append(f"{rid} unit_id 格式不对：{r['unit_id']}")
        else:
            if r.get("type") not in C.UNIT_TYPES:
                errs.append(f"{rid} type 不在枚举 {C.UNIT_TYPES}：{r.get('type')}")
            if not (_is_strlist(r.get("atom_ids")) and all(re.fullmatch(C.ATOM_ID, x) for x in r["atom_ids"])):
                errs.append(f"{rid} atom_ids 须是原子 id 列表")
            if not isinstance(r.get("text"), str) or not r.get("text", "").strip():
                errs.append(f"{rid} text 为空")
    return errs

def cross_errors(atoms, units):
    """原子 ↔ 单元的互指：原子的 unit_id 要指向本批存在的单元；单元的 atom_ids 要指向本批存在的原子。"""
    aids = {a.get("id") for a in atoms if "_bad_json" not in a}; uids = {u.get("unit_id") for u in units if "_bad_json" not in u}
    errs = []
    for a in atoms:
        if "_bad_json" not in a and a.get("unit_id") and a["unit_id"] not in uids:
            errs.append(f"{a.get('id')} 的 unit_id {a['unit_id']} 不在本批单元里")
    for u in units:
        if "_bad_json" in u:
            continue
        bad = [i for i in (u.get("atom_ids") or []) if isinstance(i, str) and i not in aids]
        if bad:
            errs.append(f"{u.get('unit_id')} 的 atom_ids 有 {len(bad)} 个不在本批原子里：{bad[:3]}")
    return errs

def restore_work_units(P, b, cat, units, up):
    """形态 D：work 单元的 text 以脚本从文件生成的为准。模型改动过的按文件覆盖、漏掉的补回；返回修正条数（写回 units 文件）。"""
    if b.get("form") != "D":
        return 0
    skel = {u["unit_id"]: u for u in C.work_skeleton(b, cat)}
    if not skel:
        return 0
    fixed = 0; out = []; seen = set()
    for u in units:
        if "_bad_json" in u or u.get("type") != "work" or u.get("unit_id") not in skel:
            out.append(u); continue
        seen.add(u["unit_id"]); k = skel[u["unit_id"]]
        if C.norm_ws(u.get("text")) != C.norm_ws(k["text"]):
            u["text"] = k["text"]; fixed += 1
        u["type"] = "work"; u["source"] = {**k["source"], **{kk: vv for kk, vv in (u.get("source") or {}).items() if kk in ("timestamp_start", "timestamp_end")}}
        out.append(u)
    for uid, k in skel.items():
        if uid not in seen:
            out.append(k); fixed += 1
    b["work_restored"] = fixed
    if fixed:
        C.write_jsonl(up, out)
    return fixed

def main():
    pos, o, fl = C.parse_args(sys.argv[1:], flags=("--pilot", "--accept", "--force"), usage=USAGE)
    pilot = "--pilot" in fl; accept = "--accept" in fl; force = "--force" in fl
    if accept:
        pilot = True
    if len(pos) > 1:
        C.die(f"多余的参数 {pos[1:]}\n{USAGE}")
    sel = pos[0] if pos else "all"
    P = C.project_root(o.get("--project"))
    bp = C.W(P, "batches.json"); C.need(bp, "S1 `beiming.py survey --corpus <目录>`")
    bj = C.read_json(bp); cat = C.load_catalog(P); cache = {}
    by = {b["batch_id"]: b for b in bj["batches"]}
    if accept:
        rules = C.W(P, "docs", "执行提示词.md"); C.need(rules, "S2 `beiming.py pilot <bNNN,…>`")
        ver, frozen = C.rules_version(C.read_text(rules))
        if not frozen:
            C.die(f"规则未冻结（版本行现在是「{ver}」；{C.freeze_hint(C.read_text(rules))}），不能接纳试点产物", code=2)
    is_pilot = lambda b: b.get("claimed_by") == "pilot"
    if sel == "all":
        if accept:
            ids = [b["batch_id"] for b in bj["batches"] if is_pilot(b) and (b["status"] in ("done", "in_progress", "failed") or (force and b["status"] == "interrupted"))]
            if not ids:
                acc = [b["batch_id"] for b in bj["batches"] if b.get("claimed_by") == "pilot-accepted"]
                C.die("没有待接纳的试点批" + (f"（已接纳：{','.join(acc)}）" if acc else "（没有 claimed_by=pilot 的批；先 `beiming.py pilot <批>`）"), code=1)
        else:
            cands = [b for b in bj["batches"] if b["status"] in ("in_progress", "failed") or (force and b["status"] == "interrupted")]
            if pilot:
                cands = [b for b in cands if is_pilot(b)]
            ids = [b["batch_id"] for b in cands]
            if not ids:
                done_p = [b["batch_id"] for b in bj["batches"] if b["status"] == "done" and (is_pilot(b) or not pilot)]
                unfinished = {k: sum(1 for b in bj["batches"] if b["status"] == k) for k in C.STATUS_UNFINISHED}
                msg = "没有可核的批（in_progress / failed 为 0" + ("，试点批范围" if pilot else "") + "）。"
                if done_p:
                    msg += f" 已 done 的批 {','.join(done_p[:12])} 要重核请点名：`settle {done_p[0]}" + (" --pilot" if pilot else "") + "`。"
                if unfinished.get("interrupted"):
                    msg += f" interrupted {unfinished['interrupted']} 个：先 `recover`（或 --force）。"
                if unfinished.get("pending"):
                    msg += f" pending {unfinished['pending']} 个：还没派（`extract`）。"
                C.die(msg, code=1)
    else:
        ids = sel.split(",")
        unknown = [i for i in ids if i not in by]
        if unknown:
            C.die(f"没有批次 {unknown}；batches.json 里的批：{', '.join(by)}")
    done = failed = moved = unreturned = stale_skip = 0
    for bid in ids:
        b = by[bid]
        if b["status"] == "interrupted" and not force:
            print(bid, "interrupted，跳过（recover 后重抽，或 --force）"); continue
        if b.get("needs_reextract"):
            print(bid, f"{b['status']}：recover / reset 后还没重新 extract，旧产物不可信（已改名 .stale），不核；先 `beiming.py extract --batches {bid}`"); stale_skip += 1; continue
        if b["status"] in ("pending", "excluded"):
            print(bid, f"{b['status']}，没有产物可核，跳过"); continue
        if accept and not is_pilot(b):
            print(bid, f"不是待接纳的试点批（claimed_by={b.get('claimed_by') or '空'}），跳过"); continue
        ap, up = os.path.join(P, b["atoms_out"]), os.path.join(P, b["units_out"])
        rp = os.path.join(P, b["report_out"]) if b.get("report_out") else ""
        errs = []
        for p, name in ((ap, "原子文件"), (up, "单元文件"), (rp, "批次报告")):
            if not p or not os.path.isfile(p):
                errs.append(f"{name}不存在" + (f"（{os.path.relpath(p, P)}）" if p else ""))
        if b["status"] == "in_progress" and all(any(e.startswith(n) for e in errs) for n in ("原子文件", "批次报告")):
            print(bid, "未返回（原子文件与批次报告都还不存在），状态不改；等子代理写完再 settle"); unreturned += 1; continue
        if not any(e.startswith(("原子文件", "单元文件")) for e in errs):
            atoms, units = C.read_jsonl(ap), C.read_jsonl(up)
            fixed = restore_work_units(P, b, cat, units, up)
            if fixed:
                units = C.read_jsonl(up)
            errs += schema_errors(atoms, "atom") + schema_errors(units, "unit") + cross_errors(atoms, units)
            if not [x for x in atoms if "_bad_json" not in x]:
                errs.append("原子为 0 条（空文件不算完成）")
            for p in (ap, up):
                t, _, m = Q.check_file(p, P, cat, cache)
                if m:
                    errs.append(f"{os.path.basename(p)} 引文未命中 {len(m)}/{t}：" + "; ".join(str(x.get('id')) for x in m[:5]))
            b["atoms"], b["units"] = len([x for x in atoms if "_bad_json" not in x]), len([x for x in units if "_bad_json" not in x])
        if errs:
            b["status"] = "failed"; b["note"] = " | ".join(errs)[:600]; failed += 1
            print("FAIL", bid, b["note"][:200])
            continue
        b["status"] = "done"; b["note"] = (f"work 单元 text 由脚本按文件恢复 {b['work_restored']} 条" if b.get("work_restored") else ""); done += 1
        print("done", bid, f"原子 {b['atoms']} 单元 {b['units']}" + (f"（work 单元 text 按文件恢复 {b['work_restored']} 条）" if b.get("work_restored") else ""))
        if accept:
            for src, key in ((ap, "atoms_out"), (up, "units_out")):
                dst = os.path.join(P, "work", "parts", os.path.basename(src))
                if os.path.abspath(src) != os.path.abspath(dst):
                    shutil.copy2(src, dst)
                b[key] = os.path.relpath(dst, P)
            b["claimed_by"] = "pilot-accepted"; moved += 1
            print("  已接纳 →", b["atoms_out"], b["units_out"])
    C.write_json(bp, bj)
    left = [b["batch_id"] for b in bj["batches"] if b["status"] in C.STATUS_UNFINISHED]
    print(f"本次 done {done} / failed {failed}" + (f" / 接纳 {moved}" if accept else "") + (f" / 未返回 {unreturned}" if unreturned else "") + (f" / 未重抽不核 {stale_skip}" if stale_skip else "") + f"；未完成批 {len(left)}" + (f"：{','.join(left[:12])}" if left else ""))
    C.pipeline_log(P, "S2" if pilot else "S3", f"settle：done {done} failed {failed} 未完成 {len(left)}" + (f" --accept 接纳 {moved}" if accept else ""))
    sys.exit(1 if (failed or unreturned or stale_skip) else 0)

if __name__ == "__main__":
    main()
