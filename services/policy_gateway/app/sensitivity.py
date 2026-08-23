from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class OpportunityAction:
    kind: str
    amount: Decimal | None = None
    discount_percent: Decimal | None = None
    regulated_product: bool = False


class SensitivityPolicy:
    def __init__(self, max_auto_discount="5", max_auto_amount="10000"):
        self.max_discount = Decimal(max_auto_discount)
        self.max_amount = Decimal(max_auto_amount)

    def evaluate(self, action: OpportunityAction) -> tuple[str, tuple[str, ...]]:
        reasons = []
        if action.kind in {"SIGN_CONTRACT", "TAKE_PAYMENT", "LEGAL_COMMITMENT", "GUARANTEE"}:
            reasons.append("PROHIBITED_AUTONOMOUS_ACTION")
        if action.discount_percent is not None and action.discount_percent > self.max_discount:
            reasons.append("DISCOUNT_REQUIRES_HUMAN")
        if action.amount is not None and action.amount > self.max_amount:
            reasons.append("AMOUNT_REQUIRES_HUMAN")
        if action.regulated_product:
            reasons.append("REGULATED_PRODUCT_REQUIRES_HUMAN")
        return ("HUMAN_REVIEW", tuple(reasons)) if reasons else ("ALLOW_RECOMMENDATION", ("WITHIN_LIMITS",))
