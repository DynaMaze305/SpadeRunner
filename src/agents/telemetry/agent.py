# agent.py
import asyncio
import json
import logging
import random
import time

from aiohttp import web
from spade import agent, behaviour
from spade.message import Message

from common.config import *
from dashboard.dashboard_server import Dashboard
from agents.telemetry.telemetrystore import TelemetryStore

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HTTP_PORT = 8080

class TelemetryAgent(agent.Agent):
    ENV_PREFIX = "TELEMETRY"
    def __init__(self, jid, password, test=False):
        super().__init__(jid, password)
        self.test = test
        self.selected_bot = None
        self.dashboard = Dashboard()
        self.last_race_time = {}
        self.last_total_time = {}
        self.current_button = None


    # ---------- behaviours ----------

    class FakeTelemetry(behaviour.PeriodicBehaviour):
        async def run(self):
            # Generate fake sensor values
            data = {"digital":{},"analog":{}, "motion": {}}
            data["digital"][1] = random.randint(0, 1)
            data["digital"][2] = random.randint(0, 1)

            for k in [0,1,2,3,4,5,10]:
                data["analog"][k] = random.random()

            data["battery"] = random.random() * 100
            data["motion"]["left_pwm"] = random.random() * 100
            data["motion"]["left_direction"] = ["stopped","forward","backward","unknown"][random.randint(0,3)]
            data["motion"]["right_pwm"] = random.random() * 100
            data["motion"]["right_direction"] = ["stopped","forward","backward","unknown"][random.randint(0,3)]
            data["motion"]["emergency_stop"] = random.randint(0, 1)

            # Build telemetry payload (same as real bots)
            payload = {
                "type": "data",
                "bot": f"telemetry-test@{COORDINATOR_HOST}",
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
            #logger.info(f"[AGENT] XMPP message: {body}")
            logger.info(f"[AGENT] XMPP message: {msg.sender}")

            if self.agent.current_button is not None:
                if self.agent.current_button == str(msg.sender.bare()):
                    logger.info(f"Agent button {self.agent.current_button} == current {msg.sender.bare()}")
                    logger.info(f"{body}")
                    if body in ["navigation done","navigation failed", "race step done", "penality done"] or body.startswith("Executed command:"):
                        logger.info("navigation impact")
                        sample = {
                            "type": "command_done",
                            "bot":  self.agent.current_button.split('-',1)[1].split('@')[0],
                        }
                        self.agent.current_button = None
                        await self.agent.dashboard.broadcast(sample)
                        return

            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                logger.warning("[AGENT] Invalid Message received.")
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

            if msg_type == "image_path" and self.agent.selected_bot is not None:
                sender = str(msg.sender.bare())
                logger.info(f"[AGENT] Receive image from {sender}")
                if self.agent.selected_bot in sender:
                    sample = {
                        "type": "image_frame",
                        "bot":  payload["bot"].split('-',1)[1].split('@')[0],
                        "ts":   payload["ts"],
                        "values": payload["data"]
                    }
                    await self.agent.dashboard.broadcast(sample)
                else:
                    logger.info(f"[AGENT] Not processing image received.")
                return

            if msg_type == "race_time":
                bot = payload["bot"]
                race_time = payload["data"]["race_time"]

                # Store last race time for this bot
                self.last_race_time[bot] = race_time

                # Broadcast to dashboard
                await self.ws_broadcast({
                    "type": "race_time",
                    "bot": bot,
                    "data": race_time
                })
                return

            if msg_type == "total_time":
                bot = payload["bot"]
                race_time = payload["data"]["total_time"]

                # Store last race time for this bot
                self.last_total_time_time[bot] = race_time

                # Broadcast to dashboard
                await self.ws_broadcast({
                    "type": "total_time",
                    "bot": bot,
                    "data": race_time
                })
                return

            logger.warning(f"[AGENT] Unknown message type: {msg_type}")
            logger.warning(f"[AGENT] {msg}")

    class XMPPSendMessage(behaviour.OneShotBehaviour):
        def __init__(self, cmd: str, target: str, value: str):
            super().__init__()
            self.cmd = cmd
            self.target = target
            self.value = value

        async def run(self):
            logger.info(f"[AGENT] handle_command: {self.cmd}")

            msg = Message(to=self.target)
            msg.set_metadata("performative", "request")
            if self.value == "":
                msg.body = f"{self.cmd}"
            else:
                msg.body = f"{self.cmd} {self.value}"
            await self.send(msg)
            logger.info(f"[AGENT] Sent XMPP message: {msg}")

            if self.target.startswith("calibrator"):
                await asyncio.sleep(60)
                sample = {
                    "type": "command_done",
                    "bot":  self.agent.current_button.split('-',1)[1].split('@')[0],
                }
                self.agent.current_button = None
                await self.agent.dashboard.broadcast(sample)

    # ---------- helpers ----------
    def _payload_to_samples(self, payload: dict) -> dict:
        """
        Convert a raw telemetry payload into a flattened sample
        suitable for both SQL storage and dashboard broadcast.
        """
        ts = payload["ts"]
        bot = payload["bot"].split('-',1)[1].split('@')[0]
        data = payload["data"]

        flat = {}

        # --- Digital sensors ---
        if "digital" in data:
            for k, v in data["digital"].items():
                flat[f"digital_{k}"] = v

        # --- Analog sensors ---
        if "analog" in data:
            for k, v in data["analog"].items():
                flat[f"analog_{k}"] = v

        # --- Battery ---
        if "battery" in data:
            flat["battery"] = data["battery"]

        # --- Motion ---
        if "motion" in data:
            for k, v in data["motion"].items():
                flat[f"motion_{k}"] = v

        return {
            "ts": ts,
            "bot": bot,
            "values": flat
        }

    def _store_sample(self, sample: dict):
        self.store.store_sample(sample)

    async def handle_command(self, cmd: str, target: str, value: str = None):
        if "@" in target:
            self.add_behaviour(self.XMPPSendMessage(cmd, target, value))
        else:
            target += f"-{self.selected_bot}@{COORDINATOR_HOST}"
            self.add_behaviour(self.XMPPSendMessage(cmd, target, value))

    # ---------- setup ----------
    def set_selected_bot(self, bot):
        self.selected_bot = bot

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
