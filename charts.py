#!/usr/bin/env python3
"""Render the whitepaper's five figures from results/runs_raw.csv into results/charts/.

  fig1_tokens_to_correct_answer  tokens to reach a correct answer, each model-and-task pair both gateways got right
  fig2_effort_per_run            median tokens, tool calls and turns per run, across all runs
  fig3_cost_vs_success           cost per correct, governed task vs. success rate, every model on both gateways
  fig4_success_by_model          success rate by model on both gateways, grouped by tier
  fig5_read_outcomes             read-task outcomes (R1 + R2): solved, ran out of turns, no answer, confidently wrong

Each figure is written as PNG (for review) and SVG (for layout). A task counts as correct and
governed when its outcome is `solved` (R1, R2) or `clean` (A1); cost per correct task is total
spend divided by correct tasks, so failed runs are priced in. Colors were checked with the
dataviz palette validator (light surface, CVD separation and contrast pass).
"""
import csv
import os
import statistics as st

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results", "charts")

CAI, OSG = "connect_ai_gateway", "open_source_gateway"
NAME = {CAI: "Connect AI Gateway", OSG: "Open-source MCP gateway"}
COLOR = {CAI: "#1F4FA3", OSG: "#D2691E"}
INK, INK2, MUTED, GRID, SURFACE = "#15151C", "#52514E", "#8A8986", "#E6E4E0", "#FFFFFF"
# Read-task outcomes are states, so they use the status palette, each with a text label.
OUTCOMES = [("solved", "Solved", "#0CA30C"), ("timeout", "Ran out of turns", "#FAB219"),
            ("no_answer", "No answer", "#EC835A"), ("wrong_answer", "Confidently wrong", "#D03B3B")]
TIERS = ["frontier", "mid", "economy"]

plt.rcParams.update({
    "font.family": ["Arial", "Helvetica", "DejaVu Sans"], "font.size": 10,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "text.color": INK, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK,
    "axes.edgecolor": GRID, "axes.spines.top": False, "axes.spines.right": False,
    "svg.fonttype": "none",
})


def load():
    cfg = yaml.safe_load(open(os.path.join(HERE, "config", "models.yaml")))
    meta = {m["id"]: (m["label"].split(" (")[0], m.get("tier")) for m in cfg["models"]}
    rows = list(csv.DictReader(open(os.path.join(HERE, "results", "runs_raw.csv"), encoding="utf-8")))
    for r in rows:
        r["label"], r["tier"] = meta[r["model"]]
        r["ok"] = r["outcome"] in ("solved", "clean")
        r["cost"] = float(r["cost_usd"] or 0)
    return rows


def summarize(rows):
    """{(label, condition): (correct, tasks, cost per correct or None)}"""
    acc = {}
    for r in rows:
        a = acc.setdefault((r["label"], r["condition"]), [0, 0, 0.0])
        a[0] += r["ok"]; a[1] += 1; a[2] += r["cost"]
    return {k: (c, n, (s / c if c else None)) for k, (c, n, s) in acc.items()}


def money(v):
    return f"${v:.2f}" if v >= 0.1 else f"${v:.3f}"


