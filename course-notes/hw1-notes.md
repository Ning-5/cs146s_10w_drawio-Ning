# HW1 工作笔记

## 我的手工分析（第①步成果）

* my-d1.json：3 节点（receive/inspect/shelve）、2 条边、无提问
* 预览图已生成并核对 ✅

## 检查项清单（evaluate() 的设计蓝图）

### A. 格式检查（代码可自动判断）

* \[ ] 1. JSON 能否被解析（json.loads 不抛异常）
* \[ ] 2. 符合 spec.schema.json（nodes/edges/questions 字段、类型齐全）
* \[ ] 3. 每个节点 id 非空字符串、不叫 "0" 或 "1"
* \[ ] 4. 节点 id 不重复
* \[ ] 5. 每条边的 source/target 都是已存在的节点 id
* \[ ] （自己补充……）

### B. 含义判断（只能人工评估，写进报告表格）

* 步骤有没有漏（比如漏了"登记入库"）
* 顺序/方向对不对（比如 质检→接收退货 就是反了）
* 有没有编造原文没有的步骤
* 该不该提问（歧义处）
* （自己补充……）

## 待办

* \[ ] 打开 starters/hw01/smoke\_test.py，读懂 Client.chat 用法
* \[ ] 写 generate()

