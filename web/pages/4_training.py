"""Training page — interactive training with AI evaluation."""

import streamlit as st
import streamlit_shadcn_ui as ui
import streamlit_antd_components as sac
import plotly.graph_objects as go

from poker_advisor.storage import Database, HandRepository
from poker_advisor import config as _cfg

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from theme import inject_theme, PLOTLY_LAYOUT, COLORS
from navigation import render_sidebar_nav

st.set_page_config(page_title="训练中心", page_icon="🎯", layout="wide")
inject_theme()
render_sidebar_nav("pages/4_training")

st.title("🎯 训练中心")

_api_key = _cfg.DOUBAO_API_KEY if _cfg.AI_PROVIDER == "doubao" else _cfg.DEEPSEEK_API_KEY
_env_var = "DOUBAO_API_KEY" if _cfg.AI_PROVIDER == "doubao" else "DEEPSEEK_API_KEY"
if not _api_key:
    st.error(f"{_env_var} 未设置。请设置环境变量后重启应用。")
    st.code(f"export {_env_var}=your-key-here", language="bash")
    st.stop()

db = Database()
repo = HandRepository(db)

# Initialize session state
if "scenarios" not in st.session_state:
    st.session_state.scenarios = []
    st.session_state.current_idx = 0
    st.session_state.scores = []
    st.session_state.training_active = False

# --- Setup ---
if not st.session_state.training_active:
    st.subheader("训练设置")

    sessions = repo.get_sessions()
    session_options = {"全部": None}
    for s in sessions:
        label = f"{s['filename']} ({s['hand_count']} hands, {s['id']})"
        session_options[label] = s["id"]

    selected = st.selectbox("选择会话", options=list(session_options.keys()))
    session_id = session_options[selected]

    col1, col2 = st.columns(2)
    with col1:
        count = st.slider("场景数量", min_value=1, max_value=20, value=5)
    with col2:
        # Focus area — segmented selector
        focus_options = ["全部", "preflop", "flop", "turn", "river", "cbet"]
        focus = sac.segmented(
            items=[sac.SegmentedItem(label=f) for f in focus_options],
            color="green",
            key="focus_seg",
        )

    if st.button("开始训练", type="primary"):
        from poker_advisor.training.session import TrainingSession
        training = TrainingSession(repo)
        focus_val = None if focus == "全部" else focus
        scenarios = training.prepare(session_id=session_id, count=count,
                                     focus=focus_val)

        if not scenarios:
            st.warning("未找到合适的训练场景。请导入更多手牌。")
        else:
            st.session_state.scenarios = scenarios
            st.session_state.current_idx = 0
            st.session_state.scores = []
            st.session_state.training_active = True
            st.session_state.focus = focus_val or ""
            st.rerun()

    # Show training history
    sac.divider(label="训练历史", icon="clock-history", color="green")
    results = repo.get_training_results(limit=20)
    if results:
        import pandas as pd
        from st_aggrid import AgGrid, GridOptionsBuilder

        df = pd.DataFrame(results)
        display_cols = ["session_date", "scenario_type", "user_action",
                        "optimal_action", "score"]
        available = [c for c in display_cols if c in df.columns]
        if available:
            df_display = df[available].copy()
            df_display.columns = ["时间", "场景类型", "你的行动", "最优行动", "评分"][:len(available)]

            gb = GridOptionsBuilder.from_dataframe(df_display)
            gb.configure_default_column(sortable=True, filterable=True, resizable=True)
            if "评分" in df_display.columns:
                gb.configure_column("评分", type=["numericColumn"], width=80)
            grid_opts = gb.build()

            AgGrid(
                df_display,
                gridOptions=grid_opts,
                theme="alpine-dark",
                height=320,
                fit_columns_on_grid_load=True,
                key="training_grid",
            )

        if "score" in df.columns:
            avg = df["score"].mean()
            ui.metric_card(title="历史平均分", content=f"{avg:.1f}/10",
                           description="所有训练评分", key="m_avg_score")

        # --- Chart 1: Training score trend (Line + markers + rolling avg) ---
        if "score" in df.columns and "session_date" in df.columns:
            sac.divider(label="评分趋势", icon="graph-up", color="green")

            df_sorted = df.sort_values("session_date")
            scores = df_sorted["score"].tolist()
            dates = df_sorted["session_date"].tolist()

            # Rolling average (window=3)
            rolling = []
            for i in range(len(scores)):
                window = scores[max(0, i - 2):i + 1]
                rolling.append(sum(window) / len(window))

            fig_trend = go.Figure()
            fig_trend.add_trace(go.Scatter(
                x=dates, y=scores,
                mode="lines+markers",
                name="评分",
                line=dict(color=COLORS["accent_green"]),
                marker=dict(size=8),
            ))
            fig_trend.add_trace(go.Scatter(
                x=dates, y=rolling,
                mode="lines",
                name="3期滚动平均",
                line=dict(color=COLORS["accent_gold"], dash="dash", width=2),
            ))
            fig_trend.update_layout(
                **PLOTLY_LAYOUT,
                height=350,
                title="训练评分趋势",
                xaxis_title="时间",
                yaxis_title="评分",
                yaxis=dict(range=[0, 10.5], gridcolor=COLORS["card_border"],
                           zerolinecolor=COLORS["card_border"]),
            )
            st.plotly_chart(fig_trend, use_container_width=True)

        # --- Chart 2: Scenario type distribution (Bar chart) ---
        if "scenario_type" in df.columns:
            sac.divider(label="场景类型分布", icon="tags", color="green")

            type_counts = df["scenario_type"].value_counts()
            fig_types = go.Figure(data=[go.Bar(
                x=type_counts.index.tolist(),
                y=type_counts.values.tolist(),
                marker_color=COLORS["accent_blue"],
            )])
            fig_types.update_layout(
                **PLOTLY_LAYOUT,
                height=350,
                title="各场景类型训练次数",
                xaxis_title="场景类型",
                yaxis_title="次数",
            )
            st.plotly_chart(fig_types, use_container_width=True)
    else:
        st.info("暂无训练记录。开始你的第一次训练吧！")

    st.stop()

