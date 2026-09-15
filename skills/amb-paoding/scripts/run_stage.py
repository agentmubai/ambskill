# -*- coding: utf-8 -*-
"""外部 CLI 并发驱动：把 work/prompts/<名>.md 各跑一次（PAODING_AGENT=codex|claude，或 PAODING_AGENT_CMD 自定义命令），回复写 work/reports/<名>.reply.md。
用法：python3 run_stage.py <名1,名2,…> [--workers N] [--project P]   名 = 提示词文件名去掉 .md
PAODING_AGENT 未设且没有 PAODING_AGENT_CMD：只列出提示词路径并退出（宿主子代理模式由执行 agent 自己派）。
429 歇 120 秒重试最多 3 次；识别额度用尽即停止全部；读到 work/STOP 不再开新任务。回复不是产物，提示词指定的文件才是。"""
import os, sys, time, threading, queue
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

USAGE = "用法：run_stage.py <名1,名2,…> [--workers N] [--project P]"

def run(P, names, workers=6):
    pdir = C.W(P, "prompts"); rdir = C.W(P, "reports"); log = os.path.join(rdir, "run.log")
    paths = [os.path.join(pdir, n + ".md") for n in names]
    missing = [p for p in paths if not os.path.exists(p)]
    if missing:
        C.die("提示词不存在：" + ", ".join(os.path.basename(m) for m in missing))
    if C.agent_name() == "none":
        print(f"{C.ENV}_AGENT=none：宿主子代理模式。把下面每份提示词各派一个子代理：")
        for p in paths:
            print(" ", os.path.relpath(p, P))
        return {}
    if C.stop_requested(P):
        C.die("work/STOP 存在：不开新任务。要继续先 `paoding.py recover`")
    q = queue.Queue(); [q.put(p) for p in paths]
    results, lock, halt = {}, threading.Lock(), threading.Event()
    def worker():
        while not q.empty() and not halt.is_set():
            if C.stop_requested(P):
                halt.set(); break
            try:
                p = q.get_nowait()
            except queue.Empty:
                return
            name = os.path.basename(p)[:-3]; out = os.path.join(rdir, name + ".reply.md"); st = "failed"
            for _ in range(3):
                st, sec = C.run_prompt(p, out, log, P)
                if st == "rate":
                    time.sleep(120)
                    if C.stop_requested(P):
                        st = "stopped"; halt.set(); break
                    continue
                break
            with lock:
                results[name] = st; print(f"{st:7} {name}")
            if st == "quota":
                halt.set()
    ts = [threading.Thread(target=worker, daemon=True) for _ in range(max(1, workers))]
    [t.start() for t in ts]; [t.join() for t in ts]
    if halt.is_set():
        print("已停止：" + ("收到 STOP" if C.stop_requested(P) else "额度用尽（quota）"))
    print(f"完成 {sum(1 for v in results.values() if v == 'ok')}/{len(paths)}；回复在 work/reports/<名>.reply.md；产物以提示词指定的文件为准，接着跑对应核验（confirm / check / lint / tally）")
    return results

if __name__ == "__main__":
    pos, o, f = C.parse_args(sys.argv[1:], opts=("--workers",), usage=USAGE)
    if len(pos) != 1:
        C.die(USAGE)
    run(C.project_root(o.get("--project")), pos[0].split(","), int(o.get("--workers", "6")))
