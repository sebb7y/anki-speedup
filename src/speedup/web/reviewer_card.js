/*
 * Speedup - card webview helpers (type-answer detection).
 * Derived from Speed Focus Mode (AGPL-3.0-or-later).
 */

(function () {
  "use strict";

  if (window.speedupTypeListenerInstalled) {
    return;
  }
  window.speedupTypeListenerInstalled = true;

  document.addEventListener(
    "keyup",
    function (event) {
      const target = event.target;
      if (target && target.id === "typeans") {
        pycmd("speedup:typeans");
      }
    },
    true
  );
})();
