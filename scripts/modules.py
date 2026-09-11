"""Module-mode bootcamp driver (v2).

v1 was day-based and assumed materials compress into 60 minutes/day. Measured
reality: Teece + Brandenburger-Stuart alone took 3-4 hours, and the full v1
reading list needs 90-125 hours against a 20-hour supply. v2 therefore tracks
*modules* that exit on "closed-book framework recall", not on calendar days.

The v1 driver (scripts/bootcamp.py) still reads content/bootcamp_20d.yaml for
historical Day 1-2 records. This file owns everything from M1 onward.

Usage:
    python scripts/modules.py status
    python scripts/modules.py show M2
    python scripts/modules.py log M1 --hours 3.5 --note "Baldwin sections 1-3"
    python scripts/modules.py forecast add M1 "..." --resolves 2027-06-30
    python scripts/modules.py exit M1 --pass
    python scripts/modules.py dashboard
"""
from __future__ import annotations

import argparse
import html
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "content" / "bootcamp_modules.yaml"
STATE = ROOT / "data" / "module_progress.yaml"
DASHBOARD = ROOT / "outputs" / "dashboard.html"


def load() -> dict[str, Any]:
    with MANIFEST.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    if "bootcamp" not in raw:
        raise SystemExit(f"{MANIFEST} must contain a 'bootcamp' mapping")
    return raw["bootcamp"]


def load_state() -> dict[str, Any]:
    if not STATE.exists():
        return {"modules": {}, "forecasts": []}
    with STATE.open("r", encoding="utf-8") as fh:
        s = yaml.safe_load(fh) or {}
    s.setdefault("modules", {})
    s.setdefault("forecasts", [])
    return s


