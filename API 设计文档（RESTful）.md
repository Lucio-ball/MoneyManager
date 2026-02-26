## 基础 URL

```
http://localhost:5000
```

------

## 3.1 交易相关

### POST `/api/transactions`

新增一笔交易
 **Request JSON:**

```json
{
  "amount": 23.5,
  "type": "expense",
  "date": "2025-02-26",
  "category_main": "餐饮",
  "category_sub": "外卖",
  "tags": ["冲动", "校外"],
  "payment_method": "wechat",
  "note": "奶茶"
}
```

### GET `/api/transactions?month=2025-02`

获取某月所有交易

------

## 3.2 分析相关

### GET `/api/stats/monthly?month=2025-02`

返回：

- 总支出
- 总收入
- 结余
- 类别统计
- 标签统计
- 每日支出数组

### GET `/api/stats/category?name=餐饮`

返回最近 3 个月趋势

### GET `/api/stats/tags?name=冲动`

返回标签趋势

------

## 3.3 行为模式识别

### GET `/api/insights/monthly?month=2025-02`

返回：

- 异常高支出日
- 长期高占比类别
- 冲动消费比例
- 学习投资比例

------

## 3.4 预算模块

### POST `/api/budgets`

新增预算

### GET `/api/budgets?month=2025-02`

获取预算 + 执行情况

------

## 3.5 AI 复盘数据包

### GET `/api/ai/monthly?month=2025-02`

返回完整 JSON 数据包