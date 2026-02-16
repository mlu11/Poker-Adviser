"""AI Analysis page — Claude-powered strategy analysis and hand review."""

import streamlit as st
import streamlit_shadcn_ui as ui
import streamlit_antd_components as sac

from poker_advisor.storage import Database, HandRepository
from poker_advisor import config as _cfg

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from theme import inject_theme
from navigation import render_sidebar_nav

st.set_page_config(page_title="复盘中心", page_icon="📋", layout="wide")
inject_theme()
render_sidebar_nav("pages/3_ai_analysis")

st.title("📋 复盘中心")

_api_key = _cfg.DOUBAO_API_KEY if _cfg.AI_PROVIDER == "doubao" else _cfg.DEEPSEEK_API_KEY
_env_var = "DOUBAO_API_KEY" if _cfg.AI_PROVIDER == "doubao" else "DEEPSEEK_API_KEY"
if not _api_key:
    st.error(f"{_env_var} 未设置。请设置环境变量后重启应用。")
    st.code(f"export {_env_var}=your-key-here", language="bash")
    st.stop()

db = Database()
repo = HandRepository(db)

sessions = repo.get_sessions()
session_options = {"全部": None}
for s in sessions:
    label = f"{s['filename']} ({s['hand_count']} hands, {s['id']})"
    session_options[label] = s["id"]

# --- Tabs using sac ---
selected_tab = sac.tabs([
    sac.TabsItem(label="批量复盘", icon="lightning"),
    sac.TabsItem(label="单局复盘", icon="suit-spade"),
    sac.TabsItem(label="全局策略", icon="graph-up"),
], color="green")

# --- Tab 1: Batch Review ---
if selected_tab == "批量复盘":
    selected = st.selectbox("选择会话", options=list(session_options.keys()),
                            key="batch_session")
    session_id = session_options[selected]

    col1, col2, col3 = st.columns(3)
    with col1:
        top_n = st.number_input("Top N 高 EV 损失手牌", min_value=3, max_value=20, value=5, step=1)
    with col2:
        use_cache = st.toggle("使用缓存（如果有）", value=True)
    with col3:
        deep = st.toggle("深度分析", value=False)

    if st.button("开始批量复盘", type="primary", key="run_batch"):
        if session_id is None:
            st.warning("请选择一个具体的会话。")
        else:
            hands = repo.get_all_hands(session_id=session_id)
            if not hands:
                st.warning("未找到手牌数据。")
            else:
                step_placeholder = st.empty()

                def update_steps(current):
                    with step_placeholder.container():
                        sac.steps(
                            items=[
                                sac.StepsItem(title="加载数据"),
                                sac.StepsItem(title="筛选 Top EV 损失"),
                                sac.StepsItem(title="AI 分析"),
                                sac.StepsItem(title="生成报告"),
                            ],
                            index=current,
                            color="green",
                        )

                update_steps(0)
                progress_text = st.empty()
                with st.spinner(f"正在分析..."):
                    from poker_advisor.analysis.batch_reviewer import BatchReviewer
                    from poker_advisor.ai.analyzer import StrategyAnalyzer
                    try:
                        update_steps(1)
                        analyzer = StrategyAnalyzer()
                        reviewer = BatchReviewer(repo, analyzer)
                        hands_batch = repo.get_all_hands(session_id=session_id)

                        def on_progress(current: int, total: int, hand_id: int):
                            progress_text.text(f"正在分析第 {current}/{total} 手牌...")

                        result = reviewer.review_top_ev_loss(
                            hands_batch,
                            top_n=int(top_n),
                            deep_ai=deep,
                            use_cache=use_cache,
                            session_id=session_id,
                            progress_callback=on_progress
                        )
                        update_steps(2)
                        report = reviewer.format_report(result)
                        update_steps(3)
                        st.markdown(report)
                    except Exception as e:
                        st.error(f"分析失败: {e}")

# --- Tab 2: Single review ---
elif selected_tab == "单局复盘":
    selected = st.selectbox("选择会话", options=list(session_options.keys()),
                            key="analysis_session")
    session_id = session_options[selected]

    # Model selector — segmented control
    model_choice = sac.segmented(
        items=[
            sac.SegmentedItem(label="标准 (Sonnet)"),
            sac.SegmentedItem(label="深度 (Opus)"),
        ],
        color="green",
        key="analysis_model",
    )
    deep = model_choice == "深度 (Opus)"

    if st.button("开始分析", type="primary", key="run_analysis"):
        hands = repo.get_all_hands(session_id=session_id)
        if not hands:
            st.warning("未找到手牌数据。")
        else:
            # Progress steps
            step_idx = 0
            step_placeholder = st.empty()

            def update_steps(current):
                with step_placeholder.container():
                    sac.steps(
                        items=[
                            sac.StepsItem(title="加载数据", description="读取手牌记录"),
                            sac.StepsItem(title="计算统计", description="生成指标"),
                            sac.StepsItem(title="AI 分析", description="策略评估"),
                            sac.StepsItem(title="完成", description="展示结果"),
                        ],
                        index=current,
                        color="green",
                    )

            update_steps(0)

            with st.spinner(f"正在分析 {len(hands)} 手牌..."):
                from poker_advisor.ai.analyzer import StrategyAnalyzer
                try:
                    update_steps(1)
                    update_steps(2)
                    analyzer = StrategyAnalyzer()
                    result = analyzer.analyze_full(hands, deep=deep)
                    update_steps(3)
                    st.markdown(result)
                except Exception as e:
                    st.error(f"分析失败: {e}")