def save_state(s: dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    with STATE.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(s, fh, allow_unicode=True, sort_keys=False)


def get_module(bc: dict[str, Any], mid: str) -> dict[str, Any] | None:
    for m in bc["modules"]:
        if m["id"].upper() == mid.upper():
            return m
    return None


def mstate(s: dict[str, Any], mid: str) -> dict[str, Any]:
    return s["modules"].get(mid, {})


def hours_logged(s: dict[str, Any], mid: str, kind: str | None = None) -> float:
    entries = mstate(s, mid).get("log", [])
    if kind:
        entries = [e for e in entries if e.get("kind") == kind]
    return round(sum(float(e.get("hours", 0)) for e in entries), 1)


def est_low(m: dict[str, Any]) -> float:
    raw = str(m.get("est_hours", "0")).split("-")[0]
    try:
        return float(raw)
    except ValueError:
        return 0.0


def forecasts_for(s: dict[str, Any], mid: str) -> list[dict[str, Any]]:
    return [f for f in s["forecasts"] if f.get("module", "").upper() == mid.upper()]


# --------------------------------------------------------------------------

def cmd_status(args, bc, s):
    print(f"\n{bc['name']}  ({bc['version']}, mode={bc['mode']})")
    print(f"总预算 {bc['total_budget_hours']}h | 训练器: "
          f"{bc['trainers']['primary']['name']} + {bc['trainers']['live_position']['name']}")
    print(f"已退出常设: " + ", ".join(d["name"] for d in bc["trainers"]["deferred"]))

    total_logged = 0.0
    print("\nModules:")
    for m in bc["modules"]:
        mid = m["id"]
        st = mstate(s, mid)
        status = st.get("status", m.get("status", "pending"))
        h = hours_logged(s, mid)
        total_logged += h
        fc = forecasts_for(s, mid)
        ok_fc = sum(1 for f in fc if f.get("linter") == "pass")
        mark = {"done": "x", "in_progress": ">", "pending": " "}.get(status, "?")
        print(f"  [{mark}] {mid} {m['name']:<24} {status:<12} "
              f"{h:>5.1f}h / est {m['est_hours']:<7} forecasts {ok_fc}/3")
        if status == "in_progress" and m.get("remaining"):
            for r in m["remaining"]:
                print(f"        - {r}")

    print(f"\n累计投入 {total_logged:.1f}h / 预算 {bc['total_budget_hours']}h")

    print("\nGates:")
    for g in bc["gates"]:
        print(f"  {g['id']} {g['name']}: {g['rule']}")

    tot_fc = len([f for f in s["forecasts"] if f.get("linter") == "pass"])
    print(f"\n可结算预测存量: {tot_fc}（目标 每 module ≥3）")


def cmd_show(args, bc, s):
    m = get_module(bc, args.mid)
    if not m:
        raise SystemExit(f"module {args.mid} 不存在")
    st = mstate(s, m["id"])
    print(f"\n{m['id']} — {m['name']}")
    print(f"  问题: {m['question']}")
    print(f"  状态: {st.get('status', m.get('status'))} | 预估 {m['est_hours']}h | "
          f"已投入 {hours_logged(s, m['id'])}h")
    if m.get("priority"):
        print(f"  优先级: {m['priority']}")
    if m.get("rationale"):
        print(f"  依据: {m['rationale']}")
    if m.get("reading_mode"):
        print(f"  读法: {m['reading_mode']}")
    if m.get("trainer_note"):
        print(f"  训练器: {m['trainer_note']}")

    print("\n  材料:")
    for mat in m.get("materials", []):
        flag = mat.get("status", "pending")
        extra = f" (实际 {mat['actual_hours']}h)" if mat.get("actual_hours") else \
                (f" (估 {mat['est_hours']}h)" if mat.get("est_hours") else "")
        print(f"    [{'x' if flag == 'done' else ' '}] {mat['title']}{extra}")
        if mat.get("scope"):
            print(f"        {mat['scope']}")

    if m.get("done_so_far"):
        print("\n  已完成:")
        for x in m["done_so_far"]:
            print(f"    + {x}")
    if m.get("remaining"):
        print("\n  剩余:")
        for x in m["remaining"]:
            print(f"    - {x}")
    if m.get("anchor_tasks"):
        print("\n  锚点任务:")
        for x in m["anchor_tasks"]:
            print(f"    * {x}")

    print("\n  出口条件:")
    for x in m.get("exit_criteria", []):
        print(f"    ? {x}")

    ai = m.get("ai_usage", {})
    if ai:
        print(f"\n  AI 模式: {ai.get('mode')}")
        print(f"    允许: {ai.get('allowed')}")
        print(f"    禁止: {ai.get('forbidden')}")
        if ai.get("special"):
            print(f"    要点: {ai['special']}")
    if m.get("safety"):
        print(f"    安全: {m['safety']}")

    fc = forecasts_for(s, m["id"])
    if fc:
        print(f"\n  预测 ({sum(1 for f in fc if f.get('linter')=='pass')} 条通过 linter):")
        for f in fc:
            print(f"    [{f.get('linter','?')}] {f['text'][:70]} → {f.get('resolves','?')}")
    print()


def cmd_log(args, bc, s):
    m = get_module(bc, args.mid)
    if not m:
        raise SystemExit(f"module {args.mid} 不存在")
    mid = m["id"]
    entry = s["modules"].setdefault(mid, {})
    entry.setdefault("status", "in_progress")
    entry.setdefault("log", []).append({
        "date": datetime.now().strftime("%Y-%m-%d"),
        "hours": args.hours,
        "kind": args.kind,
        "note": args.note or "",
    })
    save_state(s)

    total = hours_logged(s, mid)
    mat = hours_logged(s, mid, "material")
    print(f"{mid}: +{args.hours}h ({args.kind}) → 累计 {total}h")
    if total > 0 and mat / total > 0.5 and mat >= 4:
        print(f"  ⚠ 闸门 g1：材料时间 {mat}h / 总 {total}h = {mat/total:.0%} > 50%")
        print(f"    规则：材料 ≤ module 总时间 50%。请转入应用环节。")


def cmd_forecast(args, bc, s):
    if args.action == "add":
        if not get_module(bc, args.mid):
            raise SystemExit(f"module {args.mid} 不存在")
        missing = [k for k, v in [("resolves", args.resolves), ("metric", args.metric),
                                  ("threshold", args.threshold), ("source", args.source)] if not v]
        s["forecasts"].append({
            "module": args.mid.upper(),
            "text": args.text,
            "metric": args.metric,
            "threshold": args.threshold,
            "resolves": args.resolves,
            "source": args.source,
            "probability": args.probability,
            "linter": "fail" if missing else "pass",
            "linter_missing": missing,
            "added": datetime.now().strftime("%Y-%m-%d"),
        })
        save_state(s)
        if missing:
            print(f"已记录，但 linter FAIL —— 缺: {', '.join(missing)}")
            print("  不可结算的预测不计入 g3 闸门。补齐后重新添加。")
        else:
            print(f"已记录，linter PASS。{args.mid.upper()} 现有 "
                  f"{sum(1 for f in forecasts_for(s, args.mid) if f.get('linter')=='pass')}/3 条")
    else:
        for f in s["forecasts"]:
            print(f"[{f['module']}] [{f.get('linter')}] {f['text']}")
            print(f"    指标={f.get('metric')} 阈值={f.get('threshold')} "
                  f"结算={f.get('resolves')} 来源={f.get('source')}")


def cmd_exit(args, bc, s):
    m = get_module(bc, args.mid)
    if not m:
        raise SystemExit(f"module {args.mid} 不存在")
    mid = m["id"]
    ok_fc = sum(1 for f in forecasts_for(s, mid) if f.get("linter") == "pass")
    if ok_fc < 3 and args.passed:
        raise SystemExit(
            f"拒绝：{mid} 只有 {ok_fc}/3 条可结算预测。闸门 g3 未满足。\n"
            f"  用 'modules.py forecast add {mid} ...' 补齐后再出口。")
    entry = s["modules"].setdefault(mid, {})
    entry["status"] = "done" if args.passed else "in_progress"
    entry["exit_attempt"] = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "passed": bool(args.passed),
        "note": args.note or "",
    }
    save_state(s)
    print(f"{mid} 出口{'通过' if args.passed else '未通过'}。")
    if args.passed:
        nxt = None
        ids = [x["id"] for x in bc["modules"]]
        i = ids.index(mid)
        if i + 1 < len(ids):
            nxt = ids[i + 1]
        print(f"下一个 module: {nxt or '全部完成 → 进入 second wave'}")


