"use strict";
(() => {
  const body = document.body;
  const controls = ["scale", "text", "figure"].map(id => document.getElementById(id));
  const defaults = controls.map(control => control.value);
  const update = () => {
    const [scale, text, figure] = controls.map(control => Number(control.value));
    body.style.setProperty("--page-scale", scale / 100);
    body.style.setProperty("--text-size", `${text}px`);
    body.style.setProperty("--figure-width", `${figure}px`);
    document.getElementById("scale-value").textContent = `${scale}%`;
    document.getElementById("text-value").textContent = `${text}px`;
    document.getElementById("figure-value").textContent = `${figure}px`;
  };
  controls.forEach(control => control.addEventListener("input", update));
  document.getElementById("reset").addEventListener("click", () => {
    controls.forEach((control, index) => { control.value = defaults[index]; });
    update();
  });
  document.getElementById("capture").addEventListener("click", event => {
    event.stopPropagation();
    body.classList.add("capture-mode");
    window.scrollTo(0, 0);
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape") body.classList.remove("capture-mode");
  });
  body.addEventListener("click", () => body.classList.remove("capture-mode"));
  document.getElementById("print").addEventListener("click", () => window.print());
  document.getElementById("fullscreen").addEventListener("click", async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch (_) {
      document.getElementById("help").textContent = "Full screen is unavailable here. Try your browser's F11 shortcut.";
    }
  });
  update();
})();
