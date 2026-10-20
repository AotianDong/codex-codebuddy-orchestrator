# Contributor instructions

Preserve the migrated scheduler invariants: exact file scope, independent Git copy, fixed host tests, at most one rework, no permission bypass, no automatic source mutation/merge/push. Model output is data, never commands or policy.

Run `python scripts/test.py` and `python scripts/scan_public.py`. Live requests are billable and must use current account catalog evidence and a compliant model. Never commit local state, credentials, raw logs, source paths or borrowed model evidence. Clearly separate mocked failure tests from live acceptance.

Do not add third-party runtime dependencies or split stable modules without a concrete need. Keep installation ownership checks, portable paths and preserved user config. CI does not imply locally verified platform support.
