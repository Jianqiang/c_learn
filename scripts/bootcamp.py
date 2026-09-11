"""Bootcamp driver: today's plan, progress state, and a static dashboard.

Deliberately standalone from the SQLite learning_os pipeline. A bootcamp day is
orchestration metadata, not a mastered concept -- mixing the two would let a
"day completed" silently look like evidence of mastery, which is exactly what
the bootcamp design forbids (AGENTS.md P4).

Usage:
    python scripts/bootcamp.py today
    python scripts/bootcamp.py day 3
    python scripts/bootcamp.py done 1 --artifact outputs/day01/snps_map_v0.md
    python scripts/bootcamp.py closed-book 1          # mark closed-book submitted
    python scripts/bootcamp.py dashboard
"""
from __future__ import annotations

import argparse
import html
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "content" / "bootcamp_20d.yaml"
PROGRESS = ROOT / "data" / "bootcamp_progress.yaml"
DASHBOARD = ROOT / "outputs" / "dashboard.html"


# --------------------------------------------------------------------------
# manifest + progress
# --------------------------------------------------------------------------

def load_manifest() -> dict[str, Any]:
    with MANIFEST.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    if "bootcamp" not in raw:
        raise SystemExit(f"{MANIFEST} must contain a 'bootcamp' mapping")
    return raw["bootcamp"]


def load_progress() -> dict[str, Any]:
    if not PROGRESS.exists():
        return {"days": {}}
    with PROGRESS.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {"days": {}}


def save_progress(state: dict[str, Any]) -> None:
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    with PROGRESS.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(state, fh, allow_unicode=True, sort_keys=False)


def today_in_tz(bc: dict[str, Any]) -> date:
    return datetime.now(ZoneInfo(bc.get("timezone", "Asia/Shanghai"))).date()


def day_for_date(bc: dict[str, Any], on: date) -> int:
    """Map a calendar date to a bootcamp day number.

    Days are scheduled on weekdays only, so this counts business days from
    start_date rather than raw elapsed days -- a weekend must not silently
    burn two days of the plan.
    """
    start = date.fromisoformat(bc["start_date"])
    if on < start:
        return 0
    count = 0
    cursor = start
    while cursor <= on:
        if cursor.weekday() < 5:
            count += 1
        cursor += timedelta(days=1)
    return min(count, bc["duration_days"] + 1)


def get_day(bc: dict[str, Any], n: int) -> dict[str, Any] | None:
    for d in bc["days"]:
        if d["day"] == n:
            return d
    return None


def project_name(bc: dict[str, Any], slug: str) -> str:
    if slug == "all":
        return "三家公司"
    for p in bc["projects"]:
        if p["slug"] == slug:
            return f"{p['name']} ({p['ticker']})"
    return slug


def day_state(progress: dict[str, Any], n: int) -> dict[str, Any]:
    return (progress.get("days") or {}).get(n, {})


# --------------------------------------------------------------------------
# terminal rendering
# --------------------------------------------------------------------------

