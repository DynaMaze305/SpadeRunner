import logging
import os
import shutil

from aiohttp import web
from spade import agent, behaviour
from spade.message import Message

from common.config import NAVIGATOR_JID


logger = logging.getLogger(__name__)


LOGGER_STATE_DIR = "logger_state"
LATEST_IMAGE_NAME = "latest_path.jpg"
HTTP_PORT = 8080


# CORS middleware so the Grafana panel (served on :3000) can fetch from :8080.
@web.middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS":
        response = web.Response()
    else:
        response = await handler(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


# Subscriber/bridge agent. Receives "image <path>" XMPP pushes from the navigator,
# copies the file to a known location for HTTP consumption, and exposes a small
# HTTP server (port 8080) that Grafana uses for the live image display and for
# triggering a new navigation via the start button.
class LoggerAgent(agent.Agent):
    ENV_PREFIX = "LOGGER"

    class LogBehaviour(behaviour.CyclicBehaviour):

        async def run(self):
            msg = await self.receive(timeout=15)
            if msg is None:
                return

            body = (msg.body or "").strip()
            if not body.startswith("image "):
                logger.warning(f"[LOGGER] unexpected message: {body!r}")
                return

            src_path = body[len("image "):].strip()
            try:
                self._copy_to_latest(src_path)
                logger.info(f"[LOGGER] copied {src_path} -> {LATEST_IMAGE_NAME}")
            except (FileNotFoundError, OSError) as e:
                logger.error(f"[LOGGER] could not copy {src_path}: {e}")

        @staticmethod
        def _copy_to_latest(src_path: str) -> None:
            os.makedirs(LOGGER_STATE_DIR, exist_ok=True)
            dst = os.path.join(LOGGER_STATE_DIR, LATEST_IMAGE_NAME)
            tmp = dst + ".tmp"
            shutil.copy(src_path, tmp)
            os.replace(tmp, dst)

    class TriggerNavigation(behaviour.OneShotBehaviour):
        async def run(self):
            msg = Message(to=NAVIGATOR_JID)
            msg.set_metadata("performative", "request")
            msg.body = "request path"
            await self.send(msg)
            logger.info(f"[LOGGER] sent 'request path' -> {NAVIGATOR_JID}")

    async def setup(self) -> None:
        os.makedirs(LOGGER_STATE_DIR, exist_ok=True)
        self.add_behaviour(self.LogBehaviour())
        await self._start_http_server()
        logger.info(f"[LOGGER] ready (HTTP on :{HTTP_PORT})")

    async def _start_http_server(self) -> None:
        app = web.Application(middlewares=[cors_middleware])
        app.router.add_get("/", self._serve_index)
        app.router.add_get("/favicon.ico", lambda r: web.Response(status=204))
        app.router.add_get(f"/{LATEST_IMAGE_NAME}", self._serve_image)
        app.router.add_post("/start", self._handle_start)
        app.router.add_route("OPTIONS", "/{tail:.*}", lambda r: web.Response())

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", HTTP_PORT)
        await site.start()

        # Keep references so the runner isn't garbage-collected.
        self._http_runner = runner
        self._http_site = site

    async def _serve_index(self, request: web.Request) -> web.Response:
        # Friendly landing page so opening http://localhost:8080/ in a browser
        # shows the live path image. Grafana still uses /latest_path.jpg directly.
        body = (
            "<!doctype html><html><head><title>SpadeRunner Logger</title>"
            "<style>html,body{margin:0;height:100%;background:#000;color:#ddd;"
            "font-family:sans-serif}body{display:flex;flex-direction:column;"
            "align-items:center;justify-content:center;gap:8px}"
            "img{max-width:96vw;max-height:90vh;object-fit:contain}"
            ".bar{display:flex;gap:8px;align-items:center}"
            "button{font-size:18px;padding:8px 24px;cursor:pointer;background:#3b82f6;"
            "color:#fff;border:0;border-radius:6px}</style></head><body>"
            "<img id=\"img\" src=\"/latest_path.jpg\" onerror=\"this.style.display='none'\">"
            "<div class=\"bar\">"
            "<button onclick=\"fetch('/start',{method:'POST'})\">Start navigation</button>"
            "<span id=\"ts\">—</span></div>"
            "<script>setInterval(function(){var i=document.getElementById('img');"
            "i.style.display='';i.src='/latest_path.jpg?t='+Date.now();"
            "document.getElementById('ts').textContent=new Date().toLocaleTimeString();"
            "},250);</script></body></html>"
        )
        return web.Response(text=body, content_type="text/html")

    async def _serve_image(self, request: web.Request) -> web.Response:
        path = os.path.join(LOGGER_STATE_DIR, LATEST_IMAGE_NAME)
        if not os.path.exists(path):
            return web.Response(status=404, text="no image yet")
        # Cache-Control: no-store so the browser never serves a stale image.
        return web.FileResponse(
            path,
            headers={"Cache-Control": "no-store"},
        )

    async def _handle_start(self, request: web.Request) -> web.Response:
        self.add_behaviour(self.TriggerNavigation())
        return web.json_response({"status": "triggered"})
