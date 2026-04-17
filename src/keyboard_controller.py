import asyncio
import time
import readchar

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class KeyBoardController(Agent):
    """SPADE agent : sends movement commands to the robot via XMPP based on keyboard input
    """

    def __init__(self, jid, password, recipient_jid):
        super().__init__(jid, password)
        self.recipient_jid = recipient_jid

    async def setup(self):
        self.add_behaviour(self.KeyboardBehaviour())

    class KeyboardBehaviour(CyclicBehaviour):

        async def on_start(self):
            logger.info("Use arrow keys to move, SPACE to stop")

        async def run(self):
            loop = asyncio.get_event_loop()
            key = await loop.run_in_executor(None, readchar.readkey)

            command = None

            if key == readchar.key.UP:
                command = "forward"
            elif key == readchar.key.DOWN:
                command = "backward"
            elif key == readchar.key.LEFT:
                command = "left"
            elif key == readchar.key.RIGHT:
                command = "right"
            elif key == readchar.key.ESC:
                await self.agent.stop()
                # TODO : adapt the mechanism to have stop command override current command to ensure my manual emergency safety
                return

            if command:
                logger.info(f"Sending command: {command}")
                msg = Message(to=self.agent.recipient_jid)
                msg.set_metadata("performative", "inform")
                msg.body = command

                await self.send(msg)

                time.sleep(0.2)
                # msg.body = "stop"
                # await self.send(msg)
