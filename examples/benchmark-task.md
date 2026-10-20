# 比较模型

“对比 DeepSeek 和 MiniMax 哪个更适合这组开发任务，预算只允许当前账号倍率低于0.2的模型。”

先 models-refresh/probe，核验实际 ID 和账号倍率，再 benchmark --prepare 与 benchmark。两个模型从相同任务的相同 HEAD 开始，使用相同验收和时限。准备不会推理；probe 和实际 benchmark 会消耗用量。单次重复结果不满足稳定推荐条件。

查看本地 benchmark/latest.json 和 latest.md；未知真实积分写 null，成本代理与质量代理明确标记，接近或样本不足时报告“暂未确定明显优胜者”。
