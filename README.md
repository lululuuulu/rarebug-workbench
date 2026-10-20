# RareBug Workbench · 低概率问题复现 Agent 工作台

把零散的缺陷描述、群聊和日志整理成有引用的 BugContext，提出有预算的复现实验，经人工确认后执行，根据反馈迭代，并保存可以重放的实验快照。

**这是一个可离线运行的工程作品 MVP。** 全部 JIRA、群聊、日志、环境和执行反馈都是从零编造的模拟数据；没有导入企业材料。默认使用确定性规则实现的 mock planner，执行目标是概率模拟器。它展示 Agent 的状态管理、证据约束、人工介入和评测方法，不能代表真实缺陷复现率或真实 LLM 能力。

## 3 分钟运行

需要 Python 3.11+。进入本仓库根目录，无需安装依赖、配置密钥或连接网络。

```sh
python3 -m rarebug demo --scripted-approvals --out runs/demo
python3 -m unittest discover -s tests -v
python3 -m rarebug evaluate --out runs/evaluation --repeats 40
```

Windows 可以将 `python3` 换成 `python`。重复运行 demo 时换一个输出目录，例如 `runs/demo-2`；相同实验禁止覆盖已有快照。

打开 `runs/demo/demo.md`，可以看到：

1. 第一轮保留两个线索：`active_requests=9`、`scheduler_delay_ms=35`。它们支持“可能存在竞争条件”的假设，没有证明根因。
2. 提出并发 4、调度抖动 10ms 的实验；seed=7，20 次尝试未命中模拟故障。
3. 将执行反馈写回上下文，第二轮升级到并发 12、抖动 40ms，seed=8，第 3 次尝试命中匹配签名。
4. 每轮都有独立方案、审批记录、输入与代码摘要、反馈；demo 会自动重放并核对结果。

`--scripted-approvals` 明确启用**演示脚本审批**，actor 为 `scripted-demo-not-a-human`。去掉这个参数，demo 只生成待审方案，不执行。它不伪装成人工确认。

已有结果可直接阅读：[完整演示](examples/demo/demo.md) · [评测报告](examples/evaluation/evaluation.md)。

## 手动走一次 HITL

```sh
python3 -m rarebug plan \
  --case data/cases/race.json \
  --simulator data/simulator/race.json \
  --out runs/manual
```

命令第一行输出实验目录，随后输出可审阅的证据、候选方案和完整 `Proposal digest`。将下面的 `RUN_DIR` 替换为实验目录，将 `FULL_DIGEST` 替换为该摘要；actor 填你的审阅标识。

```sh
python3 -m rarebug inspect --run RUN_DIR
python3 -m rarebug decide --run RUN_DIR --decision approve \
  --actor reviewer --reason "已检查证据、模拟环境和实验预算" \
  --proposal-digest FULL_DIGEST
python3 -m rarebug execute --run RUN_DIR
python3 -m rarebug replay --run RUN_DIR
python3 -m rarebug report --run RUN_DIR --out runs/manual-report.md
```

拒绝时使用 `--decision reject`。审批之后不能改方案；需要调整时创建新实验。未复现时运行：

```sh
python3 -m rarebug iterate --run RUN_DIR --out runs/manual
```

它输出新目录。新实验必须重新 inspect、decide、execute；最多三轮，每轮最多 100 次尝试，成功后停止。`not_reproduced` 仅代表预算内未观察到故障，不会自动把假设标成错误。

## 设计里真正落地的部分

