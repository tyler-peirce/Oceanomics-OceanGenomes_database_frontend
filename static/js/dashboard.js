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

function drawKindChart() {
    const ctx = document.getElementById("kindChart");
    if (!ctx) {
        return;
    }

    const data = parseChartData("relation-kind-data");
    new Chart(ctx, {
        type: "doughnut",
        data: {
            labels: data.labels,
            datasets: [
                {
                    data: data.values,
                    backgroundColor: ["#1e847f", "#ffb85c"],
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

function drawWidthChart() {
    const ctx = document.getElementById("widthChart");
    if (!ctx) {
        return;
    }

    const data = parseChartData("width-data");
    new Chart(ctx, {
        type: "bar",
        data: {
            labels: data.labels,
            datasets: [
                {
                    data: data.values,
                    borderWidth: 0,
                    backgroundColor: "#16697a",
                    borderRadius: 8,
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

drawKindChart();
drawWidthChart();
