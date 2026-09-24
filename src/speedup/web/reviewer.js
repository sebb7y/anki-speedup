/*
 * Speedup - reviewer overlay UI.
 * Derived from Speed Focus Mode (AGPL-3.0-or-later).
 */

(function () {
  "use strict";

  let countdownEnd = 0;
  let countdownLabel = "";
  let rafHandle = null;

  function formatSeconds(totalSeconds) {
    if (totalSeconds < 0) {
      totalSeconds = 0;
    }
    if (totalSeconds < 60) {
      return totalSeconds.toFixed(1) + "s";
    }
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = Math.floor(totalSeconds % 60);
    return minutes + ":" + String(seconds).padStart(2, "0");
  }

  function formatDuration(totalSeconds) {
    totalSeconds = Math.max(0, Math.floor(totalSeconds));
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    if (hours > 0) {
      return (
        hours +
        ":" +
        String(minutes).padStart(2, "0") +
        ":" +
        String(seconds).padStart(2, "0")
      );
    }
    return minutes + ":" + String(seconds).padStart(2, "0");
  }

  function chip() {
    return (
      "display:inline-block;padding:1px 6px;margin-top:2px;border-radius:4px;" +
      "background:rgba(128,128,128,0.18);line-height:1.5;"
    );
  }

  function positionStyles() {
    return {
      "top-right": "top:10px;right:14px;text-align:right;",
      "top-left": "top:10px;left:14px;text-align:left;",
      "bottom-right": "bottom:10px;right:14px;text-align:right;",
      "bottom-left": "bottom:10px;left:14px;text-align:left;",
    };
  }

  function applyStyle() {
    const overlay = document.getElementById("speedupOverlay");
    if (!overlay) {
      return;
    }
    const styles = positionStyles();
    const position = styles[window.speedupOverlayPosition]
      ? window.speedupOverlayPosition
      : "top-right";
    const size = parseInt(window.speedupOverlayFontSize, 10) || 12;
    overlay.setAttribute(
      "style",
      "position:fixed;z-index:99999;pointer-events:none;max-width:40vw;" +
        styles[position] +
        "font-size:" +
        size +
        "px;"
    );
  }

  function configure(position, fontSize) {
    window.speedupOverlayPosition = position;
    window.speedupOverlayFontSize = fontSize;
    applyStyle();
  }

  function timeNode() {
    return document.getElementById("speedupTime");
  }

  function tick() {
    const node = timeNode();
    if (!node) {
      return;
    }
    const remaining = (countdownEnd - performance.now()) / 1000;
    node.textContent = countdownLabel + " " + formatSeconds(remaining);
    if (remaining > 0) {
      rafHandle = requestAnimationFrame(tick);
    } else {
      rafHandle = null;
    }
  }

  function setCountdown(label, seconds) {
    countdownLabel = label;
    countdownEnd = performance.now() + seconds * 1000;
    if (rafHandle !== null) {
      cancelAnimationFrame(rafHandle);
    }
    tick();
  }

  function setIdle(text) {
    countdownLabel = "";
    if (rafHandle !== null) {
      cancelAnimationFrame(rafHandle);
      rafHandle = null;
    }
    const node = timeNode();
    if (node) {
      node.textContent = text || "";
    }
  }

  function setStats(stats) {
    const node = document.getElementById("speedupStats");
    if (!node) {
      return;
    }
    const parts = [];
    if (stats.average !== null && stats.average !== undefined) {
      parts.push("avg " + formatSeconds(stats.average));
    }
    if (stats.deckTotal !== null && stats.deckTotal !== undefined) {
      parts.push("deck " + formatDuration(stats.deckTotal));
    }
    if (stats.overallTotal !== null && stats.overallTotal !== undefined) {
      parts.push("total " + formatDuration(stats.overallTotal));
    }
    if (stats.badge) {
      parts.push(stats.badge);
    }
    node.textContent = parts.join("  ·  ");
  }

  function setMoreTimeVisible(visible) {
    const button = document.getElementById("speedupMoreTime");
    if (button) {
      button.style.display = visible ? "" : "none";
    }
  }

  function build() {
    if (document.getElementById("speedupOverlay")) {
      return;
    }
    const overlay = document.createElement("div");
    overlay.id = "speedupOverlay";
    overlay.setAttribute("style", "position:fixed;pointer-events:none;");

    const hotkey = window.speedupHotkey || "";
    const button = document.createElement("button");
    button.id = "speedupMoreTime";
    button.textContent = "More time!";
    if (hotkey) {
      button.title = "Shortcut key: " + hotkey;
    }
    button.setAttribute(
      "style",
      "pointer-events:auto;display:none;margin-bottom:2px;"
    );
    button.addEventListener("click", function () {
      pycmd("speedup:moreTime");
    });

    const time = document.createElement("div");
    time.id = "speedupTime";
    time.setAttribute("style", chip());

    const stats = document.createElement("div");
    stats.id = "speedupStats";
    stats.setAttribute("style", chip());

    overlay.appendChild(button);
    overlay.appendChild(time);
    overlay.appendChild(stats);
    document.body.appendChild(overlay);
    applyStyle();
  }

  window.speedupBuild = build;
  window.speedupSetCountdown = setCountdown;
  window.speedupSetIdle = setIdle;
  window.speedupSetStats = setStats;
  window.speedupSetMoreTimeVisible = setMoreTimeVisible;
  window.speedupConfigure = configure;

  build();
})();
