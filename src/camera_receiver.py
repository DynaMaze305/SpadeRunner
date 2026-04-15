import base64
import aiofiles
import asyncio
import os
import datetime
from spade import agent, behaviour
from spade.message import Message

# Set up logging to track program execution
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ReceiverAgent(agent.Agent):
    class RequestPhotoBehaviour(behaviour.OneShotBehaviour):

        async def run(self):
            msg = Message(to="camera_agent@isc-coordinator.lan")
            msg.set_metadata("performative", "request")
            msg.body = "Requesting photo"

            # sending the Photo request
            await self.send(msg)

            logger.info(f"Request for photo sent at {datetime.datetime.now()}")

            msg = await self.receive(timeout=10)
            if msg:
                logger.info(f"Received photo at {datetime.datetime.now()}")

                # Decodes base64 into raw bytes
                img_data = base64.b64decode(msg.body)

                # Create directory if it doesn't exist
                photos_dir = os.path.join(os.getcwd(), "received_photos")
                os.makedirs(photos_dir, exist_ok=True)

                # Generate filename with timestamp
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"photo_{timestamp}.jpg"
                filepath = os.path.join(photos_dir, filename)

                # Save the received image
                async with aiofiles.open(filepath, "wb") as img_file:
                    await img_file.write(img_data)

                logger.info(f"Photo saved as '{filepath}'.")

    class ReceivePhotoBehaviour(behaviour.CyclicBehaviour):

        async def run(self):
            msg = Message(to="camera_agent@isc-coordinator.lan")
            msg.set_metadata("performative", "request")
            msg.body = "Requesting photo"
            await self.send(msg)

            now = datetime.datetime.now()

            logger.info(f"Request for photo sent at {now}")

            msg = await self.receive(timeout=9999)
            if msg:
                new_now = datetime.datetime.now()
                logger.info(f"Time to get the picture: {new_now - now}")

                # Decodes base64 into raw bytes
                img_data = base64.b64decode(msg.body)

                # Create directory if it doesn't exist
                photos_dir = os.path.join(os.getcwd(), "received_photos")
                os.makedirs(photos_dir, exist_ok=True)

                # Generate filename with timestamp
                timestamp = new_now.strftime("%Y%m%d_%H%M%S")
                filename = f"photo_{timestamp}.jpg"
                filepath = os.path.join(photos_dir, filename)

                # Save the received image
                async with aiofiles.open(filepath, "wb") as img_file:
                    await img_file.write(img_data)

                print(f"Photo saved as '{filepath}'.")

    async def setup(self):
        print(f"{self.jid} is ready.")
        self.add_behaviour(self.RequestPhotoBehaviour())
        # self.add_behaviour(self.ReceivePhotoBehaviour())

async def main():
    xmpp_server = os.getenv("XMPP_SERVER", "localhost")
    xmpp_username = os.getenv("CAMERA_USERNAME", "receiver_agent")
    xmpp_password = os.getenv("CAMERA_PASSWORD", "top_secret")

    receiver = ReceiverAgent(f"{xmpp_username}@{xmpp_server}", xmpp_password)

    await receiver.start(auto_register=True)

    if not receiver.is_alive():
        print("Receiver agent couldn't connect. Check Prosody configuration.")
        await receiver.stop()
        return

    print("Receiver agent connected successfully. Running...")

    try:
        while receiver.is_alive():
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down agent...")
    finally:
        # Clean up: stop the agent
        await receiver.stop()


if __name__ == "__main__":
    asyncio.run(main())
