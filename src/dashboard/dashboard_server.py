# dashboard_server.py
import json
import os
from aiohttp import web, WSMsgType
from common.config import *

from dashboard.render.PageComponent import PageComponent
from dashboard.render.AnalogGraphComponent import AnalogGraphComponent
from dashboard.render.DigitalGraphComponent import DigitalGraphComponent
from dashboard.render.BatteryGaugeComponent import BatteryGaugeComponent
from dashboard.render.ControlButtonsComponent import ControlButtonsComponent
from dashboard.render.ObstaclesComponent import ObstacleSensorsComponent
from dashboard.render.MotorComponent import MotorComponent
from dashboard.render.SelectBotComponent import SelectedBotComponent


XMPP_DOMAIN = os.environ.get("XMPP_DOMAIN", "prosody")
BUTTONS = [
    # target_jid full jid will be managed by the agent put only the first part
    # However if you want to put the full JID don't forget the @
    {"text": "Start", "target_jid": "navigator", "command": "request path"},
    {"text": "Register", "target_jid": "sensors", "command": "register"},
    {"text": "Calibrate ratio", "target_jid": "calibrator", "command": "calibrate ratio"},
    {"text": "Calibrate rotation", "target_jid": "calibrator", "command": "calibrate rotation"},
    {"text": "Calibrate distance", "target_jid": "calibrator", "command": "calibrate distance"},
    {"text": "Start Timer (mock)", "target_jid": TIMEKEEPER_JID, "command": "hello"},
]
DIGITAL_GRAPH = [
    {"label": "Left", "data_label": "digital_2"},
    {"label": "Right", "data_label": "digital_1"}
]
SELECT_BOT = [
    {"label": "Bot 1", "bot_id": "alphabot21-agent"},
    {"label": "Bot 2", "bot_id": "alphabot22-agent"},
    {"label": "Bot 3", "bot_id": "alphabot23-agent"},
    {"label": "Bot 4", "bot_id": "alphabot24-agent"},
    {"label": "TEST", "bot_id": f"test"},
]


class Dashboard:
    def __init__(self):
        self.latest = {"ts": None, "values": {}}
        self.websockets = set()

    # ---------------------------------------------------------
    #  HTML RENDERING FUNCTIONS
    # ---------------------------------------------------------
    def render_page(self):
        motor_left = MotorComponent("Left Moto", "motion_left_pwm", "motion_left_direction")
        motor_right = MotorComponent("Right Moto", "motion_right_pwm", "motion_right_direction")
        buttons = ControlButtonsComponent(BUTTONS)
        digitals = DigitalGraphComponent(DIGITAL_GRAPH)
        components = [
            PageComponent(),
            SelectedBotComponent(SELECT_BOT),
            ObstacleSensorsComponent(),
            BatteryGaugeComponent(),
            motor_left,
            motor_right,
            buttons,
            AnalogGraphComponent(),
            digitals

        ]

        css = "\n".join(c.render_css() for c in components)         # The css style of the component
        js_script = "\n".join(c.render_js() for c in components)    # The script of the component including the update function
        js_update = "\n".join(c.update_js() for c in components)    # The call to the update function

        html_blocks = (
            row(
                SelectedBotComponent(SELECT_BOT).render_html(),
                BatteryGaugeComponent().render_html(),
            )
            + row(
                motor_left.render_html(),
                ObstacleSensorsComponent().render_html(),
                motor_right.render_html(),
            )
            + buttons.render_html()
            + row(
                AnalogGraphComponent().render_html(),
                digitals.render_html()
            )
        )
        return f"""<html>
<head>
<style>{css}</style>
</head>
<body>

<h1>Robot Dashboard</h1>
<div id="ts">Timestamp: --</div>

{html_blocks}

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns"></script>

<script>
            const ws = new WebSocket("ws://" + location.host + "/ws");



{js_script}

ws.onmessage = (event) => {{
    let msg;

    try {{
        msg = JSON.parse(event.data);
    }} catch (e) {{
        console.warn("Invalid JSON from server:", event.data);
        return;
    }}

    switch (msg.type) {{

        case "register_ok":
            console.log("Registered to bot:", msg.bot);
            break;

        case "register_exists":
            console.log("Already registered:", msg.bot);
            break;

        case "error":
            console.error("Bot error:", msg.message);
            break;

        case "data":
            const ts = msg.ts;
            const data = msg.values;
            // console.log(data)

            document.getElementById("ts").innerText = "Timestamp: " + new Date(ts * 1000).toLocaleTimeString();

            {js_update}
            break;

        default:
            console.warn("Unknown message type:", msg.type);
    }}
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

    async def _get_analog_data(self, request):
        agent = request.app["agent"]
        bot = agent.selected_bot
        data = agent.store.query_analog(bot)
        return web.json_response(data)

    async def _get_digital_data(self, request):
        agent = request.app["agent"]
        bot = agent.selected_bot
        data = agent.store.query_digital(bot)
        return web.json_response(data)

    async def _get_bots(self, request):
        agent = request.app["agent"]
        bots = agent.store.list_bots()
        return web.json_response({"bots": bots})

    async def _set_selected_bot(self, request):
        agent = request.app["agent"]
        data = await request.json()
        bot = data.get("bot")
        agent.set_selected_bot(bot)
        return web.json_response({"ok": True})

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
        app.router.add_get("/api/analog", self._get_analog_data)
        app.router.add_get("/api/digital", self._get_digital_data)
        app.router.add_get("/api/bots", self._get_bots)
        app.router.add_post("/api/select_bot", self._set_selected_bot)

        return app

# ---------------------------------------------------------
#  HTML RENDERS HELPER
# ---------------------------------------------------------
def row(*components_html):
    return (
        '<div style="display:flex; gap:20px; align-items:flex-start;">'
        + "".join(f'<div style="flex:1;">{html}</div>' for html in components_html)
        + "</div>"
    )

