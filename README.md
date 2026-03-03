# MoneyManager（个人财务管理与分析系统）

MoneyManager 是一个面向个人场景的本地化财务管理 Web 应用，聚焦“记账、分析、预算、订阅管理、目标管理、AI 月度复盘”。

- 后端：Flask 3.1
- 数据库：SQLite（自动初始化）
- 前端：Jinja2 模板 + 原生 JavaScript + Chart.js
- 运行模式：本地离线可用（无需云端依赖）

---

## 功能概览

### 1. 首页仪表盘（`/`）
- 月度汇总：收入、支出、结余
- 图表：每日支出趋势、类别占比
- 今日支出 + 最近交易
- 情绪灯与风险卡片（预算/消费健康/趋势风险）
- 订阅概览与近期扣费提醒
- 目标进度摘要

### 2. 交易与日历
- 快速记账（通过悬浮按钮弹层提交）
- 支持字段：金额、收支类型、日期、主类/子类、标签、备注
- 月视图日历页（`/calendar`）查看每日支出与单日明细

### 3. 分析模块（`/analysis`）
- 月度统计与结构分析
- 类别趋势 / 标签趋势
- 行为识别与消费健康洞察

### 4. 预算模块（`/budget`）
- 总预算与分类预算设置
- 预算执行率、风险等级、趋势提示

### 5. 订阅管理（`/subscriptions`）
- 订阅新增、编辑、取消
- 周期支持：月付 / 年付 / 周付 / 季付
- 月折算成本、即将扣费、过期统计
- 首页/模块联动提醒
- 每次请求前自动补记到期订阅扣费（`before_request`）

### 6. 目标管理（`/goals`）
- 创建储蓄/消费控制目标
- 展示目标进度、剩余金额与截止时间

### 7. AI 月度复盘（`/ai`）
- 自动生成当月复盘数据包
- 内置提示词模板
- 支持导出 JSON（`/api/ai/monthly/export`）
- AI 复盘内容本地归档

---

## 技术栈

- Python 3.10+
- Flask==3.1.0
- SQLite3（Python 标准库）

当前依赖见 [requirements.txt](requirements.txt)。

---

## 快速开始

### 1) 安装依赖

```bash
python -m pip install -r requirements.txt
```

### 2) 启动应用

```bash
python app.py
```

### 3) 访问地址

```text
http://127.0.0.1:5000
```

> 首次启动会自动创建 `data/money_manager.db` 及全部表结构。

---

## 页面路由

- `/`：首页仪表盘
- `/calendar`：交易日历
- `/analysis`：分析页
- `/budget`：预算页
- `/goals`：目标页
- `/subscriptions`：订阅列表
- `/subscriptions/add`：新增订阅
- `/subscriptions/edit/<subscription_id>`：编辑订阅
- `/ai`：AI 月度复盘

---

## REST API 概览

### 交易与统计
- `POST /api/transactions`
- `GET /api/transactions?month=YYYY-MM`
- `GET /api/stats/monthly?month=YYYY-MM`
- `GET /api/stats/category?name=分类名&month=YYYY-MM`
- `GET /api/stats/tags?name=标签名&month=YYYY-MM`
- `GET /api/stats/analysis?month=YYYY-MM`

### 风险与日历
- `GET /api/dashboard/risk-cards?month=YYYY-MM`
- `GET /api/insights/monthly?month=YYYY-MM`
- `GET /api/calendar?month=YYYY-MM`
- `GET /api/calendar/day?date=YYYY-MM-DD`

### 预算
- `POST /api/budgets`
- `GET /api/budgets?month=YYYY-MM`
- `GET /api/budgets/health?month=YYYY-MM`

### 目标
- `POST /api/goals`
- `GET /api/goals`

### 订阅
- `POST /api/subscriptions`
- `GET /api/subscriptions`
- `GET /api/subscriptions/upcoming`
- `GET /api/subscriptions/monthly_cost?month=YYYY-MM`
- `PUT /api/subscriptions/<subscription_id>`
- `DELETE /api/subscriptions/<subscription_id>`

### AI
- `GET /api/ai/monthly?month=YYYY-MM`
- `GET /api/ai/monthly/export?month=YYYY-MM`

---

## 项目结构（核心目录）

```text
MoneyManager/
├─ app.py
├─ config.py
├─ requirements.txt
├─ quick_start.ps1
├─ quick_start.bat
├─ data/
├─ docs/
├─ extensions/
├─ models/
├─ routes/
├─ services/
├─ static/
└─ templates/
```

---

## 数据库说明

数据库初始化逻辑位于 [extensions/database.py](extensions/database.py)，启动时自动确保以下表存在：

- `transactions`
- `budgets`
- `ai_archives`
- `subscriptions`
- `subscription_cancellations`
- `subscription_charges`
- `goals`

---

## 开发说明

- 入口文件：`app.py`（`create_app()` 工厂模式）
- Blueprint 路由拆分在 `routes/`
- 业务逻辑拆分在 `services/`，数据访问与计算在 `models/` / `utils/`
- 详细设计文档见 [docs](docs) 目录

---

## 许可

本项目采用 [LICENSE](LICENSE) 中声明的许可协议。