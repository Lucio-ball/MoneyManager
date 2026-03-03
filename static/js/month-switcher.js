(function () {
  function padMonth(month) {
    return String(month).padStart(2, "0");
  }

  function currentMonthValue() {
    const now = new Date();
    return `${now.getFullYear()}-${padMonth(now.getMonth() + 1)}`;
  }

  function normalizeMonth(value) {
    const text = String(value || "").trim();
    const matched = text.match(/^(\d{4})-(\d{2})$/);
    if (!matched) {
      return currentMonthValue();
    }

    const year = Number(matched[1]);
    const month = Number(matched[2]);
    if (month < 1 || month > 12) {
      return currentMonthValue();
    }

    return `${year}-${padMonth(month)}`;
  }

  function splitMonth(value) {
    const normalized = normalizeMonth(value);
    const [yearText, monthText] = normalized.split("-");
    return {
      year: Number(yearText),
      month: Number(monthText),
      value: normalized,
    };
  }

  function shiftMonth(value, delta) {
    const { year, month } = splitMonth(value);
    const date = new Date(year, month - 1 + delta, 1);
    return `${date.getFullYear()}-${padMonth(date.getMonth() + 1)}`;
  }

  function formatMonthCn(value) {
    const { year, month } = splitMonth(value);
    return `${year}年${padMonth(month)}月`;
  }

  function buildMonthUrl(basePath, targetMonth) {
    const url = new URL(window.location.href);
    url.pathname = basePath || url.pathname;
    url.searchParams.set("month", normalizeMonth(targetMonth));
    return `${url.pathname}?${url.searchParams.toString()}`;
  }

  function initGlobalState() {
    const url = new URL(window.location.href);
    const urlMonth = normalizeMonth(url.searchParams.get("month") || "");
    window.MMMonthState = {
      month: urlMonth,
      getMonth() {
        return this.month;
      },
      setMonth(value) {
        this.month = normalizeMonth(value);
      },
    };
  }

  function navigateToMonth(basePath, targetMonth) {
    window.location.href = buildMonthUrl(basePath, targetMonth);
  }

  function initGlobalMonthSelector() {
    const selectors = document.querySelectorAll("[data-month-selector]");
    selectors.forEach((root) => {
      const basePath = root.dataset.basePath || window.location.pathname;
      const trigger = root.querySelector('[data-role="trigger"]');
      const label = root.querySelector('[data-role="label"]');
      const menu = root.querySelector('[data-role="menu"]');
      const yearNode = root.querySelector('[data-role="year"]');
      const monthGrid = root.querySelector('[data-role="month-grid"]');

      if (!trigger || !label || !menu || !yearNode || !monthGrid) {
        return;
      }

      let selectedMonth = normalizeMonth(
        (window.MMMonthState && window.MMMonthState.getMonth()) || root.dataset.month || currentMonthValue()
      );
      let viewYear = splitMonth(selectedMonth).year;

      function closeMenu() {
        menu.hidden = true;
        trigger.setAttribute("aria-expanded", "false");
      }

      function openMenu() {
        menu.hidden = false;
        trigger.setAttribute("aria-expanded", "true");
      }

      function renderMonthGrid() {
        yearNode.textContent = `${viewYear}年`;
        monthGrid.innerHTML = Array.from({ length: 12 })
          .map((_, index) => {
            const monthValue = `${viewYear}-${padMonth(index + 1)}`;
            const activeClass = monthValue === selectedMonth ? " active" : "";
            return `<button type="button" class="month-grid-item${activeClass}" data-month="${monthValue}">${index + 1}月</button>`;
          })
          .join("");

        monthGrid.querySelectorAll(".month-grid-item").forEach((button) => {
          button.addEventListener("click", function () {
            const monthValue = this.dataset.month;
            if (monthValue) {
              navigateToMonth(basePath, monthValue);
            }
          });
        });
      }

      function refresh() {
        label.textContent = formatMonthCn(selectedMonth);
        renderMonthGrid();
      }

      trigger.addEventListener("click", function () {
        if (menu.hidden) {
          openMenu();
        } else {
          closeMenu();
        }
      });

      root.querySelector('[data-action="prev"]')?.addEventListener("click", function () {
        navigateToMonth(basePath, shiftMonth(selectedMonth, -1));
      });

      root.querySelector('[data-action="next"]')?.addEventListener("click", function () {
        navigateToMonth(basePath, shiftMonth(selectedMonth, 1));
      });

      root.querySelector('[data-action="year-prev"]')?.addEventListener("click", function () {
        viewYear -= 1;
        renderMonthGrid();
      });

      root.querySelector('[data-action="year-next"]')?.addEventListener("click", function () {
        viewYear += 1;
        renderMonthGrid();
      });

      document.addEventListener("click", function (event) {
        if (!root.contains(event.target)) {
          closeMenu();
        }
      });

      refresh();
    });
  }

  function initInlineMonthNav() {
    const navNodes = document.querySelectorAll("[data-page-month-nav]");
    navNodes.forEach((node) => {
      const basePath = node.dataset.basePath || window.location.pathname;
      const monthValue = normalizeMonth(
        (window.MMMonthState && window.MMMonthState.getMonth()) || node.dataset.month || currentMonthValue()
      );
      const label = node.querySelector('[data-role="label"]');

      if (label) {
        label.textContent = formatMonthCn(monthValue);
      }

      node.querySelector('[data-action="prev"]')?.addEventListener("click", function () {
        navigateToMonth(basePath, shiftMonth(monthValue, -1));
      });

      node.querySelector('[data-action="next"]')?.addEventListener("click", function () {
        navigateToMonth(basePath, shiftMonth(monthValue, 1));
      });
    });
  }

  function initCalendarTimeline() {
    const timelines = document.querySelectorAll("[data-month-timeline]");
    timelines.forEach((node) => {
      const basePath = node.dataset.basePath || window.location.pathname;
      const selectedMonth = normalizeMonth(
        (window.MMMonthState && window.MMMonthState.getMonth()) || node.dataset.month || currentMonthValue()
      );
      const months = [];
      for (let i = 11; i >= 0; i -= 1) {
        months.push(shiftMonth(selectedMonth, -i));
      }

      node.innerHTML = months
        .map((monthValue) => {
          const activeClass = monthValue === selectedMonth ? " active" : "";
          return `<button type="button" class="month-timeline-item${activeClass}" data-month="${monthValue}">${monthValue}</button>`;
        })
        .join("");

      node.querySelectorAll(".month-timeline-item").forEach((button) => {
        button.addEventListener("click", function () {
          const monthValue = this.dataset.month;
          if (monthValue) {
            navigateToMonth(basePath, monthValue);
          }
        });
      });

      const activeButton = node.querySelector(".month-timeline-item.active");
      if (activeButton && typeof activeButton.scrollIntoView === "function") {
        activeButton.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
      }
    });
  }

  initGlobalState();
  initGlobalMonthSelector();
  initInlineMonthNav();
  initCalendarTimeline();
})();
