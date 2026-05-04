from dashboard.render.DashboardComponent import DashboardComponent

class ControlButtonsComponent(DashboardComponent):
    def __init__(self, buttons):
        self.buttons = buttons

    def render_html(self):
        html = '<div style="display:flex; gap:10px;">'
        for btn in self.buttons:
            html += (
                f'<button onclick="sendCommand('
                f'{{command: \'{btn["command"]}\', target: \'{btn["target_jid"]}\'}})">'
                f'{btn["text"]}</button>'
            )
        html += "</div>"
        return html

    def render_css(self):
        return """
            /* Button box */
            button {
                padding:10px 20px;
                background:#4fc3f7;
                border:none;
                border-radius:5px;
                cursor:pointer;
                font-size:16px;
            }
            button:hover { background:#81d4fa; }
            """

    def render_js(self):
        return """
            // ### Control Buttons Component (render js) ###
            function sendCommand(obj) {
                ws.send(JSON.stringify(obj));
            }
            """