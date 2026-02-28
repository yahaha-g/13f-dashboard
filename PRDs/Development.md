# 13F Dashboard

# Technical Architecture Document v1.0

---

# 1. 总体技术目标

本项目必须满足：

* 使用成熟主流框架
* 依赖稳定开源组件
* 不自行实现复杂基础设施
* 不手写复杂表格/图表/状态管理
* 前端仅负责渲染
* 所有数据计算在 Python 端完成

---

# 2. 技术栈选型（已锁定）

## 前端框架

### ✅ Next.js 14 (App Router)

理由：

* Vercel 原生支持
* 静态生成（SSG）优秀
* 文件路由清晰
* 长期维护稳定

---

## 类型系统

### ✅ TypeScript

强制开启：

```
"strict": true
```

---

## 样式系统

### ✅ Tailwind CSS

原因：

* 成熟稳定
* 与 shadcn 兼容
* 不写手动 CSS
* 不写 SCSS

---

## UI 组件库

### ✅ shadcn/ui

基于：

* Radix UI
* Tailwind
* 可控样式
* 无多余企业 SaaS 风

禁止：

* 自己写 Button / Modal / Tabs
* 自己写 Select

---

## 表格组件

### ✅ TanStack Table v8

原因：

* 排序成熟
* 筛选成熟
* 性能好
* 不用自己实现排序逻辑

禁止：

* 手写表格排序
* 手写分页逻辑

---

## 图表库

### ✅ Recharts

原因：

* 简洁
* 社区成熟
* 与 React 兼容好
* 适合量化风

禁止：

* 自己用 canvas 写图
* 使用冷门图表库

---

## 图标

### ✅ lucide-react

轻量、与 shadcn 兼容。

---

# 3. 数据架构（静态 JSON 模式）

## 数据来源

```
/data/
```

全部为静态 JSON。

前端：

* 不调用外部 API
* 不请求数据库
* 不计算 diff

---

## 数据加载方式

使用：

```
import fs from "fs"
import path from "path"
```

在 Server Component 中读取。

禁止：

* 在客户端 fetch JSON
* 在客户端算 diff

---

## 数据访问层

必须创建：

```
/lib/data.ts
```

封装函数：

```
getLatestQuarter()
getInstitutionList()
getInstitutionDetail(slug)
getTopMovers()
getTimeline(slug, ticker)
```

页面不允许直接读 JSON 文件。

---

# 4. 目录结构规范

```
app/
  layout.tsx
  page.tsx
  overview/page.tsx
  institution/[slug]/page.tsx
  top-movers/page.tsx
  timeline/page.tsx

components/
  layout/
    Header.tsx
    Nav.tsx
  cards/
    InstitutionCard.tsx
  tables/
    HoldingsTable.tsx
  charts/
    WeightChart.tsx
  ui/ (shadcn components)

lib/
  data.ts
  types.ts

config/
  institutions.json

data/
```

---

# 5. 页面架构策略

## Server Components 优先

* 页面为 Server Component
* 表格和图表为 Client Component

这样：

* SEO 好
* 构建稳定
* 数据安全

---

# 6. Overview 页面实现策略

使用：

* InstitutionCard 组件
* shadcn Card
* 行为标签用 Badge

禁止：

* 自己写卡片样式
* 自己写行为标签组件

---

# 7. Institution Detail 页面

使用：

* TanStack Table
* shadcn Tabs（用于筛选）
* shadcn Badge（用于 ChangeTag）

表格：

* 列定义在单独文件
* 排序由 TanStack 管理

禁止：

* 自己实现排序逻辑

---

# 8. Top Movers 实现

在：

```
lib/data.ts
```

中聚合。

页面仅渲染结果。

---

# 9. Timeline 页面实现

使用：

* Recharts LineChart
* ResponsiveContainer

禁止：

* 手写 svg 图

---

# 10. 状态管理

不使用：

* Redux
* MobX
* Zustand

仅用：

* React state
* useMemo
* useCallback

因为：

* 数据是静态的
* 无复杂共享状态

---

# 11. 主题与样式规范

仅支持：

* Dark mode（默认）
* 可后期加 Light

使用：

shadcn + Tailwind variables

禁止：

* 自己设计复杂主题系统

---

# 12. GitHub Actions（数据层）

Python 3.11

使用：

* requests
* pandas

禁止：

* Node 抓取数据
* 在前端计算 diff

---

# 13. 性能策略

* 只保留 8 季度
* 单 JSON < 1MB
* 不做客户端大规模运算

---

# 14. 错误处理

页面必须处理：

* 无数据
* JSON 为空
* slug 不存在

使用：

shadcn Alert

---

# 15. 开发优先级顺序

阶段 1：

* Layout
* Overview
* 数据加载封装

阶段 2：

* Institution Detail
* 表格排序
* ChangeTag 渲染

阶段 3：

* Top Movers
* Timeline

---

# 16. 禁止事项（防止 Cursor 乱写）

禁止：

* 自己写 table 排序
* 自己写 modal
* 自己写 tabs
* 自己写 dropdown
* 使用低活跃度库
* 使用 CSS modules
* 写 SCSS
* 使用 Redux
* 写 API Route

---

# 17. 最终技术栈依赖清单

```
next
react
typescript
tailwindcss
shadcn/ui
@tanstack/react-table
recharts
lucide-react
clsx
zod
```

---

# 18. 为什么这个方案稳定？

* 纯静态数据
* 无数据库
* 无后端 API
* 无客户端复杂计算
* 组件全部来自成熟生态
* 仅聚焦渲染层

---

# 19. 未来可升级路径

当：

* > 200 机构
* > 40 季度
* 跨机构股票分析

升级：

* Postgres
* API 层
* Edge cache

当前阶段不做。

---

