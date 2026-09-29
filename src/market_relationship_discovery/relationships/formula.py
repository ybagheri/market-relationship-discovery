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


_BARE_SYMBOL = re.compile(r"[A-Za-z0-9_.#]+")
_OPERATORS = frozenset("()*/+-")


@dataclass(frozen=True, slots=True)
class _Token:
    """One lexical unit, remembering whether it was written as an operator.

    A quoted symbol keeps its text, so ``"*"`` is a symbol whose name happens to
    be an operator character. Without the flag the two are indistinguishable and
    a quoted name would be parsed as an operation.
    """

    text: str
    is_operator: bool


def semantic_key(expression: Expression) -> str:
    """Return a canonical identity key for provable monomial expressions."""
    exponents = monomial_exponents(expression)
    if exponents is None:
        return f"S|{canonical_formula_fallback(expression)}"
    # Symbol names are quoted rather than pasted in, so a name containing the
    # separator cannot forge another formula's key and be merged into it as a
    # duplicate hypothesis.
    body = ",".join(
        f"{_quote_key_part(symbol)}^{exponent}" for symbol, exponent in sorted(exponents.items())
    )
    return f"M|{body}|C=1"


def _quote_key_part(value: str) -> str:
    return f'"{value}"' if _BARE_SYMBOL.fullmatch(value) is None else value


def canonical_formula_fallback(expression: Expression) -> str:
    if expression.symbol is not None:
        return render_symbol(expression.symbol)
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


def render_symbol(symbol: str) -> str:
    """Render a symbol name so that re-parsing recovers exactly ``symbol``.

    A name is only written bare when every character is unambiguous. Anything
    else — a hyphen, a space, an operator character — is double-quoted, because
    a canonical form that cannot be read back is not a canonical form.
    """
    if symbol and _BARE_SYMBOL.fullmatch(symbol):
        return symbol
    if '"' in symbol:
        raise ValueError(f"symbol cannot be rendered: {symbol!r}")
    return f'"{symbol}"'


class FormulaParser:
    """Parse a relationship formula into an :class:`Expression` tree.

    Tokenisation resolves the ambiguity between a hyphenated broker symbol such
    as ``XAU-USD`` and an un-spaced subtraction such as ``A-B``. An earlier
    version accepted ``-`` as an identifier character, which made ``A-B`` a
    single dependency that can never exist in a price panel: the subtraction was
    silently discarded and the candidate could never be evaluated. A bare
    hyphen is now always the subtraction operator, and a name that genuinely
    contains one must be quoted, as in ``"XAU-USD" / EURUSD``.
    """

    _whitespace = re.compile(r"\s+")
    _quoted = re.compile(r'"([^"]*)"')

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
    def _tokenize(cls, expression: str) -> list[_Token]:
        tokens: list[_Token] = []
        position = 0
        length = len(expression)
        while position < length:
            whitespace = cls._whitespace.match(expression, position)
            if whitespace is not None:
                position = whitespace.end()
                continue
            if position >= length:
                break
            character = expression[position]
            if character in _OPERATORS:
                tokens.append(_Token(character, is_operator=True))
                position += 1
                continue
            quoted = cls._quoted.match(expression, position)
            if quoted is not None:
                name = quoted.group(1)
                if not name:
                    raise ValueError(f"empty symbol name at position {position}")
                tokens.append(_Token(name, is_operator=False))
                position = quoted.end()
                continue
            bare = _BARE_SYMBOL.match(expression, position)
            if bare is not None:
                tokens.append(_Token(bare.group(0), is_operator=False))
                position = bare.end()
                continue
            raise ValueError(f"invalid character at position {position}")
        if not tokens:
            raise ValueError("formula contains no tokens")
        return tokens

    def _parse_expression(self) -> Expression:
        value = self._parse_term()
        while (token := self._peek_operator()) in {"+", "-"}:
            self._consume()
            right = self._parse_term()
            operation = Operation.ADD if token == "+" else Operation.SUBTRACT
            value = Expression.node(operation, value, right)
        return value

    def _parse_term(self) -> Expression:
        value = self._parse_factor()
        while (token := self._peek_operator()) in {"*", "/"}:
            self._consume()
            right = self._parse_factor()
            operation = Operation.MULTIPLY if token == "*" else Operation.DIVIDE
            value = Expression.node(operation, value, right)
        return value

    def _parse_factor(self) -> Expression:
        token = self._consume()
        if not token.is_operator:
            return Expression.symbol_node(token.text)
        if token.text == "(":
            value = self._parse_expression()
            closing = self._consume()
            if not closing.is_operator or closing.text != ")":
                raise ValueError("missing closing parenthesis")
            return value
        raise ValueError(f"unexpected token: {token.text}")

    def _peek(self) -> _Token | None:
        if self._position >= len(self._tokens):
            return None
        return self._tokens[self._position]

    def _peek_operator(self) -> str | None:
        """The next operator token, ignoring a quoted symbol of the same text."""
        token = self._peek()
        if token is None or not token.is_operator:
            return None
        return token.text

    def _consume(self) -> _Token:
        token = self._peek()
        if token is None:
            raise ValueError("unexpected end of formula")
        self._position += 1
        return token

    def _expect_end(self) -> None:
        token = self._peek()
        if token is not None:
            raise ValueError(f"unexpected token: {token.text}")
