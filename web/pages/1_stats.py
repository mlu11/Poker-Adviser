"""Statistics page — view player stats and positional breakdown."""

import streamlit as st
import streamlit_shadcn_ui as ui
import streamlit_antd_components as sac
import pandas as pd
import plotly.graph_objects as go

from st_aggrid import AgGrid, GridOptionsBuilder

from poker_advisor.storage import Database, HandRepository
from poker_advisor.analysis.calculator import StatsCalculator
from poker_advisor.analysis.positional import PositionalAnalyzer
from poker_advisor.models.action import Street, ActionType

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from theme import inject_theme, PLOTLY_LAYOUT, COLORS
from navigation import render_sidebar_nav

st.set_page_config(page_title="统计分析", page_icon="📊", layout="wide")
inject_theme()
render_sidebar_nav("pages/1_stats")

st.title("📊 统计分析")

db = Database()
repo = HandRepository(db)

# Session filter
sessions = repo.get_sessions()
session_options = {"全部": None}
for s in sessions:
    label = f"{s['filename']} ({s['hand_count']} hands, {s['id']})"
    session_options[label] = s["id"]

selected = st.selectbox("选择会话", options=list(session_options.keys()))
session_id = session_options[selected]

hands = repo.get_all_hands(session_id=session_id)

if not hands:
    st.warning("未找到手牌数据。请先在首页导入日志文件。")
    st.stop()

calc = StatsCalculator()
stats = calc.calculate(hands)

st.subheader(f"玩家: {stats.player_name}")
st.caption(f"共 {stats.overall.total_hands} 手牌")

# Key metrics — shadcn metric cards
c1, c2, c3, c4 = st.columns(4)
with c1:
    ui.metric_card(title="收益", content=f"${stats.total_profit:+.2f}",
                   description="总盈亏", key="m_profit")
with c2:
    ui.metric_card(title="BB/100", content=f"{stats.bb_per_100:+.1f}",
                   description="每百手大盲", key="m_bb100")
with c3:
    ui.metric_card(title="VPIP", content=f"{stats.overall.vpip:.1f}%",
                   description="入池率", key="m_vpip")
with c4:
    ui.metric_card(title="PFR", content=f"{stats.overall.pfr:.1f}%",
                   description="翻前加注", key="m_pfr")

c5, c6, c7, c8 = st.columns(4)
with c5:
    ui.metric_card(title="3-Bet%", content=f"{stats.overall.three_bet_pct:.1f}%",
                   description="三次下注", key="m_3bet")
with c6:
    ui.metric_card(title="AF", content=f"{stats.overall.aggression_factor:.2f}",
                   description="攻击因子", key="m_af")
with c7:
    ui.metric_card(title="C-Bet%", content=f"{stats.overall.cbet_pct:.1f}%",
                   description="持续下注", key="m_cbet")
with c8:
    ui.metric_card(title="WTSD%", content=f"{stats.overall.wtsd:.1f}%",
                   description="摊牌率", key="m_wtsd")

sac.divider(label="位置分析", icon="geo-alt", color="green")

# Positional breakdown — AgGrid
analyzer = PositionalAnalyzer()
pos_rows = analyzer.position_summary(stats)

