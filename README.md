# codex-codebuddy-orchestrator

[English](README_EN.md) · [迁移记录](docs/MIGRATION.md) · [验收记录](docs/VALIDATION.md)

让 Codex 理解需求、确定改动范围与验收规则，由 CodeBuddy 提供代码修改提案，宿主在独立 Git 副本执行固定测试。输出可审查的 Git Diff；测试失败最多返工一次。适合范围明确的文本代码开发任务。

Codex 负责上下文与验收，CodeBuddy 使用经过账号目录核验的低倍率模型处理代码。这个分工可减少主模型承担的代码生成工作，但并不保证整体费用更低；CodeBuddy 倍率不是实际积分或总预算。

```text
自然语言 → Codex / Skill → 本地结构化任务 → 账号模型策略
                                 ↓
                  CodeBuddy（无工具，仅输出 JSON 提案）
                                 ↓
          宿主校验范围 → 独立 Git HEAD 副本 → 固定测试 → 最多一次返工
                                 ↓
                       Diff / 验收 / 日志 / 模型统计
```

## 前提与支持状态

Python >=3.10、Git、已安装并认证的官方 CodeBuddy CLI。npm 版本另需 Node.js。项目本身无第三方运行依赖；安装在独立 venv 内使用标准库，不更改全局 pip 或全局 CodeBuddy/Codex 配置。需有本地命令与文件权限。

Windows PowerShell 在本机执行验收；macOS/Linux 提供 POSIX Shell 入口和 CI 矩阵，但本次没有对应真实设备验收。支持 npm JS 入口和原生 CLI 的发现逻辑；原生分发版本未在本机实测。ChatGPT Work 仅提供有本地执行器时的手工入口，未完成 Work 界面安装验收。没有本地执行能力时不能直接调度本机 CodeBuddy。

## 快速开始

先克隆仓库并进入项目目录：

```sh
git clone https://github.com/AotianDong/codex-codebuddy-orchestrator.git
cd codex-codebuddy-orchestrator
```

然后运行安装脚本：

```powershell
# Windows
.\scripts\install.ps1
```

```sh
# macOS/Linux（待设备验收）
sh scripts/install.sh
```

默认安装到 `$CODEX_HOME/skills`（显式设置时），否则 `~/.agents/skills`。可以传 `--skills-dir <目录> --state-dir <目录>`；不会覆盖现有同名 Skill。配置默认放 Windows `%LOCALAPPDATA%/codex-codebuddy`，POSIX `$XDG_STATE_HOME/codex-codebuddy` 或 `~/.local/state/codex-codebuddy`。安装输出实际位置与 Python 路径。已有非标准 Skill 环境请显式指定受支持的目录。

从安装输出中取得 Skill 绝对目录 `<skill>`，执行：

```sh
python <skill>/scripts/run.py doctor
python <skill>/scripts/run.py models-refresh
python <skill>/scripts/run.py models-probe
python <skill>/scripts/run.py models-status
```

`models-refresh` 读取官方 CLI ACP 账号目录，不发送模型推理；`models-probe` 为符合倍率要求的模型做最小真实请求，会产生用量。先通过官方 CodeBuddy 交互界面完成认证，不在本项目保存认证数据。初次 doctor 未就绪是正常的，不能跳过模型核验。

重新打开支持 Skill 的 Codex 会话：

> 使用 $codex-codebuddy 让 CodeBuddy 修复这个仓库的 Bug，完成后执行固定测试并给出 Diff。

也可以直接使用独立 CLI：`python scripts/cbo.py --config <config.yaml> execute <task.json>`，或 `python -m pip install .` 后使用 `codex-codebuddy`。独立 CLI 不依赖 Skill；pip 分发构建可能需要下载 setuptools。配置与 manifest 应在目标仓库外。完整字段见 [工作流](skills/codex-codebuddy/references/workflow.md)。

## 配置

`config.example.yaml` 使用 YAML 1.2 的 JSON 子集，标准库即可解析；不支持任意 YAML 写法。路径相对 config 文件所在目录解析。`.env.example` 仅说明进程环境变量，不自动加载 dotenv。

| 字段 | 含义 |
|---|---|
| codebuddy_cli / node_path | 可执行原生 CLI 或 npm JS 入口 / Node；空值自动发现 |
| candidate_models | 候选白名单；当前适配 deepseek-v4.1-flash、minimax-m3.1-flash |
| max_credit_multiplier | 严格小于此值，默认 0.2；修改是显式成本决策 |
| default_model | 冷启动默认，可空；仍须通过证据与成本检查 |
| benchmark_enabled | 是否启用测评和测评路由 |
| agent_timeout_seconds / max_reworks | 最长 600 秒 / 0 或 1；任务只能进一步收紧 |
| test_commands | manifest 未提供测试时使用的可信 argv 对象数组 |
| log_directory | 作业目录，必须位于被调度源仓库外 |

