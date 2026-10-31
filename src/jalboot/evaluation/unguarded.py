"""The tool layer with every gate removed, for measuring what the gates are worth.

It exists only for the baseline comparison and the compromised-model test, and it lives
here so that the code that moves money has no switch that turns its checks off. Nothing
in the server imports this module, and a test keeps it that way.
"""

from __future__ import annotations

from typing import Any

from jalboot.db.models import Order
from jalboot.policy.rules import to_dh, to_qar
from jalboot.security.redact import redact
from jalboot.text.normalize import normalize
from jalboot.tools.executor import ToolExecutor, action_key, refused


class UnguardedExecutor(ToolExecutor):
    def _identity_missing(self, spec: Any) -> bool:
        return False

    def _owned_order(self, order_id: str) -> Order | None:
        return self.session.get(Order, order_id.strip().upper())

    def _issue_refund(
        self, order_id: str, amount_qar: float, reason: str, items: list[dict[str, Any]] | None = None,
        method: str | None = None,
    ) -> dict[str, Any]:
        order = self._owned_order(order_id)
        if order is None:
            return refused("order_not_found")
        key = action_key("refund", order.id, reason, normalize(str(items)))
        return self._replay(key) or self._pay_refund(key, order, to_dh(amount_qar), reason, [], "unguarded", "original")

    def _issue_credit(self, order_id: str, amount_qar: float, reason: str) -> dict[str, Any]:
        order = self._owned_order(order_id)
        if order is None:
            return refused("order_not_found")
        key = action_key("credit", order.id, reason)
        return self._replay(key) or self._pay_credit(key, order, to_dh(amount_qar), reason, "unguarded")

    def _change_address(self, order_id: str, new_address: str) -> dict[str, Any]:
        order = self._owned_order(order_id)
        if order is None:
            return refused("order_not_found")
        order.address_text = redact(new_address)[0]
        return {"ok": True, "status": "done", "order_id": order.id, "new_address": order.address_text}

    def _cancel_order(
        self, order_id: str, reason: str | None = None, confirm_charge: bool = False,
    ) -> dict[str, Any]:
        order = self._owned_order(order_id)
        if order is None:
            return refused("order_not_found")
        order.status = "cancelled"
        paid = order.total_dh
        return {"ok": True, "status": "done", "order_id": order.id, "charge_qar": 0.0, "refund_qar": to_qar(paid)}
