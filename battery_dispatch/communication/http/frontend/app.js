"use strict";

// Battery dispatch page: reads the form, calls the API and draws the result with uPlot.
(() => {
  const TZ = "Europe/Berlin";
  const QUARTER_S = 900;
  const NARROW = window.matchMedia("(max-width: 639px)");
  const DARK = window.matchMedia("(prefers-color-scheme: dark)");

  const BATTERY_FIELDS = [
    ["capacity_kwh", "Capacity"],
    ["max_charge_kw", "Charge power"],
    ["max_discharge_kw", "Discharge power"],
    ["charge_efficiency", "Charge efficiency"],
    ["discharge_efficiency", "Discharge efficiency"],
    ["soc_min", "SoC min"],
    ["soc_max", "SoC max"],
    ["soc_initial", "SoC start"],
    ["degradation_cost_eur_per_mwh", "Degradation"],
  ];
  const FIELD_LABELS = Object.fromEntries([
    ...BATTERY_FIELDS,
    ["start", "From"],
    ["end", "To"],
    ["battery", "Battery"],
    ["body", "Range"],
  ]);

  const $ = (id) => document.getElementById(id);

  // ---- Formatting -------------------------------------------------------

  const num0 = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 });
  const num2 = new Intl.NumberFormat("en-GB", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  const offsetFormat = new Intl.DateTimeFormat("en-GB", {
    timeZone: TZ,
    timeZoneName: "longOffset",
  });
  const dateFormat = new Intl.DateTimeFormat("en-GB", {
    timeZone: TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  const tickFormat = new Intl.DateTimeFormat("en-GB", {
    timeZone: TZ,
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
  const stampFormat = new Intl.DateTimeFormat("en-GB", {
    timeZone: TZ,
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZoneName: "short",
  });

  // Normalise U+2212 and similar so that numbers read the same everywhere.
  const plain = (text) => text.replace(/−/g, "-");
  const eur = (value) => `${plain(num2.format(value))} EUR`;
  const kwh = (value) => `${plain(num0.format(value))} kWh`;
  const kw = (value) => `${plain(num0.format(value))} kW`;
  const int = (value) => plain(num0.format(value));

  function parts(format, ms) {
    const result = {};
    for (const part of format.formatToParts(ms)) result[part.type] = part.value;
    return result;
  }

  /** Offset of Europe/Berlin from UTC in minutes at the given instant. */
  function offsetMinutes(ms) {
    const name = parts(offsetFormat, ms).timeZoneName || "GMT";
    const match = /^GMT([+-])(\d{2}):(\d{2})$/.exec(name);
    if (!match) return 0;
    const minutes = Number(match[2]) * 60 + Number(match[3]);
    return match[1] === "-" ? -minutes : minutes;
  }

  function formatOffset(minutes) {
    const sign = minutes < 0 ? "-" : "+";
    const abs = Math.abs(minutes);
    const hh = String(Math.floor(abs / 60)).padStart(2, "0");
    const mm = String(abs % 60).padStart(2, "0");
    return `${sign}${hh}:${mm}`;
  }

  /** "2026-10-25" -> "2026-10-25T00:00:00+02:00", midnight in Europe/Berlin. */
  function berlinMidnight(date) {
    const [y, m, d] = date.split("-").map(Number);
    const utcMidnight = Date.UTC(y, m - 1, d);
    // The offset at UTC midnight is a first guess; the offset at the resulting instant is
    // the one that applies at local midnight.
    const guess = utcMidnight - offsetMinutes(utcMidnight) * 60000;
    return `${date}T00:00:00${formatOffset(offsetMinutes(guess))}`;
  }

  function addDays(date, days) {
    const [y, m, d] = date.split("-").map(Number);
    return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
  }

  function isDate(value) {
    return /^\d{4}-\d{2}-\d{2}$/.test(value) && addDays(value, 0) === value;
  }

  function todayInBerlin() {
    const p = parts(dateFormat, Date.now());
    return `${p.year}-${p.month}-${p.day}`;
  }

  /** Axis label: the date at midnight, the time otherwise. */
  function tickLabel(seconds) {
    const p = parts(tickFormat, seconds * 1000);
    return p.hour === "00" && p.minute === "00" ? `${p.day} ${p.month}` : `${p.hour}:${p.minute}`;
  }

  function stamp(ms) {
    const p = parts(stampFormat, ms);
    return `${p.weekday} ${p.day} ${p.month} ${p.year}, ${p.hour}:${p.minute} ${p.timeZoneName}`;
  }

  // ---- Status and health ------------------------------------------------

  function setStatus(text, isError = false) {
    const status = $("status");
    status.textContent = text;
    status.classList.toggle("is-error", isError);
  }

  async function checkHealth() {
    const health = $("health");
    const text = $("health-text");
    try {
      const response = await fetch("/health", { headers: { accept: "application/json" } });
      const body = await response.json();
      const ok = response.ok && body.state === "ok";
      health.classList.toggle("is-ok", ok);
      health.classList.toggle("is-down", !ok);
      text.textContent = `API ${ok ? "ok" : body.state || "down"}`;
      const components = (body.components || [])
        .map((c) => `${c.name}: ${c.state}${c.detail ? ` (${c.detail})` : ""}`)
        .join(", ");
      health.title = `State: ${body.state}${components ? `. ${components}` : ""}`;
    } catch {
      health.classList.remove("is-ok");
      health.classList.add("is-down");
      text.textContent = "API unreachable";
      health.title = "State: unreachable";
    }
  }

  // ---- Requests ---------------------------------------------------------

  async function postJson(path, payload) {
    const response = await fetch(path, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "application/json" },
      body: JSON.stringify(payload),
    });
    let body = null;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    return { ok: response.ok, status: response.status, body };
  }

  function sentence(text) {
    const trimmed = text.trim().replace(/^Value error, /, "");
    const capital = trimmed.charAt(0).toUpperCase() + trimmed.slice(1);
    return /[.!?]$/.test(capital) ? capital : `${capital}.`;
  }

  function withLabels(text) {
    return text.replace(/\b[a-z]+(?:_[a-z]+)+\b/g, (key) => FIELD_LABELS[key] || key);
  }

  function describeError(result) {
    const detail = result.body ? result.body.detail : null;
    switch (result.status) {
      case 422: {
        const first = Array.isArray(detail) ? detail[0] : null;
        if (!first) return "The request was rejected as invalid.";
        const loc = Array.isArray(first.loc) ? first.loc : [];
        const label = FIELD_LABELS[loc[loc.length - 1]] || "";
        const message = sentence(withLabels(String(first.msg || "invalid value")));
        return label ? `${label}: ${message}` : message;
      }
      case 409:
        if (detail && typeof detail === "object") {
          return (
            `Prices are incomplete: ${detail.found} of ${detail.expected} quarter hours are ` +
            `available, the first missing one starts ${stamp(Date.parse(detail.first_missing))}. ` +
            "SMARD may not have published them yet."
          );
        }
        return "Prices for this range are incomplete.";
      case 500:
        return `The optimisation did not finish${typeof detail === "string" ? `: ${detail}` : ""}.`;
      case 502:
        return (
          "SMARD could not be reached or returned unexpected data" +
          `${typeof detail === "string" ? `: ${detail}` : ""}. Try again later.`
        );
      case 503:
        return "The database is unavailable. The health indicator shows which part is down.";
      default:
        return typeof detail === "string"
          ? sentence(detail)
          : `The request failed with status ${result.status}.`;
    }
  }

  function readForm() {
    const from = $("from").value;
    const to = $("to").value;
    if (!isDate(from) || !isDate(to)) return { error: "Choose a first and a last day." };
    if (to < from) return { error: "The last day must not be before the first day." };
    const battery = {};
    for (const [key] of BATTERY_FIELDS) {
      const raw = $(key).value.trim();
      // The degradation cost is optional; left empty, the API default applies.
      if (raw === "" && key === "degradation_cost_eur_per_mwh") continue;
      // Other empty or unparsable fields are sent as null; the API names the field.
      battery[key] = raw === "" || !Number.isFinite(Number(raw)) ? null : Number(raw);
    }
    return { start: berlinMidnight(from), end: berlinMidnight(addDays(to, 1)), battery };
  }

  let busy = false;

  async function optimise() {
    if (busy) return;
    const input = readForm();
    if (input.error) {
      setStatus(input.error, true);
      return;
    }
    busy = true;
    $("optimise").disabled = true;
    document.body.classList.add("is-stale");
    setStatus("Optimising ...");
    const request = { start: input.start, end: input.end, battery: input.battery };
    try {
      let result = await postJson("/dispatch/optimize", request);
      let imported = false;
      if (result.status === 409) {
        setStatus("Importing prices from SMARD ...");
        const importResult = await postJson("/prices/import", {
          start: input.start,
          end: input.end,
        });
        if (!importResult.ok) {
          setStatus(describeError(importResult), true);
          return;
        }
        imported = true;
        setStatus("Optimising ...");
        result = await postJson("/dispatch/optimize", request);
      }
      if (!result.ok) {
        setStatus(describeError(result), true);
        return;
      }
      render(result.body, input.battery);
      document.body.classList.remove("is-stale");
      const steps = result.body.schedule.length;
      setStatus(`${int(steps)} quarter hours${imported ? ", prices imported from SMARD" : ""}.`);
    } catch {
      setStatus("The API could not be reached. Check that the application is running.", true);
    } finally {
      busy = false;
      $("optimise").disabled = false;
      checkHealth();
    }
  }

  // ---- Key figures ------------------------------------------------------

  function renderFigures(result) {
    $("fig-revenue").textContent = eur(result.revenue_eur);
    $("fig-degradation").textContent = eur(result.degradation_cost_eur);
    $("fig-charged").textContent = kwh(result.charged_kwh);
    $("fig-discharged").textContent = kwh(result.discharged_kwh);
    $("fig-cycles").textContent = num2.format(result.equivalent_full_cycles);
    $("fig-solver").textContent = `${result.solver.status}, ${int(result.solver.runtime_ms)} ms`;
  }

  // ---- Charts -----------------------------------------------------------

  let last = null; // { result, battery } of the chart currently shown
  let charts = [];

  function colours() {
    const style = getComputedStyle(document.documentElement);
    const v = (name) => style.getPropertyValue(name).trim();
    return {
      text: v("--text"),
      muted: v("--muted"),
      border: v("--border"),
      grid: v("--grid"),
      zero: v("--zero"),
      price: v("--price"),
      chargeFill: v("--charge-fill"),
      dischargeFill: v("--discharge-fill"),
      soc: v("--soc"),
      socFill: v("--soc-fill"),
      limit: v("--limit"),
      font: v("--font"),
    };
  }

  /**
   * Ranges for two y scales that put zero at the same height, so that one zero line serves
   * price and power. `share` is the fraction of the height below zero.
   */
  function alignedRanges(priceMin, priceMax, chargeMax, dischargeMax) {
    const lo = Math.min(0, priceMin);
    const hi = Math.max(0, priceMax);
    const priceShare = hi > lo ? -lo / (hi - lo) : 0.5;
    const share = Math.min(0.6, Math.max(0.4, priceShare));
    const span = (min, max) => Math.max(max / (1 - share), -min / share, 1) * 1.08;
    const priceSpan = span(lo, hi);
    const powerSpan = span(-chargeMax, dischargeMax);
    return {
      price: [-share * priceSpan, (1 - share) * priceSpan],
      power: [-share * powerSpan, (1 - share) * powerSpan],
    };
  }

  /** Width of a y axis for labels up to the given magnitude. */
  function axisSize(text) {
    return Math.ceil(text.length * 7.2 + 16);
  }

  function axis(c, extra) {
    return {
      stroke: c.muted,
      font: `12px ${c.font}`,
      labelFont: `12px ${c.font}`,
      labelSize: 18,
      labelGap: 2,
      grid: { stroke: c.grid, width: 1 },
      ticks: { stroke: c.border, width: 1, size: 4 },
      ...extra,
    };
  }

  function xAxis(c) {
    return axis(c, { space: 60, size: 34, values: (u, splits) => splits.map(tickLabel) });
  }

  function chartWidth(element) {
    return Math.max(element.clientWidth, 200);
  }

  function chartHeights() {
    return NARROW.matches ? [260, 170] : [320, 200];
  }

  function updateReadout(index) {
    const ids = ["price", "charge", "discharge", "soc"];
    if (!last || index == null) {
      $("readout-time").textContent = "Point at a chart to read the values";
      for (const id of ids) $(`readout-${id}`).textContent = "";
      return;
    }
    const step = last.result.schedule[index];
    $("readout-time").textContent = `${stamp(Date.parse(step.time))}, 15 minutes`;
    $("readout-price").textContent = `${plain(num2.format(step.price_eur_per_mwh))} EUR/MWh`;
    $("readout-charge").textContent = kw(step.charge_kw);
    $("readout-discharge").textContent = kw(step.discharge_kw);
    $("readout-soc").textContent = kwh(step.soc_kwh);
  }

  function renderCharts() {
    for (const chart of charts) chart.destroy();
    charts = [];
    if (!last || last.result.schedule.length === 0) return;

    const { result, battery } = last;
    const c = colours();
    const steps = result.schedule;
    const n = steps.length;
    const t0 = Date.parse(result.start) / 1000;
    const t1 = Date.parse(result.end) / 1000;

    // One extra point at the end of the range, so that the last quarter hour is drawn in
    // full. The SoC series starts with the initial energy at the start of the range.
    const x = [...steps.map((s) => Date.parse(s.time) / 1000), t1];
    const price = [...steps.map((s) => s.price_eur_per_mwh), steps[n - 1].price_eur_per_mwh];
    const charge = [...steps.map((s) => (s.charge_kw > 0 ? -s.charge_kw : null)), null];
    const discharge = [...steps.map((s) => (s.discharge_kw > 0 ? s.discharge_kw : null)), null];
    const capacity = battery.capacity_kwh;
    const soc = [battery.soc_initial * capacity, ...steps.map((s) => s.soc_kwh)];
    const socMin = x.map(() => battery.soc_min * capacity);
    const socMax = x.map(() => battery.soc_max * capacity);

    const prices = steps.map((s) => s.price_eur_per_mwh);
    const ranges = alignedRanges(
      Math.min(...prices),
      Math.max(...prices),
      battery.max_charge_kw,
      battery.max_discharge_kw,
    );

    const leftSize = Math.max(
      axisSize(int(Math.round(ranges.price[0]))),
      axisSize(int(Math.round(ranges.price[1]))),
      axisSize(int(capacity)),
    );
    const rightSize = Math.max(
      axisSize(int(Math.round(ranges.power[0]))),
      axisSize(int(Math.round(ranges.power[1]))),
      axisSize("100 %"),
    );

    const quarterAt = (u) => {
      const left = u.cursor.left;
      if (left == null || left < 0) return null;
      const index = Math.floor((u.posToVal(left, "x") - t0) / QUARTER_S);
      return index >= 0 && index < n ? index : null;
    };

    // uPlot keeps state in these objects, so every chart gets its own copy.
    const common = () => ({
      tzDate: (ts) => uPlot.tzDate(new Date(ts * 1000), TZ),
      legend: { show: false },
      cursor: {
        sync: { key: "dispatch", setSeries: false },
        points: { show: false },
        y: false,
        drag: { x: true, y: false, setScale: true },
      },
    });
    const readoutHook = (u) => updateReadout(quarterAt(u));
    // The data run from t0 to t1, so the automatic range is the full range; zoom and its
    // reset by double click work through uPlot's own handling.
    const xScale = () => ({ time: true });
    const bars = uPlot.paths.bars({ size: [1, Infinity, 0], align: 1, gap: 0 });
    const [powerHeight, socHeight] = chartHeights();

    const powerElement = $("chart-power");
    const socElement = $("chart-soc");
    powerElement.replaceChildren();
    socElement.replaceChildren();

    const zeroLine = (u) => {
      const ctx = u.ctx;
      const y = Math.round(u.valToPos(0, "price", true)) + 0.5;
      ctx.save();
      ctx.strokeStyle = c.zero;
      ctx.lineWidth = Math.max(1, Math.round(uPlot.pxRatio));
      ctx.beginPath();
      ctx.moveTo(u.bbox.left, y);
      ctx.lineTo(u.bbox.left + u.bbox.width, y);
      ctx.stroke();
      ctx.restore();
    };

    const powerChart = new uPlot(
      {
        ...common(),
        width: chartWidth(powerElement),
        height: powerHeight,
        hooks: { setCursor: [readoutHook], drawAxes: [zeroLine] },
        scales: {
          x: xScale(),
          price: { range: () => ranges.price },
          power: { range: () => ranges.power },
        },
        axes: [
          xAxis(c),
          axis(c, {
            scale: "price",
            label: "EUR/MWh",
            size: leftSize,
            values: (u, splits) => splits.map(int),
          }),
          axis(c, {
            scale: "power",
            side: 1,
            label: "kW",
            size: rightSize,
            grid: { show: false },
            values: (u, splits) => splits.map(int),
          }),
        ],
        series: [
          {},
          {
            label: "Charge",
            scale: "power",
            stroke: c.chargeFill,
            fill: c.chargeFill,
            width: 0,
            paths: bars,
            fillTo: () => 0,
            points: { show: false },
          },
          {
            label: "Discharge",
            scale: "power",
            stroke: c.dischargeFill,
            fill: c.dischargeFill,
            width: 0,
            paths: bars,
            fillTo: () => 0,
            points: { show: false },
          },
          {
            label: "Price",
            scale: "price",
            stroke: c.price,
            width: 1.5,
            paths: uPlot.paths.stepped({ align: 1 }),
            points: { show: false },
          },
        ],
      },
      [x, charge, discharge, price],
      powerElement,
    );

    const socChart = new uPlot(
      {
        ...common(),
        width: chartWidth(socElement),
        height: socHeight,
        hooks: { setCursor: [readoutHook] },
        scales: { x: xScale(), soc: { range: () => [0, capacity * 1.04] } },
        axes: [
          xAxis(c),
          axis(c, {
            scale: "soc",
            label: "kWh",
            size: leftSize,
            values: (u, splits) => splits.map(int),
          }),
          axis(c, {
            scale: "soc",
            side: 1,
            label: "% of capacity",
            size: rightSize,
            grid: { show: false },
            values: (u, splits) => splits.map((v) => `${int((v / capacity) * 100)} %`),
          }),
        ],
        series: [
          {},
          {
            label: "State of charge",
            scale: "soc",
            stroke: c.soc,
            fill: c.socFill,
            width: 1.5,
            fillTo: () => 0,
            points: { show: false },
          },
          { label: "SoC min", scale: "soc", stroke: c.limit, width: 1, dash: [4, 4], points: { show: false } },
          { label: "SoC max", scale: "soc", stroke: c.limit, width: 1, dash: [4, 4], points: { show: false } },
        ],
      },
      [x, soc, socMin, socMax],
      socElement,
    );

    charts = [powerChart, socChart];
  }

  function render(result, battery) {
    last = { result, battery };
    renderFigures(result);
    renderCharts();
    updateReadout(null);
  }

  function resizeCharts() {
    if (charts.length !== 2) return;
    const [powerHeight, socHeight] = chartHeights();
    charts[0].setSize({ width: chartWidth($("chart-power")), height: powerHeight });
    charts[1].setSize({ width: chartWidth($("chart-soc")), height: socHeight });
  }

  // ---- Start ------------------------------------------------------------

  function init() {
    const params = new URLSearchParams(window.location.search);
    const queryFrom = params.get("from");
    const queryTo = params.get("to");
    const today = todayInBerlin();
    const from = isDate(queryFrom || "") ? queryFrom : today;
    const to = isDate(queryTo || "") ? queryTo : from;
    $("from").value = from;
    $("to").value = to;

    if (NARROW.matches) $("battery").open = false;

    $("form").addEventListener("submit", (event) => {
      event.preventDefault();
      optimise();
    });

    let pending = 0;
    new ResizeObserver(() => {
      cancelAnimationFrame(pending);
      pending = requestAnimationFrame(resizeCharts);
    }).observe($("chart-power"));
    DARK.addEventListener("change", renderCharts);
    NARROW.addEventListener("change", resizeCharts);

    checkHealth();
    optimise();
  }

  init();
})();
