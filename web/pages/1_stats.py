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
