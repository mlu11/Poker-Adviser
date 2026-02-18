# PokerMaster Pro V2

**项目:** 德州扑克AI智能分析训练系统
**技术栈:** Python + SQLite + Streamlit + Typer + Plotly + Doubao API

---

## 已知陷阱（开发必读）

### Parser / 数据解析
- Poker Now 日志中金额是**累计值**（cumulative），需要转换为增量值（incremental）。例如 `raises to 200` 是下注总额，不是加注量
- uncalled bet 需要从 total_invested 中扣除，否则底池计算会偏大
- 金额单位是整数（不需要除以 100），`_parse_amount()` 直接返回 raw 值
- CSV 日志行按时间倒序排列（最新在前），解析时需要反转

### 数据模型
- `hand.went_to_showdown` 是手牌级别标志，表示该手牌是否进入了摊牌阶段，**不代表 hero 参与了摊牌**
- `hero_folded` 需要检查 hero 的 action 列表判断，不能仅依赖 `went_to_showdown`
- 位置分配因桌型人数不同而异，UTG+1 仅在 8+ 人桌存在；6 人桌位置：BTN/SB/BB/UTG/MP/CO

### 数据库
- `hands` 表通过 `UNIQUE(session_id, hand_id)` 防止重复导入
- `analysis_results` 表通过 `UNIQUE(hand_id, session_id, analysis_type)` 防止重复缓存
- 删除 session 时需要级联删除相关的 actions、players、winners、uncalled_bets（FK ON DELETE CASCADE）

### Web UI
- Streamlit 页面文件名前缀数字决定侧栏排序（1_stats.py, 2_leaks.py, ...）
- `navigation.py` 中的路径映射必须与页面文件名精确对应，否则导航跳转会失败

---

## 代码规范

### Web 页面
- 使用 `streamlit_antd_components as sac` 的 `sac.tabs()` 做 Tab 导航，不使用 `st.tabs()`
- 所有指标展示用 `ui.metric_card(title, content, description)` (shadcn_ui)
- 暗色主题：参考 `web/theme.py` 中的 `COLORS` 字典，所有自定义样式需适配暗色背景
- 每个页面开头调用 `inject_theme()` 注入全局 CSS
- 新 Web 页面模板：参考 `web/pages/4_training.py` 的结构（sac.tabs + 多 Tab 布局）

### 分析模块
- 漏洞定级使用 S/A/B/C 四级（不再使用 minor/moderate/major）
- EV 损失按 BB/100 量化，经验公式：0.35 BB/100 per 百分点偏差
- GTO 基线数据在 `config/baselines.json`，支持总体和位置分组

### 数据库操作
- 所有 Repository 方法在 `src/poker_advisor/storage/repository.py`
- 新表必须同步更新 `schema.sql` 和 `database.py` 的 `initialize()` 方法
- 使用参数化查询（`?` 占位符），严禁字符串拼接 SQL

### CLI
- 使用 Typer 框架，命令函数在 `cli/main.py`
- 输出使用 Rich 格式化（`Console`, `Table`, `Panel`）

---

## 开发工作流

### 推荐节奏
1. **需求分析** → 进入 Plan Mode，用 Explore agent 并行搜索相关代码
2. **实施** → 原子 commit（每个功能单元独立实施 + 验证 + commit）
3. **审查** → 用 code-reviewer + silent-failure-hunter 并行审查
4. **验证** → Web 改动后运行 `/verify-results` 做端到端验证

### Skills
- `/verify-results` — Web 应用端到端浏览器自动化验证
- `/import-and-verify` — Parser/Storage 修改后导入验证
- `/run-tests` — 运行 pytest 并诊断失败
- `/db-inspect` — 数据库一致性检查

---

## 已完成功能

### P0: 分析诊断 + 批量复盘
- ROI / WWSF% 指标、S/A/B/C 四级定级、EV 损失量化（BB/100）
- GTO 基线配置化（`config/baselines.json`）
- 分析结果缓存（`analysis_results` 表）、批量复盘（Top N 高 EV 损失手牌）

### P1: 手牌库 + 训练中心 + Web 重组
- 多条件手牌筛选、错题本/收藏系统（bookmarks 表）
- 训练方案自动生成、难度动态调整（BEGINNER → EXPERT）
- Web 导航重组：首页/数据分析/复盘中心/训练中心/手牌历史/数据管理

### P2: 复盘笔记
- review_notes 表 + 标签系统

---

## 剩余任务

- [ ] 2.4 能力画像雷达图 + 2.6 时间维度分析
- [ ] 3.3 对局还原时间线
- [ ] 5.x GTO策略库、对手分析、下风期预警、知识库、数据导出

---

## 项目结构

```
src/poker_advisor/
  parser/          # Poker Now 日志解析
  models/          # 数据模型（hand, action, card, position, stats）
  analysis/        # 漏洞检测、统计计算、批量复盘
  storage/         # SQLite 数据库（schema.sql, repository.py）
  ai/              # Doubao API 客户端 + 分析 prompts
  training/        # 训练方案生成 + 训练会话
  formatters/      # CLI 输出格式化
cli/               # Typer CLI（16 个命令）
web/               # Streamlit Web UI（6 个页面）
config/            # baselines.json, skills.json
tests/             # pytest 测试（6 个测试文件）
```
