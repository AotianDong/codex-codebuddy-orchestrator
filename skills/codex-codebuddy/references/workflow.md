# Structured task workflow

Use the following JSON shape. `repository` must be the absolute Git root. `allowed_files` and `context_files` are exact relative POSIX paths (no globs). The manifest is trusted executable input, reviewed by Codex; model output cannot change it.

```json
{
  "version": 1,
  "repository": "/absolute/path/to/repo",
  "requirements": ["Fix the described bug while preserving the public API"],
  "allowed_files": ["app.py"],
  "context_files": ["app.py", "verify.py"],
  "forbidden_operations": ["Do not edit acceptance tests, read secrets or change source repo"],
  "acceptance": [{"id": "behavior", "description": "Fixed behavior", "test_ids": ["verify"]}],
  "tests": [{"id": "verify", "argv": ["$PYTHON", "-B", "verify.py"], "timeout_seconds": 30}],
  "max_reworks": 1,
  "agent_timeout_seconds": 180
}
```

Test argv[0] is `$PYTHON` or an existing absolute executable; no shell strings/shims. `$PYTHON` uses the executing Python. Independent acceptance test files must stay outside allowed_files. A generated unit-test file may be editable, but the protected verifier must independently validate it. Empty test_ids explicitly means manual acceptance and produces needs_review.

New files are supported. File deletion, binary edits, symlinks, submodules, Git LFS/archive transformations, dirty source and repositories over 5000 files/50 MB are unsupported. Context is bounded at 160 KB, replacements at 200 KB/file. Ignored/untracked files do not migrate. No dependency installation is performed in the target copy; arrange trusted dependencies in advance. Tests that mutate tracked/untracked workspace files fail acceptance; use an external temporary directory for caches.

Commands: submit/execute <manifest>, run/status/progress/result/diff <task-id>. Config/model options precede the action. Logs remain in configured job storage outside source. A claim lock prevents replay; inspect interrupted jobs manually and submit a new task instead of deleting a lock blindly. Returned patches are for review; applying to source is a separate authorized action.
