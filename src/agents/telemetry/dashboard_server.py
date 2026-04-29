# dashboard_server.py
import json
import os
from aiohttp import web, WSMsgType


XMPP_DOMAIN = os.environ.get("XMPP_DOMAIN", "prosody")
BUTTONS = [
    {"text": "Say Hello", "target_jid": f"navigator@{XMPP_DOMAIN}", "command": "hello"},
    {"text": "Stop Robot", "target_jid": f"navigator@{XMPP_DOMAIN}", "command": "stop"},
    {"text": "Reset", "target_jid": f"navigator@{XMPP_DOMAIN}", "command": "reset"},
]

class Dashboard:
    def __init__(self):
        self.latest = {"ts": None, "values": {}}
        self.websockets = set()

    # ---------------------------------------------------------
    #  HTML RENDERING FUNCTIONS
    # ---------------------------------------------------------

    def render_styles(self):
        return """
        <style>
            body { background:#111; color:#eee; font-family:Arial; padding:20px; }
            h1 { color:#4fc3f7; }
            .box { background:#222; padding:10px; margin:10px 0; border-radius:8px; }

            /* Digital sensor box */
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

            button {
                padding:10px 20px;
                background:#4fc3f7;
                border:none;
                border-radius:5px;
                cursor:pointer;
                font-size:16px;
            }
            button:hover { background:#81d4fa; }
        </style>
        """

    def render_digital_section(self):
        return """
        <h2>Obstacle Sensors</h2>
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
        """

    def render_analog_graph(self):
        return """
        <h2>Analog Sensors (Live Graph)</h2>
        <canvas id="analogChart" width="600" height="250"></canvas>
        """

    def render_controls(self):
        html = '<h2>Controls</h2><div style="display:flex; gap:10px;">'
        for btn in BUTTONS:
            html += (
                f'<button onclick="sendCommand('
                f'{{command: \'{btn["command"]}\', target: \'{btn["target_jid"]}\'}})">'
                f'{btn["text"]}</button>'
            )
        html += "</div>"
        return html

    def render_scripts(self):
        return """
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script>
            const ws = new WebSocket("ws://" + location.host + "/ws");
            const MAX_POINTS = 900; //15 minutes

            // --- Chart.js setup ---
            const ctx = document.getElementById('analogChart').getContext('2d');
            const analogChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        { label: 'A0', data: [], borderColor: '#ff5252' },
                        { label: 'A1', data: [], borderColor: '#ffb74d' },
                        { label: 'A2', data: [], borderColor: '#fff176' },
                        { label: 'A3', data: [], borderColor: '#81c784' },
                        { label: 'A4', data: [], borderColor: '#64b5f6' },
                        { label: 'A10', data: [], borderColor: '#ba68c8' }
                    ]
                },
                options: {
                    animation: false,
                    responsive: true,
                    scales: {
                        x: {
                            title: {
                                display: true,
                                align: 'center',
                                text: 'Time',
                            },
                        },
                        y: {
                            title: {
                                display: true,
                                align: 'center',
                                text: 'Value',
                            },
                        }
                    }
                }
            });

            function updateDigitalLights(values) {
                const left = values["digital_2"];
                const right = values["digital_1"];

                document.getElementById("dig2").className =
                    "light " + (left ? "red" : "green");

                document.getElementById("dig1").className =
                    "light " + (right ? "red" : "green");
            }

            function updateAnalogGraph(ts, values) {
                analogChart.data.labels.push(ts * 1000);

                analogChart.data.datasets[0].data.push(values["analog_0"]);
                analogChart.data.datasets[1].data.push(values["analog_1"]);
                analogChart.data.datasets[2].data.push(values["analog_2"]);
                analogChart.data.datasets[3].data.push(values["analog_3"]);
                analogChart.data.datasets[4].data.push(values["analog_4"]);
                analogChart.data.datasets[5].data.push(values["analog_10"]);

                if (analogChart.data.labels.length > MAX_POINTS) {
                    analogChart.data.labels.shift();
                    analogChart.data.datasets.forEach(ds => ds.data.shift());
                }

                analogChart.update();
            }

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data || "{}");
                if (!data.ts || !data.values) return;

                document.getElementById("ts").innerText =
                    "Timestamp: " + new Date(data.ts * 1000).toLocaleTimeString();

                updateDigitalLights(data.values);
                updateAnalogGraph(data.ts, data.values);
            };

            function sendCommand(obj) {
                ws.send(JSON.stringify(obj));
            }

        </script>
        """

    def render_page(self):
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Robot Dashboard</title>
            {self.render_styles()}
        </head>
        <body>

            <h1>Robot Telemetry Dashboard</h1>
            <div id="ts">Timestamp: --</div>

            {self.render_digital_section()}
            {self.render_controls()}
            {self.render_analog_graph()}

            {self.render_scripts()}
        </body>
        </html>
        """

    # ---------------------------------------------------------
    #  HTTP HANDLERS
    # ---------------------------------------------------------

    async def _dashboard_page(self, request):
        return web.Response(text=self.render_page(), content_type="text/html")

    async def _ws_handler(self, request):
        agent = request.app["agent"]
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        self.websockets.add(ws)
        print("[DASHBOARD] WebSocket client connected")

        await ws.send_json(self.latest)

        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                data = json.loads(msg.data)
                if "command" in data:
                    await agent.handle_command(data["command"], data.get("target"))


        self.websockets.discard(ws)
        return ws

    async def broadcast(self, sample):
        self.latest = sample
        for ws in list(self.websockets):
            await ws.send_json(sample)

    def create_app(self, agent):
        app = web.Application()
        app["dashboard"] = self
        app["agent"] = agent

        app.router.add_get("/", self._dashboard_page)
        app.router.add_get("/ws", self._ws_handler)

        return app
