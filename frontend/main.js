// main.js

// ----- Resolution Toggle & Anomaly Checking -----

// Define each resolution along with its button label and chart labels
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

/**
 * Returns the current resolution object.
 */
const getCurrentResolution = () => resolutions[currentResolutionIndex];

/**
 * Updates the resolution-toggle button text.
 */
function updateResolutionButton() {
  const { buttonLabel } = getCurrentResolution();
  document.getElementById("resolution-toggle").innerText =
    `Current Usage - ${buttonLabel}`;
}

/**
 * Clears the chart data and updates its labels based on the current resolution.
 */
function resetChartData() {
  const { chartLabel, axisLabel } = getCurrentResolution();
  const chart = window.usageChart;

  chart.data.labels = [];
  chart.data.datasets[0].data = [];
  chart.data.datasets[0].label = chartLabel;
  chart.options.scales.x.title.text = axisLabel;
  chart.update();
}

/**
 * Sets up the click handler for the resolution-toggle button,
 * cycling through resolutions and resetting the chart.
 */
function setupResolutionToggle() {
  const btn = document.getElementById("resolution-toggle");
  btn.addEventListener("click", () => {
    currentResolutionIndex = (currentResolutionIndex + 1) % resolutions.length;
    updateResolutionButton();
    if (window.usageChart) {
      resetChartData();
    }
  });
}

/**
 * Polls the backend for anomaly data, updates UI text,
 * toggles the detected class, updates header & chart.
 */
async function checkAnomaly() {
  try {
    const { key } = getCurrentResolution();
    const resp = await fetch(`http://localhost:5000/current_status?resolution=${key}`, {
      cache: "no-cache"
    });
    const data = await resp.json();

    // Update anomaly status
    document.getElementById("anomaly-status").innerText = data.status;
    document.getElementById("anomaly-details").innerText =
      `Time: ${data.hour} | Power: ${data.latestPower} kW`;

    // Toggle border color
    document.getElementById("anomaly-box")
      .classList.toggle("detected", data.status !== "No Anomalies Detected!");

    // Update header time & date
    document.getElementById("header-time").innerText = data.time;
    document.getElementById("header-date").innerText = data.date;

    // Update current usage text
    document.getElementById("current-usage").innerText =
      `${data.latestPower} kW`;

    // Append to chart
    const chart = window.usageChart;
    chart.data.labels.push(data.time);
    chart.data.datasets[0].data.push(data.latestPower);

    if (chart.data.labels.length > 10) {
      chart.data.labels.shift();
      chart.data.datasets[0].data.shift();
    }

    // Ensure chart labels match reported resolution
    const reported = resolutions.find(r => r.key === data.resolution);
    if (reported) {
      if (chart.data.datasets[0].label !== reported.chartLabel) {
        chart.data.datasets[0].label = reported.chartLabel;
      }
      if (chart.options.scales.x.title.text !== reported.axisLabel) {
        chart.options.scales.x.title.text = reported.axisLabel;
      }
    }

    chart.update();
  } catch (err) {
    console.error("Error fetching anomaly status:", err);
  }
}

// ----- Temperature Animation -----

let temperatureInterval;

/**
 * Smoothly animates the current temperature reading
 * toward the target temperature, updating the estimate each step.
 */
function animateTemperature() {
  const currentElem = document.querySelector(".card.temp.current .value");
  const targetElem = document.getElementById("target-temperature");
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

/**
 * Changes the target temperature up or down by `change` degrees
 * and restarts the animation.
 */
function updateTargetTemperature(change) {
  const el = document.getElementById("target-temperature");
  let temp = parseInt(el.innerText, 10) + change;
  el.innerText = `${temp}°C`;
  animateTemperature();
}

// ----- Initialization on DOM Load -----

document.addEventListener("DOMContentLoaded", () => {
  // Initialize Chart.js line chart
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

  // Configure resolution toggle
  setupResolutionToggle();
  updateResolutionButton();

  // Bind temperature buttons
  document.getElementById("increase-temp-button")
    .addEventListener("click", () => updateTargetTemperature(1));
  document.getElementById("decrease-temp-button")
    .addEventListener("click", () => updateTargetTemperature(-1));

  // Start temperature animation and anomaly polling
  animateTemperature();
  checkAnomaly();
  setInterval(checkAnomaly, 1000);
});