不会把个人历史成绩、账号目录和倍率作为公共默认值。倍率来自当前账号 ACP 目录，带哈希、时间和 CLI 版本绑定；过期、未知、冲突或模型身份缺失时停止。显式 pin 从不切换；自动模式仅在可用性故障时转向另一个当时已核验且满足阈值的候选。

## 模型测评

```sh
python scripts/cbo.py --config <config> benchmark --prepare
python scripts/cbo.py --config <config> benchmark
python scripts/cbo.py --config <config> history
```

标准套件由迁移的十个小任务与新增单元测试编写任务组成，覆盖功能、Bug、多文件、重构、综合任务和测试编写。每模型每任务独立副本、相同 HEAD/manifest/测试，交替模型顺序；C1/E1 各重复三次。完整执行会产生多次真实用量，先查看生成的 index.json。`--single-repeat` 用于快速配对验证，不足以形成稳定路由建议。

权重：测试35、一次成功20、有限 AST 质量15、返工10、速度10、成本代理10；任务等权。记录成功、测试、Diff、返工、耗时、tokens、倍率、环境与任务来源，生成本地 JSON 和 Markdown。实际积分当前无法从 CLI 获得时为 null，倍率×tokens 只作相对成本代理，不能称为积分；单位成功任务代理成本也明确标注。质量检查不是全面代码评审。

至少十个配对任务、核心重复满足要求、正确性与质量>=90%、差距>=3 分且配对非成本 bootstrap 区间支持领先者才建议切换。相近或样本不足时不宣称胜者。默认模型或最低倍率已核验候选负责冷启动。真实任务单独持久化成功率等观测，不与 Benchmark 混分或触发频繁切换。

## 更新、卸载与示例

先自行审查并 `git pull --ff-only` 更新克隆，再运行 `scripts/update.ps1` 或 `sh scripts/update.sh`，传入原安装路径参数。更新只替换本项目拥有且未被用户改动的 Skill；外部配置、认证、历史结果保留。卸载用 `scripts/uninstall.ps1` 或 `sh scripts/uninstall.sh`；只删除经文件哈希确认的本 Skill，不删除状态目录或其他 Skill。

[基础任务](examples/basic-task.md) · [修复任务](examples/bugfix-task.md) · [模型比较](examples/benchmark-task.md)。`scripts/prepare_demo.py <新目录>` 创建独立演示 Git 仓库和外部任务文件；原始演示含缺陷，固定 8 项业务断言用于验证真实模型修改。

## 安全边界与限制

只读源仓库，不自动 merge、push、删除源文件或执行模型建议命令。CodeBuddy tools/MCP/项目设置关闭，只收到选定文件文本；宿主校验 JSON 与精确白名单。独立 Git 副本不是 OS 沙箱：可信测试会运行生成代码，并继承当前用户权限和环境。处理不可信代码需另外部署容器/OS 隔离，本项目不声称提供这一能力。

支持干净 committed HEAD；不支持脏目录、符号链接、子模块、LFS/archive 变换、二进制/删除操作，文件/上下文有上限。完整替换可能不适合大型任务。测试不得修改副本内容；依赖需事先准备。Windows 进程树终止若受权限限制，报告只记录能确认的终止结果。日志默认本地，可能含源代码和路径，禁止直接公开。

测试：`python scripts/test.py`；敏感信息检查：`python scripts/scan_public.py`。本地/模拟故障测试与真实模型验收分开报告，见 [验收记录](docs/VALIDATION.md)。故障处理见 [troubleshooting](skills/codex-codebuddy/references/troubleshooting.md)。

## GitHub Template 发布

本地已具备 MIT LICENSE、CI、Issue/PR 模板和 Git 初始化；初始本地构建阶段未创建远程或 push；后续发布在维护者明确授权后执行。先审查 `git diff --cached`、运行扫描和测试、确认原代码具有公开授权，再自行建立远程并提交推送。GitHub 仓库 Settings → General → Template repository 勾选后，朋友可点 Use this template。建议先建私有仓库完成跨平台 CI，再决定公开；具体命令见 [发布指南](docs/PUBLISHING.md)。

Skill 路径与可用范围参考 [OpenAI 官方说明](https://learn.chatgpt.com/docs/build-skills)；目录核验协议参考 [CodeBuddy ACP](https://www.codebuddy.cn/docs/cli/acp)。本项目以本机 CLI 实际输出和测试为能力证据，不把文档阅读当作实测。
