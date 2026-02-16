"""Global poker-themed dark color scheme, CSS overrides, and Plotly template."""

import streamlit as st

# --- Color palette ---
COLORS = {
    "bg_primary": "#1a1a2e",
    "bg_secondary": "#16213e",
    "bg_gradient_end": "#0f3460",
    "sidebar_bg": "#0d1b2a",
    "card_bg": "#1b2838",
    "card_border": "#2a3f5f",
    "accent_green": "#2ecc71",
    "accent_gold": "#f1c40f",
    "accent_red": "#e74c3c",
    "accent_blue": "#3498db",
    "text_primary": "#e8e8e8",
    "text_secondary": "#a0a0b0",
    "text_muted": "#6c7a89",
    "table_header": "#1e3a5f",
    "table_row_hover": "#1b2f4a",
    "button_primary": "#2ecc71",
    "button_primary_hover": "#27ae60",
    "divider": "#2a3f5f",
}

# --- Plotly dark layout template ---
PLOTLY_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=COLORS["text_primary"], family="Inter, sans-serif"),
    colorway=[
        COLORS["accent_green"],
        COLORS["accent_gold"],
        COLORS["accent_red"],
        COLORS["accent_blue"],
        "#9b59b6",
        "#1abc9c",
        "#e67e22",
        "#ecf0f1",
    ],
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        font=dict(color=COLORS["text_secondary"]),
    ),
    xaxis=dict(gridcolor="#2a3f5f", zerolinecolor="#2a3f5f"),
    yaxis=dict(gridcolor="#2a3f5f", zerolinecolor="#2a3f5f"),
    margin=dict(l=40, r=20, t=40, b=40),
)

# --- Global CSS overrides ---
POKER_THEME_CSS = f"""
<style>
/* App background */
.stApp {{
    background: linear-gradient(135deg, {COLORS['bg_primary']} 0%, {COLORS['bg_secondary']} 50%, {COLORS['bg_gradient_end']} 100%);
    color: {COLORS['text_primary']};
}}

/* Sidebar */
section[data-testid="stSidebar"] {{
    background: {COLORS['sidebar_bg']} !important;
}}
section[data-testid="stSidebar"] .stMarkdown {{
    color: {COLORS['text_primary']};
}}

/* Hide default Streamlit sidebar page links */
[data-testid="stSidebarNavItems"] {{
    display: none;
}}

/* Metric cards (shadcn) */
.stMetric, [data-testid="stMetric"] {{
    background: {COLORS['card_bg']};
    border: 1px solid {COLORS['card_border']};
    border-radius: 12px;
    padding: 16px;
}}

/* Expander */
.streamlit-expanderHeader {{
    background: {COLORS['card_bg']} !important;
    border-radius: 8px;
}}

/* Buttons */
.stButton > button[kind="primary"] {{
    background: {COLORS['button_primary']} !important;
    border: none;
    color: #fff !important;
}}
.stButton > button[kind="primary"]:hover {{
    background: {COLORS['button_primary_hover']} !important;
}}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {{
    gap: 8px;
}}
.stTabs [data-baseweb="tab"] {{
    background: {COLORS['card_bg']};
    border-radius: 8px 8px 0 0;
    color: {COLORS['text_secondary']};
}}
.stTabs [aria-selected="true"] {{
    background: {COLORS['bg_gradient_end']} !important;
    color: {COLORS['accent_green']} !important;
}}

/* AG Grid dark overrides */
.ag-theme-alpine-dark {{
    --ag-background-color: {COLORS['card_bg']};
    --ag-header-background-color: {COLORS['table_header']};
    --ag-odd-row-background-color: {COLORS['bg_secondary']};
    --ag-row-hover-color: {COLORS['table_row_hover']};
    --ag-border-color: {COLORS['card_border']};
    --ag-foreground-color: {COLORS['text_primary']};
    --ag-header-foreground-color: {COLORS['accent_gold']};
}}

/* shadcn-ui card overrides */
iframe[title="streamlit_shadcn_ui.card.card"] {{
    border: 1px solid {COLORS['card_border']} !important;
    border-radius: 12px !important;
}}

/* Progress bar */
.stProgress > div > div {{
    background: {COLORS['accent_green']} !important;
}}

/* Selectbox / inputs */
.stSelectbox > div > div,
.stTextInput > div > div {{
    background: {COLORS['card_bg']};
    border-color: {COLORS['card_border']};
    color: {COLORS['text_primary']};
}}

/* Caption text */
.stCaption {{
    color: {COLORS['text_muted']} !important;
}}

/* Scrollbar */
::-webkit-scrollbar {{
    width: 8px;
    height: 8px;
}}
::-webkit-scrollbar-track {{
    background: {COLORS['bg_primary']};
}}
::-webkit-scrollbar-thumb {{
    background: {COLORS['card_border']};
    border-radius: 4px;
}}
::-webkit-scrollbar-thumb:hover {{
    background: {COLORS['accent_green']};
}}
</style>
"""


def inject_theme():
    """Inject the global poker theme CSS into the current page."""
    st.markdown(POKER_THEME_CSS, unsafe_allow_html=True)
