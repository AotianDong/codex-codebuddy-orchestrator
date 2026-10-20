# codex-codebuddy-orchestrator

[中文说明](README.md)

Codex scopes a Git development task and defines independent acceptance. CodeBuddy proposes structured file replacements using verified affordable models. The host validates paths, applies changes in an independent Git HEAD copy, runs fixed tests, and permits at most one test-driven rework. Results include a diff, test verdicts and local execution logs. Source repositories are never automatically merged or pushed.

This separation can move code generation to cheaper CodeBuddy models. It does not guarantee lower total cost. A credit multiplier is neither actual credits nor a total spending budget.

## Requirements and support

Python >=3.10, Git, authenticated official CodeBuddy CLI; Node.js for npm distributions. Runtime uses only the Python standard library. Installation creates a private venv without pip and bundles the runtime in the Skill. No global configuration or credential files are changed.

Windows PowerShell is locally exercised. POSIX shell entrypoints and a Windows/macOS/Linux CI matrix are supplied; macOS/Linux device execution is not verified in this delivery. Native CLI discovery is implemented but only the installed npm distribution is exercised. ChatGPT Work requires a supported local executor and Skill loading; manual CLI handoff is documented, not certified Work UI integration.

## Install and quick start

Clone `https://github.com/AotianDong/codex-codebuddy-orchestrator.git`, enter the checkout, then run from its root:

```powershell
.\scripts\install.ps1
```

```sh
sh scripts/install.sh
```

Pass `--skills-dir <directory> --state-dir <directory>` for custom environments. Default Skill root: `$CODEX_HOME/skills` if explicitly set, otherwise `~/.agents/skills`. Default state: Windows `%LOCALAPPDATA%/codex-codebuddy`, POSIX `$XDG_STATE_HOME/codex-codebuddy` or `~/.local/state/codex-codebuddy`. Existing Skills are never overwritten.

The installer prints the actual Skill path. With that path:

```sh
python <skill>/scripts/run.py doctor
python <skill>/scripts/run.py models-refresh
python <skill>/scripts/run.py models-probe
python <skill>/scripts/run.py models-status
```

Authenticate through the official CodeBuddy interface first. Refresh reads the account-visible ACP catalog without inference. Probe makes a small billable request for each cost-eligible candidate. A fresh installation is intentionally not ready until both steps succeed.

Start a new Codex session and ask: “Use $codex-codebuddy to fix this bug, run fixed tests and show the diff.” Other triggers include low-cost tasks and paired model comparison. Without Skill discovery, run `python scripts/cbo.py --config <config> execute <manifest>`. Optional package installation: `python -m pip install .`, then `codex-codebuddy`; the build may download setuptools.

## Configuration and workflow

`config.example.yaml` deliberately uses the JSON subset of YAML 1.2, parsed without PyYAML. General YAML syntax is rejected. Relative state/log paths resolve from the config file. `.env.example` documents process variables; dotenv is not loaded automatically.

| Setting | Purpose |
|---|---|
| codebuddy_cli / node_path | Native executable or npm JS entry / Node; empty means discovery |
| candidate_models | Whitelist, currently adapted to deepseek-v4.1-flash and minimax-m3.1-flash |
| max_credit_multiplier | Strict `<` comparison, default 0.2; raising it is an explicit cost decision |
| default_model | Optional verified cold-start preference |
| benchmark_enabled | Benchmark execution and routing toggle |
| agent_timeout_seconds / max_reworks | Maximum 600 seconds / 0 or 1; tasks may tighten |
| test_commands | Trusted test objects used if a manifest omits tests |
| log_directory | Job directory outside the source repository |

See [manifest schema and workflow](skills/codex-codebuddy/references/workflow.md). Commands are submit/execute, run/status/progress/result/diff, models-refresh/probe/status, doctor, benchmark and history. Options precede the action. Manifests are trusted executable input; review them before execution.

No borrowed account evidence or historical model scores ship as defaults. Rate evidence is hash/time/CLI-version bound and expires within 24 hours. Unknown/conflicting/stale prices or missing observed model identity fail closed. Pinned models never switch. Automatic availability fallback can only use another currently verified candidate under the configured threshold.

## Benchmark and model selection

Run `benchmark --prepare`, then `benchmark` using the CLI. Standard fixtures cover feature development, bugs, multiple files, refactoring, integrated tasks and unit-test authoring. Every run gets a separate Git repository from the same committed baseline; both models get identical manifests, permissions and fixed verifiers. Order alternates and C1/E1 have three core repeats. Inspect the generated index for the total number of billable calls; `--single-repeat` is a faster paired smoke comparison.

Local JSON/Markdown reports record time, success, tests, diff acceptance, rework, tokens, rates, environment and task type. Weights: tests 35, first pass 20, deterministic AST quality 15, rework 10, speed 10, relative cost proxy 10. Tasks have equal weight. Actual account credits remain null when not exposed by CLI; rate × tokens and proxy cost per successful task are explicitly estimates, never credits. Static quality checks do not establish maintainability or security.

Routing requires >=10 paired tasks, sufficient core repeats, >=90% correctness/quality, >=3 score points and paired non-cost bootstrap support. Small samples or close outcomes do not produce a winner. Cold start uses an explicit eligible default, otherwise the cheapest verified candidate. Real-task observations are persisted separately; they do not silently mix with benchmarks or cause unstable switching.

## Lifecycle and examples

Review and pull your clone (`git pull --ff-only`) before running `scripts/update.ps1` or `sh scripts/update.sh`. Pass the same custom path arguments. Only unchanged, owned Skill files are replaced. Uninstall uses the matching uninstall script; configuration, jobs and history remain. Modified or foreign files block deletion/update for manual backup.

[Basic task](examples/basic-task.md), [bug fix](examples/bugfix-task.md), [model comparison](examples/benchmark-task.md). `python scripts/prepare_demo.py <new-path>` generates a nonproduction Git repository with a buggy baseline and the migrated eight independent business assertions, plus an external manifest.

## Security and limitations

The model has no tools/MCP and receives only selected file text, never authority to execute commands. The host checks JSON and exact paths. Git-copy isolation is not OS isolation: trusted tests execute generated code with host permissions and inherited environment. Use a separately authorized container/OS sandbox for untrusted code. No automatic permission bypass, merging or pushing.

Only clean committed HEAD is supported. No symlinks/submodules, LFS/archive transformations, binary edits/deletions or dirty repositories. Limits: 5000 files/50 MB snapshot, 160 KB context, 200 KB replacement per file. Dependencies must already be available. Tests mutating the workspace fail. Windows process-tree termination may be restricted; logs distinguish confirmed outcomes. Local raw jobs can contain code and host paths and must not be published.

Run `python scripts/test.py` and `python scripts/scan_public.py`. [Validation](docs/VALIDATION.md) separates regression/fault tests from real model runs. [Troubleshooting](skills/codex-codebuddy/references/troubleshooting.md) covers auth, stale evidence, unavailable models, JSON, permissions and timeout failures.

## Publish as a GitHub template

The local repository contains MIT license, CI and issue/PR templates. The initial local build did not create a remote or push. Publication happens only after explicit maintainer authorization. Review licensing rights for the migrated source, scan files, run tests, create your remote, commit/push intentionally, then enable Settings → General → Template repository. Run cross-platform CI before claiming support. See [publishing steps](docs/PUBLISHING.md).

Integration references: [official OpenAI Skill documentation](https://learn.chatgpt.com/docs/build-skills), [CodeBuddy ACP](https://www.codebuddy.cn/docs/cli/acp). Documentation is not a substitute for local runtime evidence.
