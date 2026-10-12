// Delete / drop confirmation: any button with data-confirm-action opens the shared modal.
document.addEventListener("click", function (ev) {
  const btn = ev.target.closest("[data-confirm-action]");
  if (!btn) return;
  document.getElementById("confirmForm").action = btn.dataset.confirmAction;
  document.getElementById("confirmText").textContent = btn.dataset.confirmText || "Are you sure?";
  new bootstrap.Modal(document.getElementById("confirmModal")).show();
});
