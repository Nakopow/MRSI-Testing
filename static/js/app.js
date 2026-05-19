document.querySelectorAll('[data-tab]').forEach((tab) => {
  tab.addEventListener('click', () => {
    const tabs = tab.closest('.tabs');
    if (!tabs) return;
    tabs.querySelectorAll('[data-tab]').forEach((item) => item.classList.remove('active'));
    tab.classList.add('active');
  });
});

document.querySelectorAll('[data-topic-filter]').forEach((chip) => {
  chip.addEventListener('click', () => {
    const row = chip.closest('.topic-filter-row');
    if (!row) return;
    row.querySelectorAll('[data-topic-filter]').forEach((item) => item.classList.remove('active'));
    chip.classList.add('active');
  });
});

document.querySelectorAll('[data-toggle]').forEach((toggle) => {
  toggle.addEventListener('click', () => {
    toggle.classList.toggle('on');
  });
});
