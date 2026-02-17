"""HandRecord - the core data structure for a single poker hand."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from poker_advisor.models.card import Card
from poker_advisor.models.action import PlayerAction, Street
from poker_advisor.models.position import Position


@dataclass
class HandRecord:
    """Complete record of a single poker hand."""

    hand_id: int = 0
    timestamp: str = ""
    session_id: str = ""

    # Table info
    player_count: int = 0
    dealer_seat: int = 0
    small_blind: float = 0.0
    big_blind: float = 0.0

    # Player info: seat -> name
    players: Dict[int, str] = field(default_factory=dict)
    # seat -> position
    positions: Dict[int, Position] = field(default_factory=dict)
    # seat -> stack at start
    stacks: Dict[int, float] = field(default_factory=dict)

    # Hero info
    hero_seat: Optional[int] = None
    hero_cards: List[Card] = field(default_factory=list)
    hero_name: Optional[str] = None

    # Community cards
    flop: List[Card] = field(default_factory=list)
    turn: Optional[Card] = None
    river: Optional[Card] = None

    # Actions per street
    actions: List[PlayerAction] = field(default_factory=list)

    # Showdown
    shown_cards: Dict[int, List[Card]] = field(default_factory=dict)

    # Results: seat -> net amount won/lost
    pot_total: float = 0.0
    winners: Dict[int, float] = field(default_factory=dict)

    # Uncalled bet returns: seat -> amount returned
    uncalled_bets: Dict[int, float] = field(default_factory=dict)

    @property
    def board(self) -> List[Card]:
        cards = list(self.flop)
        if self.turn:
            cards.append(self.turn)
        if self.river:
            cards.append(self.river)
        return cards

    @property
    def board_str(self) -> str:
        return " ".join(str(c) for c in self.board) if self.board else ""

    @property
    def hero_cards_str(self) -> str:
        return " ".join(str(c) for c in self.hero_cards) if self.hero_cards else ""

    def actions_on_street(self, street: Street) -> List[PlayerAction]:
        return [a for a in self.actions if a.street == street]

    @property
    def streets_seen(self) -> List[Street]:
        streets = [Street.PREFLOP]
        if self.flop:
            streets.append(Street.FLOP)
        if self.turn:
            streets.append(Street.TURN)
        if self.river:
            streets.append(Street.RIVER)
        return streets

    def hero_actions(self) -> List[PlayerAction]:
        if self.hero_seat is None:
            return []
        return [a for a in self.actions if a.seat == self.hero_seat]

    def hero_actions_on_street(self, street: Street) -> List[PlayerAction]:
        return [a for a in self.hero_actions() if a.street == street]

    @property
    def hero_position(self) -> Optional[Position]:
        if self.hero_seat is None:
            return None
        return self.positions.get(self.hero_seat)

    @property
    def went_to_showdown(self) -> bool:
        return len(self.shown_cards) > 0

    @property
    def hero_won(self) -> bool:
        return self.hero_seat is not None and self.hero_seat in self.winners

    @property
    def hand_type(self) -> str:
        """识别手牌类型（简化版）"""
        # 组合英雄手牌和公共牌
        all_cards = self.hero_cards + self.board

        if not all_cards:
            return "未知牌型"

        # 统计牌的数值和花色
        rank_counts = {}
        suit_counts = {}

        for card in all_cards:
            rank = card.rank.numeric_value
            suit = card.suit

            rank_counts[rank] = rank_counts.get(rank, 0) + 1
            suit_counts[suit] = suit_counts.get(suit, 0) + 1

        # 识别牌型
        if 4 in rank_counts.values():
            return "四条"
        if 3 in rank_counts.values() and 2 in rank_counts.values():
            return "葫芦"
        if max(suit_counts.values()) >= 5:
            # 检查是否是同花顺
            suited_cards = [c for c in all_cards if c.suit == max(suit_counts, key=suit_counts.get)]
            if self._has_straight(suited_cards):
                # 检查是否是皇家同花顺
                all_ranks = [c.rank.numeric_value for c in all_cards]
                has_royal = 14 in all_ranks and 13 in all_ranks and 12 in all_ranks and 11 in all_ranks and 10 in all_ranks
                if has_royal:
                    return "皇家同花顺"
                else:
                    return "同花顺"
            else:
                return "同花"
        if max(suit_counts.values()) >= 5:
            return "同花"

        # 检查是否有顺子
        has_straight = self._has_straight(all_cards)

        # 检查是否有其他牌型
        has_three_of_a_kind = 3 in rank_counts.values()
        has_two_pairs = list(rank_counts.values()).count(2) >= 2
        has_one_pair = 2 in rank_counts.values()

        if has_three_of_a_kind:
            return "三条"
        elif has_two_pairs:
            return "两对"
        elif has_one_pair:
            return "一对"
        elif has_straight:
            return "顺子"
        else:
            return "高牌"

    def _has_straight(self, cards) -> bool:
        """判断是否有顺子"""
        if len(cards) < 5:
            return False

        ranks = sorted([card.rank.numeric_value for card in cards])
        unique_ranks = sorted(list(set(ranks)))

        # 检查是否有连续的5个数值
        for i in range(len(unique_ranks) - 4):
            if unique_ranks[i+4] - unique_ranks[i] == 4:
                return True

        # 检查A-2-3-4-5的特殊情况
        if 14 in unique_ranks and 2 in unique_ranks and 3 in unique_ranks and 4 in unique_ranks and 5 in unique_ranks:
            return True

        return False

    def get_hand_strength(self) -> int:
        """计算手牌强度（简化版）"""
        # 根据手牌类型返回强度值
        # 高牌: 0, 一对: 1, 两对: 2, 三条: 3, 顺子: 4, 同花: 5, 葫芦: 6, 四条: 7, 同花顺: 8, 皇家同花顺: 9
        type_map = {
            "高牌": 0,
            "一对": 1,
            "两对": 2,
            "三条": 3,
            "顺子": 4,
            "同花": 5,
            "葫芦": 6,
            "四条": 7,
            "同花顺": 8,
            "皇家同花顺": 9
        }

        return type_map.get(self.hand_type, 0)

    def summary(self) -> str:
        parts = [f"Hand #{self.hand_id}"]
        if self.hero_cards:
            parts.append(f"Hero: {self.hero_cards_str}")
        if self.hero_position:
            parts.append(f"Pos: {self.hero_position.value}")
        if self.board:
            parts.append(f"Board: {self.board_str}")
        parts.append(f"Pot: ${self.pot_total:.2f}")
        if self.hero_won:
            parts.append("(Won)")
        return " | ".join(parts)
