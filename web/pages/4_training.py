"""Training page — interactive training with AI evaluation."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import streamlit_shadcn_ui as ui
import streamlit_antd_components as sac
import plotly.graph_objects as go

from poker_advisor.storage import Database, HandRepository
from poker_advisor.models.action import Street
from poker_advisor import config as _cfg

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
# Programmatic tab switch: set widget session_state value before render
if "_switch_to_tab" in st.session_state:
    st.session_state["training_tabs"] = st.session_state.pop("_switch_to_tab")
selected_tab = sac.tabs([
    sac.TabsItem(label="我的训练方案", icon="clipboard-check"),
    sac.TabsItem(label="专项训练", icon="bullseye"),
    sac.TabsItem(label="训练记录", icon="clock-history"),
], color="green", key="training_tabs")

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

                        generator = TrainingPlanGenerator()
                        plan = generator.generate_plan(leaks, stats)

                        st.session_state["generated_plan"] = plan
                        st.session_state["generated_plan_session"] = session_id
                        st.session_state["generated_plan_text"] = generator.format_plan(plan)
                        st.rerun()

                except ImportError as e:
                    st.warning(f"训练方案生成模块未完全实现: {e}")
                    st.info("此功能正在开发中，敬请期待！")
                except Exception as e:
                    st.error(f"生成训练方案失败: {e}")

    # Display plan from session_state (persists across reruns)
    if "generated_plan" in st.session_state:
        plan = st.session_state["generated_plan"]
        plan_session_id = st.session_state["generated_plan_session"]

        st.markdown("---")
        st.subheader(f"📊 {plan.plan_name}")
        st.caption(f"生成时间: {plan.created_at.strftime('%Y-%m-%d %H:%M')}")

        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            ui.metric_card(title="目标周期", content=f"{plan.duration_days} 天",
                          description="建议训练周期", key="plan_duration")
        with col_m2:
            ui.metric_card(title="每日时长", content=f"{plan.daily_minutes} 分钟",
                          description="建议训练时长", key="plan_minutes")
        with col_m3:
            ui.metric_card(title="起始难度", content=plan.start_difficulty.value,
                          description="难度等级", key="plan_diff")

        sac.divider(label="训练模块", icon="grid", color="green")

        # --- Module icon / color mapping ---
        _focus_meta = {
            "preflop": ("🃏", "#9b59b6", "翻前"),
            "flop":    ("🎴", "#3498db", "翻牌"),
            "turn":    ("🔄", "#e67e22", "转牌"),
            "river":   ("🏁", "#e74c3c", "河牌"),
            "cbet":    ("💰", "#f39c12", "C-Bet"),
            "3bet":    ("⚡", "#1abc9c", "3-Bet"),
            "general": ("📚", "#95a5a6", "综合"),
        }
        _diff_style = {
            "beginner":     ("入门", "#2ecc71"),
            "intermediate": ("进阶", "#f39c12"),
            "advanced":     ("高级", "#e74c3c"),
            "expert":       ("专家", "#9b59b6"),
        }

        for i, module in enumerate(plan.modules):
            icon, color, phase = _focus_meta.get(module.focus_area, ("📚", "#95a5a6", "综合"))
            diff_label, diff_color = _diff_style.get(module.difficulty.value, ("?", "#aaa"))

            st.markdown(
                f'<div style="border:1px solid #333;border-left:4px solid {color};'
                f'border-radius:8px;padding:16px 20px;margin-bottom:12px;'
                f'background:rgba(255,255,255,0.03);">'
                # Row 1: title + badges
                f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;flex-wrap:wrap;">'
                f'<span style="font-size:1.5em;">{icon}</span>'
                f'<span style="font-size:1.15em;font-weight:bold;">{module.name}</span>'
                f'<span style="background:{color};color:#fff;padding:2px 10px;border-radius:12px;'
                f'font-size:0.8em;">{phase}</span>'
                f'<span style="background:{diff_color};color:#fff;padding:2px 10px;border-radius:12px;'
                f'font-size:0.8em;">{diff_label}</span>'
                f'</div>'
                # Row 2: description
                f'<div style="color:#ccc;margin-bottom:14px;font-size:0.95em;">{module.description}</div>'
                # Row 3: stats
                f'<div style="display:flex;gap:24px;color:#aaa;font-size:0.85em;">'
                f'<span>🎯 弱点: <span style="color:#fff;">{module.focus_leak}</span></span>'
                f'<span>⏱ {module.duration_minutes} 分钟</span>'
                f'<span>📋 {module.scenario_count} 场景</span>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if st.button(f"开始训练 →  {module.name}", key=f"start_module_{i}", use_container_width=True):
                st.session_state["_switch_to_tab"] = "专项训练"
                st.session_state["plan_focus"] = module.focus_area
                st.session_state["plan_session_id"] = plan_session_id
                st.session_state["plan_module"] = module
                st.rerun()

        # --- Training roadmap ---
        sac.divider(label="训练路线", icon="signpost-2", color="green")

        # Build roadmap HTML
        _roadmap_items = []
        for step_i, m in enumerate(plan.modules):
            _icon, _clr, _phase = _focus_meta.get(m.focus_area, ("📚", "#95a5a6", "综合"))
            _roadmap_items.append(
                f'<div style="display:flex;align-items:flex-start;gap:14px;">'
                # circle + connector line
                f'<div style="display:flex;flex-direction:column;align-items:center;">'
                f'<div style="width:32px;height:32px;border-radius:50%;background:{_clr};'
                f'display:flex;align-items:center;justify-content:center;font-size:0.85em;'
                f'font-weight:bold;color:#fff;flex-shrink:0;">{step_i+1}</div>'
                + (f'<div style="width:2px;height:36px;background:#444;"></div>'
                   if step_i < len(plan.modules) - 1 else '')
                + f'</div>'
                # text
                f'<div style="padding-top:4px;">'
                f'<span style="font-weight:bold;color:#eee;">{m.name}</span>'
                f'<span style="color:#888;margin-left:8px;font-size:0.85em;">'
                f'{_phase} · {m.duration_minutes}分钟 · {m.scenario_count}场景</span>'
                f'</div>'
                f'</div>'
            )
        _roadmap_html = "\n".join(_roadmap_items)

        # Derive contextual tips based on plan modules
        _tips = []
        _focus_areas = [m.focus_area for m in plan.modules]
        if "preflop" in _focus_areas:
            _tips.append("翻前是牌桌利润的基石 — 从收紧起手牌范围开始，每局都问自己「这手牌值得投入吗？」")
        if "flop" in _focus_areas or "cbet" in _focus_areas:
            _tips.append("翻后决策占EV损失的最大比重 — 关注持续下注的频率和尺度，学会读牌面结构")
        if "3bet" in _focus_areas:
            _tips.append("3-Bet是对抗松凶的利器 — 找到合适的3-Bet范围，平衡价值牌和诈唬牌")
        if "river" in _focus_areas:
            _tips.append("河牌是信息最完整的街 — 学会控制底池大小，避免在弱牌时支付大注")
        if not _tips:
            _tips.append("按顺序完成每个模块，每个模块结束后检验正确率再进入下一个")
        _tips.append(f"建议每日投入 {plan.daily_minutes} 分钟，{plan.duration_days} 天完成整个计划")
        _tips.append("正确率 >80% 自动升级难度，<40% 自动降级 — 让系统帮你找到最佳训练区间")

        _tips_html = "".join(
            f'<div style="padding:6px 0;color:#ccc;font-size:0.9em;">'
            f'<span style="color:#f39c12;margin-right:6px;">💡</span>{t}</div>'
            for t in _tips
        )

        st.markdown(
            f'<div style="display:flex;gap:28px;flex-wrap:wrap;">'
            # Left: roadmap
            f'<div style="flex:1;min-width:240px;">{_roadmap_html}</div>'
            # Right: tips
            f'<div style="flex:1;min-width:240px;background:rgba(255,255,255,0.03);'
            f'border:1px solid #333;border-radius:8px;padding:16px 20px;">'
            f'<div style="font-weight:bold;margin-bottom:10px;color:#eee;">📌 训练建议</div>'
            f'{_tips_html}'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Training results
        st.markdown("---")
        st.subheader("📈 训练进度")
        if "training_progress" in st.session_state:
            progress = st.session_state["training_progress"]
            st.progress(progress["completed"] / progress["total"],
                       text=f"已完成 {progress['completed']}/{progress['total']} 个场景")
            if st.button("继续训练"):
                st.session_state["_switch_to_tab"] = "专项训练"
                st.rerun()
            if st.button("重新训练"):
                del st.session_state["training_progress"]
                st.rerun()
        else:
            st.info("暂无训练进度")
    else:
        st.info("💡 选择一个会话并点击「生成训练方案」，系统会根据你的弱点自动生成个性化训练计划。")

# --- Tab 2: 专项训练 ---
elif selected_tab == "专项训练":
    # Initialize session state
    if "scenarios" not in st.session_state:
        st.session_state.scenarios = []
        st.session_state.current_idx = 0
        st.session_state.scores = []
        st.session_state.training_active = False

    # Read pre-set focus from training plan (if redirected)
    _plan_focus = st.session_state.pop("plan_focus", None)
    _plan_session = st.session_state.pop("plan_session_id", None)
    _plan_module = st.session_state.get("plan_module", None)

    # --- Setup ---
    if not st.session_state.training_active:
        st.subheader("训练设置")

        if _plan_module:
            st.success(f"已从训练方案跳转，预设重点: **{_plan_module.name}**")
            st.markdown(f"**训练目标:** {_plan_module.description}")
        elif _plan_focus:
            st.success(f"已从训练方案跳转，预设重点: **{_plan_focus}**")

        sessions = repo.get_sessions()
        session_options = {"全部": None}
        for s in sessions:
            label = f"{s['filename']} ({s['hand_count']} hands, {s['id']})"
            session_options[label] = s["id"]

        # Pre-select session if coming from training plan
        default_session_idx = 0
        if _plan_session:
            for idx, key in enumerate(session_options.keys()):
                if session_options[key] == _plan_session:
                    default_session_idx = idx
                    break

        selected = st.selectbox("选择会话", options=list(session_options.keys()),
                                index=default_session_idx)
        session_id = session_options[selected]

        col1, col2 = st.columns(2)
        with col1:
            count = st.slider("场景数量", min_value=1, max_value=20, value=5)
        with col2:
            # Focus area — segmented selector
            focus_options = ["全部", "preflop", "flop", "turn", "river", "cbet", "3bet"]
            default_focus_idx = 0
            if _plan_module:
                # Use module's focus area if available
                if _plan_module.focus_area in focus_options:
                    default_focus_idx = focus_options.index(_plan_module.focus_area)
            elif _plan_focus and _plan_focus in focus_options:
                default_focus_idx = focus_options.index(_plan_focus)
            focus = sac.segmented(
                items=[sac.SegmentedItem(label=f) for f in focus_options],
                color="green",
                index=default_focus_idx,
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
                st.session_state["training_progress"] = {
                    "completed": 0,
                    "total": len(scenarios),
                }
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
    _hand = scenario.hand

    # --- Scenario type labels ---
    _type_labels = {
        "preflop_open": ("翻前开池", "🃏", "#9b59b6"),
        "preflop_vs_raise": ("翻前面对加注", "🃏", "#9b59b6"),
        "preflop_vs_3bet": ("翻前面对3-Bet", "⚡", "#e74c3c"),
        "preflop_vs_limpers": ("翻前面对溜入", "🃏", "#9b59b6"),
        "flop_cbet_decision": ("翻牌C-Bet决策", "💰", "#f39c12"),
        "flop_facing_bet": ("翻牌面对下注", "🎴", "#3498db"),
        "flop_check_decision": ("翻牌过牌决策", "🎴", "#3498db"),
        "turn_facing_bet": ("转牌面对下注", "🔄", "#e67e22"),
        "turn_bet_decision": ("转牌下注决策", "🔄", "#e67e22"),
        "river_facing_bet": ("河牌面对下注", "🏁", "#e74c3c"),
        "river_bet_decision": ("河牌下注决策", "🏁", "#e74c3c"),
    }
    _type_label, _type_icon, _type_clr = _type_labels.get(
        scenario.scenario_type, (scenario.scenario_type, "📋", "#95a5a6"))

    # Card chip helper
    def _chip(card_str: str) -> str:
        if not card_str or len(card_str) < 2:
            return ""
        rank, suit = card_str[:-1], card_str[-1]
        fg = "#e74c3c" if suit in ("♥", "♦") else "#ecf0f1"
        return (f'<span style="display:inline-block;background:#2c2c2c;border:1px solid #555;'
                f'border-radius:5px;padding:2px 7px;margin:1px;font-weight:bold;'
                f'color:{fg};font-family:monospace;font-size:1em;">'
                f'{rank}<span style="font-size:1.1em;">{suit}</span></span>')

    # Progress bar
    st.progress((idx) / len(scenarios),
                text=f"场景 {idx + 1}/{len(scenarios)}")

    # --- Scenario header ---
    _pos = _hand.hero_position
    _pos_str = _pos.value if _pos else "?"
    _hero_cards_html = " ".join(_chip(str(c)) for c in _hand.hero_cards) if _hand.hero_cards else "?"
    _stack_html = ""
    if _hand.hero_seat and _hand.hero_seat in _hand.stacks:
        _stk = _hand.stacks[_hand.hero_seat]
        _bb = _hand.big_blind or 1.0
        _stack_html = (f'<span style="color:#aaa;font-size:0.85em;margin-left:16px;">'
                       f'💰 ${_stk:.0f} ({_stk/_bb:.0f} BB)</span>')

    st.markdown(
        f'<div style="border:1px solid #333;border-left:4px solid {_type_clr};'
        f'border-radius:8px;padding:16px 20px;margin-bottom:14px;'
        f'background:rgba(255,255,255,0.03);">'
        # Row 1: type badge + position + blinds + players
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;flex-wrap:wrap;">'
        f'<span style="font-size:1.3em;">{_type_icon}</span>'
        f'<span style="background:{_type_clr};color:#fff;padding:3px 12px;'
        f'border-radius:12px;font-weight:bold;font-size:0.9em;">{_type_label}</span>'
        f'<span style="background:#444;color:#fff;padding:3px 10px;border-radius:12px;'
        f'font-size:0.8em;">📍 {_pos_str}</span>'
        f'<span style="color:#aaa;font-size:0.85em;">'
        f'{_hand.player_count}人桌 · 盲注 ${_hand.small_blind:.0f}/${_hand.big_blind:.0f}</span>'
        f'{_stack_html}'
        f'</div>'
        # Row 2: hero cards
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;">'
        f'<span style="color:#aaa;font-size:0.85em;">手牌</span>'
        f'{_hero_cards_html}'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # --- Board cards ---
    _board_parts = []
    _decision_order = scenario.decision_street.order
    if _decision_order >= Street.FLOP.order and _hand.flop:
        _board_parts.append(("翻牌", " ".join(_chip(str(c)) for c in _hand.flop), "#3498db"))
    if _decision_order >= Street.TURN.order and _hand.turn:
        _board_parts.append(("转牌", _chip(str(_hand.turn)), "#e67e22"))
    if _decision_order >= Street.RIVER.order and _hand.river:
        _board_parts.append(("河牌", _chip(str(_hand.river)), "#e74c3c"))

    if _board_parts:
        _board_html = ""
        for _blabel, _bcards, _bclr in _board_parts:
            _board_html += (
                f'<div style="display:flex;align-items:center;gap:8px;margin-right:20px;">'
                f'<span style="color:{_bclr};font-size:0.8em;font-weight:bold;">{_blabel}</span>'
                f'{_bcards}'
                f'</div>')
        st.markdown(
            f'<div style="display:flex;align-items:center;flex-wrap:wrap;gap:4px;'
            f'padding:10px 16px;margin-bottom:14px;background:rgba(255,255,255,0.02);'
            f'border:1px solid #333;border-radius:8px;">'
            f'<span style="color:#aaa;font-size:0.85em;margin-right:8px;">公共牌</span>'
            f'{_board_html}'
            f'</div>',
            unsafe_allow_html=True,
        )

    # --- Player positions overview ---
    if _hand.players:
        _pos_rows = []
        for _seat, _name in sorted(_hand.players.items()):
            _pos = _hand.positions.get(_seat)
            _pos_str = _pos.value if _pos else "?"
            _stack = _hand.stacks.get(_seat, 0)
            _is_hero = _seat == _hand.hero_seat
            _hero_marker = " 👈 你" if _is_hero else ""
            _bg = "rgba(46,204,113,0.15)" if _is_hero else "rgba(255,255,255,0.02)"
            _border = "#2ecc71" if _is_hero else "#333"
            _pos_rows.append(
                f'<div style="display:flex;align-items:center;gap:12px;padding:6px 10px;'
                f'background:{_bg};border:1px solid {_border};border-radius:6px;">'
                f'<span style="color:#aaa;font-size:0.8em;min-width:40px;">座位{_seat}</span>'
                f'<span style="color:#f1c40f;font-size:0.8em;min-width:50px;">{_pos_str}</span>'
                f'<span style="color:#eee;font-weight:{600 if _is_hero else 400};">{_name}</span>'
                f'<span style="color:#aaa;font-size:0.85em;margin-left:auto;">'
                f'${_stack:.0f}</span>'
                f'<span style="color:#2ecc71;font-size:0.85em;">{_hero_marker}</span>'
                f'</div>')
        st.markdown(
            f'<div style="padding:12px 16px;margin-bottom:14px;background:rgba(255,255,255,0.02);'
            f'border:1px solid #333;border-radius:8px;">'
            f'<div style="color:#aaa;font-size:0.8em;margin-bottom:10px;">🎪 玩家位置</div>'
            f'<div style="display:flex;flex-direction:column;gap:6px;">'
            f'{"".join(_pos_rows)}'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # --- Action timeline ---
    _street_colors = {
        "PREFLOP": "#9b59b6", "FLOP": "#3498db",
        "TURN": "#e67e22", "RIVER": "#e74c3c",
    }

    # Calculate cumulative bets per street for proper display
    # Poker Now logs use cumulative amounts, we store incremental - need to reconstruct
    _actions_before = []
    _cumulative_bets = {}  # seat -> total for current street
    _current_street = None

    for a in _hand.actions[:scenario.decision_index]:
        if a.action_type.value == "post_blind":
            continue
        # Reset cumulative when street changes
        if a.street != _current_street:
            _current_street = a.street
            _cumulative_bets = {}
        # For display: show cumulative if call/raise, else incremental
        if a.action_type.value in ("call", "raise", "bet"):
            _cumulative_bets[a.seat] = _cumulative_bets.get(a.seat, 0.0) + a.amount
            _display_amt = _cumulative_bets[a.seat]
        else:
            _display_amt = a.amount
        _actions_before.append((a, _display_amt))

    if _actions_before:
        _action_rows = []
        for a, _display_amt in _actions_before:
            _sname = a.street.value.upper()
            _sclr = _street_colors.get(_sname, "#888")
            _pname = "你" if a.seat == _hand.hero_seat else a.player_name
            _is_hero = a.seat == _hand.hero_seat
            _name_style = "color:#2ecc71;font-weight:bold;" if _is_hero else "color:#eee;"
            _amt = f' <span style="color:#f1c40f;">${_display_amt:.0f}</span>' if _display_amt > 0 else ""
            _action_rows.append(
                f'<div style="display:flex;align-items:center;gap:10px;padding:4px 0;">'
                f'<span style="background:{_sclr};color:#fff;padding:1px 8px;border-radius:8px;'
                f'font-size:0.7em;min-width:56px;text-align:center;">{_sname}</span>'
                f'<span style="{_name_style}font-size:0.9em;">{_pname}</span>'
                f'<span style="color:#ccc;font-size:0.9em;">{a.action_type.value}{_amt}</span>'
                f'</div>')
        st.markdown(
            f'<div style="padding:12px 16px;margin-bottom:14px;background:rgba(255,255,255,0.02);'
            f'border:1px solid #333;border-radius:8px;">'
            f'<div style="color:#aaa;font-size:0.8em;margin-bottom:8px;">行动记录</div>'
            f'{"".join(_action_rows)}'
            f'</div>',
            unsafe_allow_html=True,
        )

    # --- Pot + question ---
    _pot_est = sum(a.amount for a in _hand.actions[:scenario.decision_index] if a.amount > 0)
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:20px;padding:12px 16px;'
        f'margin-bottom:8px;background:linear-gradient(135deg,rgba(46,204,113,0.1),rgba(241,196,15,0.08));'
        f'border:1px solid #2ecc71;border-radius:8px;">'
        f'<span style="font-size:1.5em;">🎯</span>'
        f'<div>'
        f'<div style="font-size:1.1em;font-weight:bold;color:#eee;">轮到你行动</div>'
        f'<div style="color:#aaa;font-size:0.9em;">当前底池 '
        f'<span style="color:#f1c40f;font-weight:bold;">${_pot_est:.0f}</span></div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Action selection

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

                    # Update training progress
                    if "training_progress" in st.session_state:
                        st.session_state["training_progress"]["completed"] += 1

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
            )
            fig_trend.update_yaxes(range=[0, 10.5], gridcolor=COLORS["card_border"],
                                   zerolinecolor=COLORS["card_border"])
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
