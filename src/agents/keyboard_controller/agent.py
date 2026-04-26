import asyncio
import logging
import os
import signal
import threading
import readchar

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message

from common.config import ROBOT_JID

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

RELEASE_TIMEOUT = 0.05

MOVE_KEYS = {
    readchar.key.UP: 'forward',
    readchar.key.DOWN: 'backward',
    readchar.key.LEFT: 'left',
    readchar.key.RIGHT: 'right',
    readchar.key.SPACE: 'stop',
}

class KeyBoardController(Agent):
    """Sends movement commands to the robot from the keyboard input
    """
    ENV_PREFIX = "KEYBOARD"

    def __init__(self, jid, password):
        super().__init__(jid, password)
        self.recipient_jid = ROBOT_JID

    async def setup(self):
        self.add_behaviour(self.KeyboardBehaviour())

    class KeyboardBehaviour(CyclicBehaviour):

        async def on_start(self):
            # initialisation d'une queue asynchrone
            self._queue = asyncio.Queue()
            # récupère la loop active (get_running_loop pour vraiment chopper celle qui tourne, get_event_loop est déprécié sur python recent)
            self._loop = asyncio.get_running_loop()

            def read_keys():
                # vérifie qu'on a bien un TTY attaché, sinon readchar va bloquer pour toujours sans rien dire
                if not os.isatty(0):
                    logger.error("stdin is not a TTY — run with `docker compose run --rm app` (not `up`) to attach the keyboard")
                    return
                while True:
                    try:
                        key = readchar.readkey()
                    except KeyboardInterrupt:
                        # To ensure CTR+C stop to shows the last logging messages
                        os.kill(os.getpid(), signal.SIGINT)
                        break
                    # si stdin est fermé en cours de route, readkey renvoie '' en boucle, on évite de flooder la queue
                    if key == "":
                        return
                    # https://stackoverflow.com/questions/60113143/how-to-properly-use-asyncio-run-coroutine-threadsafe-function
                    asyncio.run_coroutine_threadsafe(self._queue.put(key), self._loop)

            # lance read_keys dans un Thread interne, safe par rapport à la loop asyncio (readchar est blocant, car attend une touche à read)
            # https://docs.python.org/3/library/threading.html
            # deamon=True : assure l'arrêt du thread si l'agent s'arrête
            threading.Thread(target=read_keys, daemon=True).start()

            logger.info(" -- Use ARROW KEYS to move the robot & SPACE to stop -- ")

        async def run(self):

            key = await self._queue.get()

            command = MOVE_KEYS.get(key)
            # Si une touche non prévue est pressée
            if command is None:
                return

            await self._send(command)

            while True:
                try:
                    next_key = await asyncio.wait_for(self._queue.get(), timeout=RELEASE_TIMEOUT)
                    # la même touche continue a être pressée
                    if next_key == key:
                        continue
                    # une autre touche est pressée
                    else:
                        await self._send('stop')
                        self._queue.put_nowait(next_key)
                        break
                # aucunes touches ne sont plus pressées
                except asyncio.TimeoutError:
                    await self._send('stop')
                    break

        async def _send(self, command: str):
            logger.info(f"Sending command: {command} to robot {self.agent.recipient_jid}")
            msg = Message(to=self.agent.recipient_jid)
            msg.set_metadata("performative", "request")
            msg.set_metadata("source", "keyboard") # keyboard : pour l'override de l'arrêt d'urgence en cas d'obstacle
            msg.body = command
            await self.send(msg)
