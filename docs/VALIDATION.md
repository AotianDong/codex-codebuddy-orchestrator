# 本地验收记录

固定优先级调整：当前开发任务固定DeepSeek主模型、已核验MiniMax仅作服务故障备用，详见[模型调度策略](MODEL_ROUTING.md)。下列测评及冷启动选择是调整前的历史记录，不能用来覆盖当前策略。新增分类故障/重试/干净副本恢复测试与安装验收另行记录；未重新运行这批模型比较。

验收日期：2026-10-20（Asia/Shanghai）。Windows 11 / Python 3.13.15 / CodeBuddy CLI 2.170.0。此页仅含可公开的合成任务汇总；原始响应、路径与工作副本保留在 Git 忽略的 `.local/`。

## 自动化回归

* 原系统：`python -B -m unittest discover -s outputs/codebuddy-workflow/tests -v`，37/37 通过，54.741 秒。其中18项调度器、19项模型与测评。
* 新项目：`python -B scripts/test.py`，46/46 通过，55.684 秒。覆盖成本阈值/未知倍率/过期证据/无候选、模型不可用与受限回退、手动pin、异常JSON、权限拒绝、真实子进程超时、最多一次返工、测试篡改、副本隔离、日志与新文件Diff、历史持久化、配置和敏感扫描。
* 安装器最终修正后，`python -B -m unittest tests.integration.test_lifecycle -v` 另行复跑，2/2通过。验证干净环境安装、自包含运行、配置位置默认保留、未知/被修改文件阻止更新卸载、邻近Skill保留，以及嵌套同名标记文件不会被误删。

故障注入使用测试桩，权限拒绝、不可用模型和协议错误的这些测试不代表真实服务曾拒绝访问。超时测试实际启动并终止了睡眠子进程；业务成功与模型目录另外通过真实CLI核验。

## 真实端到端

通过已经安装的 Skill `scripts/run.py execute` 发起演示任务，模型 minimax-m3.1-flash，1次完成。宿主运行原始 `tests_acceptance.py`：8/8通过。只修改两个允许的业务文件，生成 change.diff；源仓库指纹相同，未合并、未推送。

这8项是原演示业务的断言，不是8个独立模型任务。原演示代码故意保留Bug，不能把初始代码通过作为迁移基线。

## 真实双模型 Benchmark

同一调度器、同一manifest/HEAD、同一无工具权限和固定测试，12个任务，C1/E1各3次，合计32次（每模型16次）。全部一次成功、0返工；96条功能检查和32次有限AST质量检查全部通过。任务覆盖功能、新Bug、多文件、重构、综合逻辑与单元测试编写；后者用固定验证器与故障注入检查生成测试。

| 模型 | 账号目录倍率 | 运行 | 成功 | 平均秒数 | 含成本代理的分数 |
|---|---:|---:|---:|---:|---:|
| deepseek-v4.1-flash | 0.11 | 16 | 100% | 12.81 | 96.55 |
| minimax-m3.1-flash | 0.08 | 16 | 100% | 14.14 | 99.54 |

结论：没有明确优胜者，不生成性能推荐。冷启动按已核验倍率选择MiniMax，不声称它的综合性能已被证明更好。实际积分未暴露，保持null；零美元字段不能证明免费。成本代理不是积分。12个小任务的结果不能推广到大型/生产仓库或自主工具Agent；0返工也不能证明返工成功率。

`scripts/verify_results.py` 已对全部32份作业及演示执行记录自动核查：固定测试命令、模型显式pin与观测身份、严格成本阈值、源指纹、改动范围、一次返工上限、验收状态、Diff存在、相同配对条件，评分和推荐精确复算全部通过。示例：

```sh
python scripts/verify_results.py --config <config> --task-id <id> --benchmark-report <local-latest.json>
```

## 安装、打包与安全

* PowerShell入口已实际安装到用户Skill目录，并实际更新；doctor返回ready_for_execution=true。临时安装的卸载已验证，用户当前保留可用Skill。
* Git Bash（Windows）已实际跑通Shell install/update/uninstall与bash -n；这不是macOS/Linux设备验收。
* 纯标准库运行包随Skill复制，无全局pip修改。官方Skill quick_validate.py通过（开发校验依赖PyYAML放在本地忽略目录，以Python UTF-8模式执行）。
* wheel已构建，在空白venv中通过--no-index --no-deps离线安装；从无关cwd、不依赖仓库PYTHONPATH启动console entrypoint成功。此项验证包安装/入口；真实开发链路由上面的已安装Skill单独验证。
* migration-manifest.json中全部原始文件哈希重新核对未变。没有复制原认证、原作业或原模型成绩到公共仓库。
* `scripts/scan_public.py`对可发布候选文件无发现；正向测试确认能发现合成Token和个人路径。仍需维护者审查发布diff；扫描不是无秘密证明。
* 首次本地验收时Git分支main已初始化，无远程、未推送；CI矩阵已提供，当时尚未在GitHub执行。当前远程与CI状态以GitHub仓库为准。

## 尚未验证

macOS/Linux真实设备、原生CodeBuddy分发版本、ChatGPT Work界面直接安装、大型仓库/容器隔离、真实服务权限拒绝及高并发可靠性。仓库副本不提供OS级隔离；可信测试拥有宿主权限。不得把这些未验证项称为已支持或已验收。

完整可公开汇总见 validation-summary.json；运行所用的原始证据保持本地忽略，不应直接公开上传。
