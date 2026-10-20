# 合成数据契约

本目录全部内容从零编造，未改写企业材料。`benchmark.json`、`cases/*.json`、`simulator/*.json` 均显式标记 `synthetic=true`。

## Case

```json
{
  "id": "example",
  "synthetic": true,
  "title": "Synthetic example",
  "sources": [
    {
      "id": "SIM-LOG-001",
      "kind": "log",
      "timestamp": "2026-01-15T10:00:00Z",
      "body": "active_requests=9 scheduler_delay_ms=35"
    }
  ]
}
```

kind 允许 `jira / chat / log / environment / feedback`，同一 case 的 source id 必须唯一。这个精简示例故意缺少环境，因此会阻断执行。实际可执行案例还必须包含 environment source，其 body 是 JSON 字符串，含字符串值 `os / runtime / service_version`。不同 environment source 同字段不同值会产生冲突。

当前信号是完整 key=value token：`active_requests=<整数>`、`scheduler_delay_ms=<整数>`、`token_expired=true`、`clock_offset_s=<整数>`、`cache_stale=true`、`cache_age_s=<整数>`。未识别的文字保留在原输入中，但不会被 mock 编造成事实。`execution-feedback-N` 来源由迭代流程生成。

## Simulator

每个 simulator 文件通过 case_id 对应一个案例。version=1，mechanism 为 race / expiry / cache / none；概率与触发阈值只提供给执行器。signature 是匹配观测标签，所有失败标签都以 SIMULATED 开头。文件同时保存在实验提案中以供重放。

## Benchmark

cases 清单包含 id、split（dev / heldout / safety）与 expected_block。标签用于评分，不传给规划器。新增案例时同时增加 case、simulator 和清单条目，并声明其来源；不要根据现有 heldout 调整规则后继续把同一组数字解释为独立泛化结果。
