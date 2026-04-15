import os
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from alphabot_controller import AlphabotController
from camera_receiver import ReceiverAgent

async def run_alphabot_controller():
    xmpp_jid = os.getenv("XMPP_JID")
    xmpp_password = os.getenv("XMPP_PASSWORD")
    robot_recipient = os.getenv("ROBOT_RECIPIENT", "alpha-pi-zero-agent@prosody")

    instructions_str = os.getenv("ROBOT_INSTRUCTIONS", "forward")
    instructions = [instr.strip() for instr in instructions_str.split(",")]

    logger.info(f"Starting AlphabotController with JID: {xmpp_jid}")

    alphabot_controller = AlphabotController(jid=xmpp_jid, password=xmpp_password)
    await alphabot_controller.start(auto_register=True)

    send_instructions_behaviour = alphabot_controller.SendInstructionsBehaviour(robot_recipient, instructions)
    alphabot_controller.add_behaviour(send_instructions_behaviour)

    return alphabot_controller

async def run_camera_receiver():
    xmpp_jid = os.getenv("XMPP_JID")
    xmpp_password = os.getenv("XMPP_PASSWORD")
    
    logger.info(f"Starting CameraReceiver with JID: {xmpp_jid}")
    
    receiver = ReceiverAgent(xmpp_jid, xmpp_password)
    await receiver.start(auto_register=True)
    
    if not receiver.is_alive():
        logger.error("Camera receiver agent couldn't connect.")
        await receiver.stop()
        return None
    
    logger.info("Camera receiver agent started successfully.")
    return receiver

async def main():
    os.makedirs("received_photos", exist_ok=True)
    
    # alphabot_controller = await run_alphabot_controller()
    camera_receiver = await run_camera_receiver()

    if not camera_receiver:
        logger.error("Failed to start camera receiver.")
        return
    
    try:
        logger.info("Both agents running. Press Ctrl+C to stop.")
        
        # while any(behavior.is_running for behavior in alphabot_controller.behaviours):
        #     await asyncio.sleep(1)
        #
        # logger.info("Alphabot controller has completed all instructions.")
        
        # Keep the camera receiver running until explicitly stopped
        while camera_receiver.is_alive():
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt. Shutting down...")
    finally:
        # Stop both agents
        tasks = [
            # asyncio.create_task(alphabot_controller.stop()),
            asyncio.create_task(camera_receiver.stop())
        ]
        await asyncio.gather(*tasks)
        logger.info("All agents stopped.")

if __name__ == "__main__":
    asyncio.run(main()) 