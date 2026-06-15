from pynput import keyboard
from loguru import logger
import os
import signal

class EmergencyStop:
    def __init__(self):
        self.listener = keyboard.Listener(on_press=self.on_press)

    def start(self):
        logger.info("Emergency Stop active (Press 'ESC' to stop the agent)")
        self.listener.start()

    def on_press(self, key):
        if key == keyboard.Key.esc:
            logger.critical("EMERGENCY STOP TRIGGERED (ESC pressed)")
            # Kill the process
            os.kill(os.getpid(), signal.SIGINT)

    def stop(self):
        self.listener.stop()
