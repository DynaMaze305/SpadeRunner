from dashboard.render.DashboardComponent import DashboardComponent

class ControlButtonsComponent(DashboardComponent):
    def __init__(self, buttons):
        self.buttons = buttons

    def render_html(self):
        html = '<div class="control-buttons-grid">'
        for btn in self.buttons:
            html += (
                f'<button onclick="sendCommand('
                f'{{type: \'button\', command: \'{btn["command"]}\', target: \'{btn["target_jid"]}\', value: \'\'}})">'
                f'{btn["text"]}</button>'
            )
        html += "</div>"
        return html

    def render_css(self):
        return """
            /* Grid layout */
            .control-buttons-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
                gap: 12px;
                width: 100%;
            }

            /* Buttons */
            .control-buttons-grid button {
                padding: 12px 20px;
                background: #4fc3f7;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-size: 16px;
                transition: background 0.2s ease, transform 0.1s ease;
            }

            .control-buttons-grid button:hover {
                background: #FF0F00;
            }

            /* Pressed effect */
            .control-buttons-grid button:active {
                background: #000000;
                transform: scale(0.95);
            }
            /* Busy (disabled) state */
            .control-buttons-grid button:disabled {
                background: #999999 !important;
                color: #ffffff;
                cursor: not-allowed;
                transform: none;
                opacity: 0.7;
            }

            /* Busy button (only the one clicked) */
            .control-buttons-grid button.busy {
                background: #ff9800 !important;
                color: #fff;
                transform: scale(0.97);
            }
        """

    def render_js(self):
        return """
            // ### Control Buttons Component (render js) ###

            let isBusy = false;

            function sendCommand(obj) {
                if (isBusy) {
                    console.warn("Command blocked: previous command still running");
                    return;
                }

                isBusy = true;

                // Mark the clicked button as busy
                const clicked = event.target;
                clicked.classList.add("busy");

                ws.send(JSON.stringify(obj));

                // Disable all buttons
                document.querySelectorAll(".control-buttons-grid button")
                    .forEach(btn => btn.disabled = true);
            }

            function commandFinished() {
                isBusy = false;

                // Re-enable all buttons
                document.querySelectorAll(".control-buttons-grid button")
                    .forEach(btn => {
                        btn.disabled = false;
                        btn.classList.remove("busy");
                    });
            }

"""

    def update_js(self):
        return """
            if (msg.type === "command_done") {
                commandFinished();
                return;
            }
"""