if pos_rows:
    df = pd.DataFrame(pos_rows)
    df.columns = ["位置", "手数", "VPIP%", "PFR%", "3Bet%", "AF", "CBet%", "弃牌率", "WTSD%"]

    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(sortable=True, filterable=True, resizable=True)
    gb.configure_column("位置", pinned="left", width=90)
    gb.configure_column("手数", type=["numericColumn"], width=80)
    grid_opts = gb.build()

    AgGrid(
        df,
        gridOptions=grid_opts,
        theme="alpine-dark",
        height=320,
        fit_columns_on_grid_load=True,
        key="pos_grid",
    )

    # --- Chart 1: VPIP/PFR Position Comparison (Paired bar) ---
    sac.divider(label="VPIP/PFR 位置对比", icon="bar-chart", color="green")

    positions = [r["position"] for r in pos_rows]
    vpip_vals = [r["vpip"] for r in pos_rows]
    pfr_vals = [r["pfr"] for r in pos_rows]

    fig_vpip = go.Figure()
    fig_vpip.add_trace(go.Bar(
        name="VPIP%", x=positions, y=vpip_vals,
        marker_color=COLORS["accent_green"],
    ))
    fig_vpip.add_trace(go.Bar(
        name="PFR%", x=positions, y=pfr_vals,
        marker_color=COLORS["accent_gold"],
    ))
    fig_vpip.update_layout(
        **PLOTLY_LAYOUT,
        barmode="group",
        height=380,
        title="各位置 VPIP% 与 PFR%",
        xaxis_title="位置",
        yaxis_title="百分比 (%)",
    )
    st.plotly_chart(fig_vpip, width="stretch")

    # Radar chart — position group comparison (preserved, with dark theme)
    group_rows = analyzer.group_summary(stats)
    if len(group_rows) >= 2:
        sac.divider(label="位置组对比", icon="diagram-3", color="green")
        metrics = ["VPIP%", "PFR%", "3Bet%", "AF", "CBet%", "WTSD%"]
        fig = go.Figure()

        for row in group_rows:
            values = [row["vpip"], row["pfr"], row["3bet"],
                      row["af"] * 10,  # scale AF for visibility
                      row["cbet"], row["wtsd"]]
            fig.add_trace(go.Scatterpolar(
                r=values + [values[0]],
                theta=metrics + [metrics[0]],
                fill="toself",
                name=row["group"],
            ))

        fig.update_layout(
            **PLOTLY_LAYOUT,
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100],
                                gridcolor=COLORS["card_border"]),
                bgcolor="rgba(0,0,0,0)",
            ),
            height=450,
        )
        st.plotly_chart(fig, width="stretch")
        st.caption("注: AF 值已乘以 10 以便在图表中可见")
else:
    st.info("位置数据不足，无法生成分析。")

# --- Chart 2: Cumulative profit trend (Line + fill) ---
sac.divider(label="累计收益走势", icon="graph-up-arrow", color="green")

cumulative = []
running = 0.0
calc = StatsCalculator()
for h in hands:
    hero_won_amt = h.winners.get(h.hero_seat, 0) if h.hero_seat is not None else 0
    hero_invested = calc._total_invested(h, h.hero_seat) if h.hero_seat is not None else 0
    profit = hero_won_amt - hero_invested
    running += profit
    cumulative.append(running)

hand_nums = list(range(1, len(cumulative) + 1))

fig_cum = go.Figure()
fig_cum.add_trace(go.Scatter(
    x=hand_nums, y=cumulative,
    mode="lines",
    fill="tozeroy",
    line=dict(color=COLORS["accent_green"], width=2),
    fillcolor="rgba(46,204,113,0.15)",
    name="累计收益",
))
fig_cum.update_layout(
    **PLOTLY_LAYOUT,
    height=380,
    title="累计收益走势",
    xaxis_title="手牌序号",
    yaxis_title="累计收益 ($)",
)
st.plotly_chart(fig_cum, width="stretch")

# --- Chart 3: Post-flop action distribution (Grouped bar) ---
sac.divider(label="翻后行动分布", icon="layers", color="green")

street_labels = {"flop": "Flop", "turn": "Turn", "river": "River"}
action_types_display = ["bet", "raise", "call", "check", "fold"]
action_counts = {street: {a: 0 for a in action_types_display} for street in street_labels}

for h in hands:
    if h.hero_seat is None:
        continue
    for a in h.actions:
        if a.seat != h.hero_seat:
            continue
        if a.street.value not in street_labels:
            continue
        atype = a.action_type.value
        if atype in action_counts[a.street.value]:
            action_counts[a.street.value][atype] += 1

fig_actions = go.Figure()
action_colors = {
    "bet": COLORS["accent_green"],
    "raise": COLORS["accent_gold"],
    "call": COLORS["accent_blue"],
    "check": COLORS["text_secondary"],
    "fold": COLORS["accent_red"],
}
for atype in action_types_display:
    fig_actions.add_trace(go.Bar(
        name=atype.capitalize(),
        x=list(street_labels.values()),
        y=[action_counts[s][atype] for s in street_labels],
        marker_color=action_colors[atype],
    ))

fig_actions.update_layout(
    **PLOTLY_LAYOUT,
    barmode="group",
    height=380,
    title="英雄翻后行动分布",
    xaxis_title="回合",
    yaxis_title="次数",
)
st.plotly_chart(fig_actions, width="stretch")

