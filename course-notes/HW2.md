# HW2 实验报告：图表工作区的工具、Agent 与完成门

分支 `practice/main`。本报告每条结论均有提交哈希、归档 JSON 或 XML 物证背书。

## 0. 摘要

表面任务：让基于 Ollama 4B 本地模型的 Agent 在 drawio 工作区正确使用四种工具（read_diagram / inspect_diagram / apply_changes / compare_changes），跑通七类请求案例。实际任务：质量工程——发现缺陷、源码定罪、最小修复、对照实验证明。

| 交付 | 提交 | 内容 |
|---|---|---|
| 工具描述重写 + inspect 护栏 | 88ff071 | false-ok 缺陷修复 |
| agent 防崩 + compat | 9409eb8 | 崩溃路径加固；Ollama 字符串参数兼容 |
| MCP 集成 | d9dfa9d | 课程要求达成 |
| 自构三案例回归语料 | f910475 | 工具失败 / 重复写入 / 版本冲突 |
| sticky-flag 修复 | 213534a | false-negative 修复 + 对照实验 |
| 第 7 案例实战卷 | c93c975 | 陌生图表 + 真模型完整作业 |

## 1. 缺陷一：inspect_diagram 的 false-ok（静默顶替）

**现象**：传文件名或页面 id 等"坏"参数时工具不报错，静默返回文件概览（ok:true 但内容不是所查页面）——把"查询失败"伪装成"查询成功"。

**修复**（88ff071）：判别矩阵（空串→概览；页面名→详情；文件名/页面 id→ok:false 响亮拒绝）+ 描述双条款："不要传文件名（如 practice.drawio）或页面 id（如 page-a），两者都会被拒绝（ok:false）"；"读取失败时必须如实告知用户……也不得静默改查其他页面顶替"。

**实战验证**：第 7 案例模型两次 read 全部合法（overview → 直呼 Preview），锚误导零发生——护栏备而不用，预防优于拦截。

## 2. 缺陷二：agent 对模型输出缺失的崩溃路径

模型输出缺 tool_calls 字段时嵌套提取直接崩溃 → 结构防御（9409eb8）。意外收获：工具循环入口的 compat 层 `args = _json.loads(raw_args) if isinstance(raw_args, str) else raw_args`（注释："Ollama 有时把 arguments 给成 JSON 字符串"）——为 4B 模型怪癖写的防御，后来把作者自己的字符串化事故无声救回。给模型怪癖写的代码救了人类怪癖。

## 3. 缺陷三：完成门的 false-negative（sticky flag）

原代码一行复合 if 只置位不复位，恢复剧本（失败→重试成功→宣布完成）被误判 unverified——旗的行为与其注释意图（"最后一步工具失败，不算完成"）相反。修复（213534a，-2/+2）：

    if fn == "apply_changes" and args.get("operations"):
        apply_failed = not result["ok"]

旗只被"带 operations 的真实写入尝试"触碰。**对照实验**（同 harness、同模型）：tool-crash → completed（恢复者放行）；duplicate-write → unverified（冒功者拦下）；stale-version → unverified（正确执法）。一扇门的两面同时钉死。判据（版本哈希比对）从未冤枉人——冤枉人的是旗。

## 4. 案例语料

- 官方案例 1–6：sweep 全绿，档案 `.runtime/hw02/iter-results/`（events 含完整请求 args，可复现）。
- 自构三案例（f910475，`starters/hw02/replay_cases/`）：probe-oracle 先经系统亲口确认 schema（`{op, page_id, cell_id, label}`）再生成。
- 第 7 案例（c93c975，`starters/hw02/chosen-case/`）：见 §5。
- 官方 replay 五案例全绿：invalid-arguments→completed、limit→max_turns、model-down→model_error、multiple-tools→completed、unknown-tool→completed（档案 .runtime/hw02/replay-official-*.txt）。
- 代表性运行记录：`starters/hw02/run-records/`——多工具成功卷与失败拒绝卷（选自 iter-results 档案）。

工具响应形状备忘：read detail 返回 `{snapshot, version, page}`，图元表在 `page.cells`（含根/层图元 "0"/"1"，适配器禁改它们）；read/apply 均登记快照，compare_changes 依赖此表做页内 diff。

## 5. 第 7 案例：陌生图表上的实战

考卷：hw01 期末图表 chosen.drawio（单页 Preview，7 图元，样式 `whiteSpace=wrap;html=0`，与练习图 `courseRole=process` 完全不同——排除背诵可能）。因 workspace 文件名硬编码，采用顶名入场（chosen 以 practice.drawio 之名应考，考毕复原，restored: True 非平凡）。

模型作业（turns 5 / calls 4，全绿）：overview 拿名与版本 → 直呼 Preview 读详情 → apply_changes（64 位 sha256 版本 + 四键 op：receive_return → 已审核）→ **主动 inspect 复查**，answer 引用 issues: 0。终局 completed；file changed: True；XML 铁证 `value="已审核"` 在档。

## 6. 底座赞赏：shared 适配器的防御工事

`starters/shared/diagram_io.py` 是全项目质量最高的代码：文件名安全（拒目录/符号链接/遍历）、XML 安全（拒 DTD/实体）、2 MiB 上限、内存副本全部成功才落盘 + 临时文件 + 原子 os.replace + 写前二次版本校验（TOCTOU）+ finally 清理。version_conflict 消息前缀让上游可做错误分类。HW3 压缩页面已在 docstring 预告。

## 7. 方法论复盘

- 预注册对账：35% 锚误导赌局（模型没上当）、schema 四键（押"一键之差"60% 输给四处偏差）。
- tripwire → oracle：护栏从猜测式 assert（拦下两次捏造 schema）进化为 probe-oracle（probe 全绿，系统亲口确认）。
- 先读后写：L81 真结构（一行复合 if）两次击碎两行嵌套假设；ABORT 停机换来的 context 直接完成修复设计。
- 翻车史节选：#24 模板想象崩；#25 字符串化（被 compat 救回）；#26 捏造 op schema 四处偏差（六连"未知操作类型"定罪）；#27 把搜索盲区误判为证据不存在（非递归 glob，断言撤回）；#29 两行结构假设（assert 拦截，零写入）；#30 ABORT 未焊退出码。
- 结构性教训：每一个 .get 的键名、每一行"应该长这样"的代码都是假设；假设就要预注册，预注册就要能被物证否决。

## 8. 局限与展望

local_model 非确定性（对照实验靠 replay 档案的三次逐字一致复跑补强）；compare_changes 删页/加页标记非对称（删页一条 `*整页删除*`、加页逐图元）值得 HW3 提前审；HW3：压缩页面处理。
