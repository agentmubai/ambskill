#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""amb-paoding 统一入口：把子命令转给对应脚本（每个脚本一个功能，也都能单独运行）。
用法：python3 paoding.py <子命令> [参数…]        在工程目录里运行，或设 PAODING_PROJECT / --project
子命令 → 脚本：
  status        status.py         看每段完成没有、下一步是什么（接手先跑）
  survey        survey.py         P1 盘点：按形态分组、稳定文件号、篇数（兼建工程目录；--update 增量只追加）
  ingest        ingest.py         P2 切篇：一篇一原件，逐字进 work/kb/originals/（幂等，只补新的）
  cluster       cluster.py        P3 聚类型提示词（每形态一份；--update 只给新篇分类）
  confirm       confirm.py        P3 门槛：核 work/types/<形态>.json（confirmed_at、成员、薄类型）
  pattern       pattern.py        P4 写法书提示词（每 形态-类型 一份；skeleton 是旧别名）
  check         check_pack.py     P4 门槛：引文逐字 + 覆盖表 + 零引用篇处置
  dispose       dispose.py        P4 给零引用篇写处置（并入 / 排除 / 补拆）
  compose       compose.py        P5 写技能提示词（复制 references；--router 路由器；--sync-refs 只同步）
  lint          lint_product.py   P5 门槛：成品体检
  evaluate      blind_eval.py / eval_report.py   轻验收：questions | answers | judge | tally | report
  deliver       deliver.py        装配成品
  run           run_stage.py      外部 CLI 并发跑提示词（PAODING_AGENT 非 none 时）
  stop/recover  control.py        停止 / 恢复
  selfcheck     selfcheck.py      维护者：检查 amb-paoding 自身
所有子命令都接受 --project <工程目录>；未知参数报错不忽略。"""
import os, sys, runpy

HERE = os.path.dirname(os.path.abspath(__file__))
MAP = {"status": "status.py", "survey": "survey.py", "init": "survey.py", "ingest": "ingest.py", "cluster": "cluster.py", "confirm": "confirm.py",
       "pattern": "pattern.py", "skeleton": "pattern.py", "check": "check_pack.py", "dispose": "dispose.py", "compose": "compose.py", "lint": "lint_product.py",
       "deliver": "deliver.py", "run": "run_stage.py", "stop": "control.py", "recover": "control.py", "selfcheck": "selfcheck.py"}

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__); return
    cmd, rest = sys.argv[1], sys.argv[2:]
    if cmd in ("stop", "recover"):
        rest = [cmd] + rest
    if cmd == "evaluate":
        if rest and rest[0] == "report":
            script = "eval_report.py"; rest = rest[1:]
        else:
            script = "blind_eval.py"
    else:
        script = MAP.get(cmd)
    if not script:
        sys.exit(f"未知子命令 {cmd}；python3 paoding.py help 看列表")
    sys.argv = [os.path.join(HERE, script)] + rest
    sys.path.insert(0, HERE)
    runpy.run_path(os.path.join(HERE, script), run_name="__main__")

if __name__ == "__main__":
    main()
