from dashboard.render.DashboardComponent import DashboardComponent
from dashboard.render.PageComponent import row

class LedColorComponent(DashboardComponent):
    def __init__(self, led_id):
        self.led_id = led_id

    def render_html(self):
        return f"""
        <div class="led-box">
            <h2>LED: {self.led_id}</h2>

            <div class="led-preview" id="led-preview-{self.led_id}"></div>

            <div class="led-slider">
                <label>R: <span id="led-r-val-{self.led_id}">0</span></label>
                <input type="range" id="led-r-{self.led_id}" min="0" max="255" step="1" value="0">
            </div>

            <div class="led-slider">
                <label>G: <span id="led-g-val-{self.led_id}">0</span></label>
                <input type="range" id="led-g-{self.led_id}" min="0" max="255" step="1" value="0">
            </div>

            <div class="led-slider">
                <label>B: <span id="led-b-val-{self.led_id}">0</span></label>
                <input type="range" id="led-b-{self.led_id}" min="0" max="255" step="1" value="0">
            </div>

            <button id="led-send-btn-{self.led_id}" class="led-send-btn">Send LED Color</button>
            <button id="led-off-btn-{self.led_id}" class="led-send-btn">Turn down LEDr</button>
        </div>
        """

    def render_css(self):
        return """
        .led-box {
            background: #222;
            padding: 15px;
            border-radius: 10px;
            color: white;
            width: 260px;
            text-align: center;
        }

        .led-preview {
            width: 80px;
            height: 80px;
            border-radius: 50%;
            margin: 10px auto;
            background: rgb(0,0,0);
            border: 2px solid #555;
        }

        .led-slider {
            margin: 10px 0;
            text-align: left;
        }

        .led-slider input[type=range] {
            width: 100%;
        }

        .led-send-btn {
            margin-top: 15px;
            padding: 8px 12px;
            background: #444;
            color: white;
            border: 1px solid #666;
            border-radius: 6px;
            cursor: pointer;
        }

        .led-send-btn:hover {
            background: #666;
        }
        """

    def render_js(self):
        led = self.led_id

        return f"""
        function updateLedPreview_{led}() {{
            const r = Number(document.getElementById("led-r-{led}").value);
            const g = Number(document.getElementById("led-g-{led}").value);
            const b = Number(document.getElementById("led-b-{led}").value);

            document.getElementById("led-r-val-{led}").innerText = r;
            document.getElementById("led-g-val-{led}").innerText = g;
            document.getElementById("led-b-val-{led}").innerText = b;

            const preview = document.getElementById("led-preview-{led}");
            preview.style.background = `rgb(${{r}}, ${{g}}, ${{b}})`;
        }}

        document.addEventListener("DOMContentLoaded", () => {{
            ["r", "g", "b"].forEach(ch => {{
                document.getElementById(`led-${{ch}}-{led}`).addEventListener("input", updateLedPreview_{led});
            }});

            document.getElementById("led-send-btn-{led}").addEventListener("click", () => {{
                const r = Number(document.getElementById("led-r-{led}").value);
                const g = Number(document.getElementById("led-g-{led}").value);
                const b = Number(document.getElementById("led-b-{led}").value);

                const payload = {{
                    type: "play",
                    target: "camera",
                    command: "leds {led} " + r  + " " + g + " " + b,
                    value: "",
                }};

                ws.send(JSON.stringify(payload));
            }});

            document.getElementById("led-off-btn-{led}").addEventListener("click", () => {{
                const payload = {{
                    type: "play",
                    target: "camera",
                    command: "leds {led} 0 0 0",
                    value: "",
                }};

                ws.send(JSON.stringify(payload));
            }});
            updateLedPreview_{led}();
        }});
        """

class Alphabot2Leds(DashboardComponent):
    def __init__(self):
        self.led0 = LedColorComponent(0)
        self.led1 = LedColorComponent(1)
        self.led2 = LedColorComponent(2)
        self.led3 = LedColorComponent(3)

    def render_html(self):
        return row(
            self.led0.render_html(),
            self.led1.render_html(),
            self.led2.render_html(),
            self.led3.render_html(),
        )

    def render_css(self):
        return self.led0.render_css()

    def render_js(self):
        return (
            self.led0.render_js()
            + self.led1.render_js()
            + self.led2.render_js()
            + self.led3.render_js()
        )