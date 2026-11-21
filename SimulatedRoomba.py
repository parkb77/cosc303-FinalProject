# SimulatedRoomba.py
# Claude Generated File to simulate / test pathfinding.py and GUI.py until Roomb hardware is finished

import time
from pathfinding import DIRS

START = (0, 0)


class SimulatedRoomba:
    def __init__(self, seconds_per_node=0.35, seconds_per_turn=0.6):
        self.seconds_per_node = seconds_per_node
        self.seconds_per_turn = seconds_per_turn
        self.reset()

    # ---- the five things the GUI calls ----------------------------------
    def reset(self):
        self._commands = []
        self._state = "idle"
        self._pos = START
        self._t0 = None

    def upload(self, commands):
        if self._state == "running":
            raise RuntimeError("Robot is running; stop it before uploading.")
        self._commands = list(commands)
        self._state = "ready"

    def run(self):
        if self._state != "ready":
            raise RuntimeError("No route uploaded.")
        if self._pos != START:
            raise RuntimeError("Robot is not on the start cell.")
        self._t0 = time.monotonic()
        self._state = "running"

    def stop(self):
        if self._state == "running":
            self._pos = self._pose_at(time.monotonic() - self._t0)
            self._state = "stopped"

    def get_position(self):
        self._update()
        if self._state == "running":
            return self._pose_at(time.monotonic() - self._t0)
        return self._pos

    def get_state(self):
        self._update()
        return self._state

    # ---- internals ---------------------------------------------------------
    def _total_time(self):
        total = 0.0
        for c in self._commands:
            total += self.seconds_per_turn if c in ("CC", "CW") else int(c) * self.seconds_per_node
        return total

    def _update(self):
        """If the whole route has finished, record that and freeze the position."""
        if self._state == "running":
            t = time.monotonic() - self._t0
            if t >= self._total_time():
                self._pos = self._pose_at(t)
                self._state = "done"

    def _pose_at(self, t):
        """Where is the robot t seconds after Run? Walk through the commands,
        using up time as each one is 'performed'. The robot moves from node
        to node: it is always ON a node."""
        x, y, heading = START[0], START[1], 0
        for c in self._commands:
            if c in ("CC", "CW"):
                if t < self.seconds_per_turn:
                    return (x, y)                       # still turning on this node
                t -= self.seconds_per_turn
                heading = (heading + (1 if c == "CC" else -1)) % 4
            else:
                n = int(c)
                done = int(t / self.seconds_per_node)    # nodes completed so far
                dx, dy = DIRS[heading]
                if done < n:
                    return (x + dx * done, y + dy * done)
                t -= n * self.seconds_per_node
                x, y = x + dx * n, y + dy * n
        return (x, y)                                    # route finished
