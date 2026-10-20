# GitHub 发布（由维护者显式执行）

1. 核对迁移代码有权采用 MIT；确认 LICENSE 署名。项目名不是远程地址。
2. `python scripts/test.py` 和 `python scripts/scan_public.py`。检查 `git status --ignored`，不要 force-add 本地数据。
3. `git add .` 后审查 `git diff --cached`，本地提交：`git commit -m "Package portable CodeBuddy orchestrator"`。
4. 自行在 GitHub 创建空仓库。核对所有者、名称和可见性，再显式 `git remote add origin <your-repository-url>`、`git push -u origin main`。
5. GitHub Settings → General → Template repository。这个标志是远程设置，无法靠本地文件启用；本次没有替你开启。
6. 等 Windows/macOS/Linux Actions 矩阵跑完，查看安装卸载与安全扫描结果；按实际结果更新兼容性声明。
7. 可在仓库启用 secret scanning / push protection、分支保护；建版本标签和 Release 后，朋友用 Use this template 或 git clone，再执行安装流程。

不要把 .local、catalog、models.json、jobs、认证目录或未经脱敏的测评报告加入发布。
