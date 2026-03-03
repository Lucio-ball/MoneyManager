const analysisDataElement = document.getElementById("analysis-dashboard-data");
const analysisData = analysisDataElement ? JSON.parse(analysisDataElement.textContent) : {};

const structure = analysisData.structure || {};
const rhythm = analysisData.rhythm || {};
const trends = analysisData.trends || {};

const commonGridColor = "rgba(107, 114, 128, 0.08)";
const commonTextColor = "#6B7280";

function lineOptions() {
  return {
    responsive: true,
    plugins: {
      legend: { labels: { color: "#374151", boxWidth: 10, usePointStyle: true, pointStyle: "circle" } },
    },
    scales: {
      x: { grid: { color: commonGridColor }, ticks: { color: commonTextColor } },
      y: { grid: { color: commonGridColor }, ticks: { color: commonTextColor } },
    },
  };
}

function buildPalette(size) {
  const colors = ["#2563EB", "#0EA5E9", "#14B8A6", "#22C55E", "#F59E0B", "#EF4444", "#64748B", "#8B5CF6"];
  const result = [];
  for (let i = 0; i < size; i += 1) result.push(colors[i % colors.length]);
  return result;
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
    options: {
      plugins: {
        legend: {
          position: "bottom",
          labels: { color: "#374151", boxWidth: 10, usePointStyle: true, pointStyle: "circle" },
        },
      },
    },
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
          backgroundColor: "rgba(37, 99, 235, 0.14)",
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
        backgroundColor: `${categoryPalette[index]}22`,
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
        backgroundColor: `${tagPalette[index % tagPalette.length]}22`,
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
          backgroundColor: "rgba(245, 158, 11, 0.20)",
          fill: true,
          tension: 0.24,
        },
      ],
    },
    options: lineOptions(),
  });
}
