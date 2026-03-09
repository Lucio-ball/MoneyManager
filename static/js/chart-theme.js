(function () {
  if (typeof Chart === "undefined") {
    return;
  }

  const theme = {
    text: "#334155",
    textMuted: "#64748B",
    grid: "rgba(148, 163, 184, 0.18)",
    palette: ["#4F46E5", "#0F766E", "#10B981", "#F59E0B", "#EF4444", "#6366F1", "#94A3B8", "#1D4ED8"],
    lineOptions() {
      return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            labels: {
              color: this.text,
              boxWidth: 10,
              usePointStyle: true,
              pointStyle: "circle",
              padding: 18,
            },
          },
          tooltip: {
            backgroundColor: "rgba(15, 23, 42, 0.92)",
            titleColor: "#F8FAFC",
            bodyColor: "#E2E8F0",
            padding: 12,
            cornerRadius: 12,
            displayColors: true,
          },
        },
        scales: {
          x: {
            grid: { color: this.grid, drawBorder: false },
            ticks: { color: this.textMuted },
            border: { display: false },
          },
          y: {
            grid: { color: this.grid, drawBorder: false },
            ticks: { color: this.textMuted },
            border: { display: false },
          },
        },
      };
    },
    barOptions() {
      const options = this.lineOptions();
      options.plugins.legend.display = false;
      return options;
    },
    pieOptions() {
      return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "bottom",
            labels: {
              color: this.text,
              boxWidth: 10,
              usePointStyle: true,
              pointStyle: "circle",
              padding: 18,
            },
          },
          tooltip: {
            backgroundColor: "rgba(15, 23, 42, 0.92)",
            titleColor: "#F8FAFC",
            bodyColor: "#E2E8F0",
            padding: 12,
            cornerRadius: 12,
            displayColors: true,
          },
        },
      };
    },
    radarOptions() {
      return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            labels: {
              color: this.text,
              boxWidth: 10,
              usePointStyle: true,
              pointStyle: "circle",
              padding: 18,
            },
          },
          tooltip: {
            backgroundColor: "rgba(15, 23, 42, 0.92)",
            titleColor: "#F8FAFC",
            bodyColor: "#E2E8F0",
            padding: 12,
            cornerRadius: 12,
          },
        },
        scales: {
          r: {
            suggestedMin: 0,
            suggestedMax: 100,
            grid: { color: "rgba(148, 163, 184, 0.22)" },
            angleLines: { color: "rgba(148, 163, 184, 0.18)" },
            pointLabels: { color: this.text, font: { size: 12 } },
            ticks: {
              color: this.textMuted,
              backdropColor: "transparent",
              stepSize: 20,
            },
          },
        },
      };
    },
    alpha(hex, alpha) {
      const value = String(hex || "").replace("#", "");
      if (value.length !== 6) {
        return "rgba(79, 70, 229, 0.16)";
      }
      const r = parseInt(value.slice(0, 2), 16);
      const g = parseInt(value.slice(2, 4), 16);
      const b = parseInt(value.slice(4, 6), 16);
      return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    },
    buildPalette(size) {
      const result = [];
      for (let i = 0; i < size; i += 1) {
        result.push(this.palette[i % this.palette.length]);
      }
      return result;
    },
  };

  Chart.defaults.color = theme.text;
  Chart.defaults.borderColor = theme.grid;
  Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Microsoft YaHei", sans-serif';
  Chart.defaults.elements.line.borderJoinStyle = "round";
  Chart.defaults.elements.point.hoverBorderWidth = 0;

  window.MMChartTheme = theme;
})();
