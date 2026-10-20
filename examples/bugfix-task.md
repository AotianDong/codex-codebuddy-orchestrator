# 可复现 Bug 修复

```sh
python scripts/prepare_demo.py <new-demo-directory>
python scripts/cbo.py --config <config> execute <generated-task-json>
```

需求涉及金额折扣、Decimal/ROUND_HALF_UP、非法参数和多文件汇总；保护 tests_acceptance.py 中8项断言，只有两个 src 文件允许改动。初始代码有意含 Bug。执行后看 report.json 的8项业务断言结果、范围与源仓库指纹、change.diff。测试失败最多返工一次，不把模型“已完成”当作通过。
