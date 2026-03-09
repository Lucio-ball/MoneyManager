(function () {
  const pageDataNode = document.getElementById("calendar-page-data");
  const pageData = pageDataNode ? JSON.parse(pageDataNode.textContent) : {};

  const month = pageData.month;
  const calendarGrid = document.getElementById("calendar-grid");
  const detailBody = document.getElementById("calendar-day-detail-body");
  const selectedDateText = document.getElementById("calendar-selected-date");

  if (!month || !calendarGrid || !detailBody || !selectedDateText) {
    return;
  }

  const markerMeta = {
    subscription: { label: "subscription", short: "S", className: "subscription" },
    reimbursement: { label: "reimbursement", short: "R", className: "reimbursement" },
    high_spending: { label: "high_spending", short: "H", className: "high-spending" },
    budget_warning: { label: "budget_warning", short: "B", className: "budget-warning" },
  };

  const groupMeta = [
    { key: "normal_expense", label: "normal expense" },
    { key: "reimbursable_expense", label: "reimbursable expense" },
    { key: "subscription", label: "subscription" },
    { key: "income", label: "income" },
  ];

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function getHeatLevel(amount, maxAmount) {
    if (!amount || maxAmount <= 0) {
      return 0;
    }

    const ratio = amount / maxAmount;
    if (ratio >= 0.85) return 5;
    if (ratio >= 0.65) return 4;
    if (ratio >= 0.45) return 3;
    if (ratio >= 0.25) return 2;
    return 1;
  }

  function buildDate(yyyyMm, day) {
    return `${yyyyMm}-${String(day).padStart(2, "0")}`;
  }

  function currentIsoDate() {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  }

  function buildMarkerHtml(markers) {
    const markerKeys = Object.keys(markerMeta).filter((key) => markers && markers[key]);
    if (markerKeys.length === 0) {
      return '<div class="calendar-day-markers is-empty"></div>';
    }

    return `
      <div class="calendar-day-markers">
        ${markerKeys
          .map((key) => {
            const meta = markerMeta[key];
            return `<span class="calendar-day-marker ${meta.className}" title="${meta.label}">${meta.short}</span>`;
          })
          .join("")}
      </div>
    `;
  }

  function renderTransactionRow(item) {
    const category = item.category_sub
      ? `${item.category_main} / ${item.category_sub}`
      : item.category_main;
    const tags = Array.isArray(item.tags) && item.tags.length > 0
      ? item.tags.join("、")
      : "-";
    const note = item.note ? item.note : "-";
    const amountClass = item.type === "income" ? "income" : "expense";

    return `
      <tr>
        <td>${escapeHtml(item.date || "-")}</td>
        <td>${escapeHtml(category || "-")}</td>
        <td>${escapeHtml(tags)}</td>
        <td>${escapeHtml(note)}</td>
        <td class="${amountClass} mono">¥${Number(item.amount || 0).toFixed(2)}</td>
      </tr>
    `;
  }

  function renderGroupedTransactions(groupedTransactions) {
    const rows = [];

    groupMeta.forEach((group) => {
      const items = Array.isArray(groupedTransactions?.[group.key]) ? groupedTransactions[group.key] : [];
      if (items.length === 0) {
        return;
      }

      rows.push(`
        <tr class="calendar-detail-group-row">
          <td colspan="5">${group.label} (${items.length})</td>
        </tr>
      `);

      items.forEach((item) => rows.push(renderTransactionRow(item)));
    });

    return rows.join("");
  }

  async function loadDayDetails(targetDate) {
    selectedDateText.textContent = `${targetDate} · 明细加载中...`;
    detailBody.innerHTML = '<tr><td colspan="5">加载中...</td></tr>';

    const response = await fetch(`/api/calendar/day?date=${encodeURIComponent(targetDate)}`);
    if (!response.ok) {
      detailBody.innerHTML = '<tr><td colspan="5">明细加载失败，请稍后重试。</td></tr>';
      selectedDateText.textContent = `${targetDate} · 加载失败`;
      return;
    }

    const data = await response.json();
    selectedDateText.textContent = `${targetDate} · 支出 ¥${Number(data.total_expense || 0).toFixed(2)} · 收入 ¥${Number(data.total_income || 0).toFixed(2)} · ${data.transaction_count || 0} 笔`;

    const hasGroups = groupMeta.some((group) => Array.isArray(data.grouped_transactions?.[group.key]) && data.grouped_transactions[group.key].length > 0);
    if (!hasGroups) {
      detailBody.innerHTML = '<tr><td colspan="5">当日暂无交易记录。</td></tr>';
      return;
    }

    detailBody.innerHTML = renderGroupedTransactions(data.grouped_transactions);
  }

  function bindDayEvents() {
    const buttons = calendarGrid.querySelectorAll(".calendar-day-btn[data-date]");
    buttons.forEach((button) => {
      button.addEventListener("click", async function () {
        const targetDate = this.dataset.date;
        if (!targetDate) {
          return;
        }

        calendarGrid
          .querySelectorAll(".calendar-day-cell")
          .forEach((cell) => cell.classList.remove("is-selected"));

        this.closest(".calendar-day-cell")?.classList.add("is-selected");
        await loadDayDetails(targetDate);
      });
    });
  }

  async function initCalendar() {
    const response = await fetch(`/api/calendar?month=${encodeURIComponent(month)}`);
    if (!response.ok) {
      calendarGrid.innerHTML = '<div class="helper-text">日历数据加载失败，请刷新后重试。</div>';
      return;
    }

    const data = await response.json();
    const maxExpense = Number(data.max_expense || 0);
    const dayMap = new Map((data.days || []).map((item) => [item.date, item]));

    const [yearText, monthText] = month.split("-");
    const year = Number(yearText);
    const monthIndex = Number(monthText) - 1;

    const firstDate = new Date(year, monthIndex, 1);
    const daysInMonth = new Date(year, monthIndex + 1, 0).getDate();
    const firstWeekday = (firstDate.getDay() + 6) % 7;

    const cells = [];

    for (let i = 0; i < firstWeekday; i += 1) {
      cells.push('<div class="calendar-day-cell is-empty"></div>');
    }

    for (let day = 1; day <= daysInMonth; day += 1) {
      const dateStr = buildDate(month, day);
      const dayInfo = dayMap.get(dateStr) || {};
      const amount = Number(dayInfo.total_expense || 0);
      const heatLevel = getHeatLevel(amount, maxExpense);
      const markers = dayInfo.markers || {};
      const stateClass = `${dateStr === currentIsoDate() ? " is-today" : ""}${heatLevel >= 5 ? " is-peak" : ""}`;

      cells.push(`
        <div class="calendar-day-cell calendar-heat-${heatLevel}${stateClass}">
          <button type="button" class="calendar-day-btn" data-date="${dateStr}">${day}</button>
          <div class="calendar-day-amount">¥${amount.toFixed(2)}</div>
          ${buildMarkerHtml(markers)}
        </div>
      `);
    }

    calendarGrid.innerHTML = cells.join("");
    bindDayEvents();
  }

  initCalendar().catch(() => {
    calendarGrid.innerHTML = '<div class="helper-text">日历数据加载失败，请稍后重试。</div>';
  });
})();
