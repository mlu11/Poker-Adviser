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

st.set_page_config(page_title="AI 分析", page_icon="🤖", layout="wide")
inject_theme()
render_sidebar_nav("pages/3_ai_analysis")

st.title("🤖 AI 分析")

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
    sac.TabsItem(label="全局策略分析", icon="graph-up"),
    sac.TabsItem(label="单手牌复盘", icon="suit-spade"),
], color="green")

# --- Tab 1: Full analysis ---
if selected_tab == "全局策略分析":
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

# --- Tab 2: Hand review ---
elif selected_tab == "单手牌复盘":
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
            sac.SegmentedItem(label="标准 (Sonnet)"),
            sac.SegmentedItem(label="深度 (Opus)"),
        ],
        color="green",
        key="review_model",
    )
    deep2 = model_choice2 == "深度 (Opus)"

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
