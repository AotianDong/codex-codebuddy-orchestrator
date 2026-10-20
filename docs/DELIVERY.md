# 交付索引

项目名：codex-codebuddy-orchestrator。安装后的Skill自带运行包，可独立于原系统和本项目clone执行；配置和数据在安装输出的state目录。

| 交付项 | 入口与说明 |
|---|---|
| 全目录 | [TREE.md](TREE.md) |
| 复用、改造、新增与单独修复 | [MIGRATION.md](MIGRATION.md)、migration-manifest.json |
| Skill | skills/codex-codebuddy/SKILL.md；安装后重新打开支持Skill的会话，调用$codex-codebuddy |
| 独立CLI | python scripts/cbo.py --config <config>；或pip安装后codex-codebuddy |
| 模型与成本 | model_policy.py：当前账号证据、严格小于阈值、显式pin、可核验候选回退；默认0.2 |
| 测评 | benchmark.py、prepare_benchmarks.py；真实任务history独立记录；近似成本不作真实积分 |
| 测试 | [VALIDATION.md](VALIDATION.md)、validation-summary.json；46项回归、8项业务断言、32次真实模型测评 |
| 迁移到朋友电脑 | [README.md](../README.md)：clone→安装→官方认证→models-refresh→models-probe→doctor→调用Skill |
| 平台 | Windows PowerShell实测；Windows Git Bash脚本实测；macOS/Linux设备与Work界面未验收 |
| 发布剩余事项 | [PUBLISHING.md](PUBLISHING.md)：审查许可与文件、显式建远程/推送、启用Template、跑跨平台CI |

首次本地交付没有修改原调度器的配置或密钥，也没有创建远程、公开发布、合并或推送用户代码。后续远程发布按维护者明确授权执行。对当前机器的具体绝对路径由最终交付消息给出，避免将个人路径提交到公共项目。
