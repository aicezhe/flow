# scripts/make_report.py: обёртка: данные из flow.storage, числа из flow.analytics,
# здесь только HTML. Пишет самодостаточную страницу data/report.html.
# Запуск из папки проекта:  python scripts/make_report.py
import html, math, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from flow import analytics, config, storage  # noqa: E402

OUT_PATH = ROOT / "data" / "report.html"


def esc(s):
    return html.escape(str(s), quote=True)


def day(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def bars(pairs, maxv):
    out = []
    for label, v in pairs:
        w = 100 * v / maxv if maxv else 0
        out.append(f'<div class="bar"><span class="bl">{esc(label)}</span>'
                   f'<span class="bt"><i style="width:{w:.1f}%"></i></span>'
                   f'<span class="bv">{v}</span></div>')
    return "".join(out)


def heat_style(v, vmax):
    if v <= 0 or vmax <= 0:
        return ""
    a = math.log1p(v) / math.log1p(vmax)
    fg = "#fff" if a > 0.55 else "#1a1a2e"
    return f' style="background:rgba(26,58,107,{0.08 + 0.92 * a:.2f});color:{fg}"'


def render(report, rows):
    s = report["summary"]
    span = f"{day(s['first_ts'])} to {day(s['last_ts'])}"
    cards = [("People", s["people"]), ("Plays", s["plays"]), ("Artists", s["artists"]),
             ("Matrix density", f"{s['density_percent']:.1f}%")]
    cards_html = "".join(f'<div class="card"><div class="k">{esc(k)}</div><div class="v">{esc(v)}</div></div>'
                         for k, v in cards)

    user_html = []
    for u in report["users"]:
        top = [(t["artist"], t["plays"]) for t in u["top_artists"]]
        hours, hmax = u["hours"], max(u["hours"])
        hcols = "".join(
            f'<div class="hc" title="{h:02d}:00, {hours[h]} plays"><i style="height:{100 * hours[h] / hmax if hmax else 0:.0f}%"></i>'
            f'<span>{h if h % 6 == 0 else ""}</span></div>' for h in range(24))
        user_html.append(f"""
<section class="user"><h3>{esc(u['name'])}</h3>
<p class="meta">{u['plays']} plays · {u['artists']} artists · {u['heard_once']} heard once · {day(u['first_ts'])} to {day(u['last_ts'])}</p>
<div class="two"><div><h4>Top artists</h4>{bars(top, top[0][1] if top else 0)}</div>
<div><h4>Plays by hour of day</h4><div class="hours">{hcols}</div></div></div></section>""")

    sim = report["similarity"]
    users = sim["users"]
    if len(users) >= 2:
        head = "".join(f"<th>{esc(u)}</th>" for u in users)
        body = "".join(
            f"<tr><th>{esc(a)}</th>" + "".join(f'<td{heat_style(j * 100, 100)}>{100 * j:.0f}%</td>' for j in row) + "</tr>"
            for a, row in zip(users, sim["matrix"]))
        sim_html = (f'<div class="scroll"><table class="mx"><tr><th></th>{head}</tr>{body}</table></div>'
                    '<p class="meta">Share of artists two people have in common (Jaccard similarity).</p>')
        plays = analytics.plays_by_user(rows)
        for i, a in enumerate(users):
            for b in users[i + 1:]:
                common = analytics.shared_artists(plays, a, b)
                if common:
                    sim_html += f"<p><b>{esc(a)} and {esc(b)}:</b> {esc(', '.join(common))}</p>"
    else:
        sim_html = '<p class="meta">Add a second person to see how tastes overlap.</p>'

    m = report["matrix"]
    vmax = max((v for row in m["plays"] for v in row), default=0)
    head = "".join(f"<th>{esc(u)}</th>" for u in m["users"])
    body = ""
    for j, art in enumerate(m["artists"]):
        cells = "".join(f'<td{heat_style(m["plays"][i][j], vmax)}>{m["plays"][i][j] or ""}</td>'
                        for i in range(len(m["users"])))
        body += f"<tr><th class='l'>{esc(art)}</th>{cells}</tr>"
    mx_html = f'<div class="scroll"><table class="mx"><tr><th></th>{head}</tr>{body}</table></div>'

    return (PAGE.replace("{generated}", datetime.fromtimestamp(report["generated_at"]).strftime("%Y-%m-%d %H:%M"))
                .replace("{span}", span).replace("{cards}", cards_html).replace("{users}", "".join(user_html))
                .replace("{sim}", sim_html).replace("{matrix}", mx_html).replace("{n}", str(len(m["artists"]))))


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Flow data report</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;1,300&family=DM+Mono:wght@400&family=Jost:wght@300;400&display=swap" rel="stylesheet">
<style>
:root{--bg:#f5f4f0;--card:#fff;--blue:#1a3a6b;--blue2:#2d5aaa;--text:#1a1a2e;--muted:#6b7288;--line:rgba(26,58,107,.14);
--serif:'Cormorant Garamond',Georgia,serif;--mono:'DM Mono',ui-monospace,Menlo,monospace;--sans:'Jost',system-ui,sans-serif}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:300 16px/1.6 var(--sans);padding:40px 20px 80px}
main{max-width:980px;margin:0 auto}h1,h2,h3,h4,p{margin:0}
h1{font:300 clamp(36px,6vw,54px)/1.05 var(--serif);color:var(--blue)}h2{font:400 30px var(--serif);color:var(--blue);margin:48px 0 14px;border-top:1px solid var(--line);padding-top:22px}
h3{font:400 26px var(--serif);color:var(--blue)}h4{font:400 11px var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-bottom:10px}
.mono,.meta{font:400 11px var(--mono);letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}.meta{text-transform:none;letter-spacing:.02em;margin:6px 0 14px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:22px}
.card{background:var(--card);border:1px solid var(--line);padding:16px}.k{font:400 10px var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}.v{font:300 34px var(--serif);color:var(--blue)}
.user{background:var(--card);border:1px solid var(--line);padding:22px;margin-bottom:16px}.two{display:grid;grid-template-columns:1fr 1fr;gap:28px}
.bar{display:grid;grid-template-columns:minmax(80px,38%) 1fr 34px;gap:8px;align-items:center;font-size:14px;margin:3px 0}.bl{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bt{background:rgba(26,58,107,.08);height:8px}.bt i{display:block;height:100%;background:var(--blue2)}.bv{font:400 11px var(--mono);color:var(--muted);text-align:right}
.hours{display:grid;grid-template-columns:repeat(24,1fr);gap:2px;height:120px;align-items:end}.hc{display:flex;flex-direction:column;justify-content:flex-end;height:100%;position:relative}
.hc i{display:block;background:var(--blue2);min-height:1px}.hc span{position:absolute;bottom:-18px;left:0;font:400 9px var(--mono);color:var(--muted)}
.scroll{overflow-x:auto}table.mx{border-collapse:collapse;font-size:13px}table.mx th,table.mx td{border:1px solid var(--line);padding:6px 10px;text-align:center;min-width:64px}
table.mx th{font:400 11px var(--mono);color:var(--muted);background:var(--card)}table.mx th.l{text-align:left;white-space:nowrap}
.note{border-left:2px solid var(--blue2);padding:10px 16px;background:rgba(45,90,170,.07);font-size:14px;margin-top:40px}
@media(max-width:700px){.two{grid-template-columns:1fr}}
</style></head><body><main>
<div class="mono">Flow · data report</div><h1>Who listens to what</h1>
<p class="meta">Generated {generated} · plays from {span}</p>
<div class="cards">{cards}</div>
<h2>People</h2>{users}
<h2>How similar are the tastes</h2>{sim}
<h2>Matrix: people × top {n} artists</h2>
<p class="meta">This is the R matrix from the ALS idea, shown small. Each cell is the number of plays; empty means none. Real data is mostly empty.</p>{matrix}
<p class="note">This page contains personal listening data. Keep it on your computer and do not commit it to git.</p>
</main></body></html>"""


def main():
    path = config.db_path()
    if not path.exists():
        sys.exit(f"No database at {path}. Run scripts/pull_lastfm.py first.")
    rows = storage.all_scrobbles(storage.connect(path))
    if not rows:
        sys.exit("The scrobbles table is empty. Listen to something, then run pull_lastfm.py again.")
    report = analytics.build_report(rows, generated_at=int(datetime.now().timestamp()))
    OUT_PATH.write_text(render(report, rows), encoding="utf-8")
    print("Wrote", OUT_PATH)


if __name__ == "__main__":
    main()
