# -*- coding: utf-8 -*-
"""S2/S3 萃取派发：为批次生成填好的萃取提示词（一批一份），把批次标为 in_progress。
用法：python3 extract.py [--pilot b001,b004] [--batches b001,b002 | all] [--workers N] [--regenerate] [--force] [--project P]
  --pilot      S2 试点：输出改到 work/pilot/；规则文件没有时从 references/extraction-rules.md 复制为 work/docs/执行提示词.md v1.0；
               要求 work/docs/预检报告.md 已有三选一结论（第一个参与点）
  --batches    S3 全量：默认全部 pending；要求 版本行「版本：冻结 vX.Y」+ work/docs/加工样品.md 存在（第二个参与点）+ 试点批已 --accept
  --workers    BEIMING_AGENT 非 none 时，生成后交 run_stage 并发跑
  --regenerate 已 in_progress 的批也重生成提示词（续跑时用）
  --force      越过上面两处参与点检查（写进 pipeline.md，验收报告要交代）
冻结判定只看独立成行的版本行，说明句里的字样不算。未冻结 / 缺加工样品 / 试点批未接纳 就跑全量：退出码 2，不改任何批的状态。
没有可派的批（全在 in_progress / done / excluded）：退出码 1 并说明原因，不当成功。
已 done 的批要重抽：先 `beiming.py reset <批>`（退回 pending），再 extract。
形态 D 的批：脚本先把 work 单元骨架写进 units 文件（一文件一单元，text = 文件正文，从第一个说话人段起），子代理只补 summary / atom_ids，不抄全文。
宿主子代理模式（默认）：只生成提示词，一份提示词派一个子代理；跑完 settle 销账。"""
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

USAGE = "用法：extract.py [--pilot b001,b004] [--batches all|b001,b002] [--workers N] [--regenerate] [--force] [--project P]"
VERDICT_RX = r"可开工|收缩范围|补料"
RULES_HEAD = ("# 执行提示词（萃取规则工程副本）\n\n版本：v1.0（试点中，未冻结）\n\n"
              "> 由 extraction-rules.md 复制而来。第 6 节的白名单开工前填好；校准补丁追加到第 8 节并升版本号。"
              "冻结时把上面那一行版本行整行改成「版本：冻结 vX.Y」（脚本只认独立成行的版本行，这段说明不算）。\n\n")

