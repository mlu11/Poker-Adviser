"""Shared sidebar navigation using streamlit-option-menu."""

import streamlit as st
from streamlit_option_menu import option_menu

# Menu configuration: (label, icon, page_file)
MENU_ITEMS = [
    ("首页", "house-fill", "app"),
    ("数据分析", "bar-chart-line-fill", "1_stats"),
    ("复盘中心", "clock-history", "3_ai_analysis"),
    ("训练中心", "bullseye", "4_training"),
    ("手牌历史", "journal-text", "5_hands"),
    ("数据管理", "database-gear", "6_management"),
]

# Menu with sub-items for reference (future expansion)
MENU_GROUPS = {
    "数据分析": [("数据仪表盘", "pages/1_stats"), ("弱点诊断", "pages/2_leaks")],
    "复盘中心": [("单局复盘", "pages/3_ai_analysis"), ("批量复盘", "pages/3_ai_analysis"), ("复盘记录", "pages/5_hands")],
    "训练中心": [("我的训练方案", "pages/4_training"), ("专项训练库", "pages/4_training"), ("训练记录", "pages/4_training")],
    "辅助工具": [],
}

# Custom styling for the dark poker theme
MENU_STYLES = {
    "container": {
        "padding": "4px",
        "background-color": "#0d1b2a",
    },
    "icon": {
        "color": "#f1c40f",
        "font-size": "18px",
    },
    "nav-link": {
        "font-size": "14px",
        "text-align": "left",
        "margin": "2px 0",
        "padding": "8px 12px",
        "color": "#a0a0b0",
        "border-radius": "8px",
        "--hover-color": "#1b2f4a",
    },
    "nav-link-selected": {
        "background-color": "#0f3460",
        "color": "#2ecc71",
        "font-weight": "600",
    },
}


def render_sidebar_nav(current_page: str) -> str:
    """Render the sidebar navigation menu and return the selected page key.

    Parameters
    ----------
    current_page : str
        The page key of the currently active page (e.g. "app", "pages/1_stats").
        Used to set the default selected item.

    Returns
    -------
    str
        The page key the user selected (may differ from *current_page* if they
        clicked a different item).
    """
    labels = [item[0] for item in MENU_ITEMS]
    icons = [item[1] for item in MENU_ITEMS]
    keys = [item[2] for item in MENU_ITEMS]

    # Determine default index
    default_idx = 0
    # 处理当前页面路径，去掉"pages/"前缀
    if current_page.startswith("pages/"):
        current_page = current_page[len("pages/"):]
    for i, key in enumerate(keys):
        if key == current_page:
            default_idx = i
            break

    with st.sidebar:
        selected_label = option_menu(
            menu_title="Poker Advisor",
            options=labels,
            icons=icons,
            default_index=default_idx,
            styles=MENU_STYLES,
        )

    # Map label back to page key
    selected_key = keys[labels.index(selected_label)]

    # Navigate if the user clicked a different page
    if selected_key != current_page:
        if selected_key == "app":
            st.switch_page("app.py")
        else:
            st.switch_page(f"pages/{selected_key}.py")

    return selected_key
