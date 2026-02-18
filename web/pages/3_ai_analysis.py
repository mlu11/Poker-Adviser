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

    # --- Helper: inline card chip HTML ---
    def _card_chip(card_str: str) -> str:
        if not card_str or len(card_str) < 2:
            return ""
        rank_part = card_str[:-1]
        suit_char = card_str[-1]
        is_red = suit_char in ("♥", "♦")
        fg = "#e74c3c" if is_red else "#ecf0f1"
        return (
            f'<span style="display:inline-block;background:#2c2c2c;border:1px solid #555;'
            f'border-radius:5px;padding:2px 6px;margin:1px;font-weight:bold;'
            f'color:{fg};font-family:monospace;font-size:0.95em;">'
            f'{rank_part}<span style="font-size:1.1em;">{suit_char}</span></span>'
        )

    def _render_chips(cards) -> str:
        return "".join(_card_chip(str(c)) for c in cards)

    # --- 智能推荐复盘手牌 ---
    st.subheader("🌟 智能推荐复盘手牌")
    recommended_hands = []
    for h in hands:
        est_loss = h.pot_total * (0.5 if not h.hero_won else 0)
        if est_loss > 10:
            recommended_hands.append(h)

    if recommended_hands:
        recommended_hands = sorted(recommended_hands, key=lambda x: (not x.hero_won, -x.pot_total))[:5]

        cols = st.columns(len(recommended_hands))
        for i, h in enumerate(recommended_hands):
            with cols[i]:
                pos = h.hero_position.value if h.hero_position else "?"
                cards_html = _render_chips(h.hero_cards) if h.hero_cards else '<span style="color:#666;">-</span>'
                is_win = h.hero_won
                result_badge = (
                    '<span style="background:#2ecc71;color:#fff;padding:2px 8px;border-radius:10px;font-size:0.8em;">WIN</span>'
                    if is_win else
                    '<span style="background:#e74c3c;color:#fff;padding:2px 8px;border-radius:10px;font-size:0.8em;">LOSS</span>'
                ) if h.winners else ""
                est_loss = h.pot_total * (0.5 if not is_win else 0)
                border_color = "#e74c3c" if not is_win else "#2ecc71"

                st.markdown(
                    f'<div style="border:1px solid #333;border-top:3px solid {border_color};'
                    f'border-radius:8px;padding:12px;background:rgba(255,255,255,0.03);">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">'
                    f'<span style="font-weight:bold;font-size:1.1em;">#{h.hand_id}</span>'
                    f'<span style="background:#333;padding:2px 8px;border-radius:10px;font-size:0.8em;color:#aaa;">{pos}</span>'
                    f'</div>'
                    f'<div style="margin-bottom:8px;">{cards_html}</div>'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                    f'{result_badge}'
                    f'<span style="color:#f39c12;font-size:0.85em;">Pot ${h.pot_total:,.0f}</span>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if st.button("📋 复盘此手牌", key=f"recommended_review_{i}_{h.hand_id}", use_container_width=True):
                    st.session_state['selected_hand_for_review'] = h
                    st.rerun()
    else:
        st.info("未找到高EV损失的手牌")

    # --- 手牌列表 ---
    st.subheader("📋 手牌列表")

    filtered_hands = hands

    # 应用筛选条件
    if apply_filters:
        if search_query:
            filtered_hands = [h for h in filtered_hands if search_query in str(h.hand_id)]
        if selected_position != "全部":
            filtered_hands = [h for h in filtered_hands if h.hero_position and h.hero_position.value == selected_position]
        if ev_loss_range != "全部":
            temp_hands = []
            for h in filtered_hands:
                est_loss = h.pot_total * (0.5 if not h.hero_won else 0)
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
        if selected_hand_type != "全部":
            filtered_hands = [h for h in filtered_hands if h.hand_type == selected_hand_type]
        st.session_state['filtered_hands'] = filtered_hands
        st.success(f"筛选完成！共找到 {len(filtered_hands)} 手牌")
    else:
        if 'filtered_hands' in st.session_state:
            filtered_hands = st.session_state['filtered_hands']

    # Table header
    st.markdown(
        '<div style="display:grid;grid-template-columns:60px 50px 120px 100px 70px 80px;'
        'gap:8px;padding:8px 12px;background:rgba(255,255,255,0.06);border-radius:6px;'
        'font-size:0.85em;color:#888;font-weight:bold;margin-bottom:4px;">'
        '<span>#</span><span>位置</span><span>手牌</span>'
        '<span>底池</span><span>结果</span><span></span></div>',
        unsafe_allow_html=True,
    )

    # Pagination
    PAGE_SIZE = 20
    total_pages = max(1, (len(filtered_hands) + PAGE_SIZE - 1) // PAGE_SIZE)
    if 'hand_list_page' not in st.session_state:
        st.session_state['hand_list_page'] = 0
    current_page = st.session_state['hand_list_page']
    page_hands = filtered_hands[current_page * PAGE_SIZE:(current_page + 1) * PAGE_SIZE]

    for i, h in enumerate(page_hands):
        pos = h.hero_position.value if h.hero_position else "?"
        cards_html = _render_chips(h.hero_cards) if h.hero_cards else '<span style="color:#555;">-</span>'
        is_win = h.hero_won
        if h.winners:
            res_html = ('<span style="color:#2ecc71;">Win</span>' if is_win
                        else '<span style="color:#e74c3c;">Loss</span>')
        else:
            res_html = '<span style="color:#666;">-</span>'

        row_bg = "rgba(255,255,255,0.02)" if i % 2 == 0 else "rgba(255,255,255,0.04)"
        st.markdown(
            f'<div style="display:grid;grid-template-columns:60px 50px 120px 100px 70px 80px;'
            f'gap:8px;padding:6px 12px;background:{row_bg};border-radius:4px;'
            f'align-items:center;font-size:0.9em;">'
            f'<span style="font-weight:bold;">#{h.hand_id}</span>'
            f'<span style="color:#aaa;">{pos}</span>'
            f'<span>{cards_html}</span>'
            f'<span style="color:#f1c40f;">${h.pot_total:,.0f}</span>'
            f'{res_html}'
            f'<span></span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button("复盘", key=f"select_{current_page}_{i}_{h.hand_id}", use_container_width=False):
            st.session_state['selected_hand_for_review'] = h
            st.rerun()

    # Pagination controls
    if total_pages > 1:
        p_cols = st.columns([1, 2, 1])
        with p_cols[0]:
            if st.button("◀ 上一页", disabled=(current_page == 0), key="prev_page"):
                st.session_state['hand_list_page'] = current_page - 1
                st.rerun()
        with p_cols[1]:
            st.markdown(
                f'<div style="text-align:center;color:#aaa;padding:8px;">'
                f'第 {current_page + 1}/{total_pages} 页 · 共 {len(filtered_hands)} 手牌</div>',
                unsafe_allow_html=True,
            )
        with p_cols[2]:
            if st.button("下一页 ▶", disabled=(current_page >= total_pages - 1), key="next_page"):
                st.session_state['hand_list_page'] = current_page + 1
                st.rerun()

    # 选中手牌的详细分析
    if 'selected_hand_for_review' in st.session_state:
        hand = st.session_state['selected_hand_for_review']

        st.markdown("---")
        st.subheader(f"🎯 手牌分析: #{hand.hand_id}")

        # --- Structured hand display ---
        from poker_advisor.models.action import Street as _Street

        def _card_html(card_str: str) -> str:
            """Render a single card as styled HTML chip."""
            if not card_str or len(card_str) < 2:
                return ""
            rank_part = card_str[:-1]
            suit_char = card_str[-1]
            is_red = suit_char in ("♥", "♦")
            color = "#e74c3c" if is_red else "#ecf0f1"
            return (
                f'<span style="display:inline-block;background:#2c2c2c;border:1px solid #555;'
                f'border-radius:6px;padding:4px 8px;margin:2px;font-size:1.1em;font-weight:bold;'
                f'color:{color};font-family:monospace;">'
                f'{rank_part}<span style="font-size:1.2em;">{suit_char}</span></span>'
            )

        def _render_cards(cards) -> str:
            return " ".join(_card_html(str(c)) for c in cards)

        # --- Header row ---
        pos_str = hand.hero_position.value if hand.hero_position else "?"
        result_text = "✅ Win" if hand.hero_won else "❌ Loss" if hand.winners else ""
        result_color = "#2ecc71" if hand.hero_won else "#e74c3c"

        st.markdown(
            f'<div style="display:flex;gap:20px;align-items:center;flex-wrap:wrap;'
            f'padding:12px 16px;background:rgba(255,255,255,0.05);border-radius:8px;margin-bottom:12px;">'
            f'<span style="font-size:1.3em;font-weight:bold;">Hand #{hand.hand_id}</span>'
            f'<span style="color:#aaa;">👥 {hand.player_count}P</span>'
            f'<span style="color:#aaa;">💰 ${hand.small_blind:.0f}/${hand.big_blind:.0f}</span>'
            f'<span style="color:#f1c40f;font-weight:bold;">🏆 Pot ${hand.pot_total:,.2f}</span>'
            f'<span style="color:{result_color};font-weight:bold;">{result_text}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # --- Hero + Board row ---
        h_col, b_col = st.columns([1, 2])
        with h_col:
            st.markdown(
                f'<div style="padding:10px 14px;background:rgba(46,204,113,0.1);'
                f'border-left:3px solid #2ecc71;border-radius:4px;">'
                f'<div style="color:#aaa;font-size:0.85em;margin-bottom:4px;">Hero ({pos_str})</div>'
                f'<div>{_render_cards(hand.hero_cards)}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with b_col:
            board_parts = []
            if hand.flop:
                board_parts.append(f'<span style="color:#aaa;font-size:0.85em;">Flop</span> {_render_cards(hand.flop)}')
            if hand.turn:
                board_parts.append(f'<span style="color:#aaa;font-size:0.85em;">Turn</span> {_card_html(str(hand.turn))}')
            if hand.river:
                board_parts.append(f'<span style="color:#aaa;font-size:0.85em;">River</span> {_card_html(str(hand.river))}')
            board_html = '&nbsp;&nbsp;|&nbsp;&nbsp;'.join(board_parts) if board_parts else '<span style="color:#666;">No board</span>'
            st.markdown(
                f'<div style="padding:10px 14px;background:rgba(255,255,255,0.03);'
                f'border-left:3px solid #3498db;border-radius:4px;">'
                f'<div style="color:#aaa;font-size:0.85em;margin-bottom:4px;">Board</div>'
                f'<div>{board_html}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # --- Actions timeline ---
        street_labels = {
            _Street.PREFLOP: ("Preflop", "#9b59b6"),
            _Street.FLOP: ("Flop", "#3498db"),
            _Street.TURN: ("Turn", "#e67e22"),
            _Street.RIVER: ("River", "#e74c3c"),
        }

        action_cols = st.columns(len(hand.streets_seen))
        for idx, street in enumerate(hand.streets_seen):
            street_actions = hand.actions_on_street(street)
            non_blind = [a for a in street_actions
                         if street != _Street.PREFLOP or a.action_type.value != "post_blind"]
            if not non_blind:
                continue
            label, color = street_labels.get(street, (street.value, "#aaa"))
            with action_cols[idx]:
                lines_html = ""
                for a in non_blind:
                    is_hero = (hand.hero_seat is not None and a.seat == hand.hero_seat)
                    name_style = f'font-weight:bold;color:#2ecc71;' if is_hero else 'color:#ccc;'
                    act = a.action_type.value
                    if a.action_type.value in ("fold", "check"):
                        act_text = act + "s"
                        amt_text = ""
                    else:
                        act_text = act + "s"
                        amt_text = f' <span style="color:#f1c40f;">${a.amount:,.2f}</span>'
                    allin = ' <span style="color:#e74c3c;font-size:0.8em;">ALL-IN</span>' if a.is_all_in else ""
                    lines_html += (
                        f'<div style="padding:3px 0;font-size:0.9em;">'
                        f'<span style="{name_style}">{a.player_name}</span> '
                        f'{act_text}{amt_text}{allin}</div>'
                    )
                st.markdown(
                    f'<div style="padding:8px 10px;background:rgba(255,255,255,0.03);'
                    f'border-radius:6px;border-top:3px solid {color};">'
                    f'<div style="font-weight:bold;color:{color};margin-bottom:6px;'
                    f'font-size:0.95em;">{label}</div>'
                    f'{lines_html}</div>',
                    unsafe_allow_html=True,
                )

        # --- Result ---
        if hand.winners:
            winner_parts = []
            for seat, amount in hand.winners.items():
                name = hand.players.get(seat, f"Seat {seat}")
                is_hero = (seat == hand.hero_seat)
                style = "color:#2ecc71;font-weight:bold;" if is_hero else "color:#f1c40f;"
                winner_parts.append(f'<span style="{style}">{name}</span> won ${amount:,.2f}')
            st.markdown(
                f'<div style="padding:8px 14px;background:rgba(241,196,15,0.08);'
                f'border-left:3px solid #f1c40f;border-radius:4px;margin-top:8px;">'
                f'🏆 {" | ".join(winner_parts)}</div>',
                unsafe_allow_html=True,
            )

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
