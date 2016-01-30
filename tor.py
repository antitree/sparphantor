from stem import Signal
from stem.control import Controller
import config
import time

RSTTIMEOUT = 5  # seconds to wait before allowing Tor to reset

class tor:
    def __init__(self, auth="", control_port=9051):
        self.set_last_reset()
        self.control_port = control_port        # Tor Control port
        self.auth = auth                        # cookie path

    def set_last_reset(self):
        print("Time check state reset")
        self.last_reset = time.time()

    def newnym(self):
        ''' Function to generate a new circuit by issuing the
        NewNym control command'''

        ## TODO decide which circuit to cycle so not to interrupt
        if time.time() - self.last_reset >= RSTTIMEOUT: 
            self.set_last_reset()
            with Controller.from_port(port = self.control_port) as controller:
                controller.authenticate()
                controller.signal(Signal.NEWNYM)
            self.set_last_reset()
