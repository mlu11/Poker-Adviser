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

                        # 新增：显示高EV损失手牌列表（可跳转至单局复盘）
                        st.subheader("📊 高EV损失手牌列表")

                        # 折叠/展开控件
                        with st.expander(f"Top 5 高EV损失手牌（点击可深入复盘）", expanded=True):
                            for i, (hand, est_loss) in enumerate(result.top_ev_loss_hands[:5]):
                                pos = hand.hero_position.value if hand.hero_position else "?"
                                cards = hand.hero_cards_str or "-"
                                result_str = "Win" if hand.hero_won else "Loss" if hand.winners else ""

                                col1, col2, col3, col4 = st.columns([1, 3, 2, 1])
                                with col1:
                                    st.write(f"#{i+1}")
                                with col2:
                                    st.write(f"#{hand.hand_id} | {pos} | {cards} | {result_str}")
                                with col3:
                                    st.write(f"<span style='color:red;'>EV损失: ${est_loss:.2f}</span>", unsafe_allow_html=True)
                                with col4:
                                    if st.button("复盘", key=f"batch_review_{hand.hand_id}"):
                                        st.session_state['selected_hand_for_review'] = hand
                                        st.session_state['batch_review_session'] = session_id
                                        st.rerun()

                        update_steps(3)
                        st.markdown(report)
                    except Exception as e:
                        st.error(f"分析失败: {e}")

# --- Tab 2: Global Strategy ---
elif selected_tab == "全局策略":
    st.info("全局策略分析适用于评估整体策略风格、识别核心漏洞，建议首次复盘优先使用")

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

