(function () {
  if (typeof Chart === "undefined") {
    return;
  }

  const theme = {
    text: "#475569",
    textMuted: "#64748B",
    grid: "rgba(100, 116, 139, 0.14)",
    palette: ["#2563EB", "#0EA5E9", "#14B8A6", "#22C55E", "#F59E0B", "#EF4444", "#8B5CF6", "#64748B"],
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
            },
          },
        },
        scales: {
          x: { grid: { color: this.grid }, ticks: { color: this.textMuted } },
          y: { grid: { color: this.grid }, ticks: { color: this.textMuted } },
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
            },
          },
        },
      };
    },
    alpha(hex, alpha) {
      const value = String(hex || "").replace("#", "");
      if (value.length !== 6) {
        return "rgba(37, 99, 235, 0.16)";
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
  Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif';

  window.MMChartTheme = theme;
})();
