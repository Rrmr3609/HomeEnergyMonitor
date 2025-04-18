// ----- Available Resolutions Configuration -----

const resolutions = [
  {
    key: "minute",
    buttonLabel: "Per Minute",
    chartLabel: "Minute Usage (kW)",
    axisLabel: "Time (Minute)",
  },
  {
    key: "30min",
    buttonLabel: "Per 30 Minutes",
    chartLabel: "30-Minute Usage (kW)",
    axisLabel: "Time (30 Minutes)",
  },
  {
    key: "hour",
    buttonLabel: "Per Hour",
    chartLabel: "Hourly Usage (kW)",
    axisLabel: "Time (Hour)",
  },
  {
    key: "day",
    buttonLabel: "Per Day",
    chartLabel: "Daily Usage (kW)",
    axisLabel: "Time (Day)",
  },
];

let currentResolutionIndex = 0;

let anomalyHandled     = false;
let pendingAnomalyData = null;
let pausedOnAnomaly    = false;
let anomalyInterval;

const getCurrentResolution = () => resolutions[currentResolutionIndex];

function updateResolutionButton() {
  const { buttonLabel } = getCurrentResolution();
  document.getElementById("resolution-toggle").innerText =
    `Current Usage - ${buttonLabel}`;
}

function resetChartData() {
  const { chartLabel, axisLabel } = getCurrentResolution();
  const chart = window.usageChart;

  chart.data.labels = [];
  chart.data.datasets[0].data = [];
  chart.data.datasets[0].label = chartLabel;
  chart.options.scales.x.title.text = axisLabel;
  chart.update();
}

function setupResolutionToggle() {
  const btn = document.getElementById("resolution-toggle");
  btn.addEventListener("click", () => {
    // cycle resolution
    currentResolutionIndex = (currentResolutionIndex + 1) % resolutions.length;
    updateResolutionButton();
    resetChartData();

    // immediately fetch & plot the current point at the exact "now" timestamp
    clearInterval(anomalyInterval);
    checkAnomaly();
    anomalyInterval = setInterval(checkAnomaly, 1000);
  });
}


// ----- Anomaly Polling and UI Updates -----

async function checkAnomaly() {
  if (pausedOnAnomaly) return;

  try {
    const { key } = getCurrentResolution();
    const resp = await fetch(
      `http://localhost:5000/current_status?resolution=${key}`,
      { cache: "no-cache" }
    );
    const data = await resp.json();

    // normalize date/time
    const fixedDate = data.date.replace(/\/\d{4}$/, '/2025');
    const time       = data.time;
    const power      = data.latestPower;

    // update anomaly status & border
    document.getElementById("anomaly-status").innerText = data.status;
    document.getElementById("anomaly-box")
      .classList.toggle("detected", data.status !== "No Anomalies Detected!");

    // show/hide the "You are all good" subtext
    const sub = document.querySelector(".anomaly .subtext");
    if (data.status === "No Anomalies Detected!") {
      sub.style.display = "block";
    } else {
      sub.style.display = "none";
    }

    // always update header, current usage & chart
    document.getElementById("header-time").innerText    = time;
    document.getElementById("header-date").innerText    = fixedDate;
    document.querySelector(".last-updated").innerText   = `Last updated: ${time}`;
    document.getElementById("current-usage").innerText  = `${power} kW`;

    const chart = window.usageChart;
    chart.data.labels.push(time);
    chart.data.datasets[0].data.push(power);
    if (chart.data.labels.length > 10) {
      chart.data.labels.shift();
      chart.data.datasets[0].data.shift();
    }

    // sync chart labels/resolution
    const reported = resolutions.find(r => r.key === data.resolution);
    if (reported) {
      chart.data.datasets[0].label      = reported.chartLabel;
      chart.options.scales.x.title.text = reported.axisLabel;
    }
    chart.update();

    // stash anomaly data and pause on first detection
    if (data.status !== "No Anomalies Detected!" && !anomalyHandled) {
      pendingAnomalyData = { date: fixedDate, time, power };
      anomalyHandled     = true;
      pausedOnAnomaly    = true;
      clearInterval(anomalyInterval);
      clearInterval(temperatureInterval);
      document.getElementById("anomaly-details").style.display = "none";
      return;
    }

    // if anomaly cleared, resume normal operation
    if (data.status === "No Anomalies Detected!" && anomalyHandled) {
      anomalyHandled     = false;
      pendingAnomalyData = null;
    }

  } catch (err) {
    console.error("Error fetching anomaly status:", err);
  }
}

