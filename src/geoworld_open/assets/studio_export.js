"use strict";
(() => {
  // Static public presentation code only: no user text, credentials, or payloads.
  window.__gwStudioPrint?.dispose();
  const click = event => {
    if (event.target instanceof Element && event.target.closest("#gw-studio-print")) {
      event.preventDefault();
      window.print();
    }
  };
  document.addEventListener("click", click);
  const observer = new MutationObserver(() => {
    if (!document.getElementById("gw-studio-print")) controller.dispose();
  });
  const controller = {
    dispose() {
      observer.disconnect();
      document.removeEventListener("click", click);
      if (window.__gwStudioPrint === controller) delete window.__gwStudioPrint;
    },
  };
  window.__gwStudioPrint = controller;
  observer.observe(document.body, {childList: true, subtree: true});
})();
