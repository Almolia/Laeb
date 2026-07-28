"""services/catalog/app/domain/state_machine.py — pure domain, no framework imports."""
from enum import StrEnum


class DomainError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.message, self.status = code, message, status


class GameState(StrEnum):
    SUBMITTED = "Submitted"
    UNDER_REVIEW = "UnderReview"
    REJECTED = "Rejected"
    PRICE_SUGGESTED = "PriceSuggested"
    PRICE_PROPOSED = "PriceProposed"
    PUBLISHED = "Published"


# transition -> (from_state, to_state, required_role, owner_only)
TRANSITIONS = {
    "start_review": (GameState.SUBMITTED, GameState.UNDER_REVIEW, "SUPPORT", False),
    "reject": (GameState.UNDER_REVIEW, GameState.REJECTED, "SUPPORT", False),
    "approve": (GameState.UNDER_REVIEW, GameState.PRICE_SUGGESTED, "SUPPORT", False),
    "set_price": (GameState.PRICE_SUGGESTED, GameState.PRICE_PROPOSED, "DEVELOPER", True),
    "publish": (GameState.PRICE_PROPOSED, GameState.PUBLISHED, "SUPPORT", False),
    "resubmit": (GameState.REJECTED, GameState.SUBMITTED, "DEVELOPER", True),
}


def check(
    transition: str,
    current: GameState,
    actor_roles: list[str],
    actor_id: str,
    developer_id: str,
) -> GameState:
    if transition not in TRANSITIONS:
        raise DomainError("UNKNOWN_TRANSITION", transition, 400)
    src, dst, role, owner_only = TRANSITIONS[transition]
    if current is not src:
        raise DomainError(
            "ILLEGAL_TRANSITION",
            f"Cannot {transition} from {current}; expected {src}",
            409,
        )
    if role not in actor_roles and "ADMIN" not in actor_roles:
        raise DomainError("FORBIDDEN", f"{transition} requires {role}", 403)
    if owner_only and actor_id != developer_id:
        raise DomainError(
            "NOT_GAME_OWNER",
            "Only the owning developer may do this",
            403,
        )
    return dst
