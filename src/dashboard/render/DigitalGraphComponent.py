from dashboard.render.DashboardComponent import DashboardComponent
import json

class DigitalGraphComponent(DashboardComponent):
    def __init__(self, sensors):
        """
        sensors: list of dicts like:
        [
            {"label": "Left", "data_label": "digital_2"},
            {"label": "Right", "data_label": "digital_1"}
        ]
        """
        self.sensors = sensors

    def render_html(self):
        html = '<div><h2>Digital Sensors</h2>'
        for s in self.sensors:
            html += f"""
                <h3>{s['label']}</h3>
                <canvas id="chart_{s['data_label']}" width="600" height="80"></canvas>
            """
        html += "</div>"
        return html

    def render_css(self):
        return """
        canvas[id^="chart_digital"] {
            background: #111;
            border: 1px solid #444;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        """

    def render_js(self):
        sensors_json = json.dumps(self.sensors)

        return f"""
            // ### Digital Graph Component (render js) ###
            const digitalSensors = {sensors_json};

            // Create a chart object for each sensor
            const digitalCharts = {{}};

            function createDigitalChart(canvasId, label, color) {{
                const ctx = document.getElementById(canvasId).getContext('2d');
                return new Chart(ctx, {{
                    type: 'line',
                    data: {{
                        labels: [],
                        datasets: [
                            {{
                                label: label,
                                data: [],
                                borderColor: color,
                                stepped: true,
                                pointRadius: 0
                            }}
                        ]
                    }},
                    options: {{
                        animation: false,
                        responsive: true,
                        scales: {{
                            x: {{
                                type: 'time',
                                time: {{
                                    unit: 'minute',
                                    displayFormats: {{ minute: 'HH:mm' }}
                                }},
                                grid: {{ color: 'rgba(255,255,255,0.2)' }}
                            }},
                            y: {{
                                min: 0,
                                max: 1,
                                grid: {{ color: 'rgba(255,255,255,0.2)' }}
                            }}
                        }}
                    }}
                }});
            }}

            // Initialize charts
            const colors = ["#4caf50", "#ff5252", "#2196f3", "#ffb300", "#9c27b0"];
            digitalSensors.forEach((sensor, i) => {{
                const canvasId = "chart_" + sensor.data_label;
                digitalCharts[sensor.data_label] = createDigitalChart(
                    canvasId,
                    sensor.label,
                    colors[i % colors.length]
                );
            }});

            async function loadDigitalData() {{
                const response = await fetch("/api/digital");
                const data = await response.json();

                // Collect timestamps
                const timestamps = new Set();
                for (const key in data) {{
                    data[key].forEach(p => timestamps.add(p.ts));
                }}
                const sortedTs = Array.from(timestamps).sort((a, b) => a - b);

                // Update each chart
                digitalSensors.forEach(sensor => {{
                    const key = sensor.data_label;
                    const chart = digitalCharts[key];

                    chart.data.labels = sortedTs;

                    if (!data[key]) {{
                        chart.data.datasets[0].data = sortedTs.map(_ => null);
                    }} else {{
                        chart.data.datasets[0].data = sortedTs.map(ts => {{
                            const p = data[key].find(v => v.ts === ts);
                            return p ? p.value : null;
                        }});
                    }}

                    chart.update();
                }});
            }}

            setInterval(loadDigitalData, 1000);
"""
