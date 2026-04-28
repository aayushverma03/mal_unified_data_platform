"""Generate architecture diagrams for the D2 PDF.

Outputs PNGs at 200 DPI to docs/img/. Run via:
  uv run python scripts/generate_diagrams.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parent.parent / "docs" / "img"
OUT.mkdir(parents=True, exist_ok=True)

CARDS = "#ef4444"
TRANSFERS = "#2563eb"
BILLS = "#10b981"
INDIGO = "#6366f1"
SKY = "#0ea5e9"
PURPLE = "#8b5cf6"
AMBER = "#f59e0b"
SLATE = "#475569"
INK = "#0f172a"
BG = "#f8fafc"
WHITE = "#ffffff"

FONT = "DejaVu Sans"

plt.rcParams.update({
    "font.family": [FONT, "Helvetica", "Arial", "sans-serif"],
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.spines.left": False,
    "axes.spines.bottom": False,
})


def _box(ax, x, y, w, h, text, fill=WHITE, edge=SLATE, text_color=INK,
         fontweight="normal", fontsize=10):
    box = FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=1.2, edgecolor=edge, facecolor=fill, mutation_scale=1,
    )
    ax.add_patch(box)
    ax.text(x + w / 2, y + h / 2, text,
            ha="center", va="center",
            color=text_color, fontsize=fontsize, fontweight=fontweight,
            wrap=True)


def _arrow(ax, x1, y1, x2, y2, color=SLATE, lw=1.4, style="->"):
    arr = FancyArrowPatch(
        (x1, y1), (x2, y2), arrowstyle=style, mutation_scale=14,
        color=color, linewidth=lw, shrinkA=2, shrinkB=2,
    )
    ax.add_patch(arr)


def _label(ax, x, y, text, color=SLATE, fontsize=9, fontweight="normal", ha="center"):
    ax.text(x, y, text, ha=ha, va="center", color=color,
            fontsize=fontsize, fontweight=fontweight)


# ---------------------------------------------------------------------------
# Diagram 1. Current state.
# ---------------------------------------------------------------------------

def draw_current_state():
    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=200)
    ax.set_xlim(0, 12); ax.set_ylim(0, 7)
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    ax.set_facecolor(WHITE)

    # Three squad columns
    cols = [
        ("Cards squad", CARDS, 1.0, "Float USD amounts\nAuth+capture in one row\nUPPERCASE statuses"),
        ("Transfers squad", TRANSFERS, 4.5, "Amount as string\nAsia/Dubai naive ts\nSWIFT vocabulary"),
        ("Bill Payments squad", BILLS, 8.0, "Lowercase statuses\nDate-only schedules\nBiller taxonomy"),
    ]
    for name, color, x, quirks in cols:
        # Source label
        _label(ax, x + 1.5, 6.6, name.upper(), color=color, fontsize=9, fontweight="bold")
        # Squad database
        _box(ax, x, 5.2, 3, 1.0, f"{name}\ndatabase",
             fill=color + "11", edge=color, fontweight="bold", fontsize=10)
        # Schema quirks
        _box(ax, x, 3.8, 3, 1.0, quirks, fill=BG, edge=SLATE, text_color=SLATE, fontsize=8)
        # Squad-specific report
        _box(ax, x, 2.4, 3, 1.0, "Squad-specific\nreport", fill=WHITE, edge=SLATE, fontsize=9)
        # Arrows
        _arrow(ax, x + 1.5, 5.2, x + 1.5, 4.8, color=SLATE)
        _arrow(ax, x + 1.5, 3.8, x + 1.5, 3.4, color=SLATE)

    # Manual reconciliation box at the bottom
    _box(ax, 2.5, 0.5, 7, 1.2,
         "Manual reconciliation\nFinance joins three extracts by hand. Customer-id semantics differ. Float rounding errors.",
         fill="#fef2f2", edge="#dc2626", text_color="#7f1d1d", fontweight="bold", fontsize=9)

    # Three converging arrows
    for _, _, x, _ in cols:
        _arrow(ax, x + 1.5, 2.4, 6, 1.7, color="#dc2626", lw=1.2)

    fig.suptitle("Today: three squads, three schemas, three pipelines",
                 x=0.05, y=0.98, ha="left", fontsize=13, fontweight="bold", color=INK)
    fig.text(0.05, 0.93, "Each squad ships its own data into its own database. Cross-product analytics, finance reconciliation, and CBUAE reporting all suffer.",
             ha="left", fontsize=9.5, color=SLATE)

    plt.tight_layout(rect=[0, 0, 1, 0.91])
    out = OUT / "current_state.png"
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor=WHITE)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Diagram 2. Target architecture (layered).
# ---------------------------------------------------------------------------

def draw_target_architecture():
    fig, ax = plt.subplots(figsize=(12, 8.5), dpi=200)
    ax.set_xlim(0, 14); ax.set_ylim(0, 11)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_facecolor(WHITE)

    def layer_label(y, label):
        # Spaced-out caps for the layer rule.
        ax.text(0.2, y, " ".join(list(label)), ha="left", va="bottom", color=SLATE,
                fontsize=8.5, fontweight="bold")
        ax.plot([0.2, 13.8], [y - 0.1, y - 0.1], color="#e2e8f0", lw=0.8)

    # Layer 1. Sources
    layer_label(10.0, "SOURCES")
    sources = [("cards.csv", CARDS, 1.5), ("transfers.csv", TRANSFERS, 5.7), ("bill_payments.csv", BILLS, 10.0)]
    for name, color, x in sources:
        _box(ax, x, 8.95, 2.8, 0.85, name,
             fill=color + "1a", edge=color, fontweight="bold", fontsize=10)

    # Layer 2. Adapters
    layer_label(8.4, "ADAPTERS")
    for name, color, x in sources:
        squad_label = name.replace(".csv", "").replace("_", " ").title()
        _box(ax, x, 7.35, 2.8, 0.85,
             f"{squad_label} adapter", fill=WHITE, edge=color, fontweight="bold", fontsize=10)
        _arrow(ax, x + 1.4, 8.95, x + 1.4, 8.2, color=color)

    # Convergence arrows from adapters into validation
    for _, color, x in sources:
        _arrow(ax, x + 1.4, 7.35, 7, 6.5, color=color, lw=1.2)

    # Layer 3. Validation
    layer_label(6.8, "VALIDATION")
    _box(ax, 4.4, 5.7, 5.2, 0.85,
         "Pydantic v2 schema validation",
         fill=INDIGO + "1a", edge=INDIGO, fontweight="bold", fontsize=10)
    _box(ax, 10.4, 5.7, 3.2, 0.85,
         "Quarantine\n(per squad, per run)",
         fill=AMBER + "1a", edge=AMBER, fontweight="bold", fontsize=9)
    _arrow(ax, 9.6, 6.12, 10.4, 6.12, color=AMBER, lw=1.2)
    ax.text(10.0, 6.35, "invalid", ha="center", va="center", color=AMBER, fontsize=8, fontweight="bold")

    # Down arrow into storage
    _arrow(ax, 7, 5.7, 7, 5.0, color=INDIGO)

    # Layer 4. Storage
    layer_label(5.2, "STORAGE")
    _box(ax, 4.0, 4.05, 6.0, 0.95,
         "Canonical event store\nParquet, partitioned by (event_date, payment_type)",
         fill=SKY + "1a", edge=SKY, fontweight="bold", fontsize=10)

    # Layer 5. Consumers
    layer_label(3.5, "CONSUMERS")
    consumers = [
        ("DuckDB\nSQL", 0.6),
        ("Live\nreport", 3.3),
        ("Streamlit\ndashboard", 6.0),
        ("Finance\nrecon", 8.7),
        ("CBUAE\nreports", 11.4),
    ]
    for label, x in consumers:
        _box(ax, x, 1.6, 2.4, 1.05, label,
             fill=WHITE, edge=PURPLE, text_color=INK, fontweight="bold", fontsize=9)
        _arrow(ax, 7, 4.05, x + 1.2, 2.65, color=PURPLE, lw=1.0)

    fig.suptitle("Target architecture: one canonical event model",
                 x=0.05, y=0.98, ha="left", fontsize=14, fontweight="bold", color=INK)
    fig.text(0.05, 0.945,
             "Five layers. Adapters absorb squad-specific quirks. Pydantic v2 validates. Bad rows quarantine without blocking. The canonical Parquet store is the single source of truth.",
             ha="left", fontsize=9.5, color=SLATE)

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    out = OUT / "target_architecture.png"
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor=WHITE)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Diagram 3. Migration timeline.
# ---------------------------------------------------------------------------

def draw_migration_timeline():
    fig, ax = plt.subplots(figsize=(12, 4.8), dpi=200)
    ax.set_xlim(-1, 26); ax.set_ylim(0, 6)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_facecolor(WHITE)
    for s in ["top", "right", "left"]:
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#cbd5e1")

    # Week ticks
    for w in [0, 4, 8, 12, 16, 20, 24]:
        ax.axvline(w, color="#e2e8f0", lw=0.8, ymin=0.05, ymax=0.95, zorder=0)
        ax.text(w, 0.2, f"W{w}" if w else "Start", ha="center", va="top", fontsize=8.5, color=SLATE)
    ax.text(25, 0.2, "Week", ha="left", va="top", fontsize=8.5, color=SLATE, fontweight="bold")

    phases = [
        (4.6, 0,  4,  "Phase 0  Shadow mode",        "Adapters write to canonical store, squad systems unchanged",  INDIGO),
        (3.6, 4,  4,  "Phase 1  Dual-write",         "Squads dual-write. Consumers cut over to canonical store",    SKY),
        (2.6, 8,  4,  "Phase 2  Cutover",            "Squad-specific reports decommissioned, 30-day grace window",  PURPLE),
        (1.6, 12, 12, "Phase 3  Schema convergence", "Squad transactional schemas optionally adopt canonical fields", BILLS),
    ]

    for y, x_start, dur, label, sub, color in phases:
        bar = FancyBboxPatch(
            (x_start, y), dur, 0.7, boxstyle="round,pad=0.01,rounding_size=0.05",
            linewidth=1.2, edgecolor=color, facecolor=color + "26",
        )
        ax.add_patch(bar)
        ax.text(x_start + 0.15, y + 0.35, label,
                ha="left", va="center", fontsize=10, fontweight="bold", color=INK)
        ax.text(x_start + 0.15, y - 0.2, sub,
                ha="left", va="center", fontsize=8.5, color=SLATE)

    # Milestone markers
    milestones = [
        (4,  "Delta report green"),
        (8,  "Squad PM signoff"),
        (12, "Cutover complete"),
        (24, "Convergence opt-in"),
    ]
    for x, label in milestones:
        ax.plot(x, 5.4, marker="v", color="#dc2626", markersize=10, zorder=5)
        ax.text(x, 5.65, label, ha="center", va="bottom", fontsize=8, color="#7f1d1d", fontweight="bold")

    fig.suptitle("Migration timeline: 24 weeks across four phases",
                 x=0.05, y=0.98, ha="left", fontsize=13, fontweight="bold", color=INK)
    fig.text(0.05, 0.93,
             "Phase 0 has zero blast radius. Phases 1 to 2 are mechanical once the delta report is green for two weeks. Phase 3 is opt-in and runs at each squad's pace.",
             ha="left", fontsize=9.5, color=SLATE)

    plt.tight_layout(rect=[0, 0, 1, 0.91])
    out = OUT / "migration_timeline.png"
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor=WHITE)
    plt.close(fig)
    return out


if __name__ == "__main__":
    for fn in (draw_current_state, draw_target_architecture, draw_migration_timeline):
        path = fn()
        print(f"wrote {path}")
