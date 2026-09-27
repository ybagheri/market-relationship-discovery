import pytest

from market_relationship_discovery.relationships.formula import (
    Expression,
    FormulaParser,
    Operation,
    equivalent,
    monomial_exponents,
    semantic_key,
)


def test_parser_respects_precedence() -> None:
    expression = FormulaParser.parse("A * B / C")

    assert expression.operation is Operation.DIVIDE
    assert expression.left is not None
    assert expression.left.operation is Operation.MULTIPLY
    assert expression.dependencies() == {"A", "B", "C"}


@pytest.mark.parametrize("formula", ["", "A +", "A B", "(A / B", "A / B)"])
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
