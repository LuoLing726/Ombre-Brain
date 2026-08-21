# 施工单：把散落的珍珠串成能主动追溯的网（读取层）

> 创建：2026-08-21。目标：先「把门打开」——读取层落地，建的部分后聊。

## 现状（已摸清）

- 后端已在自动建边（`same_event` / `continuation_of` / `related_to`），存于桶 `metadata.relation_links`，双向写入、fire-and-forget。
- 因果边（`caused_by` / `causes`）**永不自动建**（存量手动数据仍可能存在）。
- 但浮现层只露出 `relation_hint` 的两条裸 id（`↳ 前段 → 7f3a…`），无标题、无时间、无方向分组，也没有「顺着走」的入口。
- 桶结构：`{id, content, metadata}`；metadata 有 `title`（120 上限）、`created`、`type`、`relation_links` 等。
- 读桶抓手：`rt.bucket_mgr.get(bucket_id)` / `get_including_archive(bucket_id)`。

## 三刀（按风险从低到高）

### 第一刀：recall（回想）—— 走路的大门 ✅ 已完成
- 位置：新建 `src/tools/recall/__init__.py` + `src/tools/recall/core.py`
- 职责：给定 `bucket_id`，返回该桶正文 + 完整路口（按方向分组：← 之前 / → 之后 / ≈ 同刻 / ↔ 相关，每条带邻居标题 + 日期 + id）。
- 注册：`server.py` 加 `@mcp.tool()` 的 `recall`，薄封装转发。
- 测试：`tests/test_recall.py`（4 用例，带 @pytest.mark.asyncio）。

### 第二刀：thread（串珠）—— 话题时间线 ✅ 已完成
- 位置：新建 `src/tools/thread/__init__.py` + `src/tools/thread/core.py`
- 职责：给定关键词，检索相关桶 → 按创建时间升序排成一条线 → 每站一行（序号 + 日期 + 标题 + id）。0 LLM 调用。
- 复用 recall.core 的 `_bucket_title` / `_bucket_date` / `_EXCLUDED_TYPES`。
- 排序已处理 aware/naive 时区混排（统一转 naive）。
- 注册：`server.py` 加 `@mcp.tool()` 的 `thread`。
- 测试：`tests/test_thread.py`（4 用例，带 @pytest.mark.asyncio）。

### 第三刀：breath 路口升级（分组方向化）✅ 已完成（轻量版）
- 位置：`src/ombrebrain/storage/relation_store.py`
- 职责：
  - 新增共享 `render_junction`（async，完整版：读邻居带标题/日期），供 recall 用。
  - 新增 `bucket_title`（四级回退）/ `bucket_date` / `bucket_type` / `EXCLUDED_RELATION_TYPES` / `DIRECTION_GROUPS`。
  - 升级 `relation_hint` 为「按方向分组 + 目标 id」的轻量版（零 I/O），自动惠及 breath 主浮现 / catalog / dream 三处。
- 重构：`recall/core.py` 改用共享 `render_junction`（删掉自己的重复分组）；`thread/core.py` 改 import 到 relation_store。
- 未改：`_verbatim.py` / `catalog.py` / `dream/output.py`（relation_hint 签名兼容，自动升级）。

### 第四刀：breath inline 标题化 — 决策：保持分层，暂不做
- 目标（原设想）：让主 breath 浮现末尾的路口也带邻居标题/日期。
- 判断（2026-08-21）：暂缓，倾向不做。理由：
  1. token 预算：breath 主浮现有 breath_max_tokens（默认 10000），正文逐字不截断、放不下整桶省略；
     路口带标题日期会吃掉预算、挤占正文，违背「浮现是为了读正文」的初衷。recall 单条展开无此压力。
  2. 回忆的分层本来就是对：breath 给「模糊方向」，recall 给「专注展开」。人回忆先想起「有这条线」，
     细节是「再想一下」才浮现。把 breath 也做完整 = 把 recall 的活重复一遍。
  3. 风险收益不成比例：异步化 render_stored_bucket 改 14 处源码 + 11 处测试，只省一次 recall 点击。
- 折中（若将来要做）：不异步化 render_stored_bucket，而是在 breath 渲染前的 async 循环里批量预取
  邻居标题，把标题 map 作为参数传进渲染函数。改动小、可批量避免 N×M 串行 I/O、不破坏 11 处测试。

## 标签映射（读侧展示用）

| relation 类型 | 路口标签 |
|---|---|
| continuation_of | ← 之前 |
| continues | → 之后 |
| same_event | ≈ 同刻 |
| related_to | ↔ 相关 |
| caused_by（存量） | ← 因为 |
| causes（存量） | → 所以 |
| custom | 自定义·label |

## 边界（不碰）

- 只碰读取 / 展示层。不碰写入、不碰建边、不碰遗忘/衰减、不碰原文证据、不碰删除/归档。
- 因果边维持「不自动建」；读侧保留对存量因果边的显示。

## 建的部分（待聊，先不动）

- 经历线「补线」：要不要让模型能自己补一条漏掉的边（3.0.0 关闭的手动入口）。
- 话题线「固化」：thread 现查现排 vs 预先归簇固化。

## 环境变量 / 路径依赖

- 本批改动不新增、不修改任何环境变量，不新增磁盘路径。
