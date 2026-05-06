"""
Generate system architecture diagram for AI Hazard Recognition.
Run: python generate_architecture.py
Output: architecture.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

fig, ax = plt.subplots(figsize=(20, 22))
ax.set_xlim(0, 20)
ax.set_ylim(0, 22)
ax.axis("off")
fig.patch.set_facecolor("#0f172a")

# ── Colour palette ────────────────────────────────────────────────────────────
C_BG       = "#0f172a"
C_PANEL    = "#1e293b"
C_BORDER   = "#334155"
C_HAZARD   = "#dc2626"
C_SAFE     = "#16a34a"
C_CAUTION  = "#d97706"
C_BLUE     = "#2563eb"
C_PURPLE   = "#7c3aed"
C_TEXT     = "#f1f5f9"
C_MUTED    = "#94a3b8"
C_ARROW    = "#64748b"

def box(ax, x, y, w, h, label, sublabel=None, color=C_PANEL, border=C_BORDER,
        fontsize=13, bold=True, icon=None, radius=0.3):
    patch = FancyBboxPatch((x, y), w, h,
        boxstyle=f"round,pad=0,rounding_size={radius}",
        linewidth=1.8, edgecolor=border, facecolor=color, zorder=2)
    ax.add_patch(patch)
    full = (f"{icon}  " if icon else "") + label
    weight = "bold" if bold else "normal"
    ty = y + h / 2 + (0.18 if sublabel else 0)
    ax.text(x + w/2, ty, full, ha="center", va="center",
            fontsize=fontsize, color=C_TEXT, fontweight=weight, zorder=3)
    if sublabel:
        ax.text(x + w/2, y + h/2 - 0.22, sublabel, ha="center", va="center",
                fontsize=9.5, color=C_MUTED, zorder=3)

def arrow(ax, x1, y1, x2, y2, color=C_ARROW):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
        arrowprops=dict(arrowstyle="-|>", color=color,
                        lw=2.0, mutation_scale=18), zorder=4)

def hline(ax, x, y, w, color=C_BORDER):
    ax.plot([x, x+w], [y, y], color=color, lw=1.2, zorder=2, ls="--")

# ─────────────────────────────────────────────────────────────────────────────
# Title
ax.text(10, 21.5, "AI Hazard Recognition — System Architecture",
        ha="center", va="center", fontsize=20, color=C_TEXT, fontweight="bold")
ax.text(10, 21.0, "CIVS × Purdue University Northwest",
        ha="center", va="center", fontsize=11, color=C_MUTED)

# ─────────────────────────────────────────────────────────────────────────────
# Row 1 — Camera feeds
cam_y = 19.4
for cx, lbl in [(1.5,"CAM 1\nNorth"), (5.8,"CAM 2\nMiddle"),
                (10.1,"CAM 3\nNorth"), (14.4,"CAM 4\nSouth")]:
    box(ax, cx, cam_y, 3.2, 1.2, lbl, color="#1e3a5f", border="#2563eb",
        fontsize=11, radius=0.25, bold=False)

ax.text(10, 19.1, "4 × MJPEG Camera Feeds", ha="center", va="center",
        fontsize=10, color=C_MUTED)

arrow(ax, 10, 19.4, 10, 18.65)

# ─────────────────────────────────────────────────────────────────────────────
# Row 2 — Inference
inf_y = 17.45
box(ax, 1.0, inf_y, 8.2, 1.1, "YOLO26m Inference",
    sublabel="Per frame · Per camera · GPU accelerated",
    color="#1e3a2f", border=C_SAFE, fontsize=13)
box(ax, 10.8, inf_y, 8.2, 1.1, "DeepSORT Tracker",
    sublabel="Persistent track IDs across frames",
    color="#2d1b69", border=C_PURPLE, fontsize=13)

ax.annotate("", xy=(10.8, inf_y+0.55), xytext=(9.2, inf_y+0.55),
    arrowprops=dict(arrowstyle="<->", color=C_MUTED, lw=1.8,
                    mutation_scale=16), zorder=4)

arrow(ax, 10, 17.45, 10, 16.7)

# ─────────────────────────────────────────────────────────────────────────────
# Row 3 — Hazard logic box
logic_y = 11.3
logic_h = 5.2
patch = FancyBboxPatch((0.5, logic_y), 19, logic_h,
    boxstyle="round,pad=0,rounding_size=0.3",
    linewidth=2.0, edgecolor="#475569", facecolor="#1e293b", zorder=2)
ax.add_patch(patch)

ax.text(10, logic_y + logic_h - 0.38, "Zone Hazard Logic",
        ha="center", va="center", fontsize=15, color=C_TEXT,
        fontweight="bold", zorder=3)
ax.text(10, logic_y + logic_h - 0.80, "Priority-ordered rules — evaluated every frame",
        ha="center", va="center", fontsize=10, color=C_MUTED, zorder=3)

rules = [
    ("P1",  "Person + equipment active in zone",          "HAZARD",  C_HAZARD,  "Highest priority override"),
    ("P2",  "Person + blockers confirmed + no equipment", "SAFE",    C_SAFE,    "Isolated corridor — person protected"),
    ("P3",  "Equipment physically inside zone polygon",   "HAZARD",  C_HAZARD,  "Blocker breach"),
    ("P4",  "Equipment in bay + zone NOT isolated",       "HAZARD",  C_HAZARD,  "Cross-bay propagation"),
    ("P5",  "Equipment + isolated + vehicle visible",     "SAFE",    C_SAFE,    "Camera confirms vehicle outside zone"),
    ("P5b", "Equipment + isolated + NOT visible",         "HAZARD",  C_HAZARD,  "Blind spot — vehicle unaccounted for"),
    ("P6",  "Bay idle + blockers confirmed",              "SAFE",    C_SAFE,    ""),
    ("P7",  "Bay idle + no blockers",                     "CAUTION", C_CAUTION, ""),
]

row_h   = 0.50
start_y = logic_y + logic_h - 1.15

for i, (pid, desc, outcome, col, note) in enumerate(rules):
    ry = start_y - i * row_h
    if i % 2 == 0:
        bg = FancyBboxPatch((0.7, ry - 0.20), 18.6, row_h - 0.04,
            boxstyle="round,pad=0,rounding_size=0.1",
            linewidth=0, facecolor="#263344", zorder=2)
        ax.add_patch(bg)
    ax.text(1.6,  ry + 0.12, pid,  ha="center", va="center",
            fontsize=11, color=C_MUTED, fontweight="bold", zorder=3)
    ax.text(2.5,  ry + 0.12, desc, ha="left",   va="center",
            fontsize=11, color=C_TEXT, zorder=3)
    if note:
        ax.text(12.0, ry + 0.12, f"↳ {note}", ha="left", va="center",
                fontsize=9.5, color=C_MUTED, zorder=3, style="italic")
    ax.add_patch(FancyBboxPatch((16.8, ry - 0.08), 2.4, 0.40,
        boxstyle="round,pad=0,rounding_size=0.08",
        linewidth=0, facecolor=col + "33", zorder=3))
    ax.add_patch(FancyBboxPatch((16.8, ry - 0.08), 2.4, 0.40,
        boxstyle="round,pad=0,rounding_size=0.08",
        linewidth=1.4, edgecolor=col, facecolor="none", zorder=3))
    ax.text(18.0, ry + 0.12, outcome, ha="center", va="center",
            fontsize=10, color=col, fontweight="bold", zorder=4)

arrow(ax, 10, 11.3, 10, 10.55)

# ─────────────────────────────────────────────────────────────────────────────
# Row 4 — Backend / Frontend
be_y = 9.35
box(ax, 0.6, be_y, 8.4, 1.1, "FastAPI Backend",
    sublabel="Python · Uvicorn · Thread-safe shared state",
    color="#1e2a3a", border=C_BLUE, fontsize=13)
box(ax, 11.0, be_y, 8.4, 1.1, "React Frontend",
    sublabel="Single-page app · MJPEG grid · Real-time polling",
    color="#2d1b3a", border=C_PURPLE, fontsize=13)

ax.annotate("", xy=(11.0, be_y+0.55), xytext=(9.0, be_y+0.55),
    arrowprops=dict(arrowstyle="<->", color=C_MUTED, lw=2.2,
                    mutation_scale=18), zorder=4)
ax.text(10.0, be_y + 0.76, "HTTP / MJPEG", ha="center", va="center",
        fontsize=9, color=C_MUTED)

# ─────────────────────────────────────────────────────────────────────────────
# Row 5 — API endpoints / UI features
arrow(ax, 4.8, 9.35, 4.8, 8.6)
arrow(ax, 15.2, 9.35, 15.2, 8.6)

ep_y = 7.2
box(ax, 0.6, ep_y, 8.4, 1.3, "", color="#131e2e", border="#1e3a5f", radius=0.2)
endpoints = [
    ("/stream/{1-4}",        "MJPEG video streams per camera"),
    ("/hazard_status",       "Zone state + blind spot flags"),
    ("/set_blocker",         "Blocker toggle controls"),
    ("/confirm_zone_clear",  "Blind spot clear confirmation"),
    ("/logs",                "Event log history"),
]
for j, (ep, desc) in enumerate(endpoints):
    ey = ep_y + 1.15 - j * 0.26
    ax.text(1.1,  ey, ep,   ha="left", va="center", fontsize=9.5,
            color="#60a5fa", fontweight="bold", zorder=3)
    ax.text(4.8,  ey, desc, ha="left", va="center", fontsize=9.5,
            color=C_MUTED, zorder=3)

ft_y = 7.2
box(ax, 11.0, ft_y, 8.4, 1.3, "", color="#1f1030", border="#4c1d95", radius=0.2)
features = [
    ("4-camera grid",          "Live MJPEG with detection overlays"),
    ("Blocker toggle panel",   "Far North · Inner N·S · Far South"),
    ("Zone isolation badges",  "ISOLATED · PARTIAL · OPEN · BLIND SPOT"),
    ("Confirm Zone Clear btn", "Manual blind spot acknowledgement"),
    ("Logs dashboard",         "Timestamped hazard event history"),
]
for j, (feat, desc) in enumerate(features):
    fy = ft_y + 1.15 - j * 0.26
    ax.text(11.5, fy, feat, ha="left", va="center", fontsize=9.5,
            color="#c084fc", fontweight="bold", zorder=3)
    ax.text(14.8, fy, desc, ha="left", va="center", fontsize=9.5,
            color=C_MUTED, zorder=3)

# ─────────────────────────────────────────────────────────────────────────────
# Legend
leg_y = 6.4
ax.text(10, leg_y, "Output States", ha="center", va="center",
        fontsize=11, color=C_MUTED, fontweight="bold")
for lx, lbl, col in [(4.5,"HAZARD",C_HAZARD),(8.7,"SAFE",C_SAFE),(12.9,"CAUTION",C_CAUTION)]:
    ax.add_patch(FancyBboxPatch((lx, leg_y - 0.6), 3.2, 0.48,
        boxstyle="round,pad=0,rounding_size=0.1",
        linewidth=1.8, edgecolor=col, facecolor=col+"22", zorder=3))
    ax.text(lx + 1.6, leg_y - 0.36, lbl, ha="center", va="center",
            fontsize=11, color=col, fontweight="bold", zorder=4)

# ─────────────────────────────────────────────────────────────────────────────
plt.tight_layout(pad=0)
out = "architecture.png"
plt.savefig(out, dpi=200, bbox_inches="tight",
            facecolor=C_BG, edgecolor="none")
print(f"Saved → {out}")
