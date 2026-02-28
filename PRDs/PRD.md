# 13F Dashboard

## Product & Engineering Specification v3.0

---

# 1. 项目概述

13F Dashboard 是一个基于 SEC 13F 披露数据构建的机构投资行为分析系统。

本产品不强调“机构持有什么”，
而强调：

* 行为变化识别
* 季度对比分析
* 机构信念轨迹
* 多季度行为结构

核心理念：

Institutional Behavior > Static Holdings

---

# 2. 产品定位

本产品是一个机构投资行为分析系统。

不包含：

* 交易功能
* 用户账户系统
* 社交功能
* 实时行情数据
* 投资组合管理工具
* 数据库依赖

专注于：

* 行为变化识别
* 季度对比分析
* 持仓结构可视化
* 多季度行为轨迹

---

# 3. 架构决策（已锁定）

采用：

Static JSON + GitHub Actions + Vercel

具体：

* 所有数据以 JSON 文件形式存储在 GitHub Repo
* GitHub Actions 自动抓取 + 生成 + Diff
* Vercel 仅负责静态构建和展示
* 前端不参与数据计算

不使用：

* 数据库
* 后端 API
* 浏览器本地存储作为数据源

---

# 4. 数据保留策略

仅保留最近 8 个季度。

规则：

* 每次 GitHub Action 运行后
* 若季度数 > 8
* 删除最旧季度
* 重新生成 diff

目标：

* 控制 repo 体积
* 保持构建稳定
* 保证前端加载性能

---

# 5. 数据目录结构

```
/data/
  ├── quarters.json
  ├── 2025Q1/
  │     ├── berkshire.json
  │     ├── bridgewater.json
  ├── 2024Q4/
  ├── ...
  ├── diff/
        ├── 2025Q1_berkshire.json
        ├── 2025Q1_bridgewater.json
```

---

# 6. 机构配置（支持未来自定义机构）

新增：

```
/config/institutions.json
```

结构：

```
[
  {
    "name": "Berkshire Hathaway",
    "cik": "0001067983",
    "slug": "berkshire"
  }
]
```

规则：

* GitHub Action 读取该配置
* 自动抓取对应 CIK
* 自动生成 JSON
* 新增机构仅需修改配置文件

当前阶段：

仅支持开发者修改 config，不支持前端输入。

---

# 7. 原始季度数据结构

每个机构一个文件：

```
{
  "institution": "Berkshire Hathaway",
  "cik": "0001067983",
  "quarter": "2025Q1",
  "filing_date": "2025-05-15",
  "total_value_usd": 350000000000,
  "holdings": [
    {
      "issuer": "Apple Inc",
      "ticker": "AAPL",
      "cusip": "...",
      "value_usd": 120000000000,
      "shares": 10000000
    }
  ]
}
```

要求：

* shares 必须为整数
* ticker + cusip 必须存在
* 所有字段固定，不允许动态变化

---

# 8. 行为标签标准

统一大写枚举：

NEW
ADD
TRIM
EXIT

内部保留状态：

UNCHANGED（仅内部使用）

---

# 9. Diff Engine（核心逻辑）

Diff 以 shares 为唯一判断标准。

规则：

```
NEW  → 上季度不存在，本季度存在
EXIT → 上季度存在，本季度不存在
ADD  → shares_current > shares_previous
TRIM → shares_current < shares_previous
UNCHANGED → shares_current == shares_previous
```

稳定性原则：

* 不使用 value_usd 判断行为
* 忽略价格波动
* 仅以持仓数量变化判断

匹配规则：

* ticker + cusip 双重校验
* 若 ticker 变化但 cusip 相同，视为同一标的

---

# 10. Diff 文件结构

```
{
  "institution": "Berkshire Hathaway",
  "quarter": "2025Q1",
  "previous_quarter": "2024Q4",
  "summary": {
    "NEW": 3,
    "ADD": 5,
    "TRIM": 2,
    "EXIT": 1
  },
  "holdings": [
    {
      "issuer": "Apple Inc",
      "ticker": "AAPL",
      "shares": 10000000,
      "change": "ADD",
      "shares_change": 1000000
    }
  ]
}
```

前端：

* 只读取 diff
* 不自行计算 change

---

# 11. 页面模块设计

遵循极简量化风格：

* 深色
* 克制
* 数据优先
* 行为突出

---

## 11.1 Overview Page

数据来源：

* 最新季度 diff

展示：

* Institution
* Quarter
* Filing Date
* Holdings Count
* Top1 Holding
* NEW / ADD / TRIM / EXIT

---

## 11.2 Institution Detail Page

数据来源：

* 当前季度 JSON
* diff JSON

功能：

* Statistics Panel
* Behavior Summary
* Holdings Table
* ChangeTag 筛选
* Weight 排序

---

## 11.3 Top Movers

从 diff JSON 聚合：

* 最大 NEW
* 最大 ADD
* 最大 TRIM
* 最大 EXIT

按：

* shares_change 排序

---

## 11.4 Timeline

读取最近 8 季度数据：

* 生成持仓历史
* 生成 ENTRY / EXIT 记录

前端不计算 diff，仅展示历史。

---

# 12. 自动更新流程

GitHub Action：

```
schedule:
  cron: '0 1 * * *'
```

执行流程：

1. 读取 institutions.json
2. 抓取 SEC 13F 数据
3. 生成季度 JSON
4. 运行 Diff Engine
5. 生成 diff JSON
6. 删除最旧季度（若 >8）
7. commit + push

---

# 13. 性能与规模边界

当前设计目标：

* 50 家机构以内
* 8 季度以内
* 单机构单季度 < 1MB

保证：

* Vercel 构建稳定
* 页面加载 < 1s
* 无数据库依赖

---

# 14. 稳定性优先设计原则

1. 所有计算在 Python 端完成
2. 前端只负责渲染
3. 所有枚举固定大写
4. JSON 结构固定
5. 不允许客户端生成 diff

---

# 15. 未来扩展路径

若出现：

* > 200 家机构
* > 40 季度
* 跨机构股票聚合分析

再升级为：

* PostgreSQL
* 或 ClickHouse

当前阶段不使用数据库。

---

# 16. 产品核心价值

本产品关注：

* 谁在加仓
* 谁在减仓
* 谁在建仓
* 谁在清仓
* 谁在持续持有

它是：

Institutional Behavior Intelligence Engine


