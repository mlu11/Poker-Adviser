"""Poker Advisor — Streamlit Web UI home page."""

import streamlit as st
import streamlit_shadcn_ui as ui
import streamlit_antd_components as sac

from theme import inject_theme
from navigation import render_sidebar_nav

st.set_page_config(
    page_title="Poker Advisor",
    page_icon="♠",
    layout="wide",
)

inject_theme()
render_sidebar_nav("app")

st.title("♠ Poker Advisor")
st.markdown("德州扑克策略顾问 — AI 驱动的手牌分析与训练系统")

sac.divider(label="功能导航", icon="grid-3x3-gap", color="green")

# --- Feature cards: row 1 ---
col1, col2, col3 = st.columns(3)

with col1:
    ui.card(
        title="📊 统计分析",
        content="查看 VPIP、PFR、AF 等核心指标",
        description="导入 Poker Now 日志，按位置分析统计数据",
        key="card_stats",
    ).render()
    st.page_link("pages/1_stats.py", label="查看统计", icon="📊")

with col2:
    ui.card(
        title="🔍 漏洞检测",
        content="对比 GTO 基线发现漏洞",
        description="按严重程度排序，获取针对性改进建议",
        key="card_leaks",
    ).render()
    st.page_link("pages/2_leaks.py", label="检测漏洞", icon="🔍")

with col3:
    ui.card(
        title="🤖 AI 分析",
        content="Claude 深度策略分析",
        description="单手牌 AI 复盘，支持 Sonnet / Opus 模型",
        key="card_ai",
    ).render()
    st.page_link("pages/3_ai_analysis.py", label="AI 分析", icon="🤖")

sac.divider(label="更多功能", icon="plus-circle", color="green")

# --- Feature cards: row 2 ---
col4, col5 = st.columns(2)

with col4:
    ui.card(
        title="🎯 训练模式",
        content="基于真实手牌生成训练场景",
        description="AI 评估你的决策，追踪训练进度",
        key="card_training",
    ).render()
    st.page_link("pages/4_training.py", label="开始训练", icon="🎯")

with col5:
    ui.card(
        title="📋 手牌历史",
        content="浏览导入的手牌记录",
        description="查看详细手牌记录，管理导入会话",
        key="card_hands",
    ).render()
    st.page_link("pages/5_hands.py", label="手牌历史", icon="📋")

# Sidebar — import section (below navigation)
with st.sidebar:
    sac.divider(label="导入日志", icon="upload", color="gold")
    uploaded = st.file_uploader("上传 Poker Now 日志文件", type=["csv", "txt"])
    notes = st.text_input("备注（可选）")

    if uploaded and st.button("导入", type="primary"):
        import tempfile
        from pathlib import Path
        from poker_advisor.parser.pokernow_parser import PokerNowParser
        from poker_advisor.storage import Database, HandRepository

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp.write(uploaded.getvalue())
            tmp_path = tmp.name

        try:
            parser = PokerNowParser()
            hands = parser.parse_file(tmp_path)

            if not hands:
                st.error("未在日志中找到手牌。")
            else:
                db = Database()
                repo = HandRepository(db)
                session_id = repo.save_session(
                    hands, filename=uploaded.name, notes=notes,
                )
                st.success(f"成功导入 {len(hands)} 手牌！\n\n会话 ID: `{session_id}`")
        except Exception as e:
            st.error(f"解析失败: {e}")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    sac.divider(color="gray")
    st.caption("Poker Advisor v0.1.0")
