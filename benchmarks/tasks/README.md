Run `python scripts/cbo.py --config <config> benchmark --prepare`.
The migrated ten-case suite is generated in local state/benchmark/suite, with separate Git repositories.
Categories: feature (A), bugfix (B), multifile (C), refactor (D), integrated (E).
Core C1/E1 repeat three times by default. Add unit-test-authoring case with its own protected verifier;
model-authored tests cannot serve as independent acceptance.
