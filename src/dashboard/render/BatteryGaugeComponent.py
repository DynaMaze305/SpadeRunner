from dashboard.render.DashboardComponent import DashboardComponent

class BatteryGaugeComponent(DashboardComponent):
    def render_html(self):
        return """
        <h2>Battery</h2>
        <div class="battery-box">
            <div id="battery-level" class="battery-gaugue"></div>
        </div>
        <div id="battery-text" style="margin-top:5px;">--%</div>
        """

    def render_css(self):
        return """
            .battery-box {
                width: 80%;
                height: 40px;
                border: 2px solid #fff;
                border-radius: 5px;
                position: relative;
                background: #333;
            }

            .battery-gaugue {
                height: 100%;
                width: 0%;
                background: #00e676;
                transition: width 0.3s;
            }
            """

    def render_js(self):
        return """
            function updateBattery(percent) {
                const level = document.getElementById("battery-level");
                const text = document.getElementById("battery-text");

                level.style.width = percent + "%";
                text.innerText = percent + "%";

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
                updateBattery(data.values["battery"]);
                """
