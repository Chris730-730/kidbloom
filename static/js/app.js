// Photo previews on the start form
document.querySelectorAll('input[type=file][data-preview]').forEach((input) => {
  input.addEventListener('change', () => {
    const file = input.files[0];
    const img = document.getElementById(input.dataset.preview);
    if (!file || !img) return;
    img.src = URL.createObjectURL(file);
    img.hidden = false;
    img.nextElementSibling.hidden = true;
  });
});

// Face mix slider label
const mix = document.getElementById('mix');
const mixOut = document.getElementById('mixOut');
if (mix && mixOut) {
  const update = () => { mixOut.textContent = `${100 - mix.value}% Dad / ${mix.value}% Mom`; };
  mix.addEventListener('input', update);
  update();
}

// Loading state on submit
const form = document.getElementById('startForm');
if (form) {
  form.addEventListener('submit', () => {
    const btn = document.getElementById('submitBtn');
    btn.disabled = true;
    btn.textContent = '🌱 AI is drawing your child... (up to 1 minute)';
  });
}

// Animate talent bars
requestAnimationFrame(() => {
  setTimeout(() => document.querySelectorAll('.fill').forEach((el) => el.classList.add('go')), 150);
});
