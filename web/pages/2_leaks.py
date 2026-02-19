"""Leaks page — detect and display player weaknesses."""

import streamlit as st
import streamlit_shadcn_ui as ui
import streamlit_antd_components as sac
import plotly.graph_objects as go

from poker_advisor.storage import Database, HandRepository
from poker_advisor.analysis.calculator import StatsCalculator
from poker_advisor.analysis.leak_detector import LeakDetector, Severity

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from theme import inject_theme, PLOTLY_LAYOUT, COLORS
from navigation import render_sidebar_nav

st.set_page_config(page_title="漏洞检测", page_icon="🔍", layout="wide")
inject_theme()
render_sidebar_nav("pages/2_leaks")

st.title("🔍 漏洞检测")

db = Database()
repo = HandRepository(db)

sessions = repo.get_sessions()
session_options = {"全部": None}
for s in sessions:
    label = f"{s['filename']} ({s['hand_count']} hands, {s['id']})"
    session_options[label] = s["id"]

selected = st.selectbox("选择会话", options=list(session_options.keys()))
session_id = session_options[selected]

hands = repo.get_all_hands(session_id=session_id)

if not hands:
    st.warning("未找到手牌数据。请先导入日志文件。")
    st.stop()

calc = StatsCalculator()
stats = calc.calculate(hands)

detector = LeakDetector()
leaks = detector.detect(stats)

st.caption(f"基于 {stats.overall.total_hands} 手牌分析")

if not leaks:
    st.success("未检测到明显漏洞。继续保持扎实的打法！")
    st.stop()

# Filter controls
filter_col1, filter_col2 = st.columns([1, 1])
with filter_col1:
    severity_filter = sac.segmented(
        items=[
            sac.SegmentedItem(label="全部"),
            sac.SegmentedItem(label="S/A级"),
            sac.SegmentedItem(label="S级"),
            sac.SegmentedItem(label="A级"),
            sac.SegmentedItem(label="B级"),
            sac.SegmentedItem(label="C级"),
        ],
        color="green",
        index=1,
        key="severity_filter"
    )
with filter_col2:
    show_top = st.checkbox("仅显示Top 5关键问题", value=False)

# Apply filters
filtered_leaks = leaks
if severity_filter == "S/A级":
    filtered_leaks = [l for l in leaks if l.severity in (Severity.S, Severity.A)]
elif severity_filter == "S级":
    filtered_leaks = [l for l in leaks if l.severity == Severity.S]
elif severity_filter == "A级":
    filtered_leaks = [l for l in leaks if l.severity == Severity.A]
elif severity_filter == "B级":
    filtered_leaks = [l for l in leaks if l.severity == Severity.B]
elif severity_filter == "C级":
    filtered_leaks = [l for l in leaks if l.severity == Severity.C]

if show_top:
    filtered_leaks = filtered_leaks[:5]

st.subheader(f"显示 {len(filtered_leaks)}/{len(leaks)} 个问题")

severity_colors = {
    Severity.S: "🔴",
    Severity.A: "🟡",
    Severity.B: "🟢",
    Severity.C: "🔵",
}
severity_labels = {
    Severity.S: "严重 (S)",
    Severity.A: "重要 (A)",
    Severity.B: "一般 (B)",
    Severity.C: "轻微 (C)",
}
severity_badge_variant = {
    Severity.S: "destructive",
    Severity.A: "default",
    Severity.B: "secondary",
    Severity.C: "outline",
}

for i, leak in enumerate(filtered_leaks, 1):
    icon = severity_colors[leak.severity]
    label = severity_labels[leak.severity]

    with st.expander(f"{icon} {leak.description}", expanded=(leak.severity == Severity.S or leak.severity == Severity.A)):
        bcol, mcol = st.columns([1, 3])
        with bcol:
            ui.badges(
                badge_list=[(label, severity_badge_variant[leak.severity])],
                key=f"badge_{i}",
            )
        with mcol:
            pass

        col1, col2, col3 = st.columns(3)
        with col1:
            ui.metric_card(title="实际值", content=f"{leak.actual_value:.1f}",
                           description="当前指标", key=f"leak_actual_{i}")
        with col2:
            ui.metric_card(title="基线范围",
                           content=f"{leak.baseline_low:.1f} - {leak.baseline_high:.1f}",
                           description="GTO 参考", key=f"leak_baseline_{i}")
        with col3:
            ui.metric_card(title="严重程度", content=label,
                           description="偏离程度", key=f"leak_severity_{i}")

        if leak.advice:
            st.info(f"💡 {leak.advice}")