# --- Chart 4: Ability Radar (能力画像) ---
sac.divider(label="能力画像雷达图", icon="stars", color="green")

# Load GTO baselines for comparison
import json
from pathlib import Path

baseline_path = Path(__file__).parent.parent / "config" / "baselines.json"
baselines = json.loads(baseline_path.read_text()) if baseline_path.exists() else {}
overall_baseline = baselines.get("overall", {})

# Calculate ability scores (0-100) based on distance from GTO baseline
def calculate_score(actual, low, high, inverse=False):
    """Calculate a 0-100 score based on how close actual is to the baseline range."""
    mid = (low + high) / 2
    max_deviation = max(mid - low, high - mid) * 2
    deviation = abs(actual - mid)
    score = max(0, 100 - (deviation / max_deviation) * 100)
    return 100 - score if inverse else score

# Define ability metrics and their baselines
ability_metrics = [
    ("入池松紧", "vpip", stats.overall.vpip, overall_baseline.get("vpip", [22, 30])),
    ("翻前攻击性", "pfr", stats.overall.pfr, overall_baseline.get("pfr", [17, 24])),
    ("3-Bet频率", "three_bet", stats.overall.three_bet_pct, overall_baseline.get("three_bet_pct", [6, 10])),
    ("翻后攻击性", "af", stats.overall.aggression_factor * 20, [40, 80]),  # Scale AF to 0-100
    ("持续下注", "cbet", stats.overall.cbet_pct, overall_baseline.get("cbet_pct", [55, 75])),
    ("面对C-Bet弃牌", "fold_to_cbet", stats.overall.folded_to_cbet_pct, overall_baseline.get("fold_to_cbet", [35, 55])),
    ("摊牌率", "wtsd", stats.overall.wtsd, overall_baseline.get("wtsd", [25, 35])),
    ("摊牌胜率", "wsd", stats.overall.wsd, overall_baseline.get("wsd", [48, 56])),
]

# Calculate scores for each metric
ability_labels = []
ability_scores_actual = []
ability_scores_baseline = []

for label, key, actual, (low, high) in ability_metrics:
    ability_labels.append(label)
    # Score for actual (closeness to baseline)
    score = calculate_score(actual, low, high)
    ability_scores_actual.append(score)
    # Baseline midpoint gets 100
    ability_scores_baseline.append(100)

fig_radar = go.Figure()
fig_radar.add_trace(go.Scatterpolar(
    r=ability_scores_actual + [ability_scores_actual[0]],
    theta=ability_labels + [ability_labels[0]],
    fill="toself",
    name="你的能力",
    line=dict(color=COLORS["accent_green"], width=3),
    fillcolor="rgba(46,204,113,0.2)",
))
fig_radar.add_trace(go.Scatterpolar(
    r=ability_scores_baseline + [ability_scores_baseline[0]],
    theta=ability_labels + [ability_labels[0]],
    fill="none",
    name="GTO基准",
    line=dict(color=COLORS["accent_gold"], width=2, dash="dash"),
))
fig_radar.update_layout(
    **PLOTLY_LAYOUT,
    polar=dict(
        radialaxis=dict(
            visible=True,
            range=[0, 100],
            gridcolor=COLORS["card_border"],
            tickfont=dict(color=COLORS["text_muted"]),
        ),
        angularaxis=dict(
            tickfont=dict(color=COLORS["text_primary"], size=12),
            gridcolor=COLORS["card_border"],
        ),
        bgcolor="rgba(0,0,0,0)",
    ),
    height=550,
    title="能力画像雷达图 (与GTO基准对比)",
    showlegend=True,
)
st.plotly_chart(fig_radar, width="stretch")

# Show detailed ability scores
with st.expander("查看详细能力评分"):
    score_rows = []
    for label, key, actual, (low, high) in ability_metrics:
        score = calculate_score(actual, low, high)
        score_rows.append({
            "能力维度": label,
            "实际值": f"{actual:.1f}%",
            "GTO范围": f"{low:.1f}% - {high:.1f}%",
            "评分": f"{score:.0f}/100",
            "状态": "✅" if score >= 70 else "⚠️" if score >= 50 else "❌"
        })
    df_scores = pd.DataFrame(score_rows)
    st.dataframe(df_scores, use_container_width=True, hide_index=True)

