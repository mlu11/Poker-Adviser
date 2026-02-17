"""Hands page — browse hand history and sessions."""

import streamlit as st
import streamlit_shadcn_ui as ui
import streamlit_antd_components as sac
import pandas as pd
import plotly.graph_objects as go

from st_aggrid import AgGrid, GridOptionsBuilder

from poker_advisor.storage import Database, HandRepository
from poker_advisor.formatters.text import TextFormatter

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from theme import inject_theme, PLOTLY_LAYOUT, COLORS
from navigation import render_sidebar_nav

st.set_page_config(page_title="手牌历史", page_icon="📋", layout="wide")
inject_theme()
render_sidebar_nav("pages/5_hands")

st.title("📋 手牌历史")

db = Database()
repo = HandRepository(db)

# --- Tabs using sac ---
selected_tab = sac.tabs([
    sac.TabsItem(label="手牌列表", icon="suit-spade"),
    sac.TabsItem(label="导入会话", icon="folder2-open"),
], color="green")

# --- Tab 1: Hands ---
if selected_tab == "手牌列表":
    sessions = repo.get_sessions()
    session_options = {"全部": None}
    for s in sessions:
        label = f"{s['filename']} ({s['hand_count']} hands, {s['id']})"
        session_options[label] = s["id"]

    selected = st.selectbox("选择会话", options=list(session_options.keys()),
                            key="hands_session")
    session_id = session_options[selected]

    hands = repo.get_all_hands(session_id=session_id)

    if not hands:
        st.warning("未找到手牌数据。请先导入日志文件。")
        st.stop()

    st.caption(f"共 {len(hands)} 手牌")

    # Build hands table
    rows = []
    for h in hands:
        pos = h.hero_position.value if h.hero_position else ""
        cards = h.hero_cards_str or "-"
        board = h.board_str or "-"
        result = ""
        if h.hero_won:
            won_amt = h.winners.get(h.hero_seat, 0)
            result = f"+${won_amt:.2f}"
        elif h.winners:
            result = "Lost"

        rows.append({
            "Hand ID": h.hand_id,
            "位置": pos,
            "手牌": cards,
            "公共牌": board,
            "底池": round(h.pot_total, 2),
            "结果": result,
        })

    df = pd.DataFrame(rows)

    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(sortable=True, filterable=True, resizable=True)
    gb.configure_selection("single", use_checkbox=False)
    gb.configure_column("Hand ID", width=90, pinned="left")
    gb.configure_column("底池", type=["numericColumn"], width=90)
    grid_opts = gb.build()

    grid_response = AgGrid(
        df,
        gridOptions=grid_opts,
        theme="alpine-dark",
        height=420,
        fit_columns_on_grid_load=True,
        key="hands_grid",
    )

    # Hand detail via row selection
    sac.divider(label="手牌详情", icon="card-text", color="green")

    selected_rows = grid_response.get("selected_rows", None)
    selected_hand = None

    if selected_rows is not None and len(selected_rows) > 0:
        sel_row = selected_rows.iloc[0] if hasattr(selected_rows, 'iloc') else selected_rows[0]
        sel_id = sel_row["Hand ID"]
        selected_hand = next((h for h in hands if h.hand_id == sel_id), None)
    else:
        # Fallback: show first hand or let user pick
        hand_ids = [h.hand_id for h in hands]
        if hand_ids:
            selected_id = st.selectbox("选择手牌 ID（或点击上方表格行）", options=hand_ids,
                                       key="hand_id_select")
            selected_hand = next((h for h in hands if h.hand_id == selected_id), None)

    if selected_hand:
        fmt = TextFormatter()
        ui.card(
            title=f"Hand #{selected_hand.hand_id}",
            content=fmt.format_hand(selected_hand),
            key="hand_detail_card",
        ).render()

    # --- Chart 1: Position Win/Loss distribution (Stacked bar) ---
    sac.divider(label="位置胜负分布", icon="bar-chart-steps", color="green")

    pos_wins = {}
    pos_losses = {}
    for h in hands:
        pos = h.hero_position.value if h.hero_position else "Unknown"
        if pos not in pos_wins:
            pos_wins[pos] = 0
            pos_losses[pos] = 0
        if h.hero_won:
            pos_wins[pos] += 1
        elif h.winners:
            pos_losses[pos] += 1

    all_positions = sorted(set(list(pos_wins.keys()) + list(pos_losses.keys())))
    if all_positions:
        fig_pos = go.Figure()
        fig_pos.add_trace(go.Bar(
            name="Win",
            x=all_positions,
            y=[pos_wins.get(p, 0) for p in all_positions],
            marker_color=COLORS["accent_green"],
        ))
        fig_pos.add_trace(go.Bar(
            name="Loss",
            x=all_positions,
            y=[pos_losses.get(p, 0) for p in all_positions],
            marker_color=COLORS["accent_red"],
        ))
        fig_pos.update_layout(
            **PLOTLY_LAYOUT,
            barmode="stack",
            height=380,
            title="各位置胜负分布",
            xaxis_title="位置",
            yaxis_title="手数",
        )
        st.plotly_chart(fig_pos, width="stretch")

    # --- Chart 2: Pot size distribution (Histogram) ---
    sac.divider(label="底池大小分布", icon="coin", color="green")

    pot_totals = [h.pot_total for h in hands if h.pot_total > 0]
    if pot_totals:
        fig_hist = go.Figure(data=[go.Histogram(
            x=pot_totals,
            nbinsx=20,
            marker_color=COLORS["accent_gold"],
            marker_line=dict(color=COLORS["card_border"], width=1),
        )])
        fig_hist.update_layout(
            **PLOTLY_LAYOUT,
            height=380,
            title="底池大小频次分布",
            xaxis_title="底池大小 ($)",
            yaxis_title="频次",
        )
        st.plotly_chart(fig_hist, width="stretch")

# --- Tab 2: Sessions ---
elif selected_tab == "导入会话":
    sessions = repo.get_sessions()

    if not sessions:
        st.info("暂无导入记录。在首页上传日志文件开始使用。")
    else:
        rows = []
        for s in sessions:
            rows.append({
                "会话 ID": s.get("id", ""),
                "文件名": s.get("filename", ""),
                "手数": s.get("hand_count", 0),
                "导入时间": s.get("import_date", ""),
                "备注": s.get("notes", "") or "",
            })

        df = pd.DataFrame(rows)

        gb = GridOptionsBuilder.from_dataframe(df)
        gb.configure_default_column(sortable=True, filterable=True, resizable=True)
        gb.configure_column("手数", type=["numericColumn"], width=80)
        grid_opts = gb.build()

        AgGrid(
            df,
            gridOptions=grid_opts,
            theme="alpine-dark",
            height=320,
            fit_columns_on_grid_load=True,
            key="sessions_grid",
        )
