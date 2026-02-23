function parseChartData(id) {
    const node = document.getElementById(id);
    if (!node) {
        return { labels: [], values: [] };
    }

    try {
        return JSON.parse(node.textContent);
    } catch (_err) {
        return { labels: [], values: [] };
    }
}

function drawStatusChart() {
    const ctx = document.getElementById("statusChart");
    if (!ctx) {
        return;
    }

    const data = parseChartData("status-data");
    new Chart(ctx, {
        type: "doughnut",
        data: {
            labels: data.labels,
            datasets: [
                {
                    data: data.values,
                    backgroundColor: ["#1e847f", "#ffb85c", "#2b3f54", "#b84a28"],
                    borderWidth: 0,
                },
            ],
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: "bottom",
                },
            },
        },
    });
}

function drawTrendChart() {
    const ctx = document.getElementById("trendChart");
    if (!ctx) {
        return;
    }

    const data = parseChartData("trend-data");
    new Chart(ctx, {
        type: "line",
        data: {
            labels: data.labels,
            datasets: [
                {
                    label: "Records received",
                    data: data.values,
                    borderColor: "#16697a",
                    backgroundColor: "rgba(30, 132, 127, 0.2)",
                    tension: 0.32,
                    fill: true,
                },
            ],
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        precision: 0,
                    },
                },
            },
            plugins: {
                legend: {
                    display: false,
                },
            },
        },
    });
}

drawStatusChart();
drawTrendChart();
