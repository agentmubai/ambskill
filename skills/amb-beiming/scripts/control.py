# -*- coding: utf-8 -*-
"""批次状态控制：停止 / 恢复 / 返工 / 排除。状态只由脚本改，不手改 batches.json。
用法：python3 control.py stop    [--project P]                 写 work/STOP；所有 in_progress 批标 interrupted；打印停止后该做什么
      python3 control.py recover [--project P]                 删 work/STOP；interrupted 批退回 pending；旧产物改名 *.stale-<时间>（留证据，不再被 settle 读到）
      python3 control.py reset   <b001,b002> [--reason 文字] [--project P]   把批（done / failed / excluded / in_progress 都行）退回 pending 重抽；
                                                              已接纳的试点批也能退；旧产物同样改名 .stale；依赖它的 merge 记录会因输入变化显示 stale
两者都给批打 needs_reextract 标记：extract 生成新提示词时清掉；没清掉之前 settle 不核这批（中断 / 返工前的产物不可信这条由脚本保证，不靠纪律）。
      python3 control.py exclude <b001,b002> --reason 文字 [--project P]     把批标 excluded（语料本身有问题：乱码、二手笔记）；理由必填，写进 note
停止的含义（两种派发方式都一样）：不再派新任务；已派出的等其自然结束但不销账；被中断批次的产物不算完成。
宿主子代理模式下，执行 agent 收到停止后：立刻跑 stop → 不再派子代理 → 已派出的子代理若宿主能取消就取消，不能就等它返回但不 settle →
按 status 核实存量 → 报告"完成了什么、什么被中断、下一步从哪里续"。外部 CLI 模式下 run_stage 读到 STOP 自动不开新任务。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

USAGE = "用法：control.py stop|recover [--project P]；control.py reset|exclude <b001,b002> [--reason 文字] [--project P]"

def shelve_outputs(P, b):
    """把批的旧产物改名为 <文件>.stale-<时间戳>，返回改名数。不删：留作证据；settle 只认 batches.json 里登记的路径，改名后就读不到。"""
    n = 0; ts = C.now().replace(":", "").replace("-", "")
    for key in ("atoms_out", "units_out", "report_out"):
        rel = b.get(key)
        if not rel:
            continue
        p = os.path.join(P, rel)
        if os.path.isfile(p):
            dst = f"{p}.stale-{ts}"; k = 1
            while os.path.exists(dst):
                dst = f"{p}.stale-{ts}-{k}"; k += 1  # 同一秒内两次改名不互相覆盖
            os.replace(p, dst); n += 1
    b["needs_reextract"] = True
    return n

def main():
    pos, o, f = C.parse_args(sys.argv[1:], opts=("--reason",), usage=USAGE)
    act = pos[0] if pos and pos[0] in ("stop", "recover", "reset", "exclude") else C.die(USAGE)
    P = C.project_root(o.get("--project"))
    bp = C.W(P, "batches.json"); bj = C.read_json(bp, {"batches": []})
    if act == "stop":
        C.write_text(C.W(P, "STOP"), C.now() + "\n")
        n = [b["batch_id"] for b in bj["batches"] if b["status"] == "in_progress"]
        for b in bj["batches"]:
            if b["status"] == "in_progress":
                b["status"] = "interrupted"; b["note"] = f"stop @ {C.now()}"
        C.write_json(bp, bj)
        print(f"已写 work/STOP；{len(n)} 个 in_progress 批标为 interrupted" + (f"：{','.join(n)}" if n else "") + "。")
        print("接下来：不再派任何子代理 / CLI；已派出的等其返回但不 settle；跑 `beiming.py status` 核实存量；向使用者报告 完成 / 中断 / 续点。恢复用 `beiming.py recover`。")
        C.pipeline_log(P, "STOP", f"停止：{len(n)} 批 interrupted")
        return
    if act == "recover":
        if os.path.exists(C.W(P, "STOP")):
            os.remove(C.W(P, "STOP"))
        n = [b["batch_id"] for b in bj["batches"] if b["status"] == "interrupted"]; shelved = 0
        for b in bj["batches"]:
            if b["status"] == "interrupted":
                shelved += shelve_outputs(P, b)
                b["status"] = "pending"; b["claimed_by"] = ""; b["note"] = "recover：产物需重抽（旧产物已改名 .stale）"
        C.write_json(bp, bj)
        print(f"已删 work/STOP；{len(n)} 个 interrupted 批退回 pending" + (f"：{','.join(n)}" if n else "") + f"；旧产物改名 .stale {shelved} 个（不重新 extract 之前 settle 不会核这些批）。接着 `beiming.py status` 看从哪一步续。")
        C.pipeline_log(P, "RECOVER", f"恢复：{len(n)} 批退回 pending")
        return
    # reset / exclude
    if len(pos) < 2:
        C.die(f"{act} 要给批号\n{USAGE}")
    ids = pos[1].split(","); by = {b["batch_id"]: b for b in bj["batches"]}
    unknown = [i for i in ids if i not in by]
    if unknown:
        C.die(f"没有批次 {unknown}；batches.json 里的批：{', '.join(by)}")
    reason = o.get("--reason", "")
    if act == "exclude" and not reason.strip():
        C.die("exclude 必须给 --reason（写清语料本身的问题，进 note 与验收报告）")
    for i in ids:
        b = by[i]
        if act == "reset":
            was = b["status"]; shelved = shelve_outputs(P, b)
            b["status"] = "pending"; b["claimed_by"] = ""; b["atoms"] = b["units"] = 0
            b["note"] = f"reset @ {C.now()}（原状态 {was}）" + (f"：{reason}" if reason else "") + f"；旧产物已改名 .stale（{shelved} 个）"
            print(f"{i}: {was} → pending，旧产物改名 .stale {shelved} 个（重抽：全量 `beiming.py extract --batches {i}`；仍作试点 `beiming.py pilot {i}`）")
        else:
            was = b["status"]
            b["status"] = "excluded"; b["note"] = f"excluded @ {C.now()}：{reason}"
            print(f"{i}: {was} → excluded（{reason}）")
    C.write_json(bp, bj)
    C.pipeline_log(P, "S3", f"{act}：{','.join(ids)}" + (f"（{reason}）" if reason else ""))
    print("接着 `beiming.py status`；merge 记录会因输入变化显示 stale，重跑 merge → audit。")

if __name__ == "__main__":
    main()
