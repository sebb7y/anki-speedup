(function () {
  "use strict";

  const GLOBAL = __GLOBAL_CONFIG__;
  const HTML = __HTML__;

  const CLASSES = [
    { key: "new", label: "New" },
    { key: "learning", label: "Learning", collapsedBy: "collapseNewLearning" },
    { key: "review", label: "Review" },
    { key: "relearning", label: "Relearning", collapsedBy: "collapseReviewRelearning" },
  ];

  const ACTIONS = [
    ["again", "Rate Again"],
    ["hard", "Rate Hard"],
    ["good", "Rate Good"],
    ["easy", "Rate Easy"],
    ["bury", "Bury Card"],
  ];

  function isPlainObject(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }

  function deepMerge(base, override) {
    const result = Object.assign({}, base);
    if (!isPlainObject(override)) {
      return result;
    }
    Object.keys(override).forEach((key) => {
      if (isPlainObject(result[key]) && isPlainObject(override[key])) {
        result[key] = deepMerge(result[key], override[key]);
      } else {
        result[key] = override[key];
      }
    });
    return result;
  }

  function makeNumber(value, onChange) {
    const input = document.createElement("input");
    input.type = "number";
    input.className = "form-control form-control-sm";
    input.min = "0";
    input.step = "0.1";
    input.style.maxWidth = "7rem";
    input.value = value;
    input.addEventListener("input", () => onChange(parseFloat(input.value) || 0));
    return input;
  }

  function makeSelect(value, onChange) {
    const select = document.createElement("select");
    select.className = "form-select form-select-sm";
    select.style.maxWidth = "10rem";
    ACTIONS.forEach(([val, label]) => {
      const option = document.createElement("option");
      option.value = val;
      option.textContent = label;
      select.appendChild(option);
    });
    select.value = value;
    select.addEventListener("change", () => onChange(select.value));
    return select;
  }

  function row(labelText, control) {
    const wrapper = document.createElement("div");
    wrapper.className = "d-flex align-items-center gap-2 mb-1";
    const label = document.createElement("span");
    label.style.minWidth = "13rem";
    label.textContent = labelText;
    wrapper.appendChild(label);
    wrapper.appendChild(control);
    return wrapper;
  }

  function buildClass(key, label, store) {
    const el = document.createElement("div");
    el.className = "speedup-class mb-3";

    const heading = document.createElement("h3");
    heading.textContent = label;
    el.appendChild(heading);

    const questionHeading = document.createElement("h4");
    questionHeading.textContent = "Question";
    el.appendChild(questionHeading);

    const alertAfter = makeNumber(0, () => commit());
    const revealAfter = makeNumber(0, () => commit());
    const questionActionAfter = makeNumber(0, () => commit());
    const questionAction = makeSelect("again", () => commit());

    el.appendChild(row("Play alert after", alertAfter));
    el.appendChild(row("Show answer after", revealAfter));
    const questionActionRow = document.createElement("div");
    questionActionRow.className = "d-flex align-items-center gap-2 mb-1";
    const actionLabel = document.createElement("span");
    actionLabel.textContent = "Automatically";
    questionActionRow.appendChild(actionLabel);
    questionActionRow.appendChild(questionAction);
    const afterLabel = document.createElement("span");
    afterLabel.textContent = "after";
    questionActionRow.appendChild(afterLabel);
    questionActionRow.appendChild(questionActionAfter);
    el.appendChild(questionActionRow);

    const answerHeading = document.createElement("h4");
    answerHeading.textContent = "Answer";
    el.appendChild(answerHeading);

    const answerAlertAfter = makeNumber(0, () => commit());
    const answerActionAfter = makeNumber(0, () => commit());
    const answerAction = makeSelect("good", () => commit());

    el.appendChild(row("Play alert after", answerAlertAfter));
    const answerActionRow = document.createElement("div");
    answerActionRow.className = "d-flex align-items-center gap-2 mb-1";
    const answerActionLabel = document.createElement("span");
    answerActionLabel.textContent = "Automatically";
    answerActionRow.appendChild(answerActionLabel);
    answerActionRow.appendChild(answerAction);
    const answerAfterLabel = document.createElement("span");
    answerAfterLabel.textContent = "after";
    answerActionRow.appendChild(answerAfterLabel);
    answerActionRow.appendChild(answerActionAfter);
    el.appendChild(answerActionRow);

    const reset = document.createElement("button");
    reset.className = "btn btn-sm btn-link";
    reset.textContent = "Reset to global defaults";
    reset.addEventListener("click", () => {
      store.update((data) => {
        const sp = Object.assign({}, data.speedup);
        delete sp[key];
        return Object.assign({}, data, { speedup: sp });
      });
    });
    el.appendChild(reset);

    function collect() {
      return {
        question: {
          alertAfter: parseFloat(alertAfter.value) || 0,
          revealAfter: parseFloat(revealAfter.value) || 0,
          autoAction: {
            after: parseFloat(questionActionAfter.value) || 0,
            action: questionAction.value,
          },
        },
        answer: {
          alertAfter: parseFloat(answerAlertAfter.value) || 0,
          autoAction: {
            after: parseFloat(answerActionAfter.value) || 0,
            action: answerAction.value,
          },
        },
      };
    }

    function commit() {
      const value = collect();
      store.update((data) => {
        const sp = Object.assign({}, data.speedup);
        sp[key] = value;
        return Object.assign({}, data, { speedup: sp });
      });
    }

    function render(sp) {
      const effective = deepMerge(GLOBAL.defaults[key] || {}, sp[key] || {});
      const question = effective.question || {};
      const answer = effective.answer || {};
      alertAfter.value = question.alertAfter || 0;
      revealAfter.value = question.revealAfter || 0;
      questionActionAfter.value = (question.autoAction || {}).after || 0;
      questionAction.value = (question.autoAction || {}).action || "again";
      answerAlertAfter.value = answer.alertAfter || 0;
      answerActionAfter.value = (answer.autoAction || {}).after || 0;
      answerAction.value = (answer.autoAction || {}).action || "good";
    }

    return { el, render };
  }

  function setup(options) {
    const store = options.auxData();
    const container = document.getElementById("speedup-classes");
    const enabled = document.getElementById("speedup-enabled");
    const grouping = GLOBAL.grouping || {};

    const sections = {};
    CLASSES.forEach((cardClass) => {
      if (cardClass.collapsedBy && grouping[cardClass.collapsedBy]) {
        return;
      }
      const section = buildClass(cardClass.key, cardClass.label, store);
      sections[cardClass.key] = section;
      container.appendChild(section.el);
    });

    store.subscribe((data) => {
      const sp = data.speedup || {};
      enabled.checked = sp.enabled !== undefined ? !!sp.enabled : GLOBAL.enabled !== false;
      Object.keys(sections).forEach((key) => sections[key].render(sp));
    });

    enabled.addEventListener("change", () => {
      store.update((data) => {
        const sp = Object.assign({}, data.speedup);
        sp.enabled = enabled.checked;
        return Object.assign({}, data, { speedup: sp });
      });
    });
  }

  $deckOptions.then((options) => {
    options.addHtmlAddon(HTML, () => setup(options));
  });
})();
