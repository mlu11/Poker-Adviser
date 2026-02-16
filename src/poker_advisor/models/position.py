"""Position model and seat mapping algorithm."""

from enum import Enum
from typing import Dict, List


class Position(str, Enum):
    UTG = "UTG"
    UTG1 = "UTG+1"
    MP = "MP"
    MP1 = "MP+1"
    HJ = "HJ"
    CO = "CO"
    BTN = "BTN"
    SB = "SB"
    BB = "BB"

    @property
    def is_early(self) -> bool:
        return self in (Position.UTG, Position.UTG1)

    @property
    def is_middle(self) -> bool:
        return self in (Position.MP, Position.MP1, Position.HJ)

    @property
    def is_late(self) -> bool:
        return self in (Position.CO, Position.BTN)

    @property
    def is_blind(self) -> bool:
        return self in (Position.SB, Position.BB)

    @property
    def category(self) -> str:
        if self.is_early:
            return "Early"
        if self.is_middle:
            return "Middle"
        if self.is_late:
            return "Late"
        return "Blinds"


def assign_positions(
    seats: List[int],
    dealer_seat: int,
) -> Dict[int, Position]:
    """Assign positions based on occupied seats and dealer button.

    Seats are numbered. The dealer button seat determines BTN.
    Positions assigned clockwise from BTN: SB, BB, UTG, ...

    Args:
        seats: List of occupied seat numbers (sorted).
        dealer_seat: The seat number with the dealer button.

    Returns:
        Mapping from seat number to Position.
    """
    n = len(seats)
    if n < 2:
        return {}

    sorted_seats = sorted(seats)
    # Find dealer index
    dealer_idx = sorted_seats.index(dealer_seat)

    # Order players clockwise starting after dealer
    ordered = []
    for i in range(n):
        idx = (dealer_idx + i) % n
        ordered.append(sorted_seats[idx])

    # ordered[0] = BTN (dealer)
    # For heads-up (2 players): BTN=SB, other=BB
    if n == 2:
        return {ordered[0]: Position.SB, ordered[1]: Position.BB}

    # Position assignment templates by player count
    position_orders = {
        3: [Position.BTN, Position.SB, Position.BB],
        4: [Position.BTN, Position.SB, Position.BB, Position.UTG],
        5: [Position.BTN, Position.SB, Position.BB, Position.UTG, Position.CO],
        6: [Position.BTN, Position.SB, Position.BB, Position.UTG, Position.MP, Position.CO],
        7: [Position.BTN, Position.SB, Position.BB, Position.UTG, Position.MP, Position.HJ, Position.CO],
        8: [Position.BTN, Position.SB, Position.BB, Position.UTG, Position.UTG1, Position.MP, Position.HJ, Position.CO],
        9: [Position.BTN, Position.SB, Position.BB, Position.UTG, Position.UTG1, Position.MP, Position.MP1, Position.HJ, Position.CO],
        10: [Position.BTN, Position.SB, Position.BB, Position.UTG, Position.UTG1, Position.MP, Position.MP1, Position.HJ, Position.CO, Position.BTN],
    }

    positions = position_orders.get(n, position_orders[9][:n])
    return {seat: pos for seat, pos in zip(ordered, positions)}
