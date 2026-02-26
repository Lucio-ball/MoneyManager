# MoneyManager（个人财务分析系统）

本项目是一个**本地运行**的个人财务分析 Web 系统，聚焦“快速记账 + 消费分析 + 行为识别 + 预算执行 + AI 月度复盘”。

- 后端：Flask
- 数据库：SQLite
- 前端：原生 HTML + JavaScript + Chart.js
- 运行方式：离线本地运行，不依赖云服务

---

## 核心功能

### 1) 记账模块（`/add`）
- 快速录入：金额、类型、日期、主类/子类、标签、支付方式、备注
- 提交后自动重置
- 最近 10 笔记录即时展示

### 2) 首页仪表盘（`/`）
- 本月总支出 / 总收入 / 结余
- 每日支出折线图
- 类别占比饼图
- 今日支出
- 本月前三消费类别
- 情绪灯（绿/黄/红 + 判定原因）

### 3) 分析模块（`/analysis`）
- 月度分析：收支、类别统计、标签统计
- 类别趋势：最近 3 个月
- 标签趋势：最近 3 个月
- 行为模式识别：异常高支出日、长期高占比类别、冲动/学习投资比例

### 4) 预算模块（`/budget`）
- 设置总预算 / 分类预算
- 自动计算执行率
- 状态识别：正常 / 接近（80%）/ 超支（100%）

### 5) AI 月度复盘（`/ai`）
- 自动生成 AI 输入数据包（JSON）
- 内置提示词模板
- 一键复制：数据包 / 模板 / 模板+数据
- 导出 JSON 文件
- AI 输出本地存档（成长时间轴）

---

## 项目结构

```text
MoneyManager/
├─ app.py
├─ database.py
├─ requirements.txt
├─ data/
│  └─ money_manager.db
├─ templates/
│  ├─ index.html
│  ├─ add.html
│  ├─ analysis.html
│  ├─ budget.html
│  └─ ai.html
└─ README.md
```

---

## 环境要求

- Python 3.10+
- Windows / macOS / Linux

> 首次启动会自动创建 SQLite 数据库文件 `data/money_manager.db` 及相关表结构。

---

## 本地启动

1. 安装依赖

```bash
python -m pip install -r requirements.txt
```

2. 启动服务

```bash
python app.py
```

3. 访问系统

```text
http://127.0.0.1:5000
```

---

## 页面路由

- `/` 首页仪表盘
- `/add` 记账页面
- `/analysis` 分析页面
- `/budget` 预算页面
- `/ai` AI 月度复盘页面

---

## REST API 一览

### 交易
- `POST /api/transactions`
- `GET /api/transactions?month=YYYY-MM`

### 分析
- `GET /api/stats/monthly?month=YYYY-MM`
- `GET /api/stats/category?name=分类名&month=YYYY-MM`
- `GET /api/stats/tags?name=标签名&month=YYYY-MM`

### 行为识别
- `GET /api/insights/monthly?month=YYYY-MM`

### 预算
- `POST /api/budgets`
- `GET /api/budgets?month=YYYY-MM`

### AI 复盘
- `GET /api/ai/monthly?month=YYYY-MM`
- `GET /api/ai/monthly/export?month=YYYY-MM`（下载 JSON 文件）

---

## 示例请求

### 新增交易

```json
POST /api/transactions
{
	"amount": 23.5,
	"type": "expense",
	"date": "2026-02-26",
	"category_main": "餐饮",
	"category_sub": "外卖",
	"tags": ["冲动", "校外"],
	"payment_method": "wechat",
	"note": "奶茶"
}
```

### 新增预算

```json
POST /api/budgets
{
	"month": "2026-02",
	"category_main": "餐饮",
	"budget_amount": 500
}
```

---

## 说明与约定

- `tags` 在数据库中以 JSON 字符串存储。
- `budgets` 表遵循 DDL 设计，执行率与状态由后端动态计算返回。
- 情绪灯优先依据“总预算执行率”判定；若无总预算，则使用近 3 个月月均支出做基线判定。

---

## 后续可扩展方向

- 情绪灯历史趋势（近 3 个月）
- AI 提示词模板多风格切换（严格分析/温和教练/极简行动）
- 数据导出 CSV / Excel
- 鉴权与多用户支持