# Contributing

1. Describe the observable CLI contract being added or corrected.
2. Add a focused fixture under `tests/`.
3. Run `python -m unittest discover -s tests -v`.
4. Run `python -m cliwitness run examples/cliwitness.toml`.

Keep the runtime standard-library-only. New assertions must produce useful
diagnostics without dumping captured command output.