# --- Tab 3: Global Strategy ---
elif selected_tab == "全局策略":
    selected3 = st.selectbox("选择会话", options=list(session_options.keys()),
                            key="global_session")
    session_id3 = session_options[selected3]

    # Model selector — segmented control
    model_choice3 = sac.segmented(
        items=[
            sac.SegmentedItem(label="标准分析"),
            sac.SegmentedItem(label="深度分析"),
        ],
        color="green",
        key="global_model",
    )
    deep3 = model_choice3 == "深度分析"

    if st.button("开始分析", type="primary", key="run_global"):
        hands = repo.get_all_hands(session_id=session_id3)
        if not hands:
            st.warning("未找到手牌数据。")
        else:
            # Progress steps
            step_idx = 0
            step_placeholder3 = st.empty()

            def update_steps3(current):
                with step_placeholder3.container():
                    sac.steps(
                        items=[
                            sac.StepsItem(title="加载数据", description="读取手牌记录"),
                            sac.StepsItem(title="计算统计", description="生成指标"),
                            sac.StepsItem(title="AI 分析", description="策略评估"),
                            sac.StepsItem(title="完成", description="展示结果"),
                        ],
                        index=current,
                        color="green",
                    )

            update_steps3(0)

            with st.spinner(f"正在分析 {len(hands)} 手牌..."):
                from poker_advisor.ai.analyzer import StrategyAnalyzer
                try:
                    update_steps3(1)
                    st.info("Step 1: 风格分类（快速分析）...")
                    analyzer = StrategyAnalyzer()
                    result = analyzer.analyze_full(hands, deep=deep3)
                    st.success("Step 2: 深度分析完成！")
                    update_steps3(3)
                    st.markdown(result)
                except Exception as e:
                    st.error(f"分析失败: {e}")

# --- Tab 2: Hand review ---
elif selected_tab == "单局复盘":
    selected2 = st.selectbox("选择会话", options=list(session_options.keys()),
                             key="review_session")
    session_id2 = session_options[selected2]

    hands = repo.get_all_hands(session_id=session_id2)
    if not hands:
        st.warning("未找到手牌数据。")
        st.stop()

    # Hand selector
    hand_options = {}
    for h in hands:
        pos = h.hero_position.value if h.hero_position else "?"
        cards = h.hero_cards_str or "-"
        result = "Win" if h.hero_won else "Loss" if h.winners else ""
        label = f"#{h.hand_id} | {pos} | {cards} | ${h.pot_total:.2f} {result}"
        hand_options[label] = h

    selected_hand_label = st.selectbox("选择手牌", options=list(hand_options.keys()))
    hand = hand_options[selected_hand_label]

    # Display hand in a card
    from poker_advisor.formatters.text import TextFormatter
    fmt = TextFormatter()
    ui.card(
        title="手牌详情",
        content=fmt.format_hand(hand),
        key="hand_detail_card",
    ).render()

    # Model selector
    model_choice2 = sac.segmented(
        items=[
            sac.SegmentedItem(label="标准分析"),
            sac.SegmentedItem(label="深度分析"),
        ],
        color="green",
        key="review_model",
    )
    deep2 = model_choice2 == "深度分析"

    if st.button("AI 复盘", type="primary", key="run_review"):
        step_placeholder2 = st.empty()

        def update_steps2(current):
            with step_placeholder2.container():
                sac.steps(
                    items=[
                        sac.StepsItem(title="读取手牌"),
                        sac.StepsItem(title="AI 分析"),
                        sac.StepsItem(title="完成"),
                    ],
                    index=current,
                    color="green",
                )

        update_steps2(0)
        with st.spinner("正在分析..."):
            from poker_advisor.ai.analyzer import StrategyAnalyzer
            try:
                update_steps2(1)
                analyzer = StrategyAnalyzer()
                result = analyzer.review_hand(hand, hands=hands, deep=deep2)
                update_steps2(2)
                st.markdown(result)
            except Exception as e:
                st.error(f"分析失败: {e}")
