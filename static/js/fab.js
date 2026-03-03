(function () {
  const trigger = document.getElementById("fab-trigger");
  const panel = document.getElementById("fab-panel");
  const closeButton = document.getElementById("fab-close");
  const form = document.getElementById("fab-transaction-form");
  const amountInput = document.getElementById("fab-amount");
  const typeInput = document.getElementById("fab-type");
  const categoryMainInput = document.getElementById("fab-category-main");
  const categorySubInput = document.getElementById("fab-category-sub");
  const tagsInput = document.getElementById("fab-tags");
  const incomeSourceInput = document.getElementById("fab-income-source-input");
  const noteInput = document.getElementById("fab-note");
  const dateInput = document.getElementById("fab-date");
  const submitButton = document.getElementById("fab-submit");
  const messageEl = document.getElementById("fab-message");
  const expenseCategoryMain = document.getElementById("fab-expense-category-main");
  const expenseCategorySub = document.getElementById("fab-expense-category-sub");
  const expenseTags = document.getElementById("fab-expense-tags");
  const incomeSource = document.getElementById("fab-income-source");

  if (!trigger || !panel || !form) {
    return;
  }

  const navOpenButtons = document.querySelectorAll(".js-fab-open");

  const today = new Date();
  const isoDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;

  const setMessage = function (text, isError) {
    messageEl.textContent = text || "";
    messageEl.classList.toggle("danger", Boolean(isError));
  };

  const toggleFieldsByType = function () {
    const isIncome = typeInput.value === "income";

    expenseCategoryMain.style.display = isIncome ? "none" : "";
    expenseCategorySub.style.display = isIncome ? "none" : "";
    expenseTags.style.display = isIncome ? "none" : "";
    incomeSource.style.display = isIncome ? "" : "none";

    categoryMainInput.required = !isIncome;
    if (isIncome) {
      categoryMainInput.value = "";
      categorySubInput.value = "";
      Array.from(tagsInput.options).forEach((option) => {
        option.selected = false;
      });
    } else {
      incomeSourceInput.value = "";
    }
  };

  const openPanel = function () {
    panel.classList.add("is-open");
    panel.setAttribute("aria-hidden", "false");
    dateInput.value = isoDate;
    setTimeout(() => {
      amountInput.focus();
    }, 30);
  };

  const closePanel = function () {
    panel.classList.remove("is-open");
    panel.setAttribute("aria-hidden", "true");
    setMessage("");
  };

  const renderRecentRow = function (record) {
    const typeLabel = record.type === "income" ? "收入" : "支出";
    const amountClass = record.type === "income" ? "income" : "expense";
    const amountText = Number(record.amount || 0).toFixed(2);

    let categoryText = "-";
    if (record.type === "income") {
      categoryText = record.category_sub || "-";
    } else {
      categoryText = record.category_main || "-";
      if (record.category_sub) {
        categoryText += ` / ${record.category_sub}`;
      }
    }

    const tagsText = Array.isArray(record.tags) && record.tags.length > 0 ? record.tags.join("、") : "-";
    const noteText = record.note || "-";

    return `<tr>
      <td>${record.date || "-"}</td>
      <td>${typeLabel}</td>
      <td class="${amountClass}">¥${amountText}</td>
      <td>${categoryText}</td>
      <td>${tagsText}</td>
      <td>${noteText}</td>
    </tr>`;
  };

  const refreshHomeRecentRecords = async function () {
    const recentBody = document.getElementById("home-recent-records-body");
    if (!recentBody || window.location.pathname !== "/") {
      window.location.reload();
      return;
    }

    const monthInput = document.querySelector('form.toolbar input[name="month"]');
    const month = monthInput && monthInput.value ? monthInput.value : `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;

    const response = await fetch(`/api/transactions?month=${encodeURIComponent(month)}`);
    if (!response.ok) {
      window.location.reload();
      return;
    }

    const rows = await response.json();
    const sorted = Array.isArray(rows)
      ? rows.slice().sort((a, b) => {
          if ((a.date || "") === (b.date || "")) {
            return Number(b.id || 0) - Number(a.id || 0);
          }
          return (b.date || "").localeCompare(a.date || "");
        })
      : [];

    const recentRows = sorted.slice(0, 10);
    if (recentRows.length === 0) {
      recentBody.innerHTML = '<tr><td colspan="6">暂无记录，先记第一笔吧。</td></tr>';
      return;
    }

    recentBody.innerHTML = recentRows.map(renderRecentRow).join("");
  };

  trigger.addEventListener("click", openPanel);
  closeButton.addEventListener("click", closePanel);
  navOpenButtons.forEach((button) => {
    button.addEventListener("click", openPanel);
  });
  typeInput.addEventListener("change", toggleFieldsByType);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && panel.classList.contains("is-open")) {
      closePanel();
    }
  });

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    setMessage("");
    submitButton.disabled = true;

    const payload = {
      amount: amountInput.value,
      type: typeInput.value,
      date: dateInput.value || isoDate,
      note: noteInput.value.trim(),
    };

    if (payload.type === "income") {
      payload.income_source = incomeSourceInput.value.trim();
    } else {
      payload.category_main = categoryMainInput.value;
      payload.category_sub = categorySubInput.value.trim();
      payload.tags = Array.from(tagsInput.selectedOptions).map((option) => option.value);
    }

    try {
      const response = await fetch("/api/transactions", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        setMessage(data.error || "提交失败，请检查输入", true);
        return;
      }

      form.reset();
      typeInput.value = "expense";
      dateInput.value = isoDate;
      toggleFieldsByType();
      closePanel();
      await refreshHomeRecentRecords();
    } catch (error) {
      setMessage("网络异常，请稍后重试", true);
    } finally {
      submitButton.disabled = false;
    }
  });

  toggleFieldsByType();
})();
