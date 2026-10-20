# 开发约定

使用 Python 3.11+，优先保持默认路径零第三方运行依赖。所有示例必须完全合成；不接收真实工单、群聊、日志或凭据。

```sh
python3 -m unittest discover -s tests -v
python3 scripts/check_public.py
python3 -m rarebug demo --scripted-approvals --out runs/contribution-demo
python3 -m rarebug evaluate --out runs/contribution-evaluation --repeats 40
```

修改策略时解释假设、预算和预期失败模式，保持消融基线。修改审批或执行状态时补充能击穿原错误的行为测试。不要添加与实现同形的快照断言来代替边界测试。

源码变更会改变 code_digest；因此旧实验的 replay 将按设计拒绝新版源码。`examples/` 为当前版本的交付样例；更新时使用新空目录重新生成完整 demo 和评测，再替换归档，不要手工编辑旧快照来“修好”摘要。

快照中的时间戳来自运行时，业务反馈来自合成时间线和固定 seed。跨机器比较业务反馈与摘要字段，不要求写入时间或文件夹名字在不同 Python 版本间一致。