def print_day(bc: dict[str, Any], plan: dict[str, Any], progress: dict[str, Any]) -> None:
    st = day_state(progress, plan["day"])
    week = next(w for w in bc["weeks"] if w["week"] == plan["week"])
    tag = " [EXAM]" if plan.get("exam") else ""

    print(f"\nDay {plan['day']}/{bc['duration_days']}{tag} — {plan['title']}")
    print(f"  {plan['date']} | Week {week['week']} {week['name']}: {week['subtitle']}")
    print(f"  周目标: {week['goal']}")

    cb = "已提交" if st.get("closed_book") else "未提交  <-- 分析类协助未解锁"
    print(f"\n  闭卷题: {plan['closed_book_prompt']}")
    print(f"  闭卷状态: {cb}")

    if plan.get("theory"):
        print("\n  Theory:")
        for t in plan["theory"]:
            print(f"    - {t['title']}")
            print(f"      {t['scope']}")
            if t.get("url"):
                print(f"      {t['url']}")
    else:
        print("\n  Theory: 无新内容（考试日）")

    print(f"\n  Primary [{project_name(bc, plan['primary']['project'])}] 140m:")
    print(f"    {plan['primary']['task']}")
    print(f"\n  Transfer [{project_name(bc, plan['transfer']['project'])}] 60m:")
    print(f"    {plan['transfer']['task']}")

    print("\n  Outputs（必须落盘）:")
    done = set(st.get("artifacts", []))
    for o in plan["outputs"]:
        print(f"    [ ] {o}")
    if done:
        print("  已记录 artifacts:")
        for a in sorted(done):
            print(f"    - {a}")

    ai = plan["ai_usage"]
    print(f"\n  AI 模式: {ai['mode']}")
    print(f"    允许: {ai['allowed']}")
    print(f"    禁止: {ai['forbidden']}")
    if ai.get("special"):
        print(f"    要点: {ai['special']}")
    if plan.get("safety"):
        print(f"    安全: {plan['safety']}")
    if plan.get("graduation_line"):
        print(f"\n  毕业线: {plan['graduation_line']}")

    print("\n  时间结构:")
    for b in bc["daily_blocks"]:
        print(f"    {b['minutes']:>4}m  {b['name']:<30} {b['content']}")
    print()


