from dashboard.render.DashboardComponent import DashboardComponent
import json

class SliderComponent(DashboardComponent):
    def __init__(self, sliders):
        """
        sliders: list of dicts like:
        [
            {
                "text": "Speed",
                "target_jid": "bot_1",
                "command": "set_speed",
                "min_value": 0,
                "max_value": 100,
                "n_values": 101
            }
        ]
        """
        self.sliders = sliders

    def render_html(self):
        html = '<div class="slider-box">'
        for s in self.sliders:
            html += f"""
            <div class="slider-item">
                <label>{s['text']}: <span id="val_{s['command']}">0</span></label>
                <input type="range"
                       id="slider_{s['command']}"
                       min="{s['min_value']}"
                       max="{s['max_value']}"
                       step="{(s['max_value'] - s['min_value']) / (s['n_values'] - 1)}"
                       value="{s['min_value']}">
            </div>
            """
        html += "</div>"
        return html

    def render_css(self):
        return """
        .slider-box {
            background: #222;
            padding: 15px;
            border-radius: 10px;
            color: white;
            width: 300px;
        }

        .slider-item {
            margin-bottom: 15px;
        }

        .slider-item input[type=range] {
            width: 100%;
        }
        """

    def render_js(self):
        sliders_json = json.dumps(self.sliders)

        return f"""
        const sliderDefinitions = {sliders_json};

        sliderDefinitions.forEach(s => {{
            const slider = document.getElementById("slider_" + s.command);
            const valLabel = document.getElementById("val_" + s.command);

            slider.addEventListener("input", () => {{
                valLabel.innerText = slider.value;
            }});

            slider.addEventListener("change", () => {{
                const payload = {{
                    type: "slider",
                    target: s.target_jid,
                    command: s.command,
                    value: Number(slider.value)
                }};
                ws.send(JSON.stringify(payload));
            }});
        }});
        """

    def update_js(self):
        return ""  # Sliders do not update from telemetry