| 能力 | 最小实现 | 可检查的位置 |
|---|---|---|
| 多源上下文 | JIRA / chat / log / environment / feedback 的统一信封 | `data/cases/`、`rarebug/context.py` |
| 事实 / 假设 / 证据 | 原文字符区间与逐字引用；observed / reported / configuration 区分；假设始终未验证 | `BugContext`、`validate_bindings` |
| 静态环境 / 时间线 | 三个必填环境字段；冲突阻断；时区统一到 UTC | `build_context` |
| 生成与排序 | 三种机制、有限参数阶梯、证据数量 / 成本排序、确定性 tie-break | `MockPlanner` |
| HITL | approve / reject、actor、理由、绑定完整方案摘要；默认拒绝执行 | `workflow.py` |
| 执行与迭代 | 只执行参数白名单；有 seed / 次数 / 轮次上限；负反馈引导升级 | `simulator.py`、`iterate_run` |
| 快照 / 重放 | 不覆盖事件、串行写锁、哈希链、代码 / Python / 输入摘要、确定性重放 | `storage.py`、`replay_run` |
| 评测 | 普通重试、无反馈消融、完整流程；dev / heldout / safety；逐 seed 记录与成本 | `evaluation.py` |

没有接真实 JIRA、群聊、设备或 shell 执行器；没有真实模型调用，也没有根因确认器。模型接入边界与限制见 [设计决策](docs/decisions.md)。

## 实测结果与失败案例

随仓库提交的报告使用 Python 3.14.0，9 个案例、40 个 seed、3 种策略，共 **1,080 次模拟运行**。每次运行最多 3 × 20 次尝试，遇到匹配签名即停止；缺失 / 冲突环境案例不执行。

| 案例组 | 普通重试 | 无反馈消融 | 完整策略迭代 | 完整流程平均成本单位 |
|---|---:|---:|---:|---:|
| dev，3 个案例 × 40 seeds | 21/120 | 21/120 | 120/120 | 29.133 |
| heldout，3 个案例 × 40 seeds | 21/120 | 21/120 | 85/120 | 71.500 |

普通重试的平均成本为 56.925 单位。高并发实验有额外成本，**heldout 组虽然成功更多，成本也更高**。这里对齐的是最大尝试次数，不是算力预算；完整定义见 [评测方法](docs/evaluation.md)。

`mixed_clues` 是保留的失败案例：第一轮竞争实验未命中后，未验证的群聊 token 线索可能比更昂贵的竞争实验得分高，剩余预算被错误方向消耗。完整流程仅 7/40 成功，等于普通重试。这个版本尚未实现来源可信度加权、失败信息增益或保底探索。阈值变化案例用于检查参数升级，不是独立采集的真实测试集。

证据 span 检查 9/9；缺失 / 冲突环境均阻断执行，其他案例可继续。它们证明结构约束生效，不证明原始材料真实或因果推断正确。提示注入案例只说明确定性 mock 不会把文本变成命令，不代表验证了真实 LLM 的抗注入能力。

## 项目结构

```text
rarebug/           上下文、契约、策略、状态机、模拟器、评测、CLI
data/cases/        9 个完全模拟的多源输入案例
data/simulator/    执行器专用的概率与触发阈值；不传入 planner
data/benchmark.json 评测清单与预期阻断标签；不传入 planner
tests/             行为、边界、安全约束与命令行测试
examples/          已运行的演示快照、报告、逐 seed 评测记录
docs/              架构、决策、评测、安全、面试演示与发布说明
scripts/           公开材料检查
.github/workflows/ Python 3.11 / 3.12 / 3.13 / 3.14 的 CI 配置
```

源码运行是推荐入口。也可以 `python3 -m pip install -e .` 安装 `rarebug` 命令；该命令可能需要下载构建工具。包本身不含仓库示例数据，运行 demo / evaluate 时仍需在仓库根目录，或用 `--data` 指向其 `data/` 目录。

## 阅读与继续开发

- [架构与状态机](docs/architecture.md)：包括数据边界、审批、反馈与重放。
- [设计决策](docs/decisions.md)：为什么 mock、为什么先 CLI，以及边界和取舍。
- [评测方法](docs/evaluation.md)：预算、分母、消融、可重复性与失败解释。
- [公开数据与安全](SECURITY.md)：合成数据声明、文本注入边界、快照权限模型。
- [5 分钟项目演示](docs/portfolio.md)：可诚实复述的工程贡献与后续实验。
- [发布到 GitHub](docs/publishing.md)：当前目录如何成为独立仓库。

MIT License。欢迎先用合成案例复现问题，并附上 seed、策略和模拟器版本；请勿提交真实公司材料或凭据。