def main():
    pos, o, f = C.parse_args(sys.argv[1:], opts=("--pilot", "--batches", "--workers"), flags=("--regenerate", "--force"), usage=USAGE)
    if pos:
        C.die(f"多余的位置参数 {pos}\n{USAGE}")
    pilot = o.get("--pilot"); sel = o.get("--batches", "all"); workers = int(o.get("--workers", "6"))
    regen = "--regenerate" in f; force = "--force" in f
    P = C.project_root(o.get("--project"))
    C.need(C.W(P, "batches.json"), "S1 `beiming.py survey --corpus <目录>`")
    C.stop_guard(P)
    bj = C.read_json(C.W(P, "batches.json")); cat = C.load_catalog(P)
    by = {b["batch_id"]: b for b in bj["batches"]}
    cnt = {}
    for b in bj["batches"]:
        cnt[b["status"]] = cnt.get(b["status"], 0) + 1
    rules = C.W(P, "docs", "执行提示词.md")
    forced = []
    if pilot:
        pre = C.W(P, "docs", "预检报告.md")
        if not (os.path.exists(pre) and re.search(VERDICT_RX, C.read_text(pre))):
            if not force:
                C.die("第一个参与点没走：work/docs/预检报告.md 不存在或没有「结论：可开工 / 收缩范围 / 补料」三选一。\n"
                      "先按 references/01-survey.md 模板写预检报告并交使用者看结论；使用者说可开工再 pilot。确实要越过：加 --force（会记进 pipeline.md）", code=2)
            forced.append("预检报告结论")
        if not os.path.exists(rules):
            src = os.path.join(C.SKILL_DIR, "references", "extraction-rules.md")
            C.write_text(rules, RULES_HEAD + C.read_text(src))
            print("已建 work/docs/执行提示词.md v1.0（先填第 6 节白名单再派）")
        ids = pilot.split(",")
    else:
        C.need(rules, "S2 `beiming.py pilot <bNNN,…>`")
        rtext = C.read_text(rules); ver, frozen = C.rules_version(rtext)
        if not frozen:
            C.die(f"规则未冻结（执行提示词版本行现在是「{ver}」；{C.freeze_hint(rtext)}）。不派全量，批次状态未改。\n"
                  "先做 S2：settle --pilot → calibrate → 连续两批不改五项 → 把版本行改为「版本：冻结 vX.Y」→ settle --pilot --accept", code=2)
        gate = []
        if not os.path.exists(C.W(P, "docs", "加工样品.md")):
            gate.append("缺 work/docs/加工样品.md（第二个参与点：calibrate → 子代理写样品 → 使用者看过）")
        unacc = [b["batch_id"] for b in bj["batches"] if b.get("claimed_by") == "pilot"]
        if unacc:
            gate.append(f"试点批未接纳：{','.join(unacc)}（`settle --pilot --accept`）")
        if gate:
            if not force:
                C.die("S2 没完成，不派全量，批次状态未改：\n- " + "\n- ".join(gate) + "\n确实要越过：加 --force（会记进 pipeline.md，验收报告要交代）", code=2)
            forced += gate
        if sel == "all":
            ids = [b["batch_id"] for b in bj["batches"] if b["status"] == "pending" or (regen and b["status"] == "in_progress")]
            if not ids:
                left = {k: v for k, v in cnt.items() if k != "pending"}
                hint = []
                if cnt.get("in_progress"):
                    hint.append("in_progress 的批等子代理写完后 `settle`（要重生成提示词加 --regenerate）")
                if cnt.get("failed"):
                    hint.append("failed 的批看 batches.json 的 note 修后 `extract --batches <批> --regenerate`")
                if cnt.get("interrupted"):
                    hint.append("interrupted 的批先 `recover`")
                if cnt.get("done") and not any(cnt.get(k) for k in C.STATUS_UNFINISHED):
                    hint.append("全部批已 done：接着 `merge`；要重抽某批先 `reset <批>`")
                C.die("没有可派的批：pending 0；其余 " + "，".join(f"{k} {v}" for k, v in sorted(left.items())) + "\n" + ("；".join(hint) or "先 `beiming.py status`"), code=1)
        else:
            ids = sel.split(",")
    unknown = [i for i in ids if i not in by]
    if unknown:
        C.die(f"没有批次 {unknown}；batches.json 里的批：{', '.join(by)}")
    ver, frozen = C.rules_version(C.read_text(rules))
    ver_label = ver + ("" if frozen else "（未冻结）")
    outs, skipped = [], []
    for bid in ids:
        b = by[bid]
        if b["status"] in ("done", "excluded"):
            skipped.append(f"{bid} 已 {b['status']}（要重抽先 `beiming.py reset {bid}`）"); continue
        if b["status"] == "interrupted" and not regen:
            skipped.append(f"{bid} interrupted（先 `beiming.py recover` 退回 pending）"); continue
        if b["status"] == "in_progress" and not regen and not pilot:
            skipped.append(f"{bid} in_progress（等 settle；重生成加 --regenerate）"); continue
        sub = "pilot" if pilot else "parts"
        atoms_out = f"work/{sub}/atoms_{bid}.jsonl"; units_out = f"work/{sub}/units_{bid}.jsonl"
        report_out = f"work/reports/{'pilot-' if pilot else ''}{bid}.md"
        form_note = ""
        if b["form"] == "D":
            skel = C.work_skeleton(b, cat)
            if skel:
                C.write_jsonl(os.path.join(P, units_out), skel)
                form_note = (f"形态 D：`{units_out}` 已由脚本预写好 {len(skel)} 个 work 单元（一文件一个，`text` = 文件正文，从第一个说话人段起，"
                             "平台元数据行不在内）。你**不要改** `unit_id` / `type` / `text` / `source`，只补 `summary`、`speaker`（作者名）、`atom_ids`；"
                             "可以在文件末追加新的 case / argument 单元。原子的 `unit_id` 填对应的 work 单元 id。销账时脚本会把被改动的 work 正文按文件恢复。")
        files_md = "\n".join(f"- {fn}（文件号 {b['file_nos'][fn]}；标题「{C.file_title(fn)}」）" for fn in b["files"])
        slots = {"project": P, "skill_dir": C.SKILL_DIR, "rules_path": os.path.relpath(rules, P), "batch_id": bid, "form": b["form"],
                 "oversized_note": "本批只有一个超长文件：分段读完，段间回看前 500 字。" if b.get("oversized") else "", "form_note": form_note,
                 "source_dir": b["source_dir"], "files": files_md,
                 "atoms_out": atoms_out, "units_out": units_out, "report_out": report_out,
                 "corpus_root": (cat or {}).get("corpus_root", ""), "group_no": b["group_id"][1:],
                 "max_chars": bj.get("max_chars", 100000)}
        out = C.fill_prompt("extract", slots, f"extract-{bid}", P); outs.append(out)
        b["status"] = "in_progress"; b["claimed_by"] = "pilot" if pilot else "extract"; b["rules_version"] = ver_label
        b["atoms_out"], b["units_out"], b["report_out"] = atoms_out, units_out, report_out
        b["needs_reextract"] = False; b["dispatched_at"] = C.now()
    for s in skipped:
        print("跳过", s)
    if not outs:
        C.die("没有生成提示词（上面列了每个批被跳过的原因）", code=1)
    C.write_json(C.W(P, "batches.json"), bj)
    print(f"生成 {len(outs)} 份提示词（规则 {ver_label}）：")
    for out in outs:
        print(" ", os.path.relpath(out, P))
    forced_txt = "；".join(forced)
    C.pipeline_log(P, "S2" if pilot else "S3", f"extract 生成 {len(outs)} 份提示词，规则 {ver_label}" + (f"；--force 越过参与点检查：{forced_txt}" if forced else ""))
    if forced:
        print("注意：--force 越过了参与点检查（已记 pipeline.md）：", forced_txt)
    if C.agent_name() != "none":
        import run_stage
        run_stage.run(P, [os.path.basename(x)[:-3] for x in outs], workers)
    else:
        print("宿主子代理模式：每份提示词派一个子代理（并发数按宿主上限），全部返回后 `beiming.py settle" + (" --pilot" if pilot else "") + "`。")

if __name__ == "__main__":
    main()
