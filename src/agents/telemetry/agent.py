# agent.py
import asyncio
import json
import logging
import os
import random
import time

from aiohttp import web
from spade import agent, behaviour
from spade.message import Message

from dashboard_server import Dashboard

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TelemetryAgent")

HTTP_PORT = 8080
NAVIGATOR_JID = os.environ.get("NAVIGATOR_JID", "navigator@prosody")


class TelemetryAgent(agent.Agent):
    ENV_PREFIX = "TELEMETRY"
    def __init__(self, jid, password):
        super().__init__(jid, password)

        self.current = {
            "sensors": {
                "digital": {1: None, 2: None},
                "analog": {0: None, 1: None, 2: None, 3: None, 4: None, 10: None},
            },
            "motion": {
                "speed": None,
                "direction": None,
                "rotation": None,
            },
        }

        self.dashboard = Dashboard()

    # ---------- behaviours ----------

    class FakeTelemetry(behaviour.PeriodicBehaviour):
        async def run(self):
            self.agent.current["sensors"]["digital"][1] = random.randint(0, 1)
            self.agent.current["sensors"]["digital"][2] = random.randint(0, 1)

            for k in self.agent.current["sensors"]["analog"]:
                self.agent.current["sensors"]["analog"][k] = random.random()

            self.agent.current["motion"]["speed"] = random.random()
            self.agent.current["motion"]["direction"] = random.random()
            self.agent.current["motion"]["rotation"] = random.random()

            sample = self.agent._make_sample()
            await self.agent.dashboard.broadcast(sample)
            logger.info(f"[AGENT] Telemetry sample: {sample}")

    class XMPPTelemetryListener(behaviour.CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=5)
            if msg is None:
                return

            body = (msg.body or "").strip()
            logger.info(f"[AGENT] XMPP telemetry message: {body}")

            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return

            self.agent._merge_telemetry(data)
            sample = self.agent._make_sample()
            await self.agent.dashboard.broadcast(sample)

    class XMPPSendMessage(behaviour.OneShotBehaviour):
        def __init__(self, cmd: str, target: str):
            super().__init__()
            self.cmd = cmd
            self.target = target

        async def run(self):
            logger.info(f"[AGENT] handle_command: {self.cmd}")

            msg = Message(to=self.target)
            msg.set_metadata("performative", "request")
            msg.body = f"command {self.cmd}"
            await self.send(msg)
            logger.info(f"[AGENT] Sent XMPP command '{self.cmd}' to {NAVIGATOR_JID}")

    # ---------- helpers ----------

    def _merge_telemetry(self, data):
        for section, values in data.items():
            if section in self.current and isinstance(values, dict):
                self.current[section].update(values)
            else:
                self.current[section] = values

    def _make_sample(self):
        ts = time.time()
        flat = {}

        for k, v in self.current["sensors"]["digital"].items():
            flat[f"digital_{k}"] = v

        for k, v in self.current["sensors"]["analog"].items():
            flat[f"analog_{k}"] = v

        for k, v in self.current["motion"].items():
            flat[f"motion_{k}"] = v

        return {"ts": ts, "values": flat}

    async def handle_command(self, cmd: str, target: str):
        self.add_behaviour(self.XMPPSendMessage(cmd, target))
    # ---------- setup ----------

    async def setup(self):
        logger.info("[AGENT] Starting TelemetryAgent...")

        app = self.dashboard.create_app(self)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", HTTP_PORT)
        await site.start()
        logger.info(f"[AGENT] Dashboard running on http://localhost:{HTTP_PORT}")

        self.add_behaviour(self.FakeTelemetry(period=1))
        self.add_behaviour(self.XMPPTelemetryListener())


async def main():
    jid = os.environ.get("TELEMETRY_JID", "telemetry@prosody")
    password = os.environ.get("TELEMETRY_PASSWORD", "top_secret")

    ag = TelemetryAgent(jid, password)
    await ag.start(auto_register=True)

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await ag.stop()


if __name__ == "__main__":
    asyncio.run(main())
