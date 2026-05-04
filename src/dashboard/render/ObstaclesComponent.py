from dashboard.render.DashboardComponent import DashboardComponent

class ObstacleSensorsComponent(DashboardComponent):
    def render_html(self):
        return """
        <div class="obstacle-container">
            <div class="digital-box">
                <div>
                    <div>Left</div>
                    <div id="dig2" class="light"></div>
                </div>
                <div>
                    <div>Right</div>
                    <div id="dig1" class="light"></div>
                </div>
            </div>
            <h2>Obstacle Sensors</h2>
        </div>
        """

    def render_css(self):
        return """
            .obstacle-container {
                text-align: center;
                margin: auto;
            }

            .digital-box {
                color: #000000;
                background: #ffeb3b;
                padding: 15px;
                border-radius: 10px;
                display: flex;
                justify-content: space-around;
                margin-bottom: 20px;
                align-content: center;
            }

            .light {
                width: 40px;
                height: 40px;
                border-radius: 50%;
                background: #444;
                border: 2px solid #222;
                margin:5px;
            }

            .light.green { background: #00e676; }
            .light.red { background: #ff1744; }
        """

    def render_js(self):
        return """
            // ### Obstacle Sensors Component (render js) ###
            function updateDigitalLights(values) {
                const left = values["digital_2"];
                const right = values["digital_1"];

                document.getElementById("dig2").className =
                    "light " + (left ? "red" : "green");

                document.getElementById("dig1").className =
                    "light " + (right ? "red" : "green");
            }
            """

    def update_js(self):
        return """
            // ### Obstacle Sensors Component (update js) ###
            updateDigitalLights(data);
"""
