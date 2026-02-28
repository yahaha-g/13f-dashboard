# 第一部分

# 13F Dashboard UI Design Spec v2.0（与架构完全对齐）

设计目标：

* 极简量化风
* 数据优先
* 行为标签为视觉核心
* 完全基于静态 JSON 架构
* 不依赖 API 动态查询

---

# 一、全局设计原则

1. 深色主题（默认）
2. 信息密度高
3. 无渐变
4. 无玻璃拟态
5. 行为标签视觉突出
6. 表格为核心组件
7. 所有 ChangeTag 大写

---

# 二、全局布局结构

```
┌──────────────────────────────────────────────────────────────┐
│ 13F Dashboard                          Q1 2025   🌙 Dark    │
├──────────────────────────────────────────────────────────────┤
│ Overview | Institutions | Top Movers | Timeline             │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│                    Page Content Area                         │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

说明：

* 顶部固定
* 最大宽度 1280px
* 中心对齐
* 侧边距统一 24px

---

# 三、Overview 页面草图（基于 diff JSON）

数据来源：

* /data/diff 最新季度

---

## 页面结构

```
┌──────────────────────────────────────────────────────────────┐
│ Quarter: 2025Q1                                              │
│ Filing Date Range: May 15 - Aug 15                          │
└──────────────────────────────────────────────────────────────┘

Institution Summary

┌──────────────────────────────────────────────────────────────┐
│ Berkshire Hathaway                                           │
│ Holdings: 42         Total Value: $350B                     │
│ Top1: AAPL (38%)                                            │
│                                                              │
│ [ NEW 3 ]  [ ADD 5 ]  [ TRIM 2 ]  [ EXIT 1 ]                │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ Bridgewater Associates                                       │
│ Holdings: 128        Total Value: $18B                      │
│ Top1: SPY (12%)                                             │
│                                                              │
│ [ NEW 8 ]  [ ADD 3 ]  [ TRIM 6 ]  [ EXIT 4 ]                │
└──────────────────────────────────────────────────────────────┘
```

视觉规则：

* 行为标签为色块
* NEW = 绿色
* ADD = 浅绿
* TRIM = 橙色
* EXIT = 红色

---

# 四、Institution Detail 页面草图

数据来源：

* 当前季度 JSON
* diff JSON

---

```
┌──────────────────────────────────────────────────────────────┐
│ ← Back        Berkshire Hathaway          2025Q1            │
├──────────────────────────────────────────────────────────────┤

Statistics

┌──────────────┬──────────────┬──────────────┬──────────────┐
│ Total Value  │ Holdings     │ Top1 Weight  │ Top10 Conc   │
│ $350B        │ 42           │ 38%          │ 78%          │
└──────────────┴──────────────┴──────────────┴──────────────┘

Behavior Summary

[ NEW 3 ]   [ ADD 5 ]   [ TRIM 2 ]   [ EXIT 1 ]

--------------------------------------------------------------

Holdings

Filter:  All | NEW | ADD | TRIM | EXIT
Sort: Weight ↓

┌──────────────┬──────────┬──────────┬────────┬──────────┐
│ Issuer       │ Value    │ Weight   │ Shares │ Change   │
├──────────────┼──────────┼──────────┼────────┼──────────┤
│ Apple        │ 120B     │ 38%      │ 10M    │ ADD      │
│ Coca-Cola    │ 25B      │ 8%       │ 5M     │ TRIM     │
│ Chevron      │ 18B      │ 6%       │ 3M     │ NEW      │
└──────────────┴──────────┴──────────┴────────┴──────────┘
```

设计重点：

* 表格为主要视觉
* ChangeTag 为小标签
* Weight 使用进度条辅助（可选）

---

# 五、Top Movers 页面草图

数据来源：

* diff JSON 聚合

```
Top Movers — 2025Q1

Largest NEW

┌──────────────┬──────────┬──────────┐
│ Institution  │ Issuer   │ Shares   │
├──────────────┼──────────┼──────────┤
│ Bridgewater  │ NVDA     │ +3M      │
└──────────────┴──────────┴──────────┘

Largest ADD
Largest TRIM
Largest EXIT
```

排序字段：

* shares_change

---

# 六、Timeline 页面草图

数据来源：

* 最近 8 季度 JSON

```
Stock: AAPL
Institution: Berkshire Hathaway

Weight Over Time

┌───────────────────────────────────────────────┐
│                  Line Chart                   │
└───────────────────────────────────────────────┘

Entry / Exit Log

2022Q1   NEW
2023Q2   ADD
2024Q4   TRIM
```

设计原则：

* 线图极简
* 无渐变
* 仅 2–3 种颜色

---

# 七、颜色规范

背景：

#0B1220

卡片：

#111827

边框：

#1F2937

文字主色：

#F9FAFB

行为颜色：

NEW  → #22C55E
ADD  → #4ADE80
TRIM → #F59E0B
EXIT → #EF4444

---

# 第二部分

# 推荐前端框架与组件体系（Cursor 直接使用）

目标：

* 成熟
* 稳定
* 社区大
* 和静态 JSON 架构兼容

---

# 1️⃣ 框架选择

✅ Next.js 14（App Router）
✅ TypeScript
✅ Tailwind CSS

原因：

* 静态构建优秀
* Vercel 原生支持
* 支持 SSG（适合 JSON 架构）
* 长期维护稳定

---

# 2️⃣ UI 组件体系

推荐：

✅ shadcn/ui
✅ Radix UI（底层无样式组件）

理由：

* 成熟
* 无重型依赖
* 可控样式
* 非企业 SaaS 风格（适合量化风）

---

# 3️⃣ 表格组件

推荐：

✅ TanStack Table (React Table)

原因：

* 强排序
* 强筛选
* 强性能
* 不依赖后端

---

# 4️⃣ 图表组件

推荐：

✅ Recharts

理由：

* 简洁
* 与 Tailwind 兼容
* 适合极简风

---

# 5️⃣ 状态管理

无需复杂方案：

* 仅使用 React state
* 不需要 Redux
* 不需要 Zustand

因为：

* 数据静态
* 不跨页面共享复杂状态

---

# 6️⃣ Cursor 开发基础依赖清单

让 Cursor 生成时使用：

```
next
react
typescript
tailwindcss
shadcn/ui
@tanstack/react-table
recharts
clsx
lucide-react
```

---

# 七、项目结构建议

```
app/
  overview/
  institution/[slug]/
  top-movers/
  timeline/
components/
  layout/
  table/
  charts/
lib/
  loadData.ts
data/
config/
```