# --- Tab 3: Hand review ---
elif selected_tab == "单局复盘":
    # 页面顶部指引
    st.info("单局复盘适用于深入拆解具体手牌决策、学习正确打法，建议批量复盘后针对性使用")

    selected2 = st.selectbox("选择会话", options=list(session_options.keys()),
                             key="review_session")
    session_id2 = session_options[selected2]

    hands = repo.get_all_hands(session_id=session_id2)
    if not hands:
        st.warning("未找到手牌数据。")
        st.stop()

    # 筛选控件区域
    st.subheader("🔍 精准定位手牌")
    col1, col2 = st.columns([2, 1])
    with col1:
        search_query = st.text_input("搜索手牌ID或对局时间", placeholder="输入手牌ID或时间")
    with col2:
        ev_loss_range = st.selectbox("EV损失范围", ["全部", "<-5 BB", "-5 to -3 BB", "-3 to -1 BB", "> -1 BB"])

    # 位置筛选
    positions = ["全部", "UTG", "HJ", "CO", "BTN", "SB", "BB"]
    selected_position = st.selectbox("位置", positions)

    # 牌型筛选
    hand_types = ["全部", "高牌", "一对", "两对", "三条", "顺子", "同花", "葫芦", "四条", "同花顺", "皇家同花顺"]
    selected_hand_type = st.selectbox("牌型", hand_types)

    # 应用筛选按钮
    apply_filters = st.button("应用筛选")

    # 智能推荐手牌区域
    st.subheader("🌟 智能推荐复盘手牌")
    recommended_hands = []
    for h in hands:
        # 简单的智能推荐逻辑：筛选EV损失较高的手牌
        est_loss = h.pot_total * (0.5 if not h.hero_won else 0)
        if est_loss > 10:
            recommended_hands.append(h)

    if recommended_hands:
        recommended_hands = sorted(recommended_hands, key=lambda x: (not x.hero_won, -x.pot_total))[:5]

        # 卡片式布局
        cols = st.columns(5)
        for i, h in enumerate(recommended_hands):
            with cols[i]:
                with st.container():
                    pos = h.hero_position.value if h.hero_position else "?"
                    cards = h.hero_cards_str or "-"
                    result = "Win" if h.hero_won else "Loss" if h.winners else ""
                    est_loss = h.pot_total * (0.5 if not h.hero_won else 0)

                    st.markdown(f"<div style='border: 1px solid #e0e0e0; border-radius: 8px; padding: 10px; height: 100%;'>"
                                f"<strong>#{h.hand_id}</strong><br>"
                                f"{pos} | {cards}<br>"
                                f"<span style='color: {'red' if not h.hero_won else 'green'};'>{result}</span><br>"
                                f"EV损失: ${est_loss:.2f}"
                                f"</div>", unsafe_allow_html=True)

                    if st.button("复盘", key=f"recommended_review_{i}_{h.hand_id}"):
                        st.session_state['selected_hand_for_review'] = h
                        st.rerun()
    else:
        st.info("未找到高EV损失的手牌")

    # 文档内手牌列表区域
    st.subheader("📋 文档内手牌列表")

    filtered_hands = hands

    # 应用筛选条件
    if apply_filters:
        if search_query:
            filtered_hands = [h for h in filtered_hands if search_query in str(h.hand_id)]

        if selected_position != "全部":
            filtered_hands = [h for h in filtered_hands if h.hero_position and h.hero_position.value == selected_position]

        # EV损失范围筛选
        if ev_loss_range != "全部":
            temp_hands = []
            for h in filtered_hands:
                # 计算EV损失（简化：基于底池大小和是否获胜）
                est_loss = h.pot_total * (0.5 if not h.hero_won else 0)
                # 将美元转换为BB（假设大盲为20）
                est_loss_bb = est_loss / 20

                if ev_loss_range == "<-5 BB" and est_loss_bb < -5:
                    temp_hands.append(h)
                elif ev_loss_range == "-5 to -3 BB" and -5 <= est_loss_bb < -3:
                    temp_hands.append(h)
                elif ev_loss_range == "-3 to -1 BB" and -3 <= est_loss_bb < -1:
                    temp_hands.append(h)
                elif ev_loss_range == "> -1 BB" and est_loss_bb >= -1:
                    temp_hands.append(h)
            filtered_hands = temp_hands

        # 牌型筛选
        if selected_hand_type != "全部":
            temp_hands = []
            for h in filtered_hands:
                if h.hand_type == selected_hand_type:
                    temp_hands.append(h)
            filtered_hands = temp_hands

        # 存储筛选结果到session state，以便下次重新运行时保留
        st.session_state['filtered_hands'] = filtered_hands
        st.success(f"筛选完成！共找到 {len(filtered_hands)} 手牌")
    else:
        # 如果没有点击应用筛选按钮，显示全部手牌
        # 但如果之前已经筛选过，显示上次的结果
        if 'filtered_hands' in st.session_state:
            filtered_hands = st.session_state['filtered_hands']

    # 显示手牌列表
    for i, h in enumerate(filtered_hands):
        pos = h.hero_position.value if h.hero_position else "?"
        cards = h.hero_cards_str or "-"
        result = "Win" if h.hero_won else "Loss" if h.winners else ""
        label = f"#{h.hand_id} | {pos} | {cards} | ${h.pot_total:.2f} {result}"

        if st.button(label, key=f"select_{i}_{h.hand_id}"):
            st.session_state['selected_hand_for_review'] = h
            st.rerun()

    # 选中手牌的详细分析
    if 'selected_hand_for_review' in st.session_state:
        hand = st.session_state['selected_hand_for_review']

        st.markdown("---")
        st.subheader(f"🎯 手牌分析: #{hand.hand_id}")

        # Display hand in a card
        from poker_advisor.formatters.text import TextFormatter
        fmt = TextFormatter()
        ui.card(
            title="手牌详情",
            content=fmt.format_hand(hand),
            key="hand_detail_card",
        ).render()

        # 深度思考模式
        deep_thinking_mode = st.toggle("深度思考模式", value=False, key="deep_thinking_mode")

        # Model selector
        model_choice2 = sac.segmented(
            items=[
                sac.SegmentedItem(label="标准分析"),
                sac.SegmentedItem(label="深度分析"),
            ],
            color="green",
            key="review_model",
        )
        deep2 = model_choice2 == "深度分析" or deep_thinking_mode

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
