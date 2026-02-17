# Web 页面数据分析问题详细说明

## 用户报告的问题

Web 页面显示"女神异闻录"的数据：
1. 收益: **$+12408.00** ❌
2. 每百手大盲: **+21174.1** ❌
3. VPIP: **56.0%** ✅
4. PFR: **21.5%** ✅
5. 3bet: **6.3%** ✅
6. AF: **1.53** ✅
7. C-Bet%: **40%** ✅
8. WTSD%: **83.4%** ✅

---

## 问题根源分析

### 问题 1：收益计算错误 (差额 $19456)

**位置**: `web/pages/1_stats.py` 第 169-177 行

**BUG 代码**:
```python
hero_invested = sum(
    a.amount for a in h.actions
    if h.hero_seat is not None and a.seat == h.hero_seat
)
profit = hero_won_amt - hero_invested  # ❌ 没有减去 uncalled_bets!
```

**应该改为**:
```python
from poker_advisor.analysis.calculator import StatsCalculator
calc = StatsCalculator()
hero_invested = calc._total_invested(h, h.hero_seat)  # ✅ 减去了 uncalled_bets
profit = hero_won_amt - hero_invested
```

**原因**: 页面没有使用 `StatsCalculator._total_invested()`，而是直接求和 action amounts，导致没有减去 `uncalled_bets`！

---

### 问题 2：BB/100 计算错误 (被夸大 100 倍)

**位置**: `src/poker_advisor/parser/pokernow_parser.py` 第 60-62 行

**BUG 代码**:
```python
def __init__(self):
    self._current_small_blind = 0.10   # ❌ 应该是 10，不是 0.10
    self._current_big_blind = 0.20     # ❌ 应该是 20，不是 0.20
```

**原因**:
- 这个日志使用的是**整数单位**（"posts a big blind of 20" = $20）
- 但 parser 默认值是 0.10/0.20（假设是美分单位）
- 由于日志中没有 "Blinds changed" 消息，一直使用错误的默认值
- BB/100 公式: `(profit / bb_size) / hands * 100`
- 当 bb_size 是 0.2 而不是 20 时，结果被夸大 **100 倍**！

---

## 正确的数据应该是

| 指标 | 错误值 | 正确值 | 说明 |
|------|--------|--------|------|
| 收益 | $12408 | $31864 | 差额 $19456 = uncalled_bets 总和 |
| BB/100 | 21174.1 | ~543.7 | 除以 100 (从 0.2 修正为 20) |
| VPIP | 56.0% | 56.0% | ✅ 正确 |
| PFR | 21.5% | 21.5% | ✅ 正确 |
| 3bet | 6.3% | 6.3% | ✅ 正确 |
| AF | 1.53 | 1.53 | ✅ 正确 |
| C-Bet% | 40% | 40% | ✅ 正确 |
| WTSD% | 83.4% | 83.4% | ✅ 正确 |

---

## 验证结果 - "女神异闻录"

- **总手牌**: 293
- **总收益**: $31864 (正确)
- **VPIP**: 56.0%
- **PFR**: 21.5%
- **3-Bet%**: 6.3%
- **AF**: 1.53
- **C-Bet%**: 40.0%
- **WTSD%**: 83.4%
