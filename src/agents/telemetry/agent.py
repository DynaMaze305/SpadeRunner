# agent.py
import asyncio
import json
import logging
import random
import time

from aiohttp import web
from spade import agent, behaviour
from spade.message import Message

from common.config import NAVIGATOR_JID
from dashboard.dashboard_server import Dashboard
from agents.telemetry.telemetrystore import TelemetryStore

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TelemetryAgent")

HTTP_PORT = 8080

class TelemetryAgent(agent.Agent):
    ENV_PREFIX = "TELEMETRY"
    def __init__(self, jid, password, test=False):
        super().__init__(jid, password)
        self.test = test
        self.selected_bot = None
        self.dashboard = Dashboard()


    # ---------- behaviours ----------

    class FakeTelemetry(behaviour.PeriodicBehaviour):
        async def run(self):
            # Generate fake sensor values
            data = {"sensors":{"digital":{},"analog":{}}, "motion": {}}
            data["digital"][1] = random.randint(0, 1)
            data["digital"][2] = random.randint(0, 1)

            for k in [0,1,2,3,4,5,10]:
                data["analog"][k] = random.random()

            data["battery"] = random.random() * 100
            data["motion"]["speed"] = random.random()
            data["motion"]["direction"] = random.random()
            data["motion"]["rotation"] = random.random()

            # Build telemetry payload (same as real bots)
            payload = {
                "type": "data",
                "bot": str(self.agent.jid),
                "ts": time.time(),
                "data": data
            }

            # Send to itself so listener handles it
            msg = Message(to=str(self.agent.jid))
            msg.set_metadata("performative", "inform")
            msg.body = json.dumps(payload)

            await self.send(msg)

    class XMPPTelemetryListener(behaviour.CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=1)
            if msg is None:
                return

            body = (msg.body or "").strip()
            logger.info(f"[AGENT] XMPP message: {body}")

            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                logger.warning("[AGENT] Invalid JSON received.")
                return

            msg_type = payload.get("type")

            if msg_type == "register_ok":
                logger.info(f"[AGENT] Registered to bot {payload.get('bot')}")
                return

            if msg_type == "register_exists":
                logger.info(f"[AGENT] Already registered to bot {payload.get('bot')}")
                return

            if msg_type == "data":
                telemetry = payload.get("data")
                if not telemetry:
                    logger.warning("[AGENT] Missing telemetry data.")
                    return
                sample = self.agent._payload_to_samples(payload)
                self.agent._store_sample(sample)
                sample["type"] = "data"
                await self.agent.dashboard.broadcast(sample)
                return

            if msg_type == "error":
                logger.error(f"[AGENT] Error from bot: {payload.get('message')}")
                return

            logger.warning(f"[AGENT] Unknown message type: {msg_type}")

    class XMPPSendMessage(behaviour.OneShotBehaviour):
        def __init__(self, cmd: str, target: str):
            super().__init__()
            self.cmd = cmd
            self.target = target

        async def run(self):
            logger.info(f"[AGENT] handle_command: {self.cmd}")

            msg = Message(to=self.target)
            msg.set_metadata("performative", "request")
            msg.body = f"{self.cmd}"
            await self.send(msg)
            logger.info(f"[AGENT] Sent XMPP message: {msg}")

    # ---------- helpers ----------
    def _payload_to_samples(self, payload: dict) -> dict:
        """
        Convert a raw telemetry payload into SQL rows.
        Returns a list of tuples: (ts, bot, key, value)
        """
        ts = payload["ts"]
        bot = payload["bot"]
        data = payload["data"]

        rows = {}

        # --- Digital sensors ---
        for k, v in data["digital"].items():
            rows[f"digital_{k}"] = v

        # --- Analog sensors ---
        for k, v in data["analog"].items():
            rows[f"analog_{k}"] = v

        # --- Battery ---
        rows["battery"] = data["battery"]

        # --- Motion ---
        # for k, v in data["motion"].items():
        #     rows[f"motion_{k}"] = v

        return {
            "ts": ts,
            "bot": bot,
            "values": rows
        }

    def _store_sample(self, sample: dict):
        self.store.store_sample(sample)

    async def handle_command(self, cmd: str, target: str):
        self.add_behaviour(self.XMPPSendMessage(cmd, target))

    # ---------- setup ----------

    async def setup(self):
        logger.info("[AGENT] Starting TelemetryAgent...")

        self.store = TelemetryStore()

        app = self.dashboard.create_app(self)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", HTTP_PORT)
        await site.start()
        logger.info(f"[AGENT] Dashboard running on http://localhost:{HTTP_PORT}")

        if self.test:
            self.add_behaviour(self.FakeTelemetry(period=1))
        else:
            pass

        self.add_behaviour(self.XMPPTelemetryListener())

async def main():
    jid = "telemetry@prosody"#os.environ.get("TELEMETRY_JID", "telemetry@prosody")
    password = "secret"#os.environ.get("XMPP_PASSWORD", "top_secret")

    ag = TelemetryAgent(jid, password)
    await ag.start(auto_register=True)

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await ag.stop()


if __name__ == "__main__":
    asyncio.run(main())
