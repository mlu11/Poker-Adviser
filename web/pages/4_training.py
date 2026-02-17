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

# --- Tabs using sac ---
selected_tab = sac.tabs([
    sac.TabsItem(label="我的训练方案", icon="clipboard-check"),
    sac.TabsItem(label="专项训练", icon="bullseye"),
    sac.TabsItem(label="训练记录", icon="clock-history"),
], color="green")

# --- Tab 1: 我的训练方案 ---
if selected_tab == "我的训练方案":
    st.subheader("📋 个性化训练方案")

    sessions = repo.get_sessions()
    session_options = {"请选择会话": None}
    for s in sessions:
        label = f"{s['filename']} ({s['hand_count']} hands, {s['id']})"
        session_options[label] = s["id"]

    selected = st.selectbox("选择会话以生成训练方案", options=list(session_options.keys()))
    session_id = session_options[selected]

    if st.button("生成训练方案", type="primary"):
        if session_id is None:
            st.warning("请先选择一个会话。")
        else:
            with st.spinner("正在分析数据并生成训练方案..."):
                try:
                    from poker_advisor.training.plan_generator import TrainingPlanGenerator
                    from poker_advisor.analysis.calculator import StatsCalculator
                    from poker_advisor.analysis.leak_detector import LeakDetector

                    hands = repo.get_all_hands(session_id=session_id)
                    if not hands:
                        st.warning("未找到手牌数据。")
                    else:
                        calc = StatsCalculator()
                        stats = calc.calculate(hands)
                        detector = LeakDetector()
                        leaks = detector.detect(stats)

                        generator = TrainingPlanGenerator(repo)
                        plan = generator.generate_from_leaks(leaks, stats, session_id=session_id)

                        # Display the plan
                        st.markdown("---")
                        st.subheader(f"📊 {plan.plan_name}")
                        st.caption(f"生成时间: {plan.generated_at}")

                        ui.metric_card(title="目标周期", content=f"{plan.recommended_duration_days} 天",
                                      description="建议训练周期", key="plan_duration")
                        ui.metric_card(title="每日时长", content=f"{plan.daily_minutes} 分钟",
                                      description="建议训练时长", key="plan_minutes")

                        sac.divider(label="训练模块", icon="grid", color="green")

                        for i, module in enumerate(plan.modules):
                            with st.expander(f"{i+1}. {module.name}", expanded=True):
                                st.markdown(f"**目标:** {module.description}")
                                st.markdown(f"**难度:** {'⭐' * module.difficulty_level}")
                                st.markdown(f"**预计练习:** {module.estimated_hands} 手牌")

                                if module.focus_areas:
                                    st.markdown("**重点关注:**")
                                    for area in module.focus_areas:
                                        st.markdown(f"- {area}")

                        if plan.notes:
                            sac.divider(label="备注", icon="info-circle", color="green")
                            for note in plan.notes:
                                st.info(note)

                        # Save button
                        if st.button("保存此方案"):
                            try:
                                generator.save_plan(plan)
                                st.success("训练方案已保存！")
                            except Exception as e:
                                st.error(f"保存失败: {e}")

                except ImportError as e:
                    st.warning(f"训练方案生成模块未完全实现: {e}")
                    st.info("此功能正在开发中，敬请期待！")
                except Exception as e:
                    st.error(f"生成训练方案失败: {e}")

    # Show existing plans
    sac.divider(label="已保存的训练方案", icon="history", color="green")
    try:
        from poker_advisor.training.plan_generator import TrainingPlanGenerator
        generator = TrainingPlanGenerator(repo)
        plans = generator.get_all_plans(limit=10)

        if plans:
            for plan in plans:
                with st.container():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.markdown(f"**{plan.plan_name}**")
                        st.caption(f"{plan.generated_at} | {len(plan.modules)} 个模块")
                    with col2:
                        st.metric("周期", f"{plan.recommended_duration_days}天")
                    with col3:
                        if st.button("查看", key=f"view_plan_{plan.plan_id}"):
                            st.session_state['viewing_plan'] = plan
                            st.rerun()
                    sac.divider()
        else:
            st.info("暂无保存的训练方案。")
    except Exception:
        st.info("训练方案列表功能加载中...")

# --- Tab 2: 专项训练 ---
elif selected_tab == "专项训练":
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

# --- Tab 3: 训练记录 ---
elif selected_tab == "训练记录":
    st.subheader("📊 训练历史")

    # Show training history
    results = repo.get_training_results(limit=50)
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
                height=400,
                fit_columns_on_grid_load=True,
                key="training_grid",
            )

        if "score" in df.columns:
            avg = df["score"].mean()
            c1, c2, c3 = st.columns(3)
            with c1:
                ui.metric_card(title="历史平均分", content=f"{avg:.1f}/10",
                              description="所有训练评分", key="m_avg_score")
            with c2:
                ui.metric_card(title="总训练次数", content=f"{len(df)}",
                              description="完成场景数", key="m_total")
            with c3:
                ui.metric_card(title="最高分", content=f"{df['score'].max()}/10",
                              description="最佳表现", key="m_max_score")

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
            st.plotly_chart(fig_trend, width="stretch")

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
            st.plotly_chart(fig_types, width="stretch")

        # ---错题本区域---
        sac.divider(label="错题本", icon="exclamation-triangle", color="green")

        try:
            bookmarks = repo.get_bookmarks(bookmark_type="mistake", limit=20)
            if bookmarks:
                st.info(f"共有 {len(bookmarks)} 道错题收录在错题本中")
                for bm in bookmarks:
                    with st.expander(f"错题 #{bm.get('hand_id', '?')} | {bm.get('error_grade', 'C')}级", expanded=False):
                        st.markdown(f"**笔记:** {bm.get('notes', '-')}")
                        if bm.get('tags'):
                            st.markdown(f"**标签:** {bm.get('tags')}")
            else:
                st.info("错题本为空。训练中得分<5分的手牌会自动加入错题本。")
        except Exception:
            st.info("错题本功能加载中...")

    else:
        st.info("暂无训练记录。开始你的第一次训练吧！")
