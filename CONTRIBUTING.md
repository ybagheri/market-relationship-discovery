# Contributing

1. Inspect the issue and current architecture.
2. Keep changes focused and preserve existing research semantics.
3. Add deterministic tests for formulas, costs, alignment, and safety behavior.
4. Never add credentials, machine paths in source, raw databases, or live trading.
5. Run `pytest`, `ruff check .`, `black --check .`, and `mypy` before review.
6. Document assumptions and limitations with each research feature.
7. Review `git diff` and `git status` before committing.

A contribution must not describe a research candidate as guaranteed or risk-free profit.
