from dashboard.render.DashboardComponent import DashboardComponent

class ControlButtonsComponent(DashboardComponent):
    def __init__(self, buttons):
        self.buttons = buttons

    def render_html(self):
        html = '<h2>Controls</h2><div style="display:flex; gap:10px;">'
        for btn in self.buttons:
            exclusive = "true" if btn.get("exclusive") else "false"
            html += (
                f'<button class="ctrl-btn" data-text="{btn["text"]}" '
                f'data-exclusive="{exclusive}" '
                f'onclick="sendCommand(this, '
                f'{{command: \'{btn["command"]}\', target: \'{btn["target_jid"]}\'}})">'
                f'{btn["text"]}</button>'
            )
        html += "</div>"
        return html

    def render_css(self):
        return """
            /* Button box */
            button.ctrl-btn {
                padding:10px 20px;
                background:#4fc3f7;
                border:none;
                border-radius:5px;
                cursor:pointer;
                font-size:16px;
                transition: background 0.2s;
            }
            button.ctrl-btn:hover:not(:disabled) { background:#81d4fa; }
            button.ctrl-btn:disabled {
                background:#cfd8dc !important;
                color:#78909c;
                cursor:not-allowed;
            }
            button.ctrl-btn.busy {
                background:#ff9800 !important;
                color:white;
                cursor:wait;
                animation: ctrlPulse 1s ease-in-out infinite;
            }
            @keyframes ctrlPulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.6; }
            }
            """

    def render_js(self):
        return """
            // Send a command via WS, optimistically lock all exclusive buttons
            // and mark the clicked one as the running task. Backend will send a
            // "ready" WS message when the work is actually done.
            function sendCommand(button, obj) {
                if (button.disabled) return;
                ws.send(JSON.stringify(obj));
                if (button.dataset.exclusive === "true") {
                    lockExclusiveButtons(button);
                }
            }
            function lockExclusiveButtons(activeButton) {
                document.querySelectorAll("button.ctrl-btn").forEach(btn => {
                    if (btn.dataset.exclusive === "true") {
                        btn.disabled = true;
                        if (btn === activeButton) {
                            btn.classList.add("busy");
                            btn.textContent = "Running: " + btn.dataset.text + "...";
                        }
                    }
                });
            }
            function unlockExclusiveButtons() {
                document.querySelectorAll("button.ctrl-btn").forEach(btn => {
                    btn.disabled = false;
                    btn.classList.remove("busy");
                    btn.textContent = btn.dataset.text;
                });
            }
            """