# MoneyManager（个人财务分析系统）

本项目是一个**本地运行**的个人财务分析 Web 系统，聚焦“快速记账 + 消费分析 + 行为识别 + 预算执行 + 订阅管理 + AI 月度复盘”。

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

### 6) 订阅管理（`/subscriptions`）
- 订阅列表卡片化展示，支持编辑与取消
- KPI：订阅月折算总成本、未来 7 天即将扣费、已过期数量
- 自动折算：年付自动按月折算（`amount / 12`）
- Chart.js 图表：订阅周期分布、月折算成本 TOP5
- 首页仪表盘集成订阅提醒区块

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

### Windows 一键快速启动

项目提供快速启动脚本：

- [quick_start.ps1](quick_start.ps1)
- [quick_start.bat](quick_start.bat)

常用命令：

```powershell
# 只安装依赖并启动
./quick_start.ps1

# 安装依赖 + 生成虚拟数据 + 启动
./quick_start.ps1 -SeedData

# 清空后重建虚拟数据 + 启动
./quick_start.ps1 -SeedData -ResetData

# 仅做检查，不真正启动服务
./quick_start.ps1 -NoRun
```

也可以直接双击运行：

```text
quick_start.bat
```

---

## 生成评测用虚拟数据

项目提供了数据种子脚本 [seed_data.py](seed_data.py)，可快速生成多月份的交易、预算和 AI 存档数据。

### 追加生成（不清空已有数据）

```bash
python seed_data.py --months 6 --seed 20260226
```

### 清空后重建（谨慎）

```bash
python seed_data.py --months 6 --seed 20260226 --reset
```

参数说明：

- `--months`：生成最近 N 个月数据（默认 6）
- `--seed`：随机种子（同种子可复现同分布）
- `--reset`：先清空 `transactions / budgets / ai_archives` 再生成

---

## 页面路由

- `/` 首页仪表盘
- `/add` 记账页面
- `/analysis` 分析页面
- `/budget` 预算页面
- `/subscriptions` 订阅列表页面
- `/subscriptions/add` 新增订阅页面
- `/subscriptions/edit/<id>` 编辑订阅页面
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

### 订阅
- `POST /api/subscriptions`
- `GET /api/subscriptions`
- `GET /api/subscriptions/upcoming`（未来 7 天）
- `GET /api/subscriptions/monthly_cost`（按月折算）
- `PUT /api/subscriptions/<id>`
- `DELETE /api/subscriptions/<id>`

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