# --------------------------------------------------------------------------

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif;
background:#faf9f7;color:#2c2c2a;line-height:1.6;padding:32px 24px 64px}
.wrap{max-width:1080px;margin:0 auto}
h1{font-size:20px;font-weight:500;margin-bottom:4px}
h2{font-size:15px;font-weight:500;margin:32px 0 12px;padding-bottom:6px;border-bottom:1px solid #e5e3dd}
h3{font-size:13px;font-weight:500;margin-bottom:8px}
.sub{font-size:13px;color:#5f5e5a;margin-bottom:20px}
.card{background:#fff;border:1px solid #e5e3dd;border-radius:12px;padding:20px;margin-bottom:16px}
.card.now{border-color:#378add;border-width:2px}
.card.done{background:#f6faf0;border-color:#97c459}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #eeece6;vertical-align:top}
th{font-weight:500;color:#5f5e5a;font-size:12px}
.pill{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;border:1px solid}
.ok{background:#eaf3de;border-color:#97c459;color:#27500a}
.no{background:#fcebeb;border-color:#f09595;color:#791f1f}
.warn{background:#faeeda;border-color:#efa027;color:#633806}
.info{background:#e6f1fb;border-color:#378add;color:#0c447c}
.bar{height:6px;background:#eeece6;border-radius:3px;overflow:hidden;margin:6px 0}
.bar>div{height:100%;background:#639922}
.muted{color:#5f5e5a;font-size:12px}
ul{padding-left:18px}li{margin:3px 0;font-size:13px}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
.grid{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-bottom:8px}
.cell{border:1px solid #e5e3dd;border-radius:8px;padding:10px;background:#fff;font-size:12px}
.cell.done{background:#eaf3de;border-color:#97c459}
.cell.now{background:#e6f1fb;border-color:#378add;border-width:2px}
.rule{font-size:12px;color:#5f5e5a;padding:5px 0;border-bottom:1px dashed #e5e3dd}
.rule:last-child{border:none}
.rule b{color:#2c2c2a;font-weight:500}
"""


def esc(x: Any) -> str:
    return html.escape(str(x))


def render(bc: dict[str, Any], s: dict[str, Any]) -> str:
    p: list[str] = []
    a = p.append
    a("<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>")
    a("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    a(f"<title>{esc(bc['name'])}</title><style>{CSS}</style></head><body><div class='wrap'>")
    a(f"<h1>{esc(bc['name'])}</h1>")
    gen = datetime.now(ZoneInfo(bc.get("timezone", "Asia/Shanghai"))).strftime("%Y-%m-%d %H:%M")
    total_logged = sum(hours_logged(s, m["id"]) for m in bc["modules"])
    a(f"<div class='sub'>{esc(bc['version'])} · module 制 · 累计投入 {total_logged:.1f}h / "
      f"预算 {bc['total_budget_hours']}h · 生成于 {esc(gen)}</div>")

    pct = min(int(total_logged / bc["total_budget_hours"] * 100), 100)
    a(f"<div class='card'><h3>总进度</h3><div class='bar'><div style='width:{pct}%'></div></div>")
    a(f"<div class='muted'>核心循环 {esc(' → '.join(bc['core_loop']))}　|　"
      f"终点链条 {esc(' → '.join(bc['final_chain']))}</div></div>")

    # module strip
    a("<h2>Module 进度</h2><div class='grid'>")
    for m in bc["modules"]:
        st = mstate(s, m["id"]).get("status", m.get("status", "pending"))
        cls = "cell" + (" done" if st == "done" else (" now" if st == "in_progress" else ""))
        h = hours_logged(s, m["id"])
        a(f"<div class='{cls}'><div class='mono'>{esc(m['id'])}</div>"
          f"<div>{esc(m['name'])}</div>"
          f"<div class='muted'>{h:.1f}h / {esc(m['est_hours'])}h</div></div>")
    a("</div>")

    # current module detail
    cur = next((m for m in bc["modules"]
                if mstate(s, m["id"]).get("status", m.get("status")) == "in_progress"), None)
    if cur:
        a(f"<h2>当前：{esc(cur['id'])} {esc(cur['name'])}</h2><div class='card now'>")
        a(f"<div class='muted'>{esc(cur['question'])}</div>")
        if cur.get("remaining"):
            a("<h3 style='margin-top:14px'>剩余</h3><ul>")
            for r in cur["remaining"]:
                a(f"<li>{esc(r)}</li>")
            a("</ul>")
        a("<h3 style='margin-top:14px'>出口条件</h3><ul>")
        for c in cur.get("exit_criteria", []):
            a(f"<li>{esc(c)}</li>")
        a("</ul>")
        ai = cur.get("ai_usage", {})
        if ai:
            a(f"<h3 style='margin-top:14px'>AI 模式：{esc(ai.get('mode'))}</h3>")
            a(f"<div class='rule'><b>允许</b> {esc(ai.get('allowed'))}</div>")
            a(f"<div class='rule'><b>禁止</b> {esc(ai.get('forbidden'))}</div>")
            if ai.get("special"):
                a(f"<div class='rule'><b>要点</b> {esc(ai['special'])}</div>")
        a("</div>")

    # modules table
    a("<h2>全部 module</h2><div class='card'><table>")
    a("<tr><th>ID</th><th>名称</th><th>问题</th><th>状态</th><th>工时</th><th>预测</th></tr>")
    for m in bc["modules"]:
        st = mstate(s, m["id"]).get("status", m.get("status", "pending"))
        pill = {"done": "<span class='pill ok'>完成</span>",
                "in_progress": "<span class='pill info'>进行中</span>"}.get(
                    st, "<span class='pill'>待开始</span>")
        ok = sum(1 for f in forecasts_for(s, m["id"]) if f.get("linter") == "pass")
        fp = f"<span class='pill {'ok' if ok >= 3 else 'no'}'>{ok}/3</span>"
        a(f"<tr><td class='mono'>{esc(m['id'])}</td><td><b>{esc(m['name'])}</b></td>"
          f"<td class='muted'>{esc(m['question'])}</td><td>{pill}</td>"
          f"<td class='mono'>{hours_logged(s, m['id']):.1f} / {esc(m['est_hours'])}</td>"
          f"<td>{fp}</td></tr>")
    a("</table></div>")

    # gates
    a("<h2>防失控闸门</h2><div class='card'>")
    for g in bc["gates"]:
        a(f"<div class='rule'><b>{esc(g['id'])} {esc(g['name'])}</b><br>{esc(g['rule'])}</div>")
    a("</div>")

    # trainers
    tr = bc["trainers"]
    a("<h2>训练器</h2><div class='card'>")
    a(f"<h3>主应用场：{esc(tr['primary']['name'])}</h3>")
    a(f"<div class='muted'>{esc(tr['primary']['role'])}</div>")
    a("<table style='margin-top:8px'><tr><th>标的</th><th>Teece 判断要点</th></tr>")
    for mem in tr["primary"]["members"]:
        a(f"<tr><td class='mono'>{esc(mem['ticker'])}</td><td class='muted'>{esc(mem['note'])}</td></tr>")
    a("</table>")
    a(f"<h3 style='margin-top:16px'>Live position：{esc(tr['live_position']['name'])} "
      f"<span class='mono muted'>{esc(tr['live_position']['ticker'])}</span></h3>")
    a(f"<div class='muted'>{esc(tr['live_position']['chain'])}</div>")

    if tr.get("contrast_cases"):
        a("<h3 style='margin-top:18px'>对照案例（检验框架是否依赖 edge）</h3>")
        a("<table style='margin-top:6px'><tr><th>Module</th><th>标的</th><th>核心张力</th></tr>")
        for c in tr["contrast_cases"]:
            a(f"<tr><td class='mono'>{esc(c['module'])}</td>"
              f"<td><b>{esc(c['name'])}</b><br><span class='mono muted'>{esc(c['ticker'])}</span></td>"
              f"<td class='muted'>{esc(c.get('key_tension') or c.get('why'))}</td></tr>")
        a("</table>")

    if tr.get("excluded_not_unfamiliar"):
        a("<h3 style='margin-top:18px'>已排除（本地已有决策级研究，对照功能失效）</h3>")
        for e in tr["excluded_not_unfamiliar"]:
            a(f"<div class='rule'><b>{esc(e['name'])}</b> "
              f"<span class='mono muted'>{esc(e['ticker'])}</span> — {esc(e['reason'])}</div>")

    a("<h3 style='margin-top:16px'>已退出常设</h3>")
    for d in tr["deferred"]:
        a(f"<div class='rule'><b>{esc(d['name'])}</b> {esc(d['role'])}</div>")
    a("</div>")

    lr = bc.get("local_resources")
    if lr:
        a("<h2>本地资源</h2><div class='card'>")
        a(f"<div class='mono muted'>{esc(lr['root'])}</div>")
        ca = lr.get("cninfo_announcements", {})
        a(f"<div class='rule' style='margin-top:8px'><b>cninfo 公告</b> {esc(ca.get('coverage'))}"
          f"<br><span class='muted'>{esc(ca.get('usage'))}</span></div>")
        em = lr.get("existing_memos", {})
        a(f"<div class='rule'><b>已有 memo × {esc(em.get('count'))}</b> "
          f"<span class='muted'>{esc(em.get('covers'))}</span></div>")
        a(f"<div class='rule'><b>PIT 用法（强制顺序）</b> {esc(em.get('pit_usage_rule'))}</div>")
        for x in em.get("affects_bootcamp", []):
            a(f"<div class='rule muted'>· {esc(x)}</div>")
        a("</div>")

    # forecasts
    a("<h2>Forecast Ledger</h2><div class='card'>")
    if s["forecasts"]:
        a("<table><tr><th>Module</th><th>预测</th><th>指标</th><th>阈值</th>"
          "<th>结算日</th><th>Linter</th></tr>")
        for f in s["forecasts"]:
            pill = ("<span class='pill ok'>pass</span>" if f.get("linter") == "pass"
                    else f"<span class='pill no'>fail</span>")
            a(f"<tr><td class='mono'>{esc(f['module'])}</td><td>{esc(f['text'])}</td>"
              f"<td class='muted'>{esc(f.get('metric') or '—')}</td>"
              f"<td class='muted'>{esc(f.get('threshold') or '—')}</td>"
              f"<td class='mono'>{esc(f.get('resolves') or '—')}</td><td>{pill}</td></tr>")
        a("</table>")
    else:
        a("<div class='muted'>尚无预测。闸门 g3 要求每个 module ≥3 条可结算预测。<br>"
          "<span class='mono'>modules.py forecast add M1 \"...\" --metric X --threshold Y "
          "--resolves 2027-06-30 --source \"10-Q\"</span></div>")
    a("</div>")

    a("<h2>第二波</h2><div class='card'>")
    sw = bc["second_wave"]
    a(f"<div class='muted'>触发：{esc(sw['trigger'])} · 预估 {esc(sw['est_hours'])}h</div>")
    a(f"<div style='margin-top:8px'>{esc(sw['content'])}</div>")
    a(f"<div class='muted' style='margin-top:6px'>{esc(sw['candidates_note'])}</div>")
    a("<ul style='margin-top:8px'>")
    for d in sw["deliverables"]:
        a(f"<li>{esc(d)}</li>")
    a("</ul></div>")

    a("</div></body></html>")
    return "".join(p)


def cmd_dashboard(args, bc, s):
    DASHBOARD.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD.write_text(render(bc, s), encoding="utf-8")
    print(f"dashboard -> {DASHBOARD}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Module-mode bootcamp driver (v2)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status").set_defaults(func=cmd_status)
    sub.add_parser("dashboard").set_defaults(func=cmd_dashboard)

    p = sub.add_parser("show"); p.add_argument("mid"); p.set_defaults(func=cmd_show)

    p = sub.add_parser("log", help="记录投入工时")
    p.add_argument("mid"); p.add_argument("--hours", type=float, required=True)
    p.add_argument("--kind", default="material",
                   choices=["material", "application", "transfer", "decision", "exam"])
    p.add_argument("--note")
    p.set_defaults(func=cmd_log)

    p = sub.add_parser("forecast")
    p.add_argument("action", choices=["add", "list"])
    p.add_argument("mid", nargs="?", default="M1")
    p.add_argument("text", nargs="?", default="")
    p.add_argument("--metric"); p.add_argument("--threshold")
    p.add_argument("--resolves"); p.add_argument("--source")
    p.add_argument("--probability", type=float)
    p.set_defaults(func=cmd_forecast)

    p = sub.add_parser("exit", help="尝试 module 出口")
    p.add_argument("mid")
    p.add_argument("--pass", dest="passed", action="store_true")
    p.add_argument("--note")
    p.set_defaults(func=cmd_exit)

    args = ap.parse_args()
    bc = load()
    s = load_state()
    args.func(args, bc, s)


if __name__ == "__main__":
    main()
