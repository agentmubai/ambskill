# -*- coding: utf-8 -*-
"""P4 处置零引用篇：把「这篇一处没被骨架 / 句式引到」的结论写进 <pack>/dispositions.json；check 读它判门槛。
用法：python3 dispose.py <形态-类型> <编号,…> --as 并入|排除|补拆 [--note 文字] [--project P]
  并入  这篇其实属于别的类型 → note 写目标类型；之后改 work/types/<形态>.json 的 members 并重跑 confirm
  排除  语料本身的问题（重复、残篇、不是对方本人的）→ note 写原因；仍留在原件库，只不进拆解层
  补拆  是拆漏了 → 之后 pattern --update 让子代理补引用，补完 check 会看到它不再零引用
处置不是删除：原件永远在。这一步只是把「为什么没用上」写成能查的记录。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core as C

USAGE = "用法：dispose.py <形态-类型> <编号,…> --as 并入|排除|补拆 [--note 文字] [--project P]"

def main():
    pos, o, f = C.parse_args(sys.argv[1:], opts=("--as", "--note"), usage=USAGE)
    if len(pos) != 2 or not o.get("--as"):
        C.die(USAGE)
    key, ids = pos[0], pos[1].split(","); how = o["--as"]; note = o.get("--note", ""); P = C.project_root(o.get("--project"))
    if how not in C.DISPOSITIONS:
        C.die(f"--as 只能是 {' / '.join(C.DISPOSITIONS)}")
    if how in ("并入", "排除") and not note.strip():
        C.die(f"{how} 要写 --note（并入写目标类型；排除写语料问题）")
    form, t = C.parse_ft(P, key); idx = C.orig_index(P)
    for i in ids:
        if i not in idx:
            C.die(f"原件 {i} 不在原件库")
        if i not in t["members"]:
            C.die(f"原件 {i} 不是类型 {key} 的成员")
    pk = C.pack_dir(P, key); p = os.path.join(pk, "dispositions.json"); d = C.read_json(p, {})
    for i in ids:
        d[i] = {"as": how, "note": note, "at": C.now()}
    C.write_json(p, d)
    print(f"{key}: {len(ids)} 篇标为「{how}」" + (f"（{note}）" if note else "") + f"。接着重跑 `paoding.py check {key}`" + ("；并入的记得改 types 文件后 confirm" if how == "并入" else "；补拆的跑 `pattern {key} --update`" if how == "补拆" else ""))
    C.pipeline_log(P, "P4", f"dispose {key} {','.join(ids)} → {how}")

if __name__ == "__main__":
    main()
