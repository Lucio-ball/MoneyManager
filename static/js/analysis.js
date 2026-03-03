const analysisDataElement = document.getElementById("analysis-dashboard-data");
const analysisData = analysisDataElement ? JSON.parse(analysisDataElement.textContent) : {};

const structure = analysisData.structure || {};
const rhythm = analysisData.rhythm || {};
const trends = analysisData.trends || {};
const consumptionHealth = analysisData.consumption_health || {};

const chartTheme = window.MMChartTheme || {
  palette: ["#2563EB", "#0EA5E9", "#14B8A6", "#22C55E", "#F59E0B", "#EF4444", "#64748B", "#8B5CF6"],
  lineOptions() {
    return {
      responsive: true,
      plugins: {
        legend: { labels: { color: "#475569", boxWidth: 10, usePointStyle: true, pointStyle: "circle" } },
      },
      scales: {
        x: { grid: { color: "rgba(100, 116, 139, 0.14)" }, ticks: { color: "#64748B" } },
        y: { grid: { color: "rgba(100, 116, 139, 0.14)" }, ticks: { color: "#64748B" } },
      },
    };
  },
  pieOptions() {
    return {
      plugins: {
        legend: {
          position: "bottom",
          labels: { color: "#475569", boxWidth: 10, usePointStyle: true, pointStyle: "circle" },
        },
      },
    };
  },
  alpha(color, alpha) {
    const value = String(color || "").replace("#", "");
    if (value.length !== 6) return "rgba(37, 99, 235, 0.16)";
    const r = parseInt(value.slice(0, 2), 16);
    const g = parseInt(value.slice(2, 4), 16);
    const b = parseInt(value.slice(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  },
  buildPalette(size) {
    const result = [];
    for (let i = 0; i < size; i += 1) result.push(this.palette[i % this.palette.length]);
    return result;
  },
};

function lineOptions() {
  return chartTheme.lineOptions();
}

function buildPalette(size) {
  return chartTheme.buildPalette(size);
}

const healthDimensions = consumptionHealth.dimensions || [];
if (healthDimensions.length > 0) {
  new Chart(document.getElementById("consumptionHealthRadarChart"), {
    type: "radar",
    data: {
      labels: healthDimensions.map((item) => item.label),
      datasets: [
        {
          label: "消费健康度",
          data: healthDimensions.map((item) => item.value),
          borderColor: "#2563EB",
          backgroundColor: chartTheme.alpha("#2563EB", 0.2),
          pointRadius: 3,
          pointHoverRadius: 4,
          borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: {
          labels: { color: "#475569", boxWidth: 10, usePointStyle: true, pointStyle: "circle" },
        },
      },
      scales: {
        r: {
          suggestedMin: 0,
          suggestedMax: 100,
          grid: { color: "rgba(100, 116, 139, 0.2)" },
          angleLines: { color: "rgba(100, 116, 139, 0.2)" },
          pointLabels: { color: "#475569", font: { size: 12 } },
          ticks: { color: "#64748B", backdropColor: "transparent", stepSize: 20 },
        },
      },
    },
  });
}

const categoryStats = structure.category_stats || [];
if (categoryStats.length > 0) {
  new Chart(document.getElementById("categoryStructureChart"), {
    type: "pie",
    data: {
      labels: categoryStats.map((item) => item.name),
      datasets: [
        {
          data: categoryStats.map((item) => item.amount),
          borderWidth: 0,
          backgroundColor: buildPalette(categoryStats.length),
        },
      ],
    },
    options: chartTheme.pieOptions(),
  });
}

const dailyExpense = rhythm.daily_expense || [];
if (dailyExpense.length > 0) {
  new Chart(document.getElementById("dailyRhythmChart"), {
    type: "line",
    data: {
      labels: dailyExpense.map((item) => item.date),
      datasets: [
        {
          label: "每日支出",
          data: dailyExpense.map((item) => item.amount),
          borderColor: "#2563EB",
          backgroundColor: chartTheme.alpha("#2563EB", 0.16),
          pointRadius: 2,
          pointHoverRadius: 4,
          borderWidth: 2.2,
          tension: 0.36,
          fill: true,
        },
      ],
    },
    options: lineOptions(),
  });
}

const categoryTrend = trends.category_trend || { months: [], series: [] };
if ((categoryTrend.series || []).length > 0) {
  const categoryPalette = buildPalette(categoryTrend.series.length);
  new Chart(document.getElementById("categoryTrendChart"), {
    type: "line",
    data: {
      labels: categoryTrend.months || [],
      datasets: categoryTrend.series.map((item, index) => ({
        label: item.name,
        data: item.values || [],
        borderColor: categoryPalette[index],
        backgroundColor: chartTheme.alpha(categoryPalette[index], 0.14),
        fill: false,
        tension: 0.24,
      })),
    },
    options: lineOptions(),
  });
}

const tagTrend = trends.tag_trend || { months: [], series: [] };
if ((tagTrend.series || []).length > 0) {
  const tagPalette = ["#EF4444", "#22C55E", "#0EA5E9", "#F59E0B"];
  new Chart(document.getElementById("tagTrendChart"), {
    type: "line",
    data: {
      labels: tagTrend.months || [],
      datasets: tagTrend.series.map((item, index) => ({
        label: item.name,
        data: item.values || [],
        borderColor: tagPalette[index % tagPalette.length],
        backgroundColor: chartTheme.alpha(tagPalette[index % tagPalette.length], 0.14),
        fill: false,
        tension: 0.24,
      })),
    },
    options: lineOptions(),
  });
}

const totalExpenseTrend = trends.total_expense_trend || [];
if (totalExpenseTrend.length > 0) {
  new Chart(document.getElementById("totalExpenseTrendChart"), {
    type: "bar",
    data: {
      labels: totalExpenseTrend.map((item) => item.month),
      datasets: [
        {
          label: "总支出",
          data: totalExpenseTrend.map((item) => item.amount),
          borderRadius: 8,
          backgroundColor: "#2563EB",
        },
      ],
    },
    options: lineOptions(),
  });
}

const subscriptionTrend = trends.subscription_cost_trend || [];
if (subscriptionTrend.length > 0) {
  new Chart(document.getElementById("subscriptionTrendChart"), {
    type: "line",
    data: {
      labels: subscriptionTrend.map((item) => item.month),
      datasets: [
        {
          label: "订阅折算成本",
          data: subscriptionTrend.map((item) => item.amount),
          borderColor: "#F59E0B",
          backgroundColor: chartTheme.alpha("#F59E0B", 0.2),
          fill: true,
          tension: 0.24,
        },
      ],
    },
    options: lineOptions(),
  });
}

const budgetExecutionTrend = trends.budget_execution_trend || [];
if (budgetExecutionTrend.length > 0) {
  new Chart(document.getElementById("budgetExecutionTrendChart"), {
    type: "bar",
    data: {
      labels: budgetExecutionTrend.map((item) => item.month),
      datasets: [
        {
          type: "bar",
          label: "实际支出",
          data: budgetExecutionTrend.map((item) => item.actual),
          borderRadius: 8,
          backgroundColor: "#2563EB",
          yAxisID: "y",
        },
        {
          type: "line",
          label: "预算",
          data: budgetExecutionTrend.map((item) => item.budget),
          borderColor: "#F59E0B",
          backgroundColor: chartTheme.alpha("#F59E0B", 0.2),
          tension: 0.24,
          yAxisID: "y",
        },
        {
          type: "line",
          label: "执行率(%)",
          data: budgetExecutionTrend.map((item) => item.execution_rate),
          borderColor: "#EF4444",
          backgroundColor: chartTheme.alpha("#EF4444", 0.2),
          tension: 0.24,
          yAxisID: "y1",
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { labels: { color: "#475569", boxWidth: 10, usePointStyle: true, pointStyle: "circle" } },
      },
      scales: {
        x: { grid: { color: "rgba(100, 116, 139, 0.14)" }, ticks: { color: "#64748B" } },
        y: { grid: { color: "rgba(100, 116, 139, 0.14)" }, ticks: { color: "#64748B" } },
        y1: {
          position: "right",
          grid: { drawOnChartArea: false },
          ticks: { color: "#64748B" },
          suggestedMin: 0,
          suggestedMax: 150,
        },
      },
    },
  });
}

const budgetDeviation = trends.budget_category_deviation || [];
if (budgetDeviation.length > 0) {
  new Chart(document.getElementById("budgetDeviationChart"), {
    type: "bar",
    data: {
      labels: budgetDeviation.map((item) => item.category),
      datasets: [
        {
          label: "偏离金额",
          data: budgetDeviation.map((item) => item.deviation_amount),
          borderRadius: 8,
          backgroundColor: budgetDeviation.map((item) => (item.deviation_amount > 0 ? "#EF4444" : "#22C55E")),
        },
      ],
    },
    options: lineOptions(),
  });
}
