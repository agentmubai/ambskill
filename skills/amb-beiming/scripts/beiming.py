#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""amb-beiming 统一入口：把子命令转给对应脚本（每个脚本一个功能，也都能单独运行）。
用法：python3 beiming.py <子命令> [参数…]        在工程目录里运行，或设 BEIMING_PROJECT / --project
子命令 → 脚本：
  status        status.py         看每段完成没有、下一步是什么（接手先跑）
  survey        survey.py         S1 盘点切批（兼建工程目录；`init` 是它的别名）
  pilot         extract.py --pilot   S2 试点萃取（选 2–3 批；要求预检报告有结论，--force 越过）
  calibrate     calibrate.py      S2 校准提示词 → 加工样品 + 补丁
  settle        settle.py         核验销账（--pilot 试点批 / --accept 接纳试点批进 parts）
  extract       extract.py        S3 全量萃取派发（要求冻结 + 加工样品 + 试点已接纳，--force 越过；形态 D 预写 work 单元）
  run           run_stage.py      外部 CLI 并发跑提示词（BEIMING_AGENT 非 none 时）
  read          read_atoms.py     阅读版 / 抽样
  merge         merge.py          合并去重
  audit         audit_loss.py     折损审计
  plan          plan.py           S4 数据表 + 拆合提示词
  repool        repool.py         S4 按 tasks.json 重建任务池
  distill       distill.py        S5 知识包 / 六层 / 案例卡 提示词（--step）
  caselib       case_library.py   S5 案例库全文
  screen        screen_layers.py  S5 六层粗筛
  check-layers  check_layers.py   S5 六层逐字核对（门槛）
  index         index_kb.py       S5 知识库索引
  compose       compose.py        S6 写技能 / --router 路由器 提示词
  lint          lint_product.py   S6 成品体检（门槛）
  evaluate      blind_eval.py / eval_report.py   S7：questions | answers | judge | tally | report
  deliver       deliver.py        S8 装配成品
  update        update.py         S9 增量提示词
  stop/recover  control.py        停止 / 恢复（recover 把旧产物改名 .stale，未重抽的批 settle 不核）
  reset         control.py        把批退回 pending（done 批返工、重抽，不手改 batches.json）
  exclude       control.py        把批标 excluded（--reason 必填）
  selfcheck     selfcheck.py      维护者：检查 amb-beiming 自身
所有子命令都接受 --project <工程目录>；未知参数报错不忽略。"""
import os, sys, runpy

HERE = os.path.dirname(os.path.abspath(__file__))
MAP = {"status": "status.py", "survey": "survey.py", "init": "survey.py", "pilot": "extract.py", "calibrate": "calibrate.py", "settle": "settle.py",
       "extract": "extract.py", "run": "run_stage.py", "read": "read_atoms.py", "merge": "merge.py", "audit": "audit_loss.py", "plan": "plan.py",
       "repool": "repool.py", "distill": "distill.py", "caselib": "case_library.py", "screen": "screen_layers.py", "check-layers": "check_layers.py",
       "index": "index_kb.py", "compose": "compose.py", "lint": "lint_product.py", "deliver": "deliver.py", "update": "update.py",
       "stop": "control.py", "recover": "control.py", "reset": "control.py", "exclude": "control.py", "selfcheck": "selfcheck.py"}

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__); return
    cmd, rest = sys.argv[1], sys.argv[2:]
    if cmd == "pilot":
        if not rest or rest[0].startswith("--"):
            sys.exit("用法：beiming.py pilot <b001,bNNN>  （选 2–3 批：最长文件所在批 + 一个别的形态）")
        rest = ["--pilot", rest[0]] + rest[1:]
    if cmd in ("stop", "recover", "reset", "exclude"):
        rest = [cmd] + rest
    if cmd == "evaluate":
        if rest and rest[0] == "report":
            script = "eval_report.py"; rest = rest[1:]
        else:
            script = "blind_eval.py"
    else:
        script = MAP.get(cmd)
    if not script:
        sys.exit(f"未知子命令 {cmd}；python3 beiming.py help 看列表")
    sys.argv = [os.path.join(HERE, script)] + rest
    sys.path.insert(0, HERE)
    runpy.run_path(os.path.join(HERE, script), run_name="__main__")

if __name__ == "__main__":
    main()
