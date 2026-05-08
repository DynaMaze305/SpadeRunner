from dashboard.render.DashboardComponent import DashboardComponent

class PlayButtonsComponent(DashboardComponent):
    def __init__(self, buttons):
        self.buttons = buttons

    def render_html(self):
        html = '<div class="play-buttons-grid">'
        for btn in self.buttons:
            html += (
                f'<button onclick="sendPlayCommand('
                f'{{type: \'play\', command: \'{btn["command"]}\', target: \'{btn["target_jid"]}\', value: \'\'}})">'
                f'{btn["text"]}</button>'
            )
        html += "</div>"
        return html

    def render_css(self):
        return """
            /* Grid layout play */
            .play-buttons-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
                gap: 12px;
                width: 100%;
            }

            /* Play buttons */
            .play-buttons-grid button {
                padding: 12px 20px;
                background: #4fc3f7;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-size: 16px;
                transition: background 0.2s ease, transform 0.1s ease;
            }

            .play-buttons-grid button:hover {
                background: #FF0F00;
            }

            /* Pressed effect */
            .play-buttons-grid button:active {
                background: #000000;
                transform: scale(0.95);
            }
        """

    def render_js(self):
        return """
            // ### Play Buttons Component (render js) ###
            function sendPlayCommand(obj) {
                const clicked = event.target;

                ws.send(JSON.stringify(obj));
            }
"""

    def update_js(self):
        return """
"""