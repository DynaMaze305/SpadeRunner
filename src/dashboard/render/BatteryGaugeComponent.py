from dashboard.render.DashboardComponent import DashboardComponent

class BatteryGaugeComponent(DashboardComponent):
    def render_html(self):
        return """
        <div class="battery-container">
            <h2>Battery</h2>
            <div class="battery-box">
                <div id="battery-level" class="battery-gaugue"></div>
            </div>
            <div id="battery-text" class="battery-text">--%</div>
        </div>
        """

    def render_css(self):
        return """
            .battery-container {
                text-align: center;
                width: 200px;
                margin: auto;
            }

            .battery-box {
                width: 80%;
                height: 40px;
                border: 2px solid #fff;
                border-radius: 5px;
                position: relative;
                background: #333;
                margin: auto;
            }

            .battery-gaugue {
                height: 100%;
                width: 0%;
                background: #00e676;
                transition: width 0.3s;
            }

            .battery-text {
                margin-top: 5px;
            }
        """

    def render_js(self):
        return """
            function updateBattery(percent) {
                const level = document.getElementById("battery-level");
                const text = document.getElementById("battery-text");

                // Limit number to 2 digits
                const percent_display = Math.round(percent).toString().slice(0, 2);

                level.style.width = percent_display + "%";
                text.innerText = percent_display + "%";

                if (percent > 50) {
                    level.style.background = "#00e676"; // green
                } else if (percent > 20) {
                    level.style.background = "#ffeb3b"; // yellow
                } else {
                    level.style.background = "#ff1744"; // red
                }
            }
            """

    def update_js(self):
        return """
            updateBattery(data.battery);
        """
