from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class Operation(StrEnum):
    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"


@dataclass(frozen=True, slots=True)
class Expression:
    operation: Operation | None = None
    left: Expression | None = None
    right: Expression | None = None
    symbol: str | None = None

    @classmethod
    def symbol_node(cls, symbol: str) -> Expression:
        return cls(symbol=symbol)

    @classmethod
    def node(cls, operation: Operation, left: Expression, right: Expression) -> Expression:
        return cls(operation=operation, left=left, right=right)

    def dependencies(self) -> set[str]:
        if self.symbol is not None:
            return {self.symbol}
        if self.left is None or self.right is None:
            raise ValueError("invalid expression node")
        return self.left.dependencies() | self.right.dependencies()


def monomial_exponents(expression: Expression) -> dict[str, int] | None:
    """Return signed symbol exponents when the expression is a monomial ratio.

    Addition, subtraction, literals, and functions are not provable here, so the
    function returns ``None`` and callers fall back to syntactic identity.
    """
    if expression.symbol is not None:
        return {expression.symbol: 1}
    if expression.left is None or expression.right is None or expression.operation is None:
        return None
    left = monomial_exponents(expression.left)
    right = monomial_exponents(expression.right)
    if left is None or right is None:
        return None
    match expression.operation:
        case Operation.MULTIPLY:
            result = dict(left)
            for symbol, exponent in right.items():
                result[symbol] = result.get(symbol, 0) + exponent
        case Operation.DIVIDE:
            result = dict(left)
            for symbol, exponent in right.items():
                result[symbol] = result.get(symbol, 0) - exponent
        case _:
            return None
    return {symbol: exponent for symbol, exponent in result.items() if exponent != 0}


def semantic_key(expression: Expression) -> str:
    """Return a canonical identity key for provable monomial expressions."""
    exponents = monomial_exponents(expression)
    if exponents is None:
        return f"S|{canonical_formula_fallback(expression)}"
    body = ",".join(f"{symbol}^{exponent}" for symbol, exponent in sorted(exponents.items()))
    return f"M|{body}|C=1"


def canonical_formula_fallback(expression: Expression) -> str:
    if expression.symbol is not None:
        return expression.symbol
    if expression.left is None or expression.right is None or expression.operation is None:
        return "invalid"
    left = canonical_formula_fallback(expression.left)
    right = canonical_formula_fallback(expression.right)
    symbol = {"add": "+", "subtract": "-", "multiply": "*", "divide": "/"}[
        expression.operation.value
    ]
    return f"({left}{symbol}{right})"


def equivalent(first: Expression, second: Expression) -> bool:
    """Whether two expressions are proven equal by the semantic normal form."""
    return semantic_key(first) == semantic_key(second)


class FormulaParser:
    _token_pattern = re.compile(r"\s*(?:(?P<operator>[()*/+\-])|(?P<identifier>[A-Za-z0-9_.\-#]+))")

    def __init__(self, expression: str) -> None:
        self._expression = expression
        self._tokens = self._tokenize(expression)
        self._position = 0

    @classmethod
    def parse(cls, expression: str) -> Expression:
        if not expression.strip():
            raise ValueError("formula cannot be empty")
        parser = cls(expression)
        result = parser._parse_expression()
        parser._expect_end()
        return result

    @classmethod
    def _tokenize(cls, expression: str) -> list[str]:
        tokens: list[str] = []
        position = 0
        while position < len(expression):
            match = cls._token_pattern.match(expression, position)
            if match is None:
                raise ValueError(f"invalid character at position {position}")
            tokens.append(match.group("operator") or match.group("identifier"))
            position = match.end()
        if not tokens:
            raise ValueError("formula contains no tokens")
        return tokens

    def _parse_expression(self) -> Expression:
        value = self._parse_term()
        while self._peek() in {"+", "-"}:
            operator = self._consume()
            right = self._parse_term()
            operation = Operation.ADD if operator == "+" else Operation.SUBTRACT
            value = Expression.node(operation, value, right)
        return value

    def _parse_term(self) -> Expression:
        value = self._parse_factor()
        while self._peek() in {"*", "/"}:
            operator = self._consume()
            right = self._parse_factor()
            operation = Operation.MULTIPLY if operator == "*" else Operation.DIVIDE
            value = Expression.node(operation, value, right)
        return value

    def _parse_factor(self) -> Expression:
        token = self._consume()
        if token == "(":
            value = self._parse_expression()
            if self._consume() != ")":
                raise ValueError("missing closing parenthesis")
            return value
        if token in {"+", "-", "*", "/", ")"}:
            raise ValueError(f"unexpected token: {token}")
        return Expression.symbol_node(token)

    def _peek(self) -> str | None:
        if self._position >= len(self._tokens):
            return None
        return self._tokens[self._position]

    def _consume(self) -> str:
        token = self._peek()
        if token is None:
            raise ValueError("unexpected end of formula")
        self._position += 1
        return token

    def _expect_end(self) -> None:
        if self._peek() is not None:
            raise ValueError(f"unexpected token: {self._peek()}")
