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
