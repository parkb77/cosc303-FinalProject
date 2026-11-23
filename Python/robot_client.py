"""Persistent Linux/Pi subprocess connector. Standard library; mock backend only.
A reader thread routes asynchronous completion events by request ID. GUI code
should poll ticket.done or drain client.events on its own GUI thread.
"""
import json
import queue
import subprocess
import threading
from pathlib import Path

TERMINAL = {"completed", "rejected", "failed", "cancelled"}

class MotionError(RuntimeError):
    def __init__(self, response):
        self.response = response
        super().__init__(response.get("error") or response.get("status"))

class Ticket:
    def __init__(self, request_id):
        self.id = request_id
        self._condition = threading.Condition()
        self._terminal = None
        self._exception = None
        self.accepted = None

    @property
    def done(self):
        with self._condition:
            return self._terminal is not None or self._exception is not None

    def _receive(self, response):
        with self._condition:
            if response["status"] == "accepted":
                self.accepted = response
            else:
                self._terminal = response
            self._condition.notify_all()

    def _fail(self, error):
        with self._condition:
            self._exception = error
            self._condition.notify_all()

    def wait(self, timeout=12.0):
        # A caller timeout does NOT imply the physical action stopped. Use STOP.
        with self._condition:
            if not self._condition.wait_for(
                lambda: self._terminal is not None or self._exception is not None,
                timeout=timeout,
            ):
                raise TimeoutError(f"request {self.id} not finished; issue STOP")
            if self._exception:
                raise self._exception
            if self._terminal["status"] != "completed":
                raise MotionError(self._terminal)
            return self._terminal

class RobotClient:
    def __init__(self, executable=None, config=None):
        root = Path(__file__).resolve().parents[1]
        executable = Path(executable or root / "build/motion_api").resolve()
        config = Path(config or root / "config/mock.conf").resolve()
        self.process = subprocess.Popen(
            [str(executable), "--backend", "mock", "--config", str(config)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1,
        )  # stderr inherited: no unread diagnostics pipe.
        self.events = queue.Queue(maxsize=512)  # GUI notifications, not control delivery.
        self._lock = threading.RLock()
        self._pending = {}
        self._last_id = 0
        self._closed = False
        self._error = None
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()

    def _read(self):
        error = RuntimeError("C++ process closed stdout")
        try:
            while True:
                line = self.process.stdout.readline(65537)
                if not line:
                    break
                if len(line) > 65536 or not line.endswith("\n"):
                    raise RuntimeError("oversized or incomplete response")
                response = json.loads(line)
                if (not isinstance(response, dict) or
                    type(response.get("id")) is not int or
                    response.get("status") not in TERMINAL | {"accepted"} or
                    response.get("backend") != "mock"):
                    raise RuntimeError("invalid API response")
                with self._lock:
                    ticket = self._pending.get(response["id"])
                    if ticket is None:
                        raise RuntimeError("unexpected response ID")
                    ticket._receive(response)
                    if response["status"] in TERMINAL:
                        del self._pending[response["id"]]
                try:
                    self.events.put_nowait(response)
                except queue.Full:
                    pass  # Ticket delivery is independent and never dropped.
        except Exception as exc:
            error = RuntimeError(f"API transport failed: {exc}")
            if self.process.poll() is None:
                self.process.terminate()
        finally:
            with self._lock:
                self._error = error
                for ticket in self._pending.values():
                    ticket._fail(error)
                self._pending.clear()

    def _submit(self, body):
        with self._lock:
            if self._closed or self._error or self.process.poll() is not None:
                raise RuntimeError("client closed or subprocess unavailable")
            self._last_id += 1
            ticket = Ticket(self._last_id)
            self._pending[ticket.id] = ticket
            try:
                self.process.stdin.write(f"{ticket.id} {body}\n")
                self.process.stdin.flush()
            except Exception:
                del self._pending[ticket.id]
                raise
            return ticket

    def move(self, units):
        if type(units) is not int or not -20 <= units <= 20:
            raise ValueError("MOVE needs integer units in [-20,20]")
        return self._submit(f"MOVE {units}")

    def turn(self, direction, quarter_turns=1):
        if direction not in {"CW", "CCW"}:
            raise ValueError("direction must be CW or CCW")
        if type(quarter_turns) is not int or not 1 <= quarter_turns <= 4:
            raise ValueError("quarter_turns must be an integer in [1,4]")
        return self._submit(f"TURN {direction} {quarter_turns}")

    def stop(self):
        return self._submit("STOP")

    def get_state(self):
        return self._submit("GET_STATE")

    def clear_fault(self):
        return self._submit("CLEAR_FAULT")

    def mock(self, kind, side, value):
        if kind not in {"WD", "STALL", "RATE"} or side not in {"L", "R"}:
            raise ValueError("invalid mock injection")
        if type(value) is not int or not (1 <= value <= 200 if kind == "RATE"
                                         else value in (0, 1)):
            raise ValueError("invalid mock value")
        return self._submit(f"MOCK {kind} {side} {value}")

    def close(self):
        if self._closed:
            return
        try:
            if self.process.poll() is None and self._error is None:
                self.stop().wait(1.0)
        except (RuntimeError, TimeoutError, OSError):
            pass
        finally:
            with self._lock:
                self._closed = True
                self.process.stdin.close()
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            self._reader.join(timeout=1)
            self.process.stdout.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
