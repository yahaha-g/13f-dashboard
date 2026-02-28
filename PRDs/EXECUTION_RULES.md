EXECUTION_RULES.md
1. 项目当前状态说明

本项目已经存在一个可运行的 13F Dashboard：

已完成 GitHub + Vercel 部署

已完成 JSON 数据结构

已完成基础页面

已完成 Diff 逻辑

已可正常运行

本次升级属于“架构强化与规范升级”，不是重做项目。

2. 执行原则

在实现 PRD 与技术规范时，必须遵守以下规则：

不允许删除现有页面

不允许重排现有目录结构

不允许重命名已有文件

不允许重写已稳定功能

不允许引入数据库

不允许新增 API Route

不允许改变数据架构

3. 升级方式

必须采用“渐进式升级”：

先抽离数据访问层

再替换 UI 组件

再升级表格

再新增页面

每一步都应最小化改动。

4. 禁止行为

禁止：

全局重构

重新生成 layout

替换 Next.js 框架

删除 data 目录

删除 diff 逻辑

5. 目标

目标是：

在不破坏现有运行系统的前提下，逐步升级为更稳定、更规范的架构。

禁止删改 index.html / workflow / 已有 data 结构（阶段 1）

禁止改 diff 逻辑位置与语义

禁止上数据库、API route

必须用 Next.js 14 + TS + Tailwind + shadcn + TanStack + Recharts + lucide