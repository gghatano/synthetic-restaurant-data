from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class IdFactory:
    counters: dict[str, int] = field(default_factory=dict)

    def _next(self, prefix: str, width: int = 8) -> str:
        current = self.counters.get(prefix, 0) + 1
        self.counters[prefix] = current
        return f"{prefix}{current:0{width}d}"

    def next_visit(self) -> str:
        return self._next("V")

    def next_order(self) -> str:
        return self._next("O")

    def next_order_item(self) -> str:
        return self._next("OI")

    def next_receipt(self) -> str:
        return self._next("R")

    def next_run(self) -> str:
        return self._next("RUN")

    def next_customer(self) -> str:
        return self._next("C")

    def next_menu_price_hist(self) -> str:
        return self._next("MPH")

    def next_tax_rate_hist(self) -> str:
        return self._next("TH")

    def next_change_log(self) -> str:
        return self._next("CH")

    @classmethod
    def from_existing_max(cls, max_values: dict[str, int]) -> "IdFactory":
        return cls(counters=dict(max_values))
