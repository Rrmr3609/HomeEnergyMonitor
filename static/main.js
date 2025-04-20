// ----- Available Resolutions Configuration -----

const resolutions = [   //defines the different time resolutions for data aggregation and respective UI labels
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

let currentResolutionIndex = 0; //tracks the currently selected resolution index in the resolutions array

//state variables for handling anomalies and insights
let anomalyHandled     = false;
let pendingAnomalyData = null;
let pausedOnAnomaly    = false;
let anomalyInterval;
let insight1Data = [];

//helper to retrieve the current resolution object
const getCurrentResolution = () => resolutions[currentResolutionIndex];

function setupResolutionToggle() {  //sets up the resolution toggle button to cycle through available resolutions
  const btn = document.getElementById("resolution-toggle");
  btn.addEventListener("click", () => {
    //cycle to next resolution
    currentResolutionIndex = (currentResolutionIndex + 1) % resolutions.length;
    updateResolutionButton();
    resetChartData();

    //immediately fetch and plot the current point at the exact "now" timestamp
    clearInterval(anomalyInterval);
    checkAnomaly();
    anomalyInterval = setInterval(checkAnomaly, 1000);
  });
}

function updateResolutionButton() {   //updates the resolution toggle button label based on the current resolution
  const { buttonLabel } = getCurrentResolution();
  document.getElementById("resolution-toggle").innerText =
    `Current Usage - ${buttonLabel}`;
}


// ---- Insights Updaters ----

function updateSessionInsight() {   //updates the session based insight (Insight 1) comparing last 7 periods vs previous 7
  const arr = insight1Data;
  if (arr.length < 14) {
    document.getElementById("insight-1").innerText = "Gathering more data…";
    return;
  }
  const last7 = arr.slice(-7).reduce((a, b) => a + b, 0);
  const prev7 = arr.slice(-14, -7).reduce((a, b) => a + b, 0) || 1;
  const pct   = (((last7 - prev7) / prev7) * 100).toFixed(1);
  const dir   = pct >= 0 ? "higher" : "lower";
  document.getElementById("insight-1").innerText =
    `Your average usage over the last 7 periods was ${Math.abs(pct)}% ${dir} than the 7 before.`;
}

async function updateInsights() {    //fetches server driven insight (Insight 2) and updates the UI accordingly
  try {
    const { key: resolution } = getCurrentResolution();
    const resp = await fetch(`/insights?resolution=${resolution}`, { cache: "no-cache" });
    const { sevenPctChange, deltaKw } = await resp.json();

    //Insight 2 - last window kW delta
    const kw   = Math.abs(deltaKw).toFixed(3);
    const dir2 = deltaKw >= 0 ? "higher" : "lower";
    document.getElementById("insight-2").innerText =
      `Your current window's total energy usage is ${kw} kW ${dir2} than the previous window.`;

    //dynamic footer message based on performance
    const footerEl = document.querySelector(".insights .success");
    if (sevenPctChange < 0 && deltaKw < 0) {
      footerEl.innerText = "Well done!";
      footerEl.style.color = "var(--success-color)";
    } else {
      footerEl.innerText = "You are not improving your electricity usage!";
      footerEl.style.color = "#FFA000";
    }

  } catch (err) {
    console.error("Error updating insights:", err);
  }
}


// ---- Tips Updater ----

async function updateTips() {    //updates the personalised tips section and shows placeholders until enough data, then fetches server tips
  const tipsEls = document.querySelectorAll(".tips p.tip");
  if (tipsEls.length < 2) return; //guard

  //if insufficient data, show default gathering data tips
  if (insight1Data.length < 14) {
    tipsEls[0].innerText =
      "Gathering data on your usage — more detailed insights will appear once we have more readings.";
    tipsEls[1].innerText =
      "Your usage is steady. Unused devices can still draw phantom power. Try unplugging what you’re not using.";
    return;
  }

  //otherwise fetch server generated tips
  try {
    const { key: resolution } = getCurrentResolution();
    const resp = await fetch(
      `/tips?sevenPctChange=${encodeURIComponent(
        (await fetch(`/insights?resolution=${resolution}`, { cache: "no-cache" })
          .then(r => r.json())
          .then(j => j.sevenPctChange)
        )
      )}&deltaKw=${encodeURIComponent(
        (await fetch(`/insights?resolution=${resolution}`, { cache: "no-cache" })
          .then(r => r.json())
          .then(j => j.deltaKw)
        )
      )}`,
      { cache: "no-cache" }
    );
    const { tips } = await resp.json();

    //populate the two <p.tip> elements with fetched tips
    tipsEls[0].innerText = tips[0] || "";
    tipsEls[1].innerText = tips[1] || "";
  } catch (err) {
    console.error("Error fetching tips:", err);
    //fallback in case of error
    tipsEls[0].innerText = "Unable to load tips right now.";
    tipsEls[1].innerText = "";
  }
}


// ----- Anomaly Polling and UI Updates -----

async function checkAnomaly() {    //periodically polls for anomaly status, updates the chart and UI, and handles anomaly pauses
  if (pausedOnAnomaly) return;

  try {
    const { key } = getCurrentResolution();
    const resp = await fetch(
      `http://localhost:5000/current_status?resolution=${key}`,
      { cache: "no-cache" }
    );
    const data = await resp.json();

    //normalise and extract date/time/power
    const fixedDate = data.date.replace(/\/\d{4}$/, '/2025');
    const time = data.time;
    const power = data.latestPower;

    //update anomaly status text and highlight box if detected
    document.getElementById("anomaly-status").innerText = data.status;
    document.getElementById("anomaly-box")
      .classList.toggle("detected", data.status !== "No Anomalies Detected!");

    //show or hide the "all good" subtext
    const sub = document.querySelector(".anomaly .subtext");
    sub.style.display = data.status === "No Anomalies Detected!" ? "block" : "none";

    //update headers, usage text, and chart
    document.getElementById("header-time").innerText   = time;
    document.getElementById("header-date").innerText   = fixedDate;
    document.querySelector(".last-updated").innerText  = `Last updated: ${time}`;
    document.getElementById("current-usage").innerText = `${power} kW`;

    const chart = window.usageChart;
    chart.data.labels.push(time);
    chart.data.datasets[0].data.push(power);
    insight1Data.push(power);
    if (chart.data.labels.length > 10) {
      chart.data.labels.shift();
      chart.data.datasets[0].data.shift();
    }

    //sync chart labels if resolution changed on the server side
    const reported = resolutions.find(r => r.key === data.resolution);
    if (reported) {
      chart.data.datasets[0].label      = reported.chartLabel;
      chart.options.scales.x.title.text = reported.axisLabel;
    }
    chart.update();

    //update insights based on new data
    updateInsights();
    updateTips();
    updateSessionInsight();

    //on first anomaly detection, pause updates and store data for detail view
    if (data.status !== "No Anomalies Detected!" && !anomalyHandled) {
      pendingAnomalyData = { date: fixedDate, time, power };
      anomalyHandled     = true;
      pausedOnAnomaly    = true;
      clearInterval(anomalyInterval);
      clearInterval(temperatureInterval);
      document.getElementById("anomaly-details").style.display = "none";
      return;
    }

    //if anomaly cleared after pause, resume normal operation
    if (data.status === "No Anomalies Detected!" && anomalyHandled) {
      anomalyHandled     = false;
      pendingAnomalyData = null;
    }

  } catch (err) {
    console.error("Error fetching anomaly status:", err);
  }
}

function resetChartData() {    //resets the chart data and insights when resolution changes
  const { chartLabel, axisLabel } = getCurrentResolution();
  const chart = window.usageChart;

  chart.data.labels = [];
  chart.data.datasets[0].data = [];
  chart.data.datasets[0].label = chartLabel;
  chart.options.scales.x.title.text = axisLabel;
  chart.update();
  insight1Data = [];

  //refresh insights with cleared data
  updateInsights();
  updateTips();
  updateSessionInsight();
}


// ----- Target Temperature Controls and Animation -----

let temperatureInterval;

function animateTemperature() {   //animates the current temperature towards the target, updating the estimate
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

function updateTargetTemperature(change) {   //adjusts the target temperature by the given change (+/-) and animates again
  const el = document.getElementById("target-temperature");
  let temp = parseInt(el.innerText, 10) + change;
  el.innerText = `${temp}°C`;
  animateTemperature();
}


// ----- DOMContentLoaded - Chart, Controls and Polling Setup -----

document.addEventListener("DOMContentLoaded", () => {
  //initialise Chart.js line chart with default resolution labels
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

  //configure resolution toggle and initialise button text
  setupResolutionToggle();
  updateResolutionButton();

  //bind increase/decrease temperature buttons
  document.getElementById("increase-temp-button")
    .addEventListener("click", () => updateTargetTemperature(1));
  document.getElementById("decrease-temp-button")
    .addEventListener("click", () => updateTargetTemperature(-1));

  //anomaly details click handler, shows stored anomaly info and then resumes
  document.querySelector(".details").addEventListener("click", () => {
    if (!pausedOnAnomaly || !pendingAnomalyData) return;

    const { date, time, power } = pendingAnomalyData;
    const detEl = document.getElementById("anomaly-details");

    //show the anomaly banner and details
    detEl.innerText     = `Check Your Phone! Date: ${date} | Time: ${time} | Power: ${power} kW`;
    detEl.style.display = "block";

    //immediately inject the stored point for consistency
    document.getElementById("header-time").innerText    = time;
    document.getElementById("header-date").innerText    = date;
    document.querySelector(".last-updated").innerText   = `Last updated: ${time}`;
    document.getElementById("current-usage").innerText  = `${power} kW`;

    //after 5s, hide details & resume normal operation
    setTimeout(() => {
      detEl.style.display       = "none";
      pendingAnomalyData        = null;
      pausedOnAnomaly           = false;
      anomalyHandled            = false;
      animateTemperature();
      anomalyInterval = setInterval(checkAnomaly, 1000);
    }, 5000);
  });

  //start temperature animation and anomaly polling
  animateTemperature();
  checkAnomaly();
  anomalyInterval = setInterval(checkAnomaly, 1000);
  document.getElementById("anomaly-details").style.display = "none";

  //initial insights and tips
  updateInsights();
  updateTips();
  updateSessionInsight();

  //tutorial configuration using Intro.js
  document
    .getElementById("view-tutorial")
    .addEventListener("click", () => {
      introJs().setOptions({
        steps: [
          {
            element: "#resolution-toggle",
            intro: "Click here to cycle between minute, 30‑minute, hourly or daily usage!",
          },
          {
            element: "#usageGraph",
            intro: "This graph shows your live energy usage over time.",
          },
          {
            element: "#insight-1",
            intro: "Here’s insight into your current session, comparing the last 7 periods with the 7 before.",
          },
          {
            element: "#insight-2",
            intro: "And this one compares the kW usage in your current window vs. the previous window.",
          },
          {
            element: ".tips h2",
            intro: "Finally, these are personalized tips based on your usage that you can act on right now.",
          },
          {
            intro:
              "That’s it! Click “Done” to end this tutorial. Enjoy!",
          },
        ],
        showBullets: false,
        showProgress: true,
        exitOnOverlayClick: false,
      }).start();
    });
});
