# Fixed primary and qualified fallback

Development tasks always start with `deepseek-v4.1-flash`. Benchmark rankings and the lowest-price candidate do not override this priority. Manual `--model` pins are still supported for debugging/comparison, and never silently switch. Model IDs and rates must be verified against the current account catalog; no permanent-free assumption is made.

Configuration is JSON (also valid YAML 1.2):

```json
{
  "primary_model": "deepseek-v4.1-flash",
  "fallback_model": null,
  "fallback_model_name": "MiniMax-M3.1-Flash",
  "fallback_model_verified": false,
  "max_credit_multiplier": "0.2",
  "max_technical_retries": 1
}
```

Keep the existing other configuration fields. To enable fallback, first use `models-refresh`, inspect the catalog, then `models-probe`. Only after the exact `minimax-m3.1-flash` ID passes current headless verification and its rate is strictly below 0.2 may the configured fallback be set to that ID with `fallback_model_verified: true`. The boolean alone is insufficient: every invocation revalidates catalog hash, age, CLI version, rate and successful matching probe evidence. Null/false disables fallback. No third model or reverse-switch loop is supported. The threshold can be tightened but cannot exceed 0.2; equality is rejected.

| Failure | Automatic action |
|---|---|
| Explicit model unavailable, HTTP service 500/502/503/529 | Qualified MiniMax fallback |
| Explicit HTTP 429 / rate-limit or model capacity error | Qualified MiniMax fallback |
| Explicit remote model timeout / HTTP 408/504 | Same-model technical retries, then qualified fallback |
| Normal code fails fixed tests | Same successful implementation model gets at most one rework |
| Agent task error, business logic, scope/diff, JSON error | Fail; no model switch |
| Local environment, permission or unexplained CLI wall-clock timeout | Fail; no model switch |
| Termination of timed-out process tree cannot be confirmed | Fail; no retry/switch |

The default technical retry budget is **one extra call**, so two consecutive confirmed remote timeouts exhaust the budget. This is separate from the one code rework. Budget 0..2 is supported. Local process hangs are not silently treated as provider outages. A successful retry keeps DeepSeek. MiniMax failure never selects a third model or switches back. Manual pins never switch automatically.

Every inference uses explicit `--model ID`. The CLI `--fallback-model` feature is not enabled: the scheduler owns all switching. Empty tools/MCP and the existing permission controls remain. Retry and fallback calls use distinct log/session IDs, record model/rate/reason and retain exit/consumption evidence where available. Exceptions without a returned session record the requested session and do not invent an actual session or billing result.

The scheduler fingerprints the working files and Git metadata around each call. Unexpected changes stop the task. At task preparation it retains a validated original clean independent copy. If a service failure during rework triggers a switch, it archives the partial workspace, checks the saved baseline, restores a clean independent workspace and rebuilds the original prompt without the other model's partial implementation. The existing test/rework budget is not reset or increased. No source repository reset, stash, commit, merge or push is performed.

Tests run with host permissions: these fingerprints detect changes but are not a hostile-code sandbox or hard process containment. Official model error messages are conservatively classified; unidentified local errors stop. Provider/internal routing and future price changes are not guaranteed by local evidence.
