# Troubleshooting

* `configuration_or_environment_error`: install Python >=3.10, Git and official CodeBuddy CLI. Set codebuddy_cli to a native binary or npm JS entry, and node_path for npm. Shell shims are never run by the dispatcher. Config uses a JSON subset of YAML 1.2; arbitrary YAML syntax is rejected.
* `rate_evidence_stale/invalid`, `credit_multiplier_unknown`: models-refresh, inspect account catalog, models-probe. Rates expire after <=24 hours and CLI version changes invalidate them. No public pricing guesses or borrowed account evidence.
* `fallback_unavailable`, `no_compliant_model`: check exact MiniMax ID, explicit fallback qualification, current catalog and probe evidence. The multiplier must be strictly below the configured ceiling, which cannot exceed 0.2. No third model or default-model escape.
* `policy_route_unknown`: custom endpoint/product override makes account pricing unverifiable. Restore the user's intended official route before refreshing; do not overwrite global configuration.
* `permission_denied`: inspect local stderr and environment permissions. Never retry using bypass flags.
* `json_parse_failed`, `model_identity_mismatch`: inspect local response metadata; model prose and missing identity aren't success. No automatic protocol rework.
* `repository_dirty`: user must choose a committed baseline or deliberately prepare another repository. Never stash/discard automatically.
* `model_timeout`: only confirmed remote model timeouts qualify for bounded same-model technical retries, then a qualified MiniMax fallback. `execution_timeout` (unexplained CLI hang), local/test `timeout`, or `termination_unconfirmed` stop without model switching. Inspect command metadata; Windows descendants are not strongly contained.
* `workspace_state_uncertain`: unexpected file/Git changes stop retries and switching. During normal rework, switching after a provider failure archives partial work and restores the validated independent baseline; the source repository is never reset.
* `test_failed`: at most one rework; fixed tests and requirements are unchanged. `needs_review` is not passed acceptance.
* Installer refuses overwrite: choose another Skill root or update only an owned installation. Edited/unknown installed files must be backed up first. Config/history live outside the installed Skill and survive uninstall.

Raw jobs may contain source, host paths and model responses. They are ignored by Git; don't upload them as issues. Share only reviewed/redacted aggregate summaries.
