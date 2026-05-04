from dashboard.render.DashboardComponent import DashboardComponent

class MotorComponent(DashboardComponent):
    def __init__(self, motor_name: str, pwm_key: str, dir_key: str, emergency_key: str = "motion_emergency_stop"):
        """
        motor_name: Display name ("Left Motor", "Right Motor")
        pwm_key: key in telemetry ("motion_left_pwm")
        dir_key: key in telemetry ("motion_left_direction")
        emergency_key: key in telemetry ("motion_emergency_stop")
        """
        self.motor_name = motor_name
        self.pwm_key = pwm_key
        self.dir_key = dir_key
        self.emergency_key = emergency_key

    def render_html(self):
        return f"""
        <div class="motor-box">
            <h3>{self.motor_name}</h3>

            <div class="motor-info">
                <span id="{self.pwm_key}_value" class="motor-speed">0</span>
                <span id="{self.dir_key}_value" class="motor-direction">stopped</span>
            </div>

            <div class="motor-bar">
                <div id="{self.pwm_key}_bar" class="motor-bar-fill"></div>
            </div>
        </div>
        """

    def render_css(self):
        return """
        .motor-box {
            width: -moz-available;
            padding: 10px;
            margin: 10px;
            background: #222;
            border-radius: 8px;
            color: white;
            text-align: center;
            display: inline-block;
        }

        .motor-info {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 18px;
        }

        .motor-speed {
            font-size: 28px;
            font-weight: bold;
        }

        .motor-direction {
            font-size: 16px;
            opacity: 0.8;
        }

        .motor-bar {
            width: 100%;
            height: 20px;
            background: #444;
            border-radius: 10px;
            overflow: hidden;
            position: relative;
        }

        .motor-bar-fill {
            height: 100%;
            width: 0%;
            background: #4caf50;
            transition: width 0.2s linear, margin-left 0.2s linear, background 0.2s linear;
        }
        """

    def render_js(self):
        return f"""
            // ### Motor Component (render js) ###
            function update_{self.pwm_key}(values) {{
                const pwm = values["{self.pwm_key}"] ?? 0;
                const dir = values["{self.dir_key}"] ?? "stopped";
                const emergency = values["{self.emergency_key}"] ?? false;

                // Limit number to 2 digits
                const pwm_display = Math.round(pwm).toString().slice(0, 4);

                // Update numeric display
                document.getElementById("{self.pwm_key}_value").innerText = pwm_display;

                // Update direction text
                const dirElem = document.getElementById("{self.dir_key}_value");
                dirElem.innerText = dir;

                // Normalize PWM to -100..100
                let pct = Math.min(100, Math.max(0, (pwm / 255) * 100));

                // Bar element
                const bar = document.getElementById("{self.pwm_key}_bar");

                // Emergency stop → everything red
                if (emergency) {{
                    bar.style.background = "#ff1744";
                    dirElem.style.color = "#ff1744";
                }} else {{
                    bar.style.background = "#4caf50";
                    dirElem.style.color = "white";
                }}

                // Fill from center
                if (dir === "forward") {{
                    bar.style.marginLeft = (50 - pct/2) + "%";
                    bar.style.width = (pct/2) + "%";
                }}
                else if (dir === "backward") {{
                    bar.style.marginLeft = "50%";
                    bar.style.width = (pct/2) + "%";
                }}
                else {{
                    // stopped
                    bar.style.marginLeft = "50%";
                    bar.style.width = "0%";
                }}
            }}
        """

    def update_js(self):
        return f"""
            // ### Motor Component (update js) ###
            update_{self.pwm_key}(data)
"""