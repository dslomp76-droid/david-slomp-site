
document.addEventListener('DOMContentLoaded', () => {
  const toggle = document.querySelector('.nav-toggle');
  const nav = document.querySelector('.site-nav');
  if (toggle && nav) {
    toggle.addEventListener('click', () => {
      const expanded = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', String(!expanded));
      nav.classList.toggle('open');
    });
  }

  const current = document.body.dataset.page;
  if (current) {
    document.querySelectorAll('.site-nav a[data-page]').forEach(link => {
      if (link.dataset.page === current) {
        link.classList.add('active');
        link.setAttribute('aria-current', 'page');
      }
    });
  }
});