# --- Chart 5: Time Analysis (时间维度分析) ---
sac.divider(label="时间维度分析", icon="clock-history", color="green")

# Try to extract dates from timestamps
def parse_timestamp(ts):
    """Parse timestamp string - handle various formats."""
    if not ts:
        return None
    try:
        # Try ISO format first
        if "T" in ts:
            from datetime import datetime
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        # Try simple date
        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"]:
            try:
                from datetime import datetime
                return datetime.strptime(ts[:10], fmt)
            except:
                continue
    except:
        pass
    return None

# Group hands by date
from collections import defaultdict
daily_stats = defaultdict(lambda: {
    "hands": 0, "profit": 0.0, "vpip_sum": 0.0, "pfr_sum": 0.0,
    "won_count": 0, "showdown_count": 0
})

calc = StatsCalculator()

for h in hands:
    # Try to get date from hand
    dt = parse_timestamp(h.timestamp)
    if not dt:
        # Use hand sequence if no timestamp
        date_key = "按手数分组"
    else:
        date_key = dt.strftime("%Y-%m-%d")

    daily_stats[date_key]["hands"] += 1

    # Calculate profit for this hand
    if h.hero_seat is not None:
        hero_won_amt = h.winners.get(h.hero_seat, 0)
        hero_invested = calc._total_invested(h, h.hero_seat)
        daily_stats[date_key]["profit"] += (hero_won_amt - hero_invested)

        # Check if hero won
        if h.hero_seat in h.winners:
            daily_stats[date_key]["won_count"] += 1

        # Check went to showdown
        hero_folded = any(
            a.seat == h.hero_seat and a.action_type == ActionType.FOLD
            for a in h.actions
        )
        if h.went_to_showdown and not hero_folded:
            daily_stats[date_key]["showdown_count"] += 1

# Prepare time series data
if len(daily_stats) > 0:
    date_labels = sorted(daily_stats.keys())
    profits = [daily_stats[d]["profit"] for d in date_labels]
    hand_counts = [daily_stats[d]["hands"] for d in date_labels]
    win_rates = [
        (daily_stats[d]["won_count"] / daily_stats[d]["hands"] * 100)
        if daily_stats[d]["hands"] > 0 else 0
        for d in date_labels
    ]

    # Cumulative profit over time
    cumulative_profit = []
    running = 0.0
    for p in profits:
        running += p
        cumulative_profit.append(running)

    # Time chart
    fig_time = go.Figure()

    # Add profit bars
    fig_time.add_trace(go.Bar(
        x=date_labels,
        y=profits,
        name="单日收益 ($)",
        marker_color=[COLORS["accent_green"] if p >= 0 else COLORS["accent_red"] for p in profits],
        opacity=0.7,
        yaxis="y",
    ))

    # Add cumulative profit line
    fig_time.add_trace(go.Scatter(
        x=date_labels,
        y=cumulative_profit,
        name="累计收益 ($)",
        line=dict(color=COLORS["accent_gold"], width=3),
        yaxis="y2",
    ))

    fig_time.update_layout(
        **PLOTLY_LAYOUT,
        height=400,
        title="时间维度收益分析",
        xaxis_title="日期",
        yaxis=dict(
            title="单日收益 ($)",
            side="left",
            gridcolor=COLORS["card_border"],
        ),
        yaxis2=dict(
            title="累计收益 ($)",
            side="right",
            overlaying="y",
            gridcolor=COLORS["card_border"],
        ),
        legend=dict(x=0, y=1.1, orientation="h"),
    )
    st.plotly_chart(fig_time, width="stretch")

    # Summary stats by time period
    with st.expander("查看时间段统计详情"):
        time_detail_rows = []
        for d in date_labels:
            s = daily_stats[d]
            time_detail_rows.append({
                "日期": d,
                "手数": s["hands"],
                "收益": f"${s['profit']:+.2f}",
                "胜率": f"{(s['won_count']/s['hands']*100):.1f}%" if s["hands"] > 0 else "-",
                "摊牌率": f"{(s['showdown_count']/s['hands']*100):.1f}%" if s["hands"] > 0 else "-",
            })
        df_time = pd.DataFrame(time_detail_rows)
        st.dataframe(df_time, use_container_width=True, hide_index=True)
else:
    st.info("暂无时间维度数据，需要手牌时间戳信息。")