# --- Summary bar ---
sac.divider(label="汇总", icon="clipboard-data", color="green")
c1, c2, c3, c4 = st.columns(4)
s_count = sum(1 for l in leaks if l.severity == Severity.S)
a_count = sum(1 for l in leaks if l.severity == Severity.A)
b_count = sum(1 for l in leaks if l.severity == Severity.B)
c_count = sum(1 for l in leaks if l.severity == Severity.C)

with c1:
    ui.metric_card(title="S级", content=str(s_count),
                   description="需要立即改进", key="sum_s")
with c2:
    ui.metric_card(title="A级", content=str(a_count),
                   description="建议关注", key="sum_a")
with c3:
    ui.metric_card(title="B级", content=str(b_count),
                   description="可优化", key="sum_b")
with c4:
    ui.metric_card(title="C级", content=str(c_count),
                   description="轻微问题", key="sum_c")

# --- Chart 1: Severity distribution (Donut chart) ---
sac.divider(label="漏洞分布", icon="pie-chart", color="green")

severity_counts = [s_count, a_count, b_count, c_count]
severity_names = ["S级 (严重)", "A级 (重要)", "B级 (一般)", "C级 (轻微)"]
severity_chart_colors = [COLORS["accent_red"], COLORS["accent_gold"], COLORS["accent_green"], COLORS["accent_blue"]]

fig_donut = go.Figure(data=[go.Pie(
    labels=severity_names,
    values=severity_counts,
    hole=0.5,
    marker=dict(colors=severity_chart_colors),
    textinfo="label+value",
    textfont=dict(color=COLORS["text_primary"]),
)])
fig_donut.update_layout(
    **PLOTLY_LAYOUT,
    height=380,
    title="漏洞严重程度分布",
    showlegend=True,
)
st.plotly_chart(fig_donut, width="stretch")

# --- Chart 2: Actual vs Baseline Range (Horizontal bar + scatter) ---
sac.divider(label="实际值 vs 基线", icon="sliders", color="green")

leak_names = [l.description[:30] for l in leaks]
baseline_lows = [l.baseline_low for l in leaks]
baseline_highs = [l.baseline_high for l in leaks]
actual_vals = [l.actual_value for l in leaks]
baseline_widths = [h - lo for lo, h in zip(baseline_lows, baseline_highs)]

fig_compare = go.Figure()

# Baseline range as horizontal bars
fig_compare.add_trace(go.Bar(
    y=leak_names,
    x=baseline_widths,
    base=baseline_lows,
    orientation="h",
    name="基线范围",
    marker=dict(color="rgba(160,160,176,0.3)", line=dict(color=COLORS["text_muted"], width=1)),
))

# Actual values as diamond markers
severity_marker_colors = []
for l in leaks:
    if l.severity == Severity.S:
        severity_marker_colors.append(COLORS["accent_red"])
    elif l.severity == Severity.A:
        severity_marker_colors.append(COLORS["accent_gold"])
    elif l.severity == Severity.B:
        severity_marker_colors.append(COLORS["accent_green"])
    else:
        severity_marker_colors.append(COLORS["accent_blue"])

fig_compare.add_trace(go.Scatter(
    y=leak_names,
    x=actual_vals,
    mode="markers",
    name="实际值",
    marker=dict(
        symbol="diamond",
        size=14,
        color=severity_marker_colors,
        line=dict(color=COLORS["text_primary"], width=1),
    ),
))

fig_compare.update_layout(
    **PLOTLY_LAYOUT,
    height=max(300, len(leaks) * 50),
    title="各指标: 实际值 vs GTO 基线范围",
    xaxis_title="数值",
    barmode="overlay",
)
st.plotly_chart(fig_compare, width="stretch")