# --- Active training ---
scenarios = st.session_state.scenarios
idx = st.session_state.current_idx

if idx >= len(scenarios):
    # Training complete
    st.subheader("训练完成！")
    scores = st.session_state.scores
    if scores:
        avg = sum(scores) / len(scores)
        c1, c2, c3 = st.columns(3)
        with c1:
            ui.metric_card(title="完成场景",
                           content=f"{len(scores)}/{len(scenarios)}",
                           description="训练进度", key="done_count")
        with c2:
            ui.metric_card(title="平均评分", content=f"{avg:.1f}/10",
                           description="本次训练", key="done_avg")
        with c3:
            ui.metric_card(title="最高分", content=f"{max(scores)}/10",
                           description="最佳表现", key="done_max")

    if st.button("重新开始"):
        st.session_state.training_active = False
        st.rerun()
    st.stop()

scenario = scenarios[idx]

# Progress bar
st.progress((idx) / len(scenarios),
            text=f"场景 {idx + 1}/{len(scenarios)} — {scenario.scenario_type}")

# Show scenario
st.markdown(f"**场景类型:** `{scenario.scenario_type}`")
st.text(scenario.description)

# Action selection — sac buttons
st.subheader("你的行动")

action_items = [sac.ButtonsItem(label=a) for a in scenario.available_actions]
action_items.append(sac.ButtonsItem(label="自定义行动", icon="pencil"))

action_choice = sac.buttons(
    items=action_items,
    align="start",
    color="green",
    key=f"action_btn_{idx}",
)

custom_action = ""
if action_choice == "自定义行动":
    custom_action = st.text_input("输入你的行动", key=f"custom_{idx}")

reasoning = st.text_area("理由（可选）", key=f"reason_{idx}",
                          placeholder="简述你选择这个行动的理由...")

user_action = custom_action if action_choice == "自定义行动" else action_choice

col_submit, col_skip = st.columns([1, 1])

with col_submit:
    if st.button("提交", type="primary", disabled=not user_action):
        with st.spinner("AI 正在评估你的决策..."):
            from poker_advisor.training.session import TrainingSession
            training = TrainingSession(repo)
            try:
                evaluation = training.evaluate(scenario, user_action, reasoning)

                # Show result — rating + metric card
                sac.rate(value=evaluation.score, count=10, color="gold",
                         key=f"rate_{idx}")
                ui.metric_card(title="评分", content=f"{evaluation.score}/10",
                               description="AI 评估", key=f"score_card_{idx}")
                st.markdown(evaluation.feedback)

                # Save result
                try:
                    training.save_result(scenario, user_action, evaluation,
                                         focus_area=st.session_state.focus)
                except Exception:
                    pass

                st.session_state.scores.append(evaluation.score)
                st.session_state.current_idx += 1

                st.button("下一个场景 →", on_click=lambda: None, key="next")
            except Exception as e:
                st.error(f"AI 评估失败: {e}")

with col_skip:
    if st.button("跳过"):
        st.session_state.current_idx += 1
        st.rerun()

# Quit button in sidebar
with st.sidebar:
    if st.button("结束训练"):
        st.session_state.training_active = False
        st.rerun()
