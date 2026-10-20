---
name: codex-codebuddy
description: Delegate scoped Git development tasks to CodeBuddy with verified low-cost models, independent tests and reviewable diffs; compare CodeBuddy models on paired benchmarks when requested.
---

# Codex directs CodeBuddy

Use this Skill for requests such as “使用 CodeBuddy 完成这个开发任务”, “让 CodeBuddy 修复 Bug 并测试”, “使用低成本模型”, or “对比 DeepSeek 和 MiniMax”.

The installed entrypoint is `scripts/run.py` relative to this Skill directory. Invoke it with an available Python >=3.10 (the installation includes `.venv/Scripts/python.exe` on Windows or `.venv/bin/python` on POSIX). Always resolve the Skill directory from the actual loaded location. Do not assume a username, checkout location or Skill root.

Run `python <skill>/scripts/run.py doctor`. If catalog evidence is missing/stale, run `models-refresh` (no inference), inspect `models-status`, then `models-probe` (small billable requests). Authentication belongs to the user's official CodeBuddy CLI. Never copy credentials into a task or request that they paste secrets.

Identify a clean committed target Git root, requirements, exact editable files, context files, and fixed test commands. Read [workflow.md](references/workflow.md) to build the version-1 manifest. Write it outside the target repository. Explain that only committed HEAD is copied; don't stash, commit or discard the user's pending changes automatically. If needed, ask for the missing repository or acceptance requirements.

Call `execute <absolute-manifest-path>` and inspect `result <task-id>` and `diff <task-id>`. Success requires host-run tests, mapped acceptance, in-scope changes and unchanged source. CodeBuddy prose is never evidence of completion. Report model, verified multiplier, observed tokens, actual credits if available (otherwise unknown), attempts, test results, diff location and remaining review.

The worker has no tools and proposes complete text replacements. The host materializes only approved paths in a separate Git copy. Development always starts with `deepseek-v4.1-flash`; benchmark/price rankings never override priority. Only explicit model service outages, rate/capacity errors or confirmed remote timeouts after the configured technical retry budget may switch to the exact, independently qualified `minimax-m3.1-flash`. No third model or CLI implicit fallback. Test failures get at most one rework with the current successful implementation model. Local timeouts, permissions, protocol, scope and pricing failures stop. Inspect workspace/Git state before switching; archive legitimate partial work and restart a validated clean copy when needed. Never add tools, bypass permissions or auto merge/push. Host tests need trusted code or separate OS/container isolation.

For a named model use `--model <verified-id>` before the action. A pin cannot silently switch. Unknown/stale cost is unavailable; refresh evidence. All models must remain strictly below the configured threshold, never above the hard 0.2 ceiling. Free rates are evidence with an expiry, not a permanent assumption. A multiplier ceiling is not a total-spend cap.

For an authorized model comparison: `benchmark --prepare`, then `benchmark` (32+ billable calls for the standard suite; inspect generated index for exact count). Use identical suite/baseline and protected tests for both models. Review JSON/Markdown reports. Small samples, close scores and unknown credits cannot justify declaring a winner. Real-task history is separate and observational.

On failure, read [troubleshooting.md](references/troubleshooting.md). In an environment without a local shell or supported Skill loading, provide the documented manual CLI handoff; do not claim execution or Work compatibility was verified.