def finish(fig, ax_or_axes, title, subtitle, name):
    h = fig.get_figheight()
    fig.subplots_adjust(top=1 - (0.95 + 0.18 * subtitle.count("\n")) / h)
    fig.text(0.01, 1 - 0.25 / h, title, ha="left", va="top", fontsize=14, fontweight="bold")
    fig.text(0.01, 1 - 0.55 / h, subtitle, ha="left", va="top", fontsize=10, color=INK2)
    for ax in (ax_or_axes if isinstance(ax_or_axes, (list, tuple)) else [ax_or_axes]):
        ax.grid(axis="x", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(length=0)
    os.makedirs(OUT, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(OUT, f"{name}.{ext}"), dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("wrote", os.path.join("results", "charts", name + ".{png,svg}"))


def legend(ax, loc="lower right", **kw):
    handles = [plt.Line2D([], [], marker="o", linestyle="", markersize=8, color=COLOR[c], label=NAME[c])
               for c in (CAI, OSG)]
    ax.legend(handles=handles, loc=loc, frameon=False, fontsize=9.5, **kw)


def fig_tokens(rows):
    """Tokens to reach a correct answer: for each model-and-task pair with correct runs on both gateways,
    the median tokens of its correct runs on each gateway (log-log), against the line of equal tokens."""
    by = {}
    for r in rows:
        if r["ok"]:
            by.setdefault((r["label"], r["task"], r["condition"]), []).append(float(r["total_tokens"] or 0))
    pairs = []
    for (m, t, c), v in by.items():
        if c == CAI and (m, t, OSG) in by:
            pairs.append((m, t, st.median(v), st.median(by[(m, t, OSG)])))
    ratios = sorted(o / a for _, _, a, o in pairs)
    med = st.median(ratios)
    fig, ax = plt.subplots(figsize=(8.5, 7.4))
    (x0, x1), (y0, y1) = (2e4, 2e6), (6e4, 6e6)  # two decades on each axis, so the diagonal is at 45 degrees
    ax.plot([y0, x1], [y0, x1], color=MUTED, linewidth=1.2, zorder=1)
    ax.plot([x0, y1 / 10], [x0 * 10, y1], color=GRID, linewidth=1.4, zorder=1)
    ax.text(x1 / 1.08, x1 / 1.25, "same tokens\non both gateways", fontsize=9, color=INK2, ha="right", va="top")
    ax.text(y1 / 10 * 1.12, y1 / 1.06, "ten times the tokens", fontsize=9, color=INK2, ha="left", va="top")
    ax.scatter([a for *_, a, _ in pairs], [o for *_, o in pairs], s=54, color=COLOR[OSG],
               edgecolor=SURFACE, linewidth=1.5, zorder=3)
    task = {"r1": "R1", "r2": "R2", "a1": "A1"}
    place = {("Qwen 3.8 Flash", "r1"): (10, 0, "left")}  # the widest pair; other labels would cover dots
    for m, t, a, o in pairs:
        if (m, t) in place:
            dx, dy, ha = place[(m, t)]
            ax.annotate(f"{m}, {task[t]}: {a / 1000:,.0f}K vs. {o / 1e6:.2f}M tokens", (a, o), xytext=(dx, dy),
                        textcoords="offset points", fontsize=9, color=INK, va="center", ha=ha,
                        bbox=dict(boxstyle="round,pad=0.15", fc=SURFACE, ec="none", alpha=0.85), zorder=4)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    lab = lambda v: f"{v / 1e6:g}M" if v >= 1e6 else f"{v / 1e3:g}K"
    xt, yt = [3e4, 1e5, 3e5, 1e6], [1e5, 3e5, 1e6, 3e6]
    ax.set_xticks(xt); ax.set_xticklabels([lab(v) for v in xt])
    ax.set_yticks(yt); ax.set_yticklabels([lab(v) for v in yt])
    ax.minorticks_off()
    ax.set_aspect("equal")
    ax.set_xlabel("Tokens through Connect AI Gateway (median of the pair's correct runs, log scale)")
    ax.set_ylabel("Tokens through the open-source MCP gateway (log scale)")
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    above = sum(1 for _, _, a, o in pairs if o > a)
    finish(fig, ax, "Tokens to reach the same correct answer",
           f"Each dot is one model on one task that both gateways got right ({len(pairs)} pairs). "
           f"{'All' if above == len(pairs) else above} {len(pairs)} sit above the line of equal tokens;\n"
           f"the median pair used {100 * (1 - 1 / med):.0f}% fewer tokens through Connect AI Gateway.",
           "fig1_tokens_to_correct_answer")


def fig_cost(rows, S):
    """Cost per correct task (log x) vs. success rate, one point per model per gateway, paired by a line."""
    models = sorted({k[0] for k in S})
    none_x = 60.0  # strip for models with no correct task on that gateway
    fig, ax = plt.subplots(figsize=(10, 6.2))
    for m in models:
        pts = []
        for c in (CAI, OSG):
            ok, n, cpc = S[(m, c)]
            pts.append((cpc if cpc else none_x, 100 * ok / n))
        for c, (x, y) in zip((CAI, OSG), pts):
            if x != none_x:
                ax.scatter(x, y, s=46, color=COLOR[c], edgecolor=SURFACE, linewidth=1.5, zorder=3)
    for c, dy in ((OSG, 10), (CAI, -10)):
        n = sum(1 for m in models if S[(m, c)][0] == 0)
        ax.scatter(none_x, 0, s=46 + 14 * n, color=COLOR[c], edgecolor=SURFACE, linewidth=1.5,
                   zorder=3 if c == OSG else 4)
        side = "open-source gateway" if c == OSG else "Connect AI Gateway"
        ax.annotate(f"{n} model{'s' if n != 1 else ''}, {side}", (none_x, 0), xytext=(-12, dy + 2),
                    textcoords="offset points", ha="right", fontsize=9, color=INK2)
    # All-model totals: the headline pair.
    tot = {}
    for c in (CAI, OSG):
        rs = [r for r in rows if r["condition"] == c]
        ok = sum(r["ok"] for r in rs); spend = sum(r["cost"] for r in rs)
        tot[c] = (spend / ok, 100 * ok / len(rs))
    ax.plot([tot[CAI][0], tot[OSG][0]], [tot[CAI][1], tot[OSG][1]], color=INK2, linewidth=1.5,
            linestyle=(0, (1, 2)), zorder=2)
    for c, xy, ha in ((CAI, (14, 10), "left"), (OSG, (-14, -14), "right")):
        x, y = tot[c]
        ax.scatter(x, y, s=190, color=COLOR[c], edgecolor=INK, linewidth=1.5, zorder=5)
        ax.annotate(f"All 27 models: {money(x)} per correct task, {y:.0f}% correct", (x, y),
                    xytext=xy, textcoords="offset points", fontsize=9.5, fontweight="bold",
                    color=INK, va="center", ha=ha,
                    bbox=dict(boxstyle="round,pad=0.25", fc=SURFACE, ec="none", alpha=0.9), zorder=6)
    ax.set_xscale("log")
    ax.set_xlim(0.004, 110)
    ax.axvline(30, color=GRID, linewidth=1)
    ticks = [0.01, 0.03, 0.1, 0.3, 1, 3, 10]
    ax.set_xticks(ticks + [none_x])
    ax.set_xticklabels([f"${t:g}" for t in ticks] + ["none\ncorrect"])
    ax.minorticks_off()
    ax.set_ylim(-4, 104)
    ax.set_yticks(range(0, 101, 20))
    ax.set_yticklabels([f"{v}%" for v in range(0, 101, 20)])
    ax.set_xlabel("Cost per correct, governed task (log scale; lower is better)")
    ax.set_ylabel("Tasks correct (of 15 per model)")
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    legend(ax, loc="lower left")
    finish(fig, ax, "Cost per correct task and success rate, every model on both gateways",
           f"One dot per model per gateway; large dots are all 27 models together: {money(tot[CAI][0])} vs. "
           f"{money(tot[OSG][0])} per correct task, failed runs priced in.".replace("$", r"\$"),  # no mathtext
           "fig3_cost_vs_success")


def fig_success(S):
    """Success rate by model, both gateways, grouped by tier (dumbbell)."""
    order, labels, ys, y = [], [], [], 0
    tier_rows = []
    for t in TIERS:
        ms = sorted({m for (m, c) in S if TIER[m] == t},
                    key=lambda m: (-S[(m, CAI)][0], -S[(m, OSG)][0], m))
        tier_rows.append((t, y))
        y += 1  # header row
        for m in ms:
            order.append(m); ys.append(y); labels.append(m); y += 1
        y += 0.4
    fig, ax = plt.subplots(figsize=(9, 9.5))
    for m, yy in zip(order, ys):
        a = 100 * S[(m, CAI)][0] / 15; b = 100 * S[(m, OSG)][0] / 15
        ax.plot([a, b], [yy, yy], color=GRID, linewidth=2, zorder=1)
        ax.scatter([b], [yy], s=52, color=COLOR[OSG], edgecolor=SURFACE, linewidth=1.5, zorder=3)
        ax.scatter([a], [yy], s=52, color=COLOR[CAI], edgecolor=SURFACE, linewidth=1.5, zorder=3)
    for t, yy in tier_rows:
        ax.text(-2, yy, t.capitalize() + " tier", fontweight="bold", fontsize=10.5, ha="left", va="center")
    ax.set_yticks(ys)
    ax.set_yticklabels(labels)
    ax.set_ylim(y - 0.4, -0.8)
    ax.set_xlim(-3, 103)
    ax.set_xticks(range(0, 101, 20))
    ax.set_xticklabels([f"{v}%" for v in range(0, 101, 20)])
    ax.set_xlabel("Tasks correct (5 runs x 3 tasks per model and gateway)")
    ax.spines["left"].set_visible(False)
    legend(ax, loc="lower left", bbox_to_anchor=(-0.02, 1.0), ncol=2)
    full = {c: sum(1 for m in order if S[(m, c)][0] == 15) for c in (CAI, OSG)}
    finish(fig, ax, "Who stays reliable",
           f"{full[CAI]} models got every task right through Connect AI Gateway; "
           f"{full[OSG]} did through the open-source gateway.",
           "fig4_success_by_model")


def fig_effort(rows):
    """Median effort per run, across all runs: tokens, tool calls, turns. Different scales, so one panel each."""
    measures = [("total_tokens", "Tokens per run", lambda v: f"{v / 1000:,.0f}K"),
                ("tool_calls", "Tool calls per run", lambda v: f"{v:g}"),
                ("turns", "Turns per run", lambda v: f"{v:g}")]
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.4))
    for ax, (col, title, fmt) in zip(axes, measures):
        vals = [st.median(float(r[col] or 0) for r in rows if r["condition"] == c) for c in (CAI, OSG)]
        bars = ax.barh([1, 0], vals, height=0.55, color=[COLOR[CAI], COLOR[OSG]])
        for b, v in zip(bars, vals):
            ax.text(b.get_width() + max(vals) * 0.02, b.get_y() + b.get_height() / 2, fmt(v),
                    va="center", fontsize=10, color=INK)
        ax.set_title(f"{title} (median)", loc="left", fontsize=10.5, fontweight="bold")
        ax.set_yticks([1, 0])
        ax.set_yticklabels(["Connect AI\nGateway", "Open-source\nMCP gateway"] if ax is axes[0] else ["", ""])
        ax.set_xlim(0, max(vals) * 1.25)
        ax.set_xticks([])
        ax.spines["bottom"].set_visible(False); ax.spines["left"].set_visible(False)
        ax.text(0, -0.62, f"{vals[1] / vals[0]:.1f}x more through the open-source gateway", fontsize=9.5,
                color=INK2, transform=ax.get_yaxis_transform())
    finish(fig, list(axes), "Where the cost goes, across all runs",
           "Medians of all 405 runs per gateway. Through the open-source gateway, the model fetches each system separately and does the math itself.",
           "fig2_effort_per_run")


