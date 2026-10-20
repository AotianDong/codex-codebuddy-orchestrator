# Troubleshooting

* `configuration_or_environment_error`: install Python >=3.10, Git and official CodeBuddy CLI. Set codebuddy_cli to a native binary or npm JS entry, and node_path for npm. Shell shims are never run by the dispatcher. Config uses a JSON subset of YAML 1.2; arbitrary YAML syntax is rejected.
* `rate_evidence_stale/invalid`, `credit_multiplier_unknown`: models-refresh, inspect account catalog, models-probe. Rates expire after <=24 hours and CLI version changes invalidate them. No public pricing guesses or borrowed account evidence.
* `no_compliant_model`: check whitelist, current catalog rates, authentication and probe results. Lower-cost candidates must satisfy the configured strict `<` threshold. Raising the threshold is an explicit user configuration decision; no automatic escalation.
* `policy_route_unknown`: custom endpoint/product override makes account pricing unverifiable. Restore the user's intended official route before refreshing; do not overwrite global configuration.
* `permission_denied`: inspect local stderr and environment permissions. Never retry using bypass flags.
* `json_parse_failed`, `model_identity_mismatch`: inspect local response metadata; model prose and missing identity aren't success. No automatic protocol rework.
* `repository_dirty`: user must choose a committed baseline or deliberately prepare another repository. Never stash/discard automatically.
* `timeout/model_timeout`: process termination is attempted; inspect command metadata for tree-kill failure. Windows taskkill restrictions may leave descendants; no strong sandbox guarantee. No automatic timeout retry.
* `test_failed`: at most one rework; fixed tests and requirements are unchanged. `needs_review` is not passed acceptance.
* Installer refuses overwrite: choose another Skill root or update only an owned installation. Edited/unknown installed files must be backed up first. Config/history live outside the installed Skill and survive uninstall.

Raw jobs may contain source, host paths and model responses. They are ignored by Git; don't upload them as issues. Share only reviewed/redacted aggregate summaries.
