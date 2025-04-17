// ----- Available Resolutions Configuration -----

const resolutions = [           //define each resolution along with its button label and chart labels
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
let pausedOnAnomaly = false;
let anomalyInterval;

const getCurrentResolution = () => resolutions[currentResolutionIndex];     //returns the currently selected resolution settings

function updateResolutionButton() {    //updates the resolution toggle button text
  const { buttonLabel } = getCurrentResolution();
  document.getElementById("resolution-toggle").innerText =
    `Current Usage - ${buttonLabel}`;
}

function resetChartData() {
  const { chartLabel, axisLabel } = getCurrentResolution();     //clears the chart data and updates its labels based on the current resolution
  const chart = window.usageChart;

  chart.data.labels = [];
  chart.data.datasets[0].data = [];
  chart.data.datasets[0].label = chartLabel;
  chart.options.scales.x.title.text = axisLabel;
  chart.update();
}

function setupResolutionToggle() {      //cycle through available resolutions on button click
  const btn = document.getElementById("resolution-toggle");
  btn.addEventListener("click", () => {
    currentResolutionIndex = (currentResolutionIndex + 1) % resolutions.length;
    updateResolutionButton();
    if (window.usageChart) {
      resetChartData();
    }
  });
}

// ----- Anomaly Polling and UI Updates -----

async function checkAnomaly() {    //polls the backend for anomaly data, updates UI text and border colour, updates header/date, appends to chart and handles the pause on anomaly logic
  if (pausedOnAnomaly) return;          
  try {
    const { key } = getCurrentResolution();
    const resp = await fetch(`http://localhost:5000/current_status?resolution=${key}`, {
      cache: "no-cache"
    });
    const data = await resp.json();

    //update anomaly status
    document.getElementById("anomaly-status").innerText = data.status;
    const fixedDate2 = data.date.replace(/\/\d{4}$/, '/2025');      //force the year in the displayed date to 2025
    document.getElementById("anomaly-details").innerText = `Date: ${fixedDate2} | Time: ${data.time} | Power: ${data.latestPower} kW`;

    //toggle border color
    document.getElementById("anomaly-box")
      .classList.toggle("detected", data.status !== "No Anomalies Detected!");

    if (data.status !== "No Anomalies Detected!" && !anomalyHandled) {

      pendingAnomalyData = { time: data.time, power: data.latestPower };

      //pause all loops
      anomalyHandled = true;
      pausedOnAnomaly = true;
      clearInterval(anomalyInterval);
      clearInterval(temperatureInterval);
      
      document.querySelector(".anomaly .subtext").style.display = "none";          // hide the “You are all good for now!” line
      
      document.getElementById("anomaly-details").style.display = "none";  
      document.getElementById("anomaly-details").innerText = 'Latest data not loaded yet.';     
      
      return; //stop further updates
    }

    if(data.status === "No Anomalies Detected!" && anomalyHandled){
      
    document.querySelector(".anomaly .subtext").style.display = "block";

    anomalyHandled = false;
    pendingAnomalyData = null;
      
    }

    //update header time and date
    document.getElementById("header-time").innerText = data.time;
    const fixedDate = data.date.replace(/\/\d{4}$/, '/2025');    //take the incoming “DD/MM/YYYY” and force the YYYY to be 2025
    document.getElementById("header-date").innerText = fixedDate;

    document.querySelector('.last-updated')
      .innerText = `Last updated: ${data.time}`;

    //update current usage text
    document.getElementById("current-usage").innerText =
      `${data.latestPower} kW`;

    //append to chart
    const chart = window.usageChart;
    chart.data.labels.push(data.time);
    chart.data.datasets[0].data.push(data.latestPower);

    if (chart.data.labels.length > 10) {
      chart.data.labels.shift();
      chart.data.datasets[0].data.shift();
    }

    //ensure chart labels match reported resolution
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

// ----- Target Temperature Controls and Animation -----

let temperatureInterval;

function animateTemperature() {
  const currentElem = document.querySelector(".card.temp.current .value");        //smoothly animates the current temperature reading toward the target temperature, updating the estimate each step
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

function updateTargetTemperature(change) {             //changes the target temperature up or down by 'change' degrees and restarts the animation
  const el = document.getElementById("target-temperature");
  let temp = parseInt(el.innerText, 10) + change;
  el.innerText = `${temp}°C`;
  animateTemperature();
}

// ----- DOMContentLoaded: Chart, Controls and Polling Setup -----

document.addEventListener("DOMContentLoaded", () => {
  //initialise Chart.js line chart
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

  //configure resolution toggle
  setupResolutionToggle();
  updateResolutionButton();

  //bind temperature buttons
  document.getElementById("increase-temp-button")
    .addEventListener("click", () => updateTargetTemperature(1));
  document.getElementById("decrease-temp-button")
    .addEventListener("click", () => updateTargetTemperature(-1));

    document.querySelector(".details").addEventListener("click", () => {
      if (!pausedOnAnomaly) return;                //do nothing if no anomaly
      const details = document.getElementById("anomaly-details");
      if (!details.innerText.startsWith('Check Your Email!')) {                //prefix and reveal the line
        details.innerText = `Check Your Email! ${details.innerText}`;
      }
      details.style.display = "block";

      if (pendingAnomalyData){

        const{time,power} = pendingAnomalyData;
        const chart = window.usageChart;
        chart.data.labels.push(time);
        chart.data.datasets[0].data.push(power);
        if (chart.data.labels.length > 10) {
          chart.data.labels.shift();
          chart.data.datasets[0].data.shift();
        }
        chart.update();
      }

      anomalyInterval = setInterval(checkAnomaly, 1000);         //restart both loops
      animateTemperature();
      pausedOnAnomaly = false;
    });    

  //start temperature animation and anomaly polling
  animateTemperature();
  checkAnomaly();
  anomalyInterval = setInterval(checkAnomaly, 1000);  //store the interval to clear it later
  document.getElementById("anomaly-details").style.display = "none";      //hide the details paragraph until user clicks
});
