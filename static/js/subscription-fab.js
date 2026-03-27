(function () {
  const trigger = document.getElementById("subscription-fab-trigger");
  const panel = document.getElementById("subscription-fab-panel");
  const closeButton = document.getElementById("subscription-fab-close");
  const firstInput = document.getElementById("subscription-fab-name");

  if (!trigger || !panel || !closeButton) {
    return;
  }

  const openPanel = function () {
    panel.classList.add("is-open");
    panel.setAttribute("aria-hidden", "false");
    window.setTimeout(() => {
      if (firstInput) {
        firstInput.focus();
      }
    }, 30);
  };

  const closePanel = function () {
    panel.classList.remove("is-open");
    panel.setAttribute("aria-hidden", "true");
  };

  trigger.addEventListener("click", openPanel);
  closeButton.addEventListener("click", closePanel);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && panel.classList.contains("is-open")) {
      closePanel();
    }
  });

  if (panel.dataset.openOnLoad === "true") {
    openPanel();
  }
})();
