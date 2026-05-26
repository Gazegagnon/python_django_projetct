document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("form[data-loading]").forEach(function (form) {
    form.addEventListener("submit", function () {
      const btn = form.querySelector('button[type="submit"]');
      if (btn) {
        btn.disabled = true;
        btn.dataset.originalText = btn.textContent;
        btn.textContent = "Envoi…";
      }
    });
  });

  document.querySelectorAll("[data-confirm]").forEach(function (el) {
    el.addEventListener("click", function (event) {
      const message = el.getAttribute("data-confirm");
      if (message && !window.confirm(message)) {
        event.preventDefault();
      }
    });
  });
});
