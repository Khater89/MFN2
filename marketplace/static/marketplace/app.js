document.querySelectorAll('form[data-submit]').forEach(form => {
  form.addEventListener('submit', event => {
    if (!form.checkValidity()) return;
    const file = form.querySelector('input[type=file]');
    if (file?.files[0] && file.files[0].size > 5 * 1024 * 1024) {
      event.preventDefault();
      form.querySelector('.submit-status').textContent = 'File is too large. Choose a document smaller than 5 MB.';
      return;
    }
    const clicked = event.submitter;
    // Preserve named submit buttons (approve/reject) before disabling controls.
    if (clicked?.name) {
      const hidden = document.createElement('input');
      hidden.type = 'hidden'; hidden.name = clicked.name; hidden.value = clicked.value;
      form.append(hidden);
    }
    form.querySelectorAll('button[type=submit], button:not([type])').forEach(b => b.disabled = true);
    const status = form.querySelector('.submit-status');
    if (status) status.textContent = file?.files.length ? 'Uploading document and saving for private review…' : 'Saving your request…';
    if (file?.files.length && status) {
      const progress = document.createElement('progress');
      progress.className = 'upload-progress'; progress.setAttribute('aria-label', 'Uploading document');
      status.append(progress);
    }
  });
});
const quantity = document.querySelector('#id_quantity');
const total = document.querySelector('[data-unit-price]');
if (quantity && total) {
  quantity.addEventListener('input', () => {
    const n = Number(quantity.value);
    total.textContent = n > 0 ? `${(Number(total.dataset.unitPrice) * n).toFixed(3)} ${total.dataset.currency}` : 'Enter a quantity';
  });
}
window.addEventListener('pageshow', () => document.querySelectorAll('form[data-submit] button').forEach(b => b.disabled = false));
