# dashboard_server.py
import json
import os
from aiohttp import web, WSMsgType
from common.config import NAVIGATOR_JID

from dashboard.render.PageComponent import PageComponent
from dashboard.render.AnalogGraphComponent import AnalogGraphComponent
from dashboard.render.BatteryGaugeComponent import BatteryGaugeComponent
from dashboard.render.ControlButtonsComponent import ControlButtonsComponent
from dashboard.render.ObstaclesComponent import ObstacleSensorsComponent


XMPP_DOMAIN = os.environ.get("XMPP_DOMAIN", "prosody")
BUTTONS = [
    {"text": "Say Hello", "target_jid": f"navigator@{XMPP_DOMAIN}", "command": "hello"},
    {"text": "Stop Robot", "target_jid": f"navigator@{XMPP_DOMAIN}", "command": "stop"},
    {"text": "Reset", "target_jid": f"navigator@{XMPP_DOMAIN}", "command": "reset"},
    {"text": "Start", "target_jid": f"{NAVIGATOR_JID}", "command": "request path"},
]

class Dashboard:
    def __init__(self):
        self.latest = {"ts": None, "values": {}}
        self.websockets = set()

    # ---------------------------------------------------------
    #  HTML RENDERING FUNCTIONS
    # ---------------------------------------------------------
    def render_page(self):
        components = [
            PageComponent(),
            ObstacleSensorsComponent(),
            BatteryGaugeComponent(),
            ControlButtonsComponent(BUTTONS),
            AnalogGraphComponent(),
        ]

        css = "\n".join(c.render_css() for c in components)
        html_blocks = "\n".join(c.render_html() for c in components)
        js_init = "\n".join(c.render_js() for c in components)
        js_update = "\n".join(c.update_js() for c in components)
        return f"""<html>
<head>
<style>{css}</style>
</head>
<body>

<h1>Robot Dashboard</h1>
<div id="ts">Timestamp: --</div>

{html_blocks}

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
            const ws = new WebSocket("ws://" + location.host + "/ws");
{js_init}

ws.onmessage = (event) => {{
                const data = JSON.parse(event.data || "{{}}");
                if (!data.ts || !data.values) return;

                document.getElementById("ts").innerText =
                    "Timestamp: " + new Date(data.ts * 1000).toLocaleTimeString();
{js_update}
}};
</script>

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
