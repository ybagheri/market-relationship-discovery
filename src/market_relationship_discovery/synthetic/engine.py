from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from market_relationship_discovery.domain.errors import InvalidFormulaError
from market_relationship_discovery.domain.market import Quote
from market_relationship_discovery.relationships.formula import Expression, FormulaParser, Operation


class DiscrepancyKind(StrEnum):
    NONE = "none"
    THEORETICAL = "theoretical"
    EXECUTABLE = "executable"


@dataclass(frozen=True, slots=True)
class Discrepancy:
    kind: DiscrepancyKind
    absolute_difference: float
    percentage_difference: float
    buy_target_sell_synthetic: float
    sell_target_buy_synthetic: float


@dataclass(frozen=True, slots=True)
class SyntheticPriceResult:
    target_symbol: str
    formula: str
    theoretical_price: float
    executable_low: float
    executable_high: float
    discrepancy: Discrepancy | None


@dataclass(frozen=True, slots=True)
class _PriceRange:
    low: float
    high: float


class SyntheticPriceEngine:
    def evaluate(
        self,
        formula: str,
        quotes: Mapping[str, Quote],
        target_symbol: str | None = None,
    ) -> SyntheticPriceResult:
        try:
            expression = FormulaParser.parse(formula)
            interval = self._evaluate(expression, quotes)
            theoretical_price = self._evaluate_mid(expression, quotes)
        except (KeyError, ValueError, ZeroDivisionError) as exc:
            raise InvalidFormulaError(f"Cannot evaluate formula {formula!r}: {exc}") from exc
        target = target_symbol or self._target_from_expression(expression)
        actual = quotes.get(target)
        discrepancy = (
            self._discrepancy(actual, theoretical_price, interval) if actual is not None else None
        )
        return SyntheticPriceResult(
            target_symbol=target,
            formula=formula,
            theoretical_price=theoretical_price,
            executable_low=interval.low,
            executable_high=interval.high,
            discrepancy=discrepancy,
        )

    def _evaluate(self, expression: Expression, quotes: Mapping[str, Quote]) -> _PriceRange:
        if expression.symbol is not None:
            quote = quotes[expression.symbol]
            return _PriceRange(quote.bid, quote.ask)
        if expression.left is None or expression.right is None or expression.operation is None:
            raise ValueError("invalid expression node")
        left = self._evaluate(expression.left, quotes)
        right = self._evaluate(expression.right, quotes)
        match expression.operation:
            case Operation.ADD:
                return _PriceRange(left.low + right.low, left.high + right.high)
            case Operation.SUBTRACT:
                return _PriceRange(left.low - right.high, left.high - right.low)
            case Operation.MULTIPLY:
                return _PriceRange(left.low * right.low, left.high * right.high)
            case Operation.DIVIDE:
                if right.low <= 0:
                    raise ValueError("division denominator must be strictly positive")
                return _PriceRange(left.low / right.high, left.high / right.low)
        raise ValueError(f"unsupported operation: {expression.operation}")

    def _evaluate_mid(self, expression: Expression, quotes: Mapping[str, Quote]) -> float:
        if expression.symbol is not None:
            return quotes[expression.symbol].mid
        if expression.left is None or expression.right is None or expression.operation is None:
            raise ValueError("invalid expression node")
        left = self._evaluate_mid(expression.left, quotes)
        right = self._evaluate_mid(expression.right, quotes)
        match expression.operation:
            case Operation.ADD:
                return left + right
            case Operation.SUBTRACT:
                return left - right
            case Operation.MULTIPLY:
                return left * right
            case Operation.DIVIDE:
                if right == 0:
                    raise ValueError("division denominator must be non-zero")
                return left / right
        raise ValueError(f"unsupported operation: {expression.operation}")

    @staticmethod
    def _discrepancy(
        actual: Quote, theoretical_price: float, synthetic: _PriceRange
    ) -> Discrepancy:
        buy_edge = actual.bid - synthetic.high
        sell_edge = synthetic.low - actual.ask
        difference = actual.mid - theoretical_price
        if max(buy_edge, sell_edge) > 0:
            kind = DiscrepancyKind.EXECUTABLE
        elif difference != 0:
            kind = DiscrepancyKind.THEORETICAL
        else:
            kind = DiscrepancyKind.NONE
        return Discrepancy(
            kind=kind,
            absolute_difference=difference,
            percentage_difference=difference / theoretical_price * 100.0,
            buy_target_sell_synthetic=buy_edge,
            sell_target_buy_synthetic=sell_edge,
        )

    @staticmethod
    def _target_from_expression(expression: Expression) -> str:
        if expression.symbol is not None:
            return expression.symbol
        if expression.left is None or expression.right is None:
            raise ValueError("cannot infer target symbol")
        return sorted(expression.dependencies())[0]