def fig_outcomes(rows):
    """Read-task outcomes (R1 + R2) as 100% stacked bars, one per gateway."""
    fig, ax = plt.subplots(figsize=(10, 2.9))
    for yy, c in ((1, CAI), (0, OSG)):
        rs = [r for r in rows if r["condition"] == c and r["task"] in ("r1", "r2")]
        left = 0.0
        for key, label, color in OUTCOMES:
            share = 100 * sum(r["outcome"] == key for r in rs) / len(rs)
            ax.barh(yy, share, left=left, height=0.56, color=color, edgecolor=SURFACE, linewidth=2)
            if share >= 6:
                ax.text(left + share / 2, yy, f"{share:.0f}%", ha="center", va="center", fontsize=10,
                        color=INK, fontweight="bold")
            left += share
    ax.set_yticks([1, 0])
    ax.set_yticklabels(["Connect AI Gateway", "Open-source MCP gateway"])
    ax.set_xlim(0, 100)
    ax.set_xticks(range(0, 101, 25))
    ax.set_xticklabels([f"{v}%" for v in range(0, 101, 25)])
    ax.set_xlabel("Share of read runs (270 per gateway)")
    ax.spines["left"].set_visible(False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=col, label=lab) for _, lab, col in OUTCOMES]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.38), ncol=4, frameon=False, fontsize=9.5)
    finish(fig, ax, "Trustworthy answers",
           "A confidently wrong answer looks like a right one. Segments under 6% are unlabeled; see the table in the paper.",
           "fig5_read_outcomes")


if __name__ == "__main__":
    ROWS = load()
    TIER = {r["label"]: r["tier"] for r in ROWS}
    SUMMARY = summarize(ROWS)
    for old in os.listdir(OUT) if os.path.isdir(OUT) else []:
        if old.startswith("fig") and old.endswith((".png", ".svg")):
            os.remove(os.path.join(OUT, old))  # figure numbers follow the whitepaper; drop stale names
    fig_tokens(ROWS)
    fig_effort(ROWS)
    fig_cost(ROWS, SUMMARY)
    fig_success(SUMMARY)
    fig_outcomes(ROWS)
