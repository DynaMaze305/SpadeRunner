from dashboard.render.DashboardComponent import DashboardComponent

class AnalogGraphComponent(DashboardComponent):
    def render_html(self):
        return """
        <h3>Analog Sensors</h3>
        <canvas id="analogChart" width="600" height="250"></canvas>
        """

    def render_js(self):
        return """
            // ### Analog Grap Component (render js) ###
            const MAX_POINTS = 900; // 15 minutes

            // --- Data store (not inside the chart) ---
            const analogStore = {
                ts: [],
                analog_0: [],
                analog_1: [],
                analog_2: [],
                analog_3: [],
                analog_4: [],
                analog_10: []
            };

            // --- Chart.js setup ---
            const ctx = document.getElementById('analogChart').getContext('2d');
            const analogChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        { label: 'IR line L+ (A0)', data: [], borderColor: '#ff5252', pointRadius: 0 },
                        { label: 'IR line L  (A1)', data: [], borderColor: '#ffb74d', pointRadius: 0 },
                        { label: 'IR line C  (A2)', data: [], borderColor: '#fff176', pointRadius: 0 },
                        { label: 'IR line R  (A3)', data: [], borderColor: '#81c784', pointRadius: 0 },
                        { label: 'IR line R+ (A4)', data: [], borderColor: '#64b5f6', pointRadius: 0 },
                        { label: 'Battery raw (A10)', data: [], borderColor: '#ba68c8', pointRadius: 0 }
                    ]
                },
                options: {
                    animation: false,
                    responsive: true,
                    scales: {
                        x: {
                            type: 'time',
                            time: {
                                unit: 'minute',
                                displayFormats: { minute: 'HH:mm' }
                            },
                            title: {
                                display: true,
                                text: 'Time'
                            },
                            grid: { color: "rgba(255,255,255,0.2)" }
                        },
                        y: {
                            title: {
                                display: true,
                                text: 'Value'
                            },
                            grid: { color: "rgba(255,255,255,0.2)" }
                        }
                    }
                }
            });

            async function loadAnalogData() {
                const response = await fetch("/api/analog");
                const data = await response.json();
                const map = {
                    "analog_0": 0,
                    "analog_1": 1,
                    "analog_2": 2,
                    "analog_3": 3,
                    "analog_4": 4,
                    "analog_10": 5
                };

                analogChart.data.labels = [];
                analogChart.data.datasets.forEach(ds => ds.data = []);

                const timestamps = new Set();

                for (const key in data) {
                    data[key].forEach(p => timestamps.add(p.ts));
                }

                const sortedTs = Array.from(timestamps).sort((a, b) => a - b);
                analogChart.data.labels = sortedTs;

                for (const key in data) {
                    const idx = map[key];
                    if (idx === undefined) continue; // skip unknown keys

                    analogChart.data.datasets[idx].data = sortedTs.map(ts => {
                        const p = data[key].find(v => v.ts === ts);
                        return p ? p.value : null;
                    });
                }

                analogChart.update();
            }


            setInterval(loadAnalogData, 1000);
        """

    def update_js(self):
        return """
        """
