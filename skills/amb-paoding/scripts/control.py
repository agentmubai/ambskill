# -*- coding: utf-8 -*-
"""停止 / 恢复。
用法：python3 control.py stop    [--project P]   写 work/STOP；此后所有生成提示词的脚本（cluster / pattern / compose / evaluate）拒绝，退出码 2
      python3 control.py recover [--project P]   删 work/STOP
本技能没有批次销账表：停止只管"不再派新的"。已派出的子代理等其返回；返回后照常跑 confirm / check / lint 核验它写的文件——核验只看文件，与是否被中断无关。
停止后先 `paoding.py status` 核实存量，向使用者报告 完成了什么 / 什么没做完 / 从哪续。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

USAGE = "用法：control.py stop|recover [--project P]"

def main():
    pos, o, f = C.parse_args(sys.argv[1:], usage=USAGE)
    if len(pos) != 1 or pos[0] not in ("stop", "recover"):
        C.die(USAGE)
    P = C.project_root(o.get("--project"))
    if pos[0] == "stop":
        C.write_text(C.W(P, "STOP"), C.now() + "\n")
        print("已写 work/STOP。接下来：不再派任何子代理 / CLI；已派出的等其返回，回来后照常核验；跑 `paoding.py status` 核实存量并向使用者报告。恢复用 `paoding.py recover`。")
        C.pipeline_log(P, "STOP", "停止")
    else:
        if os.path.exists(C.W(P, "STOP")):
            os.remove(C.W(P, "STOP"))
        print("已删 work/STOP。接着 `paoding.py status` 看从哪一步续。")
        C.pipeline_log(P, "RECOVER", "恢复")

if __name__ == "__main__":
    main()
