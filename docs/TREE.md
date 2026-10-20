# 完整发布目录

下列清单不含本地Git元数据、venv、认证、日志及验收工作副本。

```text
codex-codebuddy-orchestrator/
├── .env.example
├── .gitattributes
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   └── feature_request.md
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── workflows/
│       └── ci.yml
├── .gitignore
├── AGENTS.md
├── LICENSE
├── README.md
├── README_EN.md
├── benchmarks/
│   ├── results/
│   │   └── README.md
│   └── tasks/
│       └── README.md
├── config.example.yaml
├── docs/
│   ├── DELIVERY.md
│   ├── MIGRATION.md
│   ├── PUBLISHING.md
│   ├── TREE.md
│   ├── VALIDATION.md
│   ├── migration-manifest.json
│   └── validation-summary.json
├── examples/
│   ├── basic-task.md
│   ├── benchmark-task.md
│   ├── bugfix-task.md
│   ├── demo-project/
│   │   ├── src/
│   │   │   ├── order_summary.py
│   │   │   └── pricing.py
│   │   └── tests_acceptance.py
│   └── task.example.json
├── pyproject.toml
├── scripts/
│   ├── cbo.py
│   ├── doctor.py
│   ├── install.ps1
│   ├── install.sh
│   ├── manage.py
│   ├── prepare_demo.py
│   ├── scan_public.py
│   ├── test.py
│   ├── uninstall.ps1
│   ├── uninstall.sh
│   ├── update.ps1
│   ├── update.sh
│   └── verify_results.py
├── skills/
│   └── codex-codebuddy/
│       ├── SKILL.md
│       ├── references/
│       │   ├── troubleshooting.md
│       │   └── workflow.md
│       └── scripts/
│           └── run.py
├── src/
│   └── orchestrator/
│       ├── __init__.py
│       ├── __main__.py
│       ├── audit_models.py
│       ├── benchmark.py
│       ├── config.py
│       ├── dispatcher.py
│       ├── doctor.py
│       ├── evaluator.py
│       ├── manage_models.py
│       ├── model_policy.py
│       ├── prepare_benchmarks.py
│       ├── runtime.py
│       └── scheduler.py
└── tests/
    ├── __init__.py
    ├── integration/
    │   ├── __init__.py
    │   └── test_lifecycle.py
    └── unit/
        ├── __init__.py
        ├── test_model_policy.py
        ├── test_packaging.py
        └── test_scheduler.py
```
