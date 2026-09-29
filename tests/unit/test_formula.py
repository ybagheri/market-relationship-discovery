import pytest

from market_relationship_discovery.relationships.formula import (
    Expression,
    FormulaParser,
    Operation,
    equivalent,
    monomial_exponents,
    render_symbol,
    semantic_key,
)


def test_parser_respects_precedence() -> None:
    expression = FormulaParser.parse("A * B / C")

    assert expression.operation is Operation.DIVIDE
    assert expression.left is not None
    assert expression.left.operation is Operation.MULTIPLY
    assert expression.dependencies() == {"A", "B", "C"}


def test_an_unspaced_hyphen_is_a_subtraction_not_a_symbol() -> None:
    expression = FormulaParser.parse("A-B")

    assert expression.operation is Operation.SUBTRACT
    assert expression.symbol is None
    assert expression.dependencies() == {"A", "B"}


def test_an_unspaced_hyphen_matches_the_spaced_spelling() -> None:
    assert equivalent(FormulaParser.parse("A-B"), FormulaParser.parse("A - B"))


def test_a_hyphenated_broker_name_is_a_single_symbol_when_quoted() -> None:
    expression = FormulaParser.parse('"XAU-USD" / EURUSD')

    assert expression.dependencies() == {"XAU-USD", "EURUSD"}


def test_a_hyphenated_broker_name_is_not_confused_with_a_subtraction() -> None:
    quoted = FormulaParser.parse('"XAU-USD" / EURUSD')
    unquoted = FormulaParser.parse("XAU-USD / EURUSD")

    assert quoted.dependencies() == {"XAU-USD", "EURUSD"}
    assert unquoted.dependencies() == {"XAU", "USD", "EURUSD"}
    assert not equivalent(quoted, unquoted)


@pytest.mark.parametrize("symbol", ["XAU-USD", "EUR/USD", "A B", "gold*", ""])
def test_render_symbol_round_trips_through_the_parser(symbol: str) -> None:
    rendered = render_symbol(symbol)

    if not symbol:
        assert rendered == '""'
        with pytest.raises(ValueError):
            FormulaParser.parse(rendered)
        return
    assert FormulaParser.parse(rendered).dependencies() == {symbol}


def test_rendered_canonical_form_reparses_to_the_same_identity() -> None:
    expression = FormulaParser.parse('"XAU-USD" / "EUR-USD"')

    reparsed = FormulaParser.parse(render_symbol("XAU-USD") + "/" + render_symbol("EUR-USD"))

    assert reparsed.dependencies() == expression.dependencies()
    assert semantic_key(reparsed) == semantic_key(expression)


def test_a_symbol_containing_the_key_separator_cannot_forge_another_key() -> None:
    """Two different formulas must not collapse onto one semantic key."""
    first = FormulaParser.parse('"A,B"/"C"')
    second = FormulaParser.parse('"A"/"B,C"')

    assert first.dependencies() != second.dependencies()
    assert semantic_key(first) != semantic_key(second)


def test_trailing_and_leading_whitespace_are_tolerated() -> None:
    assert FormulaParser.parse("  A / B  ").dependencies() == {"A", "B"}


def test_an_unterminated_quote_is_rejected() -> None:
    with pytest.raises(ValueError):
        FormulaParser.parse('"A / B')


def test_a_quoted_operator_character_is_a_symbol_name() -> None:
    assert FormulaParser.parse('"*"').dependencies() == {"*"}


@pytest.mark.parametrize("formula", ["", "A +", "A B", "(A / B", "A / B)", "A  /  "])
def test_parser_rejects_invalid_formulas(formula: str) -> None:
    with pytest.raises(ValueError):
        FormulaParser.parse(formula)


def test_division_by_a_product_equals_dividing_by_each_factor() -> None:
    formulas = ("A/(B*C)", "A/B/C", "A/(C*B)", "A/C/B")

    keys = {semantic_key(FormulaParser.parse(formula)) for formula in formulas}

    assert len(keys) == 1


def test_cancelling_a_factor_recovers_the_original() -> None:
    formulas = ("(A/B)*B", "A*(B/B)", "A")

    keys = {semantic_key(FormulaParser.parse(formula)) for formula in formulas}

    assert len(keys) == 1
    assert monomial_exponents(FormulaParser.parse("A")) == {"A": 1}


def test_inverted_and_different_products_are_not_equivalent() -> None:
    assert not equivalent(FormulaParser.parse("A/B"), FormulaParser.parse("B/A"))
    assert not equivalent(FormulaParser.parse("A*B*C"), FormulaParser.parse("A*B*D"))


def test_exponent_multiplicity_is_preserved() -> None:
    assert not equivalent(FormulaParser.parse("A*A"), FormulaParser.parse("A"))
    assert not equivalent(FormulaParser.parse("A/B/B"), FormulaParser.parse("A/B"))


def test_additive_expressions_fall_back_to_syntactic_identity() -> None:
    first = FormulaParser.parse("A*B+C*D")
    second = FormulaParser.parse("C*D+A*B")

    assert monomial_exponents(first) is None
    assert not equivalent(first, second)
    assert semantic_key(first).startswith("S|")


def test_semantic_key_never_raises_on_malformed_trees() -> None:
    assert semantic_key(Expression()) == "S|invalid"