# --------------------------------------------------------------------------
# static dashboard
# --------------------------------------------------------------------------

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif;
background:#faf9f7;color:#2c2c2a;line-height:1.6;padding:32px 24px 64px}
.wrap{max-width:1080px;margin:0 auto}
h1{font-size:20px;font-weight:500;margin-bottom:4px}
h2{font-size:15px;font-weight:500;margin:32px 0 12px;padding-bottom:6px;border-bottom:1px solid #e5e3dd}
h3{font-size:13px;font-weight:500;margin-bottom:8px}
.sub{font-size:13px;color:#5f5e5a;margin-bottom:24px}
.card{background:#fff;border:1px solid #e5e3dd;border-radius:12px;padding:20px;margin-bottom:16px}
.grid{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}
.cell{border:1px solid #e5e3dd;border-radius:8px;padding:10px;background:#fff;font-size:12px;min-height:76px}
.cell.done{background:#eaf3de;border-color:#97c459}
.cell.today{background:#e6f1fb;border-color:#378add;border-width:2px}
.cell.exam{background:#fcebeb;border-color:#f09595}
.cell.exam.done{background:#eaf3de;border-color:#97c459}
.cell .n{font-weight:500;font-size:11px;color:#5f5e5a}
.cell .t{margin-top:4px;color:#2c2c2a;line-height:1.35}
.wk{font-size:11px;color:#888780;margin:16px 0 6px;text-transform:none}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #eeece6;vertical-align:top}
th{font-weight:500;color:#5f5e5a;font-size:12px}
.pill{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;border:1px solid}
.ok{background:#eaf3de;border-color:#97c459;color:#27500a}
.no{background:#fcebeb;border-color:#f09595;color:#791f1f}
.warn{background:#faeeda;border-color:#efa027;color:#633806}
.blocks{display:flex;gap:0;border-radius:8px;overflow:hidden;border:1px solid #e5e3dd;margin-top:8px}
.blk{padding:8px 6px;font-size:11px;text-align:center;border-right:1px solid #e5e3dd;color:#2c2c2a}
.blk:last-child{border-right:none}
.blk b{display:block;font-weight:500;font-size:12px}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
ul{padding-left:18px}li{margin:3px 0;font-size:13px}
.muted{color:#5f5e5a;font-size:12px}
.bar{height:6px;background:#eeece6;border-radius:3px;overflow:hidden;margin:8px 0 4px}
.bar>div{height:100%;background:#639922}
.two{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.rule{font-size:12px;color:#5f5e5a;padding:6px 0;border-bottom:1px dashed #e5e3dd}
.rule:last-child{border:none}
.rule b{color:#2c2c2a;font-weight:500}
"""


def esc(s: Any) -> str:
    return html.escape(str(s))


def render_dashboard(bc: dict[str, Any], progress: dict[str, Any], today_n: int) -> str:
    days = bc["days"]
    completed = sum(1 for d in days if day_state(progress, d["day"]).get("completed"))
    pct = int(completed / len(days) * 100)

    parts: list[str] = []
    a = parts.append
    a(f"<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>")
    a("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    a(f"<title>{esc(bc['name'])}</title><style>{CSS}</style></head><body><div class='wrap'>")
    a(f"<h1>{esc(bc['name'])}</h1>")
    gen = datetime.now(ZoneInfo(bc.get("timezone", "Asia/Shanghai"))).strftime("%Y-%m-%d %H:%M")
    a(f"<div class='sub'>{esc(bc['duration_days'])} 天 · 每天 {esc(bc['daily_hours'])} 小时 · "
      f"起始 {esc(bc['start_date'])} · 生成于 {esc(gen)}</div>")

    a("<div class='card'>")
    a(f"<h3>进度 {completed}/{len(days)} 天完成（{pct}%）</h3>")
    a(f"<div class='bar'><div style='width:{pct}%'></div></div>")
    a(f"<div class='muted'>核心循环：{esc(' → '.join(bc['core_loop']))}　|　"
      f"终点链条：{esc(' → '.join(bc['final_chain']))}</div></div>")

    # ---- today ----
    plan = get_day(bc, today_n)
    if plan:
        st = day_state(progress, today_n)
        week = next(w for w in bc["weeks"] if w["week"] == plan["week"])
        a("<h2>今日计划</h2><div class='card'>")
        tag = " · 闭卷考试" if plan.get("exam") else ""
        a(f"<h3>Day {plan['day']} — {esc(plan['title'])}{tag}</h3>")
        a(f"<div class='muted'>{esc(plan['date'])} · Week {week['week']} {esc(week['name'])}"
          f" — {esc(week['subtitle'])}</div>")
        a(f"<div class='muted' style='margin-top:4px'>周目标：{esc(week['goal'])}</div>")

        cb = st.get("closed_book")
        pill = "<span class='pill ok'>闭卷已提交</span>" if cb else \
               "<span class='pill no'>闭卷未提交 · 分析类协助未解锁</span>"
        a(f"<div style='margin-top:14px'>{pill}</div>")
        a(f"<div style='margin-top:8px'><b>闭卷题：</b>{esc(plan['closed_book_prompt'])}</div>")

        a("<div class='blocks'>")
        for b in bc["daily_blocks"]:
            a(f"<div class='blk' style='flex:{b['minutes']}'><b>{b['minutes']}m</b>{esc(b['name'])}</div>")
        a("</div>")

        a("<div class='two' style='margin-top:16px'>")
        a(f"<div><h3>Primary · {esc(project_name(bc, plan['primary']['project']))}</h3>"
          f"<div class='muted'>{esc(plan['primary']['task'])}</div></div>")
        a(f"<div><h3>Transfer · {esc(project_name(bc, plan['transfer']['project']))}</h3>"
          f"<div class='muted'>{esc(plan['transfer']['task'])}</div></div>")
        a("</div>")

        if plan.get("theory"):
            a("<h3 style='margin-top:16px'>Theory</h3><ul>")
            for t in plan["theory"]:
                link = f" <a href='{esc(t['url'])}' class='mono'>链接</a>" if t.get("url") else ""
                a(f"<li>{esc(t['title'])} — <span class='muted'>{esc(t['scope'])}</span>{link}</li>")
            a("</ul>")

        arts = set(st.get("artifacts", []))
        a("<h3 style='margin-top:16px'>今日 outputs</h3><ul>")
        for o in plan["outputs"]:
            a(f"<li>{esc(o)}</li>")
        a("</ul>")
        if arts:
            a("<div class='muted' style='margin-top:6px'>已落盘：" +
              ", ".join(f"<span class='mono'>{esc(x)}</span>" for x in sorted(arts)) + "</div>")

        ai = plan["ai_usage"]
        a(f"<h3 style='margin-top:16px'>AI 模式：{esc(ai['mode'])}</h3>")
        a(f"<div class='rule'><b>允许</b> {esc(ai['allowed'])}</div>")
        a(f"<div class='rule'><b>禁止</b> {esc(ai['forbidden'])}</div>")
        if ai.get("special"):
            a(f"<div class='rule'><b>要点</b> {esc(ai['special'])}</div>")
        if plan.get("safety"):
            a(f"<div class='rule'><b>安全</b> {esc(plan['safety'])}</div>")
        if plan.get("graduation_line"):
            a(f"<div class='rule'><b>毕业线</b> {esc(plan['graduation_line'])}</div>")
        a("</div>")
    elif today_n == 0:
        a("<div class='card'>bootcamp 尚未开始。</div>")
    else:
        a("<div class='card'>bootcamp 已完成全部 20 天。</div>")

    # ---- 20 day grid ----
    a("<h2>20 天进度</h2>")
    for w in bc["weeks"]:
        a(f"<div class='wk'>Week {w['week']} · {esc(w['name'])} — {esc(w['subtitle'])}</div>")
        a("<div class='grid'>")
        for d in [x for x in days if x["week"] == w["week"]]:
            st = day_state(progress, d["day"])
            cls = "cell"
            if d.get("exam"):
                cls += " exam"
            if st.get("completed"):
                cls += " done"
            if d["day"] == today_n:
                cls += " today"
            a(f"<div class='{cls}'><div class='n'>Day {d['day']} · {esc(d['date'][5:])}</div>"
              f"<div class='t'>{esc(d['title'])}</div></div>")
        a("</div>")

    # ---- projects ----
    a("<h2>三个训练器</h2><div class='card'><table><tr><th>公司</th><th>角色</th>"
      "<th>训练链条</th><th>Primary 天数</th><th>Primary source</th></tr>")
    for p in bc["projects"]:
        pdays = [str(d["day"]) for d in days if d["primary"]["project"] == p["slug"]]
        tdays = [str(d["day"]) for d in days if d["transfer"]["project"] == p["slug"]]
        a(f"<tr><td><b>{esc(p['name'])}</b><br><span class='mono muted'>{esc(p['ticker'])}</span></td>"
          f"<td>{esc(p['role'])}</td><td class='muted'>{esc(p['chain'])}</td>"
          f"<td class='mono'>主 {','.join(pdays) or '-'}<br>迁 {','.join(tdays) or '-'}</td>"
          f"<td><a href='{esc(p['primary_source'])}' class='mono'>filing</a></td></tr>")
    a("</table></div>")

    # ---- principles ----
    a("<h2>四条训练设计</h2><div class='card'>")
    for pr in bc["design_principles"]:
        a(f"<div class='rule'><b>{esc(pr['name'])}</b><br>{esc(pr['rule'])}</div>")
    a("</div>")

    # ---- artifacts ----
    a("<h2>产物清单</h2><div class='card'>")
    a(f"<div class='muted'>只保存三类正式产物：{esc(' / '.join(bc['artifact_policy']['save']))}。"
      f"不保存：{esc(' / '.join(bc['artifact_policy']['never_save']))}。</div>")
    rows = []
    for d in days:
        st = day_state(progress, d["day"])
        for art in st.get("artifacts", []):
            fp = ROOT / art
            ok = "<span class='pill ok'>存在</span>" if fp.exists() else "<span class='pill no'>缺失</span>"
            rows.append(f"<tr><td class='mono'>D{d['day']}</td><td class='mono'>{esc(art)}</td><td>{ok}</td></tr>")
    if rows:
        a("<table style='margin-top:10px'><tr><th>天</th><th>文件</th><th>状态</th></tr>"
          + "".join(rows) + "</table>")
    else:
        a("<div class='muted' style='margin-top:10px'>尚无记录的 artifact。用 "
          "<span class='mono'>bootcamp.py done &lt;day&gt; --artifact &lt;path&gt;</span> 登记。</div>")
    a("</div>")

    # ---- deferred ----
    a("<h2>已刻意暂缓（降级为 JIT）</h2><div class='card'>")
    a(f"<div class='muted'>{esc(bc['deferred_to_jit']['reason'])}</div><ul style='margin-top:8px'>")
    for it in bc["deferred_to_jit"]["items"]:
        a(f"<li class='muted'>{esc(it)}</li>")
    a("</ul></div>")

    a("</div></body></html>")
    return "".join(parts)


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def cmd_today(args: argparse.Namespace) -> None:
    bc = load_manifest()
    n = day_for_date(bc, today_in_tz(bc))
    if n == 0:
        print(f"bootcamp 尚未开始（起始 {bc['start_date']}）")
        return
    plan = get_day(bc, n)
    if plan is None:
        print(f"bootcamp 已完成全部 {bc['duration_days']} 天。")
        return
    print_day(bc, plan, load_progress())


def cmd_day(args: argparse.Namespace) -> None:
    bc = load_manifest()
    plan = get_day(bc, args.n)
    if plan is None:
        raise SystemExit(f"day {args.n} 不在 1..{bc['duration_days']}")
    print_day(bc, plan, load_progress())


def cmd_closed_book(args: argparse.Namespace) -> None:
    bc = load_manifest()
    if get_day(bc, args.n) is None:
        raise SystemExit(f"day {args.n} 不存在")
    state = load_progress()
    state.setdefault("days", {}).setdefault(args.n, {})
    state["days"][args.n]["closed_book"] = True
    state["days"][args.n]["closed_book_at"] = datetime.now().isoformat(timespec="seconds")
    save_progress(state)
    print(f"Day {args.n}: 闭卷已标记提交，分析类协助解锁。")


def cmd_done(args: argparse.Namespace) -> None:
    bc = load_manifest()
    if get_day(bc, args.n) is None:
        raise SystemExit(f"day {args.n} 不存在")
    state = load_progress()
    entry = state.setdefault("days", {}).setdefault(args.n, {})
    if args.artifact:
        arts = set(entry.get("artifacts", []))
        arts.update(args.artifact)
        entry["artifacts"] = sorted(arts)
    if not args.artifact and not entry.get("artifacts"):
        raise SystemExit("拒绝：没有任何 artifact 的一天不算完成（AGENTS.md §5）。")
    entry["completed"] = True
    entry["completed_at"] = datetime.now().isoformat(timespec="seconds")
    if args.note:
        entry["note"] = args.note
    save_progress(state)
    print(f"Day {args.n} 标记完成，artifacts: {entry.get('artifacts')}")


def cmd_dashboard(args: argparse.Namespace) -> None:
    bc = load_manifest()
    progress = load_progress()
    n = day_for_date(bc, today_in_tz(bc))
    DASHBOARD.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD.write_text(render_dashboard(bc, progress, n), encoding="utf-8")
    print(f"dashboard -> {DASHBOARD}")


def cmd_status(args: argparse.Namespace) -> None:
    bc = load_manifest()
    progress = load_progress()
    n = day_for_date(bc, today_in_tz(bc))
    print(f"{bc['name']} | today=Day {n}/{bc['duration_days']}")
    for d in bc["days"]:
        st = day_state(progress, d["day"])
        mark = "x" if st.get("completed") else (">" if d["day"] == n else " ")
        cb = "CB" if st.get("closed_book") else "  "
        ex = "EXAM" if d.get("exam") else "    "
        print(f"  [{mark}] D{d['day']:>2} {d['date']} {ex} {cb} {d['title']}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Deliberate practice bootcamp driver")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("today", help="显示今日计划").set_defaults(func=cmd_today)
    sub.add_parser("status", help="20 天总览").set_defaults(func=cmd_status)
    sub.add_parser("dashboard", help="生成静态进度网页").set_defaults(func=cmd_dashboard)

    p = sub.add_parser("day", help="显示指定天")
    p.add_argument("n", type=int)
    p.set_defaults(func=cmd_day)

    p = sub.add_parser("closed-book", help="标记闭卷已提交（解锁分析类协助）")
    p.add_argument("n", type=int)
    p.set_defaults(func=cmd_closed_book)

    p = sub.add_parser("done", help="标记某天完成（必须带 artifact）")
    p.add_argument("n", type=int)
    p.add_argument("--artifact", action="append", help="产物路径，可重复")
    p.add_argument("--note")
    p.set_defaults(func=cmd_done)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
