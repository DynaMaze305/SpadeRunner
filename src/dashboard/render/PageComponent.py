from dashboard.render.DashboardComponent import DashboardComponent

class PageComponent(DashboardComponent):
    def render_css(self):
        return """
            body { background:#111; color:#eee; font-family:Arial; padding:20px; }
            h1 { color:#4fc3f7; }
            .box { background:#222; padding:10px; margin:10px 0; border-radius:8px; }
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
