/*
 * Speedup - reviewer overlay UI.
 * Derived from Speed Focus Mode (AGPL-3.0-or-later).
 */

(function () {
  "use strict";

  let countdownEnd = 0;
  let countdownLabel = "";
  let rafHandle = null;
  let dragging = false;
  let dragOffsetX = 0;
  let dragOffsetY = 0;

  function numberOr(value, fallback) {
    const number = parseFloat(value);
    return Number.isFinite(number) ? number : fallback;
  }

  function clamp(value, minimum, maximum) {
    return Math.min(maximum, Math.max(minimum, value));
  }

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

  function chip(extra) {
    return (
      "display:inline-block;padding:1px 6px;margin-top:2px;border-radius:4px;" +
      "background:rgba(128,128,128,0.18);line-height:1.5;" +
      (extra || "")
    );
  }

  function presetStyles() {
    return {
      "top-right": { top: "10px", right: "14px", textAlign: "right" },
      "top-left": { top: "10px", left: "14px", textAlign: "left" },
      "bottom-right": { bottom: "10px", right: "14px", textAlign: "right" },
      "bottom-left": { bottom: "10px", left: "14px", textAlign: "left" },
    };
  }

  function overlayNode() {
    return document.getElementById("speedupOverlay");
  }

  function contentVisible() {
    return ["speedupMoreTime", "speedupTime", "speedupStats"].some(function (id) {
      const node = document.getElementById(id);
      return node && node.style.display !== "none";
    });
  }

  function updateOverlayVisibility() {
    const overlay = overlayNode();
    if (!overlay) {
      return;
    }
    const visible = contentVisible();
    const wasHidden = overlay.style.display === "none";
    overlay.style.display = visible ? "" : "none";
    if (visible && !dragging) {
      if (wasHidden) {
        applyStyle();
      } else if (window.speedupOverlayPosition === "custom") {
        window.requestAnimationFrame(clampOverlay);
      }
    }
  }

  function clampOverlay() {
    const overlay = overlayNode();
    if (!overlay || dragging || overlay.style.display === "none") {
      return;
    }
    if (window.speedupOverlayPosition !== "custom") {
      return;
    }
    const rect = overlay.getBoundingClientRect();
    const maxLeft = Math.max(0, window.innerWidth - rect.width);
    const maxTop = Math.max(0, window.innerHeight - rect.height);
    const left = clamp(parseFloat(overlay.style.left) || 0, 0, maxLeft);
    const top = clamp(parseFloat(overlay.style.top) || 0, 0, maxTop);
    overlay.style.left = left + "px";
    overlay.style.top = top + "px";
  }

  function applyStyle() {
    const overlay = overlayNode();
    if (!overlay) {
      return;
    }
    const size = parseInt(window.speedupOverlayFontSize, 10) || 12;
    overlay.style.position = "fixed";
    overlay.style.zIndex = "99999";
    overlay.style.pointerEvents = "none";
    overlay.style.maxWidth = "40vw";
    overlay.style.fontSize = size + "px";
    overlay.style.left = "auto";
    overlay.style.right = "auto";
    overlay.style.top = "auto";
    overlay.style.bottom = "auto";
    overlay.style.textAlign = "left";

    if (window.speedupOverlayPosition === "custom") {
      const x = clamp(numberOr(window.speedupOverlayXPercent, 70), 0, 100);
      const y = clamp(numberOr(window.speedupOverlayYPercent, 8), 0, 100);
      overlay.style.left = (x / 100) * window.innerWidth + "px";
      overlay.style.top = (y / 100) * window.innerHeight + "px";
      window.requestAnimationFrame(clampOverlay);
      return;
    }

    const styles = presetStyles();
    const preset = styles[window.speedupOverlayPosition] || styles["top-right"];
    Object.keys(preset).forEach(function (key) {
      overlay.style[key] = preset[key];
    });
  }

  function configure(position, fontSize, xPercent, yPercent) {
    window.speedupOverlayPosition = position || "top-right";
    window.speedupOverlayFontSize = fontSize;
    window.speedupOverlayXPercent = numberOr(xPercent, 70);
    window.speedupOverlayYPercent = numberOr(yPercent, 8);
    if (!dragging) {
      applyStyle();
    }
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
    const node = timeNode();
    if (node) {
      node.style.display = "";
    }
    updateOverlayVisibility();
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
      node.style.display = text ? "" : "none";
    }
    updateOverlayVisibility();
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
    node.style.display = parts.length ? "" : "none";
    updateOverlayVisibility();
  }

  function setMoreTimeVisible(visible) {
    const button = document.getElementById("speedupMoreTime");
    if (button) {
      button.style.display = visible ? "" : "none";
    }
    updateOverlayVisibility();
  }

  function stopTimers() {
    pycmd("speedup:moreTime");
  }

  function startDrag(event) {
    const overlay = overlayNode();
    const handle = document.getElementById("speedupDragHandle");
    if (!overlay || !handle) {
      return;
    }
    if (event.pointerType === "mouse" && event.button !== 0) {
      return;
    }
    if (event.isPrimary === false) {
      return;
    }
    event.preventDefault();
    const rect = overlay.getBoundingClientRect();
    dragging = true;
    dragOffsetX = event.clientX - rect.left;
    dragOffsetY = event.clientY - rect.top;
    overlay.style.right = "auto";
    overlay.style.bottom = "auto";
    overlay.style.left = rect.left + "px";
    overlay.style.top = rect.top + "px";
    overlay.style.textAlign = "left";
    handle.style.cursor = "grabbing";
    handle.style.opacity = "0.9";
    if (handle.setPointerCapture) {
      try {
        handle.setPointerCapture(event.pointerId);
      } catch (error) {
        // Some embedded webviews do not support pointer capture.
      }
    }
  }

  function moveDrag(event) {
    if (!dragging) {
      return;
    }
    const overlay = overlayNode();
    if (!overlay) {
      return;
    }
    event.preventDefault();
    const rect = overlay.getBoundingClientRect();
    const left = clamp(
      event.clientX - dragOffsetX,
      0,
      Math.max(0, window.innerWidth - rect.width)
    );
    const top = clamp(
      event.clientY - dragOffsetY,
      0,
      Math.max(0, window.innerHeight - rect.height)
    );
    overlay.style.left = left + "px";
    overlay.style.top = top + "px";
  }

  function endDrag(event, save) {
    if (!dragging) {
      return;
    }
    const overlay = overlayNode();
    const handle = document.getElementById("speedupDragHandle");
    dragging = false;
    if (handle) {
      handle.style.cursor = "grab";
      handle.style.opacity = "0.45";
      if (handle.releasePointerCapture && event && event.pointerId !== undefined) {
        try {
          handle.releasePointerCapture(event.pointerId);
        } catch (error) {
          // Pointer capture may already be released.
        }
      }
    }
    if (!overlay) {
      return;
    }
    const rect = overlay.getBoundingClientRect();
    const x = clamp((rect.left / Math.max(1, window.innerWidth)) * 100, 0, 100);
    const y = clamp((rect.top / Math.max(1, window.innerHeight)) * 100, 0, 100);
    window.speedupOverlayPosition = "custom";
    window.speedupOverlayXPercent = x;
    window.speedupOverlayYPercent = y;
    applyStyle();
    if (save) {
      pycmd("speedup:overlayMoved:" + JSON.stringify({ x: x, y: y }));
    }
  }

  function build() {
    if (overlayNode()) {
      return;
    }
    const hotkey = window.speedupHotkey || "";
    const overlay = document.createElement("div");
    overlay.id = "speedupOverlay";

    const handle = document.createElement("div");
    handle.id = "speedupDragHandle";
    handle.textContent = "⠿";
    handle.title = "Drag to move the overlay";
    handle.setAttribute(
      "style",
      "display:inline-block;pointer-events:auto;cursor:grab;opacity:0.45;" +
        "padding:0 4px;margin-bottom:2px;user-select:none;touch-action:none;" +
        "font-size:0.9em;line-height:1;"
    );
    handle.addEventListener("pointerdown", startDrag);
    handle.addEventListener("mouseenter", function () {
      handle.style.opacity = "0.9";
    });
    handle.addEventListener("mouseleave", function () {
      if (!dragging) {
        handle.style.opacity = "0.45";
      }
    });

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
    button.addEventListener("click", stopTimers);

    const time = document.createElement("div");
    time.id = "speedupTime";
    time.setAttribute(
      "style",
      chip("pointer-events:auto;cursor:pointer;display:none;")
    );
    time.title = hotkey
      ? "Click to stop timers (" + hotkey + ")"
      : "Click to stop timers";
    time.addEventListener("click", stopTimers);

    const stats = document.createElement("div");
    stats.id = "speedupStats";
    stats.setAttribute("style", chip("display:none;"));

    overlay.appendChild(handle);
    overlay.appendChild(button);
    overlay.appendChild(time);
    overlay.appendChild(stats);
    document.body.appendChild(overlay);
    applyStyle();
    updateOverlayVisibility();
  }

  window.addEventListener("resize", function () {
    if (!dragging) {
      applyStyle();
    }
  });
  window.addEventListener("pointermove", moveDrag);
  window.addEventListener("pointerup", function (event) {
    endDrag(event, true);
  });
  window.addEventListener("pointercancel", function (event) {
    endDrag(event, true);
  });

  window.speedupBuild = build;
  window.speedupSetCountdown = setCountdown;
  window.speedupSetIdle = setIdle;
  window.speedupSetStats = setStats;
  window.speedupSetMoreTimeVisible = setMoreTimeVisible;
  window.speedupConfigure = configure;

  build();
})();
