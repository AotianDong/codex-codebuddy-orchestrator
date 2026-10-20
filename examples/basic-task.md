# 基础开发

对 Codex 说：“使用 CodeBuddy 为当前干净 Git 仓库新增稳定去重函数，只改 module.py；由 verify.py 覆盖空列表、重复项和顺序。”

Codex 读取 Skill，生成精确 allowed_files 与 acceptance→test_ids 映射，执行任务并展示 change.diff。源仓库不变，用户审查后再决定采用。
