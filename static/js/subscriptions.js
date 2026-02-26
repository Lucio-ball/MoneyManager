const subscriptionDataElement = document.getElementById("subscription-dashboard-data");
const subscriptionData = subscriptionDataElement
  ? JSON.parse(subscriptionDataElement.textContent)
  : { summary: {}, subscriptions: [] };

const summary = subscriptionData.summary || {};
const topMonthlyCost = summary.top_monthly_cost || [];
const cycleDistribution = summary.cycle_distribution || {};

const cycleLabelsMap = {
  monthly: "月付",
  yearly: "年付",
  weekly: "周付",
  quarterly: "季付",
};

const cycleLabels = Object.keys(cycleDistribution)
  .filter((key) => (cycleDistribution[key] || 0) > 0)
  .map((key) => cycleLabelsMap[key] || key);
const cycleValues = Object.keys(cycleDistribution)
  .filter((key) => (cycleDistribution[key] || 0) > 0)
  .map((key) => cycleDistribution[key]);

if (cycleLabels.length > 0) {
  new Chart(document.getElementById("subscriptionCycleChart"), {
    type: "doughnut",
    data: {
      labels: cycleLabels,
      datasets: [
        {
          data: cycleValues,
          borderWidth: 0,
          backgroundColor: ["#2563EB", "#14B8A6", "#F59E0B", "#8B5CF6"],
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

if (topMonthlyCost.length > 0) {
  new Chart(document.getElementById("subscriptionTopCostChart"), {
    type: "bar",
    data: {
      labels: topMonthlyCost.map((item) => item.name),
      datasets: [
        {
          label: "月折算成本",
          data: topMonthlyCost.map((item) => item.monthly_cost),
          backgroundColor: ["#2563EB", "#0EA5E9", "#14B8A6", "#22C55E", "#F59E0B"],
          borderRadius: 6,
        },
      ],
    },
    options: {
      plugins: {
        legend: { display: false },
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: "#6B7280" } },
        y: { grid: { color: "rgba(107, 114, 128, 0.08)" }, ticks: { color: "#6B7280" } },
      },
    },
  });
}

const deleteButtons = document.querySelectorAll(".delete-subscription-btn");
deleteButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    const id = button.dataset.id;
    const name = button.dataset.name;
    const ok = window.confirm(`确认取消订阅「${name}」吗？`);
    if (!ok) {
      return;
    }

    button.disabled = true;
    button.textContent = "处理中...";

    try {
      const response = await fetch(`/api/subscriptions/${id}`, {
        method: "DELETE",
      });

      if (!response.ok) {
        throw new Error("删除失败");
      }

      const card = document.getElementById(`subscription-card-${id}`);
      if (card) {
        card.remove();
      }
      window.location.reload();
    } catch (error) {
      window.alert("取消失败，请稍后重试。");
      button.disabled = false;
      button.textContent = "取消订阅";
    }
  });
});
