"""Data management page — batch import, session management, and deletion."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
from pathlib import Path

import streamlit as st
import streamlit_shadcn_ui as ui
import streamlit_antd_components as sac
import pandas as pd

from poker_advisor.storage import Database, HandRepository
from poker_advisor.parser.pokernow_parser import PokerNowParser

from theme import inject_theme
from navigation import render_sidebar_nav

st.set_page_config(page_title="数据管理", page_icon="🗄", layout="wide")
inject_theme()
render_sidebar_nav("pages/6_management")

st.title("🗄 数据管理")

db = Database()
repo = HandRepository(db)

# --- Tabs ---
selected_tab = sac.tabs([
    sac.TabsItem(label="批量导入", icon="cloud-upload"),
    sac.TabsItem(label="会话管理", icon="table"),
    sac.TabsItem(label="数据导出", icon="download"),
    sac.TabsItem(label="危险操作", icon="exclamation-triangle"),
], color="green")

# ============================================================
# Tab 1: Batch Import
# ============================================================
if selected_tab == "批量导入":
    st.subheader("📤 批量导入日志文件")
    st.caption("支持同时上传多个 Poker Now 日志文件，每个文件将作为独立会话导入。")

    uploaded_files = st.file_uploader(
        "选择日志文件（支持多选）",
        type=["csv", "txt"],
        accept_multiple_files=True,
        key="batch_upload",
    )
    shared_notes = st.text_input("共享备注（可选，将应用到每个文件）", key="batch_notes")

    if uploaded_files and st.button("开始导入", type="primary", key="run_import"):
        total = len(uploaded_files)
        results = []
        progress_bar = st.progress(0, text=f"正在导入 0/{total} ...")

        for i, uploaded in enumerate(uploaded_files):
            progress_bar.progress((i) / total, text=f"正在导入 {i + 1}/{total}: {uploaded.name}")
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
                    tmp.write(uploaded.getvalue())
                    tmp_path = tmp.name

                parser = PokerNowParser()
                hands = parser.parse_file(tmp_path)

                if not hands:
                    results.append({
                        "文件名": uploaded.name,
                        "状态": "失败",
                        "手牌数": 0,
                        "会话ID": "-",
                        "原因": "未找到手牌数据",
                    })
                else:
                    session_id = repo.save_session(
                        hands, filename=uploaded.name, notes=shared_notes,
                    )
                    results.append({
                        "文件名": uploaded.name,
                        "状态": "成功",
                        "手牌数": len(hands),
                        "会话ID": session_id,
                        "原因": "",
                    })
            except Exception as e:
                results.append({
                    "文件名": uploaded.name,
                    "状态": "失败",
                    "手牌数": 0,
                    "会话ID": "-",
                    "原因": str(e),
                })
            finally:
                if tmp_path:
                    Path(tmp_path).unlink(missing_ok=True)

        progress_bar.progress(1.0, text="导入完成！")

        # Summary metrics
        success_count = sum(1 for r in results if r["状态"] == "成功")
        total_hands = sum(r["手牌数"] for r in results)
        fail_count = total - success_count

        col1, col2, col3 = st.columns(3)
        with col1:
            ui.metric_card(title="成功导入", content=f"{success_count} 个文件",
                          description=f"共 {total} 个文件", key="import_success")
        with col2:
            ui.metric_card(title="总手牌数", content=str(total_hands),
                          description="新增手牌", key="import_hands")
        with col3:
            ui.metric_card(title="导入失败", content=f"{fail_count} 个文件",
                          description="请检查文件格式", key="import_fail")

        # Detail table
        st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)

# ============================================================
# Tab 2: Session Management
# ============================================================
elif selected_tab == "会话管理":
    st.subheader("📋 会话管理")

    sessions = repo.get_sessions()
    total_hands = repo.get_hand_count()

    # Overview metrics
    col1, col2 = st.columns(2)
    with col1:
        ui.metric_card(title="总会话数", content=str(len(sessions)),
                      description="已导入的会话", key="mgmt_sessions")
    with col2:
        ui.metric_card(title="总手牌数", content=str(total_hands),
                      description="所有会话合计", key="mgmt_hands")

    if not sessions:
        st.info("暂无会话数据。请先在「批量导入」标签页导入日志文件。")
        st.stop()

    # Sessions table with AgGrid
    from st_aggrid import AgGrid, GridOptionsBuilder

    df_sessions = pd.DataFrame(sessions)
    display_cols = []
    col_mapping = {}
    for original, display in [("id", "会话ID"), ("filename", "文件名"),
                               ("hand_count", "手牌数"), ("import_date", "导入时间"),
                               ("notes", "备注")]:
        if original in df_sessions.columns:
            display_cols.append(original)
            col_mapping[original] = display

    df_display = df_sessions[display_cols].copy()
    df_display.rename(columns=col_mapping, inplace=True)

    gb = GridOptionsBuilder.from_dataframe(df_display)
    gb.configure_default_column(sortable=True, filterable=True, resizable=True)
    gb.configure_selection(selection_mode="single", use_checkbox=False)
    if "手牌数" in df_display.columns:
        gb.configure_column("手牌数", type=["numericColumn"], width=100)
    grid_opts = gb.build()

    grid_response = AgGrid(
        df_display,
        gridOptions=grid_opts,
        theme="alpine-dark",
        height=300,
        fit_columns_on_grid_load=True,
        key="sessions_grid",
    )

    # Session detail panel
    selected_rows = grid_response.get("selected_rows", None)
    if selected_rows is not None and len(selected_rows) > 0:
        selected_session_id = selected_rows.iloc[0]["会话ID"]

        sac.divider(label="会话详情", icon="info-circle", color="green")

        detail = repo.get_session_detail(selected_session_id)
        if detail:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                ui.metric_card(title="手牌数", content=str(detail["total_hands"]),
                              description="总局数", key="detail_hands")
            with c2:
                ui.metric_card(title="胜率", content=f"{detail['win_rate']}%",
                              description=f"{detail['wins']} 局胜出", key="detail_winrate")
            with c3:
                ui.metric_card(title="平均底池", content=f"${detail['avg_pot']:.0f}",
                              description="每局平均", key="detail_pot")
            with c4:
                ui.metric_card(title="摊牌数", content=str(detail["showdowns"]),
                              description="进入摊牌", key="detail_showdown")

            st.markdown(
                f'<div style="display:flex;gap:20px;padding:12px 16px;'
                f'background:rgba(255,255,255,0.03);border:1px solid #333;border-radius:8px;'
                f'margin-top:8px;">'
                f'<span style="color:#aaa;">📌 收藏: <strong style="color:#fff;">'
                f'{detail["bookmarks_count"]}</strong> 条</span>'
                f'<span style="color:#aaa;">🧠 分析缓存: <strong style="color:#fff;">'
                f'{detail["analysis_count"]}</strong> 条</span>'
                f'<span style="color:#aaa;">📝 复盘笔记: <strong style="color:#fff;">'
                f'{detail["notes_count"]}</strong> 条</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.warning("无法加载会话详情。")

# ============================================================
# Tab 3: Data Export
# ============================================================
elif selected_tab == "数据导出":
    st.subheader("📥 数据导出")
    st.caption("导出数据为 CSV 或 JSON 格式，便于外部分析。")

    # Session filter for export
    sessions = repo.get_sessions()
    export_options = {"全部会话": None}
    for s in sessions:
        label = f"{s['filename']} ({s['hand_count']} hands, {s['id']})"
        export_options[label] = s["id"]

    selected_export = st.selectbox("选择要导出的会话", options=list(export_options.keys()), key="export_session")
    export_session_id = export_options[selected_export]

    # Export format selection
    export_format = st.radio("导出格式", ["CSV", "JSON"], horizontal=True, key="export_format")

    # What to export
    export_type = st.radio(
        "导出内容",
        ["手牌概要", "完整手牌数据（含动作）", "统计分析结果"],
        horizontal=True,
        key="export_type"
    )

    if st.button("生成导出文件", type="primary", key="btn_export"):
        hands = repo.get_all_hands(session_id=export_session_id)

        if not hands:
            st.warning("没有可导出的数据。")
        else:
            import io
            import json
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            if export_type == "手牌概要":
                # Export summary as CSV
                summary_data = []
                for h in hands:
                    hero_pos = h.positions.get(h.hero_seat)
                    summary_data.append({
                        "hand_id": h.hand_id,
                        "session_id": h.session_id,
                        "timestamp": h.timestamp,
                        "hero_position": hero_pos.value if hero_pos else None,
                        "hero_cards": ", ".join(c.to_short() for c in h.hero_cards) if h.hero_cards else None,
                        "board": " ".join(c.to_short() for c in h.flop + ([h.turn] if h.turn else []) + ([h.river] if h.river else [])),
                        "pot_total": h.pot_total,
                        "hero_won": h.hero_won,
                        "went_to_showdown": h.went_to_showdown,
                    })

                df = pd.DataFrame(summary_data)

                if export_format == "CSV":
                    csv_buffer = io.StringIO()
                    df.to_csv(csv_buffer, index=False, encoding="utf-8")
                    csv_str = csv_buffer.getvalue()

                    st.download_button(
                        label="📥 下载 CSV",
                        data=csv_str,
                        file_name=f"poker_hands_summary_{timestamp}.csv",
                        mime="text/csv",
                    )
                else:
                    json_str = json.dumps(summary_data, ensure_ascii=False, indent=2, default=str)
                    st.download_button(
                        label="📥 下载 JSON",
                        data=json_str,
                        file_name=f"poker_hands_summary_{timestamp}.json",
                        mime="application/json",
                    )

                st.success(f"已生成导出文件，共 {len(summary_data)} 条记录。")
                st.dataframe(df, use_container_width=True)

            elif export_type == "完整手牌数据（含动作）":
                # Export full data with actions
                full_data = []
                for h in hands:
                    hand_dict = {
                        "hand_id": h.hand_id,
                        "session_id": h.session_id,
                        "timestamp": h.timestamp,
                        "player_count": h.player_count,
                        "small_blind": h.small_blind,
                        "big_blind": h.big_blind,
                        "hero_seat": h.hero_seat,
                        "hero_name": h.hero_name,
                        "hero_cards": [c.to_short() for c in h.hero_cards],
                        "flop": [c.to_short() for c in h.flop],
                        "turn": h.turn.to_short() if h.turn else None,
                        "river": h.river.to_short() if h.river else None,
                        "pot_total": h.pot_total,
                        "hero_won": h.hero_won,
                        "went_to_showdown": h.went_to_showdown,
                        "players": h.players,
                        "positions": {s: p.value for s, p in h.positions.items()},
                        "stacks": h.stacks,
                        "winners": h.winners,
                        "uncalled_bets": h.uncalled_bets,
                        "actions": [
                            {
                                "player_name": a.player_name,
                                "seat": a.seat,
                                "action_type": a.action_type.value,
                                "amount": a.amount,
                                "street": a.street.value,
                                "is_all_in": a.is_all_in,
                            }
                            for a in h.actions
                        ],
                    }
                    full_data.append(hand_dict)

                json_str = json.dumps(full_data, ensure_ascii=False, indent=2, default=str)
                st.download_button(
                    label="📥 下载 JSON",
                    data=json_str,
                    file_name=f"poker_hands_full_{timestamp}.json",
                    mime="application/json",
                )
                st.success(f"已生成导出文件，共 {len(full_data)} 条完整手牌记录。")

                with st.expander("预览数据结构"):
                    st.json(full_data[0] if full_data else {})

            elif export_type == "统计分析结果":
                # Export stats
                from poker_advisor.analysis.calculator import StatsCalculator
                calc = StatsCalculator()
                stats = calc.calculate(hands)

                stats_data = {
                    "export_timestamp": timestamp,
                    "session_id": export_session_id,
                    "total_hands": stats.overall.total_hands,
                    "total_profit": stats.total_profit,
                    "bb_per_100": stats.bb_per_100,
                    "overall": {
                        "vpip": stats.overall.vpip,
                        "pfr": stats.overall.pfr,
                        "three_bet_pct": stats.overall.three_bet_pct,
                        "aggression_factor": stats.overall.aggression_factor,
                        "cbet_pct": stats.overall.cbet_pct,
                        "folded_to_cbet_pct": stats.overall.folded_to_cbet_pct,
                        "wtsd": stats.overall.wtsd,
                        "wsd": stats.overall.wsd,
                        "wwsf": stats.overall.wwsf,
                    },
                    "positional": {},
                }

                # Add positional stats
                for pos, pos_stats in stats.positional.items():
                    stats_data["positional"][pos.value] = {
                        "total_hands": pos_stats.total_hands,
                        "vpip": pos_stats.vpip,
                        "pfr": pos_stats.pfr,
                        "three_bet_pct": pos_stats.three_bet_pct,
                        "aggression_factor": pos_stats.aggression_factor,
                        "cbet_pct": pos_stats.cbet_pct,
                        "wtsd": pos_stats.wtsd,
                        "wsd": pos_stats.wsd,
                    }

                json_str = json.dumps(stats_data, ensure_ascii=False, indent=2, default=str)
                st.download_button(
                    label="📥 下载 JSON",
                    data=json_str,
                    file_name=f"poker_stats_{timestamp}.json",
                    mime="application/json",
                )
                st.success("已生成统计分析导出文件。")
                st.json(stats_data)

# ============================================================
# Tab 4: Dangerous Operations
# ============================================================
elif selected_tab == "危险操作":
    st.subheader("⚠️ 危险操作")
    st.warning("以下操作不可撤销，请谨慎执行。")

    # --- Delete single session ---
    sac.divider(label="删除单个会话", icon="trash", color="red")

    sessions = repo.get_sessions()
    if not sessions:
        st.info("暂无会话数据。")
    else:
        session_options = {}
        for s in sessions:
            label = f"{s['id']} — {s['filename']} ({s['hand_count']} 手牌)"
            session_options[label] = s["id"]

        selected_label = st.selectbox("选择要删除的会话", options=list(session_options.keys()),
                                      key="delete_session_select")
        target_session_id = session_options[selected_label]

        # Show impact preview
        detail = repo.get_session_detail(target_session_id)
        if detail:
            st.markdown(
                f'<div style="padding:12px 16px;background:rgba(231,76,60,0.08);'
                f'border:1px solid #e74c3c;border-radius:8px;margin:8px 0;">'
                f'<div style="font-weight:bold;color:#e74c3c;margin-bottom:8px;">'
                f'将删除以下数据：</div>'
                f'<div style="color:#ccc;line-height:1.8;">'
                f'🃏 手牌记录: <strong>{detail["total_hands"]}</strong> 条<br>'
                f'📌 收藏/错题: <strong>{detail["bookmarks_count"]}</strong> 条<br>'
                f'🧠 分析缓存: <strong>{detail["analysis_count"]}</strong> 条<br>'
                f'📝 复盘笔记: <strong>{detail["notes_count"]}</strong> 条'
                f'</div></div>',
                unsafe_allow_html=True,
            )

        confirm_text = st.text_input(
            f"输入会话 ID `{target_session_id}` 以确认删除",
            key="confirm_delete_session",
        )

        if st.button("删除此会话", type="primary",
                     disabled=(confirm_text != target_session_id),
                     key="btn_delete_session"):
            result = repo.delete_session(target_session_id)
            st.success(
                f"已删除会话 `{result['session_id']}`：\n\n"
                f"- 手牌: {result['hands_deleted']} 条\n"
                f"- 收藏: {result['bookmarks_deleted']} 条\n"
                f"- 分析缓存: {result['analysis_deleted']} 条\n"
                f"- 复盘笔记: {result['notes_deleted']} 条"
            )
            st.rerun()

    # --- Delete all data ---
    sac.divider(label="清空所有数据", icon="radioactive", color="red")

    sessions_all = repo.get_sessions()
    total_hands_all = repo.get_hand_count()

    st.error(
        f"⚠️ 此操作将清空数据库中的所有数据，包括 "
        f"**{len(sessions_all)} 个会话** 和 **{total_hands_all} 手牌**，"
        f"以及所有收藏、分析缓存、复盘笔记和训练记录。此操作不可撤销！"
    )

    confirm_all = st.text_input(
        "输入「删除所有数据」以确认",
        key="confirm_delete_all",
    )

    if st.button("清空所有数据", type="primary",
                 disabled=(confirm_all != "删除所有数据"),
                 key="btn_delete_all"):
        result = repo.delete_all_data()
        lines = [f"- {table}: {count} 条" for table, count in result.items() if count > 0]
        summary = "\n".join(lines) if lines else "数据库已为空"
        st.success(f"已清空所有数据：\n\n{summary}")
        st.rerun()
