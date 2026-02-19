"""Poker Simulation page - multi-agent poker game simulation."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import subprocess
import streamlit_shadcn_ui as ui
import streamlit_antd_components as sac
import time
from typing import Dict, List, Optional

from poker_advisor.storage import Database, HandRepository
from poker_advisor.models.action import ActionType
from poker_advisor.models.simulation import (
    SimulationConfig, AgentConfig, PlayStyle, AgentLevel, GamePhase
)
from poker_advisor.simulation.engine import SimulationEngine
from poker_advisor.agents.factory import AgentFactory

from theme import inject_theme, PLOTLY_LAYOUT, COLORS
from navigation import render_sidebar_nav


# --- Notification helper functions ---
def send_macos_notification(title: str, message: str, subtitle: str = ""):
    """Send a macOS system notification."""
    try:
        script = f'display notification "{message}" with title "{title}"'
        if subtitle:
            script = f'display notification "{message}" with title "{title}" subtitle "{subtitle}"'
        subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True
        )
        return True
    except Exception:
        return False


# Track last notification time to avoid spamming
LAST_NOTIFICATION_KEY = "last_hero_notification_time"
NOTIFICATION_COOLDOWN = 5  # seconds

st.set_page_config(page_title="牌局模拟", page_icon="🎰", layout="wide")
inject_theme()
render_sidebar_nav("pages/7_simulation")

st.title("🎰 牌局模拟")

# --- Session state initialization ---
if "sim_engine" not in st.session_state:
    st.session_state.sim_engine = None
if "sim_config" not in st.session_state:
    st.session_state.sim_config = None
if "game_active" not in st.session_state:
    st.session_state.game_active = False
if "waiting_for_hero" not in st.session_state:
    st.session_state.waiting_for_hero = False
if "auto_play" not in st.session_state:
    st.session_state.auto_play = False
if "sim_hands" not in st.session_state:
    st.session_state.sim_hands = []


# --- Tabs using sac ---
selected_tab = sac.tabs([
    sac.TabsItem(label="牌局配置", icon="gear-fill"),
    sac.TabsItem(label="实时对战", icon="controller"),
    sac.TabsItem(label="历史记录", icon="journal-text"),
], color="green", key="simulation_tabs")


# --- Tab 1: 牌局配置 ---
if selected_tab == "牌局配置":
    st.subheader("⚙️ 牌局配置")

    # Basic settings
    col1, col2, col3 = st.columns(3)
    with col1:
        player_count = st.slider("玩家数量", min_value=2, max_value=9, value=6)
    with col2:
        small_blind = st.number_input("小盲注", min_value=1, max_value=1000, value=10)
    with col3:
        big_blind = st.number_input("大盲注", min_value=2, max_value=2000, value=20)

    starting_stack = st.number_input("起始筹码", min_value=100, max_value=100000, value=1000)

    st.markdown("---")
    st.subheader("👤 Hero 配置")

    hero_seat = st.selectbox(
        "Hero 座位",
        options=[None] + list(range(1, 10)),
        format_func=lambda x: "随机" if x is None else f"座位 {x}",
        index=1
    )
    hero_name = st.text_input("Hero 昵称", value="Hero")

    st.markdown("---")
    st.subheader("🤖 Agent 配置")

    # Generate random agent configs
    factory = AgentFactory()

    if "agent_configs" not in st.session_state:
        st.session_state.agent_configs = []

    # Button to generate random agents
    if st.button("🎲 随机生成 Agent"):
        configs = factory.create_random_configs(
            player_count=player_count,
            hero_seat=hero_seat,
            exclude_hero=True
        )
        st.session_state.agent_configs = configs
        st.rerun()

    # Display and edit agent configs
    style_labels = {
        PlayStyle.LOOSE_AGGRESSIVE: "LAG - 松凶",
        PlayStyle.LOOSE_PASSIVE: "LP - 松被动",
        PlayStyle.TIGHT_AGGRESSIVE: "TAG - 紧凶",
        PlayStyle.TIGHT_PASSIVE: "TP - 紧被动",
    }

    level_labels = {
        AgentLevel.BEGINNER: "入门",
        AgentLevel.ADVANCED: "进阶",
        AgentLevel.EXPERT: "专家",
    }

    # Ensure we have the right number of agents
    agents_needed = player_count - (1 if hero_seat is not None else 0)
    while len(st.session_state.agent_configs) > agents_needed:
        st.session_state.agent_configs.pop()

    for i in range(len(st.session_state.agent_configs)):
        cfg = st.session_state.agent_configs[i]
        with st.expander(f"🎭 {cfg.name or f'Agent {i+1}'} (座位 {cfg.seat})", expanded=True):
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                new_name = st.text_input("昵称", value=cfg.name, key=f"name_{i}")
            with col_b:
                new_style = st.selectbox(
                    "风格",
                    options=list(PlayStyle),
                    format_func=lambda s: style_labels.get(s, s.value),
                    index=list(PlayStyle).index(cfg.style) if cfg.style in PlayStyle else 0,
                    key=f"style_{i}"
                )
            with col_c:
                new_seat = st.number_input(
                    "座位",
                    min_value=1, max_value=9, value=cfg.seat,
                    key=f"seat_{i}"
                )

            # Update config
            st.session_state.agent_configs[i].name = new_name
            st.session_state.agent_configs[i].style = new_style
            st.session_state.agent_configs[i].seat = int(new_seat)

    st.markdown("---")

    # Start game button
    if st.button("▶️ 开始牌局", type="primary", use_container_width=True):
        # Create simulation config
        config = SimulationConfig(
            player_count=player_count,
            small_blind=small_blind,
            big_blind=big_blind,
            hero_stack=starting_stack,
            hero_seat=hero_seat,
            hero_name=hero_name,
            agent_configs=st.session_state.agent_configs.copy(),
        )

        # Create engine
        engine = SimulationEngine(config)

        st.session_state.sim_config = config
        st.session_state.sim_engine = engine
        st.session_state.game_active = False
        st.session_state.waiting_for_hero = False
        st.session_state.sim_hands = []

        st.success("牌局配置完成！切换到「实时对战」开始游戏。")
        st.session_state["_switch_to_tab"] = "实时对战"
        time.sleep(0.5)
        st.rerun()


# --- Tab 2: 实时对战 ---
elif selected_tab == "实时对战":
    st.subheader("🎮 实时对战")

    engine: Optional[SimulationEngine] = st.session_state.sim_engine

    if engine is None:
        st.info("请先在「牌局配置」中配置并开始牌局。")
        if st.button("去配置 →"):
            st.session_state["_switch_to_tab"] = "牌局配置"
            st.rerun()
    else:
        # Game controls
        col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([1, 1, 1])

        with col_ctrl1:
            if not st.session_state.game_active:
                if st.button("🆕 新发一手", type="primary", use_container_width=True):
                    engine.start_new_hand()
                    st.session_state.game_active = True
                    st.session_state.waiting_for_hero = False
                    st.rerun()
            else:
                if st.button("⏭️ 跳过这手牌", use_container_width=True):
                    st.session_state.game_active = False
                    st.rerun()

        with col_ctrl2:
            st.session_state.auto_play = st.toggle("🤖 自动播放", value=st.session_state.auto_play)

        with col_ctrl3:
            if st.button("🔄 重置牌局", use_container_width=True):
                st.session_state.sim_engine = None
                st.session_state.game_active = False
                st.rerun()

        st.markdown("---")

        # Display game state
        state = engine.get_state()

        if state is None:
            st.info("点击「新发一手」开始游戏。")
        else:
            # --- Two-column layout ---
            col_left, col_right = st.columns([4, 6])

            with col_left:
                # Game info header
                col_info1, col_info2 = st.columns(2)
                with col_info1:
                    ui.metric_card(
                        title="牌局 #",
                        content=str(state.hand_number),
                        description="当前手牌",
                        key="hand_num"
                    )
                with col_info2:
                    phase_labels = {
                        GamePhase.WAITING: "等待中",
                        GamePhase.PREFLOP: "翻前",
                        GamePhase.FLOP: "翻牌",
                        GamePhase.TURN: "转牌",
                        GamePhase.RIVER: "河牌",
                        GamePhase.SHOWDOWN: "摊牌",
                        GamePhase.COMPLETE: "完成",
                    }
                    ui.metric_card(
                        title="阶段",
                        content=phase_labels.get(state.phase, state.phase.value),
                        description="游戏阶段",
                        key="game_phase"
                    )

                col_info3, col_info4 = st.columns(2)
                with col_info3:
                    ui.metric_card(
                        title="底池",
                        content=f"${state.pot:.0f}",
                        description="总底池",
                        key="pot_size"
                    )
                with col_info4:
                    hero = state.hero
                    if hero:
                        ui.metric_card(
                            title="Hero 筹码",
                            content=f"${hero.stack:.0f}",
                            description="当前筹码",
                            key="hero_stack"
                        )

                st.markdown("---")

                # --- Poker table visualization ---
                # Helper for card display
                def card_html(card=None, hidden=False):
                    if hidden or card is None:
                        return '<span style="display:inline-block;background:#333;border:2px solid #555;border-radius:8px;padding:10px 14px;margin:2px;font-weight:bold;color:#666;font-family:monospace;font-size:1.1em;">?</span>'
                    rank = card.rank.value
                    suit = card.suit.symbol
                    color = COLORS["accent_red"] if card.suit.value in ("h", "d") else COLORS["text_primary"]
                    return f'<span style="display:inline-block;background:#222;border:2px solid #444;border-radius:8px;padding:10px 14px;margin:2px;font-weight:bold;color:{color};font-family:monospace;font-size:1.1em;">{rank}{suit}</span>'

                # CSS styles
                st.markdown("""
                <style>
                .player-seat{background:rgba(255,255,255,0.05);border:1px solid #333;border-radius:12px;padding:12px 16px;margin:8px 0;}
                .player-seat.hero{border-color:#2ecc71;background:rgba(46,204,113,0.1);}
                .player-seat.current{border-color:#f1c40f;box-shadow:0 0 10px rgba(241,196,15,0.3);}
                .player-seat.folded{opacity:0.5;}
                .game-area{background:rgba(0,0,0,0.2);border-radius:16px;padding:20px;text-align:center;}
                </style>
                """, unsafe_allow_html=True)

                # Community cards in a nice game area
                st.markdown('<div class="game-area">', unsafe_allow_html=True)
                st.markdown('<div style="font-size:1em;color:#aaa;margin-bottom:12px;">🃏 公共牌</div>', unsafe_allow_html=True)
                if state.community_cards:
                    cards_html = "".join(card_html(c) for c in state.community_cards)
                    st.markdown(f'<div style="font-size:1.2em;">{cards_html}</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div style="color:#666;font-size:1.1em;">-</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

                st.markdown("---")

                # --- Action log in left column ---
                with st.expander("📜 行动记录", expanded=True):
                    for msg in state.action_history[-10:]:
                        st.text(msg)

            with col_right:
                st.markdown("### 👥 玩家")

                # Display each player as a separate, complete HTML block
                for seat in sorted(state.players.keys()):
                    player = state.players[seat]
                    is_current = seat == state.current_player_seat
                    is_hero = player.is_hero

                    classes = ["player-seat"]
                    if is_hero:
                        classes.append("hero")
                    if is_current:
                        classes.append("current")
                    if player.is_folded:
                        classes.append("folded")

                    pos_str = player.position.value if player.position else "?"
                    style_badge = ""
                    if player.agent_config:
                        style_str = player.agent_config.style.value
                        style_badge = f'<span style="background:#555;color:#fff;padding:2px 8px;border-radius:10px;font-size:0.7em;margin-left:8px;">{style_str}</span>'

                    cards_display = ""
                    if player.cards:
                        if is_hero or state.phase == GamePhase.COMPLETE:
                            cards_display = "".join(card_html(c) for c in player.cards)
                        else:
                            cards_display = "".join(card_html(None, hidden=True) for _ in player.cards)

                    status_badge = ""
                    if player.is_folded:
                        status_badge = '<span style="background:#e74c3c;color:#fff;padding:2px 8px;border-radius:10px;font-size:0.7em;margin-left:8px;">已弃牌</span>'
                    if player.is_all_in:
                        status_badge = '<span style="background:#f39c12;color:#fff;padding:2px 8px;border-radius:10px;font-size:0.7em;margin-left:8px;">ALL-IN</span>'
                    if is_current:
                        status_badge = '<span style="background:#f1c40f;color:#000;padding:2px 8px;border-radius:10px;font-size:0.7em;margin-left:8px;">思考中...</span>'

                    # Player card with better layout - cards on left, info on right
                    empty_cards = '<span style="color:#666;">-</span>'
                    player_html = '<div class="' + ' '.join(classes) + '">'
                    player_html += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">'
                    player_html += '<div>'
                    player_html += '<span style="font-weight:bold;font-size:1.1em;">' + player.name + '</span>'
                    player_html += style_badge
                    player_html += status_badge
                    player_html += '</div>'
                    player_html += '<div style="text-align:right;">'
                    player_html += '<span style="color:#aaa;font-size:0.8em;">座位 ' + str(seat) + ' · ' + pos_str + '</span>'
                    player_html += '</div>'
                    player_html += '</div>'
                    player_html += '<div style="display:flex;justify-content:space-between;align-items:center;gap:20px;">'
                    player_html += '<div style="flex:1;">'
                    player_html += cards_display if cards_display else empty_cards
                    player_html += '</div>'
                    player_html += '<div style="text-align:right;min-width:100px;">'
                    player_html += '<div style="color:#f1c40f;font-weight:bold;font-size:1.2em;">💰 $' + f'{player.stack:.0f}' + '</div>'
                    player_html += '<div style="color:#aaa;font-size:0.85em;">投入: $' + f'{player.total_invested:.0f}' + '</div>'
                    player_html += '</div>'
                    player_html += '</div>'
                    player_html += '</div>'
                    st.markdown(player_html, unsafe_allow_html=True)

            st.markdown("---")

            # --- Action area ---
            if state.phase != GamePhase.COMPLETE:
                if engine.is_hero_turn():
                    st.markdown("### 🎯 轮到你行动")

                    # Send macOS system notification (with cooldown)
                    import time
                    now = time.time()
                    last_notification = st.session_state.get(LAST_NOTIFICATION_KEY, 0)
                    if now - last_notification > NOTIFICATION_COOLDOWN:
                        send_macos_notification(
                            "PokerMaster Pro - 轮到你行动！",
                            "牌局模拟等待你的决策",
                            f"牌局 #{state.hand_number}"
                        )
                        st.session_state[LAST_NOTIFICATION_KEY] = now

                    # Browser notification - request permission and send notification
                    notification_js = """
                    <script>
                    // Request notification permission on page load
                    function requestNotificationPermission() {
                        if (!("Notification" in window)) {
                            console.log("This browser does not support desktop notification");
                        } else if (Notification.permission === "granted") {
                            // Permission already granted
                        } else if (Notification.permission !== "denied") {
                            Notification.requestPermission();
                        }
                    }

                    // Send notification
                    function sendHeroTurnNotification() {
                        if ("Notification" in window && Notification.permission === "granted") {
                            new Notification("PokerMaster Pro - 轮到你行动！", {
                                body: "牌局模拟等待你的决策",
                                icon: "🎰"
                            });
                        }
                    }

                    // Request permission when page loads
                    requestNotificationPermission();

                    // Send notification when it's hero's turn
                    // We'll use a small timeout to ensure the DOM is ready
                    setTimeout(function() {
                        // Check if we haven't sent this notification recently
                        var lastNotification = sessionStorage.getItem('lastHeroNotification');
                        var now = Date.now();
                        if (!lastNotification || (now - lastNotification > 5000)) {
                            sendHeroTurnNotification();
                            sessionStorage.setItem('lastHeroNotification', now);
                        }
                    }, 500);
                    </script>
                    """
                    st.components.v1.html(notification_js, height=0)

                    available_actions = engine.get_available_actions()

                    # Display action buttons
                    action_labels = {
                        ActionType.FOLD: ("弃牌", "e74c3c"),
                        ActionType.CHECK: ("过牌", "3498db"),
                        ActionType.CALL: ("跟注", "f39c12"),
                        ActionType.BET: ("下注", "2ecc71"),
                        ActionType.RAISE: ("加注", "9b59b6"),
                        ActionType.ALL_IN: ("ALL-IN", "e74c3c"),
                    }

                    # Calculate amounts
                    hero = state.hero
                    to_call = state.current_bet - (hero.current_bet if hero else 0)
                    min_raise = state.min_raise
                    max_raise = (hero.stack + hero.current_bet) if hero else 0

                    # Action buttons
                    action_cols = st.columns(len(available_actions))
                    selected_action = None

                    for i, action in enumerate(available_actions):
                        label, color = action_labels.get(action, (action.value, "#888"))
                        if action in (ActionType.CALL, ActionType.BET, ActionType.RAISE, ActionType.ALL_IN):
                            if action == ActionType.CALL:
                                label += f" (${to_call:.0f})"
                            elif action == ActionType.BET:
                                label += f" (≥${state.big_blind:.0f})"
                            elif action == ActionType.RAISE:
                                label += f" (≥${to_call + min_raise:.0f})"

                        with action_cols[i]:
                            if st.button(label, key=f"action_{action.value}", use_container_width=True):
                                selected_action = action

                    # Bet/Raise amount input
                    amount = 0
                    if selected_action in (ActionType.BET, ActionType.RAISE):
                        if selected_action == ActionType.BET:
                            min_amt = state.big_blind
                            max_amt = hero.stack if hero else 0
                            default = min(state.big_blind * 3, max_amt)
                        else:  # RAISE
                            min_amt = to_call + min_raise
                            max_amt = (hero.stack + hero.current_bet) if hero else 0
                            default = min(to_call + min_raise * 2, max_amt)

                        amount = st.slider(
                            "金额",
                            min_value=float(min_amt),
                            max_value=float(max_amt),
                            value=float(default),
                            step=10.0,
                            key="bet_amount"
                        )
                    elif selected_action == ActionType.CALL:
                        amount = to_call
                    elif selected_action == ActionType.ALL_IN:
                        amount = (hero.stack + hero.current_bet) if hero else 0

                    # Execute action
                    if selected_action:
                        try:
                            engine.player_action(selected_action, amount)
                            st.rerun()
                        except Exception as e:
                            st.error(f"行动失败: {e}")

                else:
                    # Agent's turn - auto play
                    st.markdown("### 🤖 Agent 思考中...")

                    if st.session_state.auto_play or not st.session_state.waiting_for_hero:
                        # Small delay for realism
                        time.sleep(0.5)
                        try:
                            engine.agent_action()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Agent 行动失败: {e}")
                            st.session_state.game_active = False
            else:
                # Hand complete
                st.markdown("### ✅ 牌局完成")

                if st.button("🆕 下一手", type="primary"):
                    # Save hand if we have it
                    hand = engine.to_hand_record()
                    if hand:
                        st.session_state.sim_hands.append(hand)

                    engine.start_new_hand()
                    st.rerun()

            # --- Action log ---
            st.markdown("---")
            with st.expander("📜 行动记录", expanded=False):
                for msg in state.action_history:
                    st.text(msg)


# --- Tab 3: 历史记录 ---
elif selected_tab == "历史记录":
    st.subheader("📋 牌局历史")

    hands = st.session_state.sim_hands

    if not hands:
        st.info("暂无牌局记录。开始游戏后，完成的牌局将显示在这里。")
    else:
        for i, hand in enumerate(reversed(hands)):
            with st.expander(f"🎰 牌局 #{hand.hand_id} - {hand.timestamp[:19]}", expanded=i == 0):
                col_h1, col_h2, col_h3, col_h4 = st.columns(4)
                with col_h1:
                    ui.metric_card(
                        title="玩家数",
                        content=str(hand.player_count),
                        key=f"p_{i}"
                    )
                with col_h2:
                    ui.metric_card(
                        title="盲注",
                        content=f"${hand.small_blind:.0f}/${hand.big_blind:.0f}",
                        key=f"b_{i}"
                    )
                with col_h3:
                    ui.metric_card(
                        title="底池",
                        content=f"${hand.pot_total:.0f}",
                        key=f"pt_{i}"
                    )
                with col_h4:
                    hero_won = hand.hero_won
                    result = "✅ 赢" if hero_won else "❌ 输"
                    ui.metric_card(
                        title="结果",
                        content=result,
                        key=f"r_{i}"
                    )

                if hand.hero_cards:
                    st.markdown(f"**Hero 手牌:** {' '.join(str(c) for c in hand.hero_cards)}")
                if hand.board:
                    st.markdown(f"**公共牌:** {' '.join(str(c) for c in hand.board)}")

                if hand.winners:
                    winner_str = ", ".join(
                        f"{hand.players.get(s, f'座位{s}')} (${a:.0f})"
                        for s, a in hand.winners.items()
                    )
                    st.markdown(f"**赢家:** {winner_str}")