// ----- Target Temperature Controls and Animation -----

let temperatureInterval;

function animateTemperature() {
  const currentElem  = document.querySelector(".card.temp.current .value");
  const targetElem   = document.getElementById("target-temperature");
  const estimateElem = document.querySelector(".card.temp.current .estimate span");

  let currentTemp = parseInt(currentElem.innerText, 10);
  const targetTemp = parseInt(targetElem.innerText, 10);
  let diff = targetTemp - currentTemp;

  if (diff === 0) {
    estimateElem.innerText = "Target Reached";
    return;
  }

  estimateElem.innerText = `${Math.abs(diff * 5)}s`;
  clearInterval(temperatureInterval);

  temperatureInterval = setInterval(() => {
    currentTemp += Math.sign(diff);
    currentElem.innerText = `${currentTemp}°C`;
    diff = targetTemp - currentTemp;

    if (diff === 0) {
      estimateElem.innerText = "Target Reached";
      clearInterval(temperatureInterval);
    } else {
      estimateElem.innerText = `${Math.abs(diff * 5)}s`;
    }
  }, 5000);
}

function updateTargetTemperature(change) {
  const el = document.getElementById("target-temperature");
  let temp = parseInt(el.innerText, 10) + change;
  el.innerText = `${temp}°C`;
  animateTemperature();
}

// ----- DOMContentLoaded: Chart, Controls and Polling Setup -----

document.addEventListener("DOMContentLoaded", () => {
  // initialise Chart.js line chart
  const ctx = document.getElementById("usageGraph").getContext("2d");
  const { chartLabel, axisLabel } = resolutions[0];

  window.usageChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [{
        label: chartLabel,
        data: [],
        borderColor: "#FF9800",
        backgroundColor: "rgba(255,152,0,0.2)",
        fill: true,
        tension: 0.2,
      }]
    },
    options: {
      scales: {
        x: { title: { display: true, text: axisLabel } },
        y: { title: { display: true, text: "Usage (kW)" }, beginAtZero: true }
      }
    }
  });

  // configure resolution toggle
  setupResolutionToggle();
  updateResolutionButton();

  // bind temperature buttons
  document.getElementById("increase-temp-button")
    .addEventListener("click", () => updateTargetTemperature(1));
  document.getElementById("decrease-temp-button")
    .addEventListener("click", () => updateTargetTemperature(-1));

  // anomaly details click handler
  document.querySelector(".details").addEventListener("click", () => {
    if (!pausedOnAnomaly || !pendingAnomalyData) return;

    const { date, time, power } = pendingAnomalyData;
    const detEl = document.getElementById("anomaly-details");

    // show the anomaly banner and details
    detEl.innerText     = `Check Your Email! Date: ${date} | Time: ${time} | Power: ${power} kW`;
    detEl.style.display = "block";

    // immediately inject the stored point
    document.getElementById("header-time").innerText    = time;
    document.getElementById("header-date").innerText    = date;
    document.querySelector(".last-updated").innerText   = `Last updated: ${time}`;
    document.getElementById("current-usage").innerText  = `${power} kW`;

    // after 5s, hide details & resume
    setTimeout(() => {
      detEl.style.display       = "none";
      pendingAnomalyData        = null;
      pausedOnAnomaly           = false;
      anomalyHandled            = false;
      animateTemperature();
      anomalyInterval = setInterval(checkAnomaly, 1000);
    }, 5000);
  });

  // start everything
  animateTemperature();
  checkAnomaly();
  anomalyInterval = setInterval(checkAnomaly, 1000);
  document.getElementById("anomaly-details").style.display = "none";
});
