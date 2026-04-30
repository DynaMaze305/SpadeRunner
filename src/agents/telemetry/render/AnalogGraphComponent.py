from agents.telemetry.render.DashboardComponent import DashboardComponent

class AnalogGraphComponent(DashboardComponent):
    def render_html(self):
        return """
        <h3>Analog Sensors</h3>
        <canvas id="analogChart" width="600" height="250"></canvas>
        """

    def render_js(self):
        return """
            const MAX_POINTS = 900; //15 minutes

            // --- Chart.js setup ---
            const ctx = document.getElementById('analogChart').getContext('2d');
            const analogChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        { label: 'A0', data: [], borderColor: '#ff5252' },
                        { label: 'A1', data: [], borderColor: '#ffb74d' },
                        { label: 'A2', data: [], borderColor: '#fff176' },
                        { label: 'A3', data: [], borderColor: '#81c784' },
                        { label: 'A4', data: [], borderColor: '#64b5f6' },
                        { label: 'A10', data: [], borderColor: '#ba68c8' }
                    ]
                },
                options: {
                    animation: false,
                    responsive: true,
                    scales: {
                        x: {
                            title: {
                                display: true,
                                align: 'center',
                                text: 'Time',
                            },
                        },
                        y: {
                            title: {
                                display: true,
                                align: 'center',
                                text: 'Value',
                            },
                        }
                    }
                }
            });

            function updateAnalogGraph(ts, values) {
                analogChart.data.labels.push(ts * 1000);

                analogChart.data.datasets[0].data.push(values["analog_0"]);
                analogChart.data.datasets[1].data.push(values["analog_1"]);
                analogChart.data.datasets[2].data.push(values["analog_2"]);
                analogChart.data.datasets[3].data.push(values["analog_3"]);
                analogChart.data.datasets[4].data.push(values["analog_4"]);
                analogChart.data.datasets[5].data.push(values["analog_10"]);

                if (analogChart.data.labels.length > MAX_POINTS) {
                    analogChart.data.labels.shift();
                    analogChart.data.datasets.forEach(ds => ds.data.shift());
                }

                analogChart.update();
            }
        """

    def update_js(self):
        return """
                updateAnalogGraph(data.ts, data.values);
        """
