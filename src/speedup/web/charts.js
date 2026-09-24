/*
 * Speedup - statistics dialog charts.
 * Derived from Speed Focus Mode (AGPL-3.0-or-later).
 */

(function () {
  "use strict";

  const dataNode = document.getElementById("speedup-data");
  const data = dataNode ? JSON.parse(dataNode.textContent) : {};

  function seconds(ms) {
    if (ms === null || ms === undefined) {
      return "–";
    }
    return (ms / 1000).toFixed(1) + "s";
  }

  function duration(secondsValue) {
    if (secondsValue === null || secondsValue === undefined) {
      return "–";
    }
    const minutes = Math.floor(secondsValue / 60);
    const secs = Math.floor(secondsValue % 60);
    if (minutes >= 60) {
      const hours = Math.floor(minutes / 60);
      return hours + "h " + (minutes % 60) + "m";
    }
    return minutes + "m " + String(secs).padStart(2, "0") + "s";
  }

  function renderSummary() {
    const node = document.getElementById("summary");
    const items = [
      ["Avg front", seconds(data.avgFrontMs)],
      ["Avg back", seconds(data.avgBackMs)],
      ["Avg total (revlog)", seconds(data.avgTotalMs)],
      ["Cards tracked", String((data.cards || []).length)],
    ];
    node.innerHTML = items
      .map(
        ([label, value]) =>
          '<div class="item"><div class="muted">' +
          label +
          "</div><div>" +
          value +
          "</div></div>"
      )
      .join("");
  }

  function renderRecommendation() {
    const node = document.getElementById("recommend");
    if (!data.recommendation) {
      node.innerHTML =
        '<span class="muted">Enable analytics to get recommended timings.</span>';
      return;
    }
    const recommendation = data.recommendation;
    const reveal = recommendation.question.revealAfter;
    const action = recommendation.answer.autoAction.after;
    node.innerHTML =
      "<div>Suggested: reveal after <b>" +
      reveal +
      "s</b>, rate after <b>" +
      action +
      "s</b> on the answer side.</div>";
    const button = document.createElement("button");
    button.textContent = "Apply recommended timings to this deck";
    button.style.marginTop = "0.5rem";
    button.addEventListener("click", () => {
      pycmd("speedup-apply:" + JSON.stringify(recommendation));
    });
    node.appendChild(button);
  }

  function histogram(values, binCount) {
    if (!values.length) {
      return null;
    }
    const max = Math.max.apply(null, values) || 1;
    const width = max / binCount;
    const counts = new Array(binCount).fill(0);
    values.forEach((value) => {
      let index = Math.floor(value / width);
      if (index >= binCount) {
        index = binCount - 1;
      }
      if (index < 0) {
        index = 0;
      }
      counts[index] += 1;
    });
    return { counts, width, max };
  }

  function drawHistogram(svg, series, binCount) {
    svg.innerHTML = "";
    const allValues = series.reduce((acc, item) => acc.concat(item.values), []);
    const hist = histogram(allValues, binCount);
    if (!hist) {
      return;
    }
    const totalHeight = 220;
    const width = 640;
    const padding = 30;
    const chartWidth = width - padding * 2;
    const chartHeight = totalHeight - padding * 2;
    const barGroupWidth = chartWidth / binCount;
    const barWidth = barGroupWidth / (series.length + 0.5);
    const maxCount = Math.max.apply(null, hist.counts) || 1;

    series.forEach((item, seriesIndex) => {
      const itemHist = histogram(item.values, binCount);
      if (!itemHist) {
        return;
      }
      itemHist.counts.forEach((count, index) => {
        const height = (count / maxCount) * chartHeight;
        const x = padding + index * barGroupWidth + seriesIndex * barWidth;
        const y = totalHeight - padding - height;
        const rect = document.createElementNS(
          "http://www.w3.org/2000/svg",
          "rect"
        );
        rect.setAttribute("x", x.toFixed(1));
        rect.setAttribute("y", y.toFixed(1));
        rect.setAttribute("width", Math.max(1, barWidth - 1).toFixed(1));
        rect.setAttribute("height", Math.max(0, height).toFixed(1));
        rect.setAttribute("class", "bar " + (item.className || ""));
        svg.appendChild(rect);
      });
    });
  }

  function renderCharts() {
    const cards = data.cards || [];
    const distribution = data.distribution || { front: [], back: [] };
    drawHistogram(
      document.getElementById("chart-cards"),
      [{ values: cards.map((card) => card.total), className: "" }],
      20
    );
    drawHistogram(
      document.getElementById("chart-answers"),
      [
        { values: distribution.front || [], className: "" },
        { values: distribution.back || [], className: "back" },
      ],
      20
    );
  }

  function renderCards() {
    const table = document.getElementById("cards");
    const cards = (data.cards || []).slice(0, 50);
    if (!cards.length) {
      table.innerHTML =
        '<tr><td class="muted">No per-card data yet. Enable analytics and review some cards.</td></tr>';
      return;
    }
    const rows = cards.map((card) => {
      let badge = "";
      if (data.slowThresholdMs && card.total >= data.slowThresholdMs) {
        badge = '<span class="badge slow">slow</span>';
      } else if (data.fastThresholdMs && card.total <= data.fastThresholdMs) {
        badge = '<span class="badge fast">fast</span>';
      }
      return (
        "<tr><td>" +
        card.cid +
        "</td><td>" +
        seconds(card.front) +
        "</td><td>" +
        seconds(card.back) +
        "</td><td>" +
        seconds(card.total) +
        "</td><td>" +
        card.count +
        "</td><td>" +
        badge +
        "</td></tr>"
      );
    });
    table.innerHTML =
      "<tr><th>Card</th><th>Front</th><th>Back</th><th>Total</th><th>Reviews</th><th></th></tr>" +
      rows.join("");
  }

  document.getElementById("deck-name").textContent =
    data.deckName || "Deck statistics";
  renderSummary();
  renderRecommendation();
  renderCharts();
  renderCards();
})();
