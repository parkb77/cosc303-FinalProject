# WebGUI.py

import time
from nicegui import ui, app
from pathfinding import shortest_path, path_to_commands, FREE, BLOCKED, DIRS
from robot_client import RobotClient


ROBOT_EXE = None                    # None = default path in robot_client.py
ROBOT_CONF = None

UNITS_PER_CELL = 10                 # MOVE units per grid cell (max 20)
STEP_TIMEOUT_S = 15.0               # Max wait on one move / turn before STOP


WEB_PORT = 8080

WIDTH, HEIGHT, CELL = 12, 8, 50     # cols, rows, pixels per cell
START = (0, 0)                      # Bottom left start
POLL_S = 0.15                       # How often location is polled

C_FREE, C_BLOCKED, C_PATH = "#ffffff", "#404040", "#BDD7EE"
C_START, C_STOP, C_ROBOT = "#548235", "#C00000", "#1F3864"


class Course:
    def __init__(self):
        try:
            self.robot = RobotClient(ROBOT_EXE, ROBOT_CONF)   
            startup_msg = ("Pick a mode, build a course, set a stop, then press 1. Calculate route.", "info")
        except Exception as err:
            self.robot = None       # page still loads and shows the error
            startup_msg = ("Could not start the robot API (%s): %s" % (ROBOT_EXE or "default path", err), "error")
        self.matrix = [[FREE] * WIDTH for _ in range(HEIGHT)]
        self.stop = None
        self.path = []
        self.commands = []
        self.route_ready = False    # Route calculated
        self.uploaded = False       # Route uploaded
        self.running = False        # Robot is driving
        self.mode = "obstacle"      # state / mode to determine what click does
        self.paint_value = BLOCKED  # paints blocked or erased when holding
        self.return_to_start = True
        self.robot_pos = START
        self.robot_heading = 0      # Index into DIRS, 0 = east
        self.robot_state = "idle"   # idle / ready / running / done / stopped
        self.steps = []             # Commands split into single MOVE / CW / CCW
        self.step_i = 0             # Which step is being done
        self.ticket = None          # Step the robot is working on
        self.deadline = 0.0         # Time limit for that step
        self.calc_ms = None
        self.search_failed = False
        self.message = startup_msg
        self.version = 0            # updates every change, redraws image

    # Helper functions
    def changed(self):
        self.version += 1

    def say(self, text, kind="info"):
        self.message = (text, kind)
        self.changed()

    def cell_from(self, e):
        """Pixel position inside the board -> (x, y) grid cell, or None.
        The board counts y DOWN from the top; our grid counts y UP from the
        bottom (START is bottom-left), so the row is flipped."""
        x = int(e.image_x // CELL)
        y = HEIGHT - 1 - int(e.image_y // CELL)
        return (x, y) if 0 <= x < WIDTH and 0 <= y < HEIGHT else None

    def enabled(self):
        """Which workflow buttons can be pressed right now."""
        at_start = (self.robot_pos == START)
        return {
            "calc":   not self.running,
            "upload": self.route_ready and not self.uploaded and not self.running and at_start,
            "run":    self.uploaded and not self.running,
            "stop":   self.running,
            "reset":  (not self.running) and not at_start,
        }

    def next_step(self):
        en = self.enabled()
        if not self.route_ready and en["calc"]:
            return "calc"
        for key in ("upload", "run", "reset"):
            if en[key]:
                return key
        return None

    # Mouse functions
    def mouse(self, e):
        cell = self.cell_from(e)
        if cell is None:
            return
        if self.running:
            if e.type == "mousedown":
                self.say("The course is locked while the robot is running.", "error")
            return
        x, y = cell
        if e.type == "mousedown":
            if self.mode == "stop":
                self.set_stop(cell)
            else:       # Can drag click to place obstacles
                self.paint_value = BLOCKED if self.matrix[y][x] == FREE else FREE
                self.paint(cell)
        elif e.type == "mousemove" and self.mode == "obstacle" and (e.buttons & 1):
            self.paint(cell)

    def paint(self, cell):
        x, y = cell
        if cell == START or cell == self.stop:
            return
        if self.matrix[y][x] != self.paint_value:
            self.matrix[y][x] = self.paint_value
            self.invalidate_route()

    def set_stop(self, cell):
        x, y = cell
        if cell == START or self.matrix[y][x] == BLOCKED:
            self.say("The stop can't be on the start cell or on an obstacle.", "error")
            return
        self.stop = cell
        self.invalidate_route()
        self.say("Stop set to (%d, %d). Now press 1. Calculate route." % cell, "ok")

    def invalidate_route(self):
        """The course changed, so any calculated / uploaded route is out of date."""
        self.path, self.commands = [], []
        self.route_ready = self.uploaded = False
        if self.robot_state == "ready":
            self.robot_state = "idle"
        self.calc_ms, self.search_failed = None, False
        self.changed()

    # Calc -> Upload -> Run (or stop)
    def calculate(self):
        if self.stop is None:
            self.say("Set a stop first: click 'Set stop', then click a cell.", "error")
            return
        started = time.perf_counter()                        # start timer
        path = shortest_path(self.matrix, START, self.stop)  # output data to pathfinding
        if path is None or isinstance(path, str):
            ms = (time.perf_counter() - started) * 1000
            self.invalidate_route()
            self.calc_ms, self.search_failed = ms, True
            self.say("No path found: the stop is walled off.", "error")
            return
        full = path + path[::-1][1:] if self.return_to_start else path   # Return -> reversed path. Ensures end direction is east 
        commands, heading = path_to_commands(full)
        if self.return_to_start:
            turn = (0 - heading) % 4          # 0 = east
            commands.extend({0: [], 1: ["CC"], 2: ["CC", "CC"], 3: ["CW"]}[turn])
        ms = (time.perf_counter() - started) * 1000          # Stop timer
        self.path, self.commands = path, commands
        self.route_ready, self.uploaded = True, False
        self.calc_ms, self.search_failed = ms, False
        self.say("Route found. Commands: %s.  Next: 2. Upload route." % ", ".join(commands), "ok")

    def upload(self):
        """Nothing is sent to the robot yet. Commands are split into single steps:
        "3" -> MOVE MOVE MOVE, "CC" -> CCW, "CW" -> CW."""
        if self.robot is None:
            self.say("Robot API not running. Check the paths, then restart.", "error")
            return
        steps = []
        for c in self.commands:
            if c == "CC":
                steps.append("CCW")
            elif c == "CW":
                steps.append("CW")
            elif c.isdigit():
                steps.extend(["MOVE"] * int(c))
            else:
                self.say("Upload failed: unknown command %r" % c, "error")
                return
        self.steps = steps
        self.uploaded = True
        self.robot_state = "ready"
        self.say("Route uploaded: %d commands (%d robot steps). Next: 3. Run route."
                 % (len(self.commands), len(steps)), "ok")

    def send_step(self):
        """Send the current step to the robot, keep its ticket."""
        step = self.steps[self.step_i]
        if step == "MOVE":
            self.ticket = self.robot.move(UNITS_PER_CELL)
        else:
            self.ticket = self.robot.turn(step, 1)
        self.deadline = time.monotonic() + STEP_TIMEOUT_S

    def run(self):
        if self.robot is None:
            self.say("Robot API not running. Check the paths, then restart.", "error")
            return
        if not self.steps or self.robot_pos != START:
            self.say("Route not uploaded, or robot is not on the start cell.", "error")
            return
        self.step_i = 0
        self.robot_heading = 0          # Routes assume facing east at START
        try:
            self.send_step()
        except Exception as err:
            self.say("Could not start: %s" % err, "error")
            return
        self.running = True
        self.robot_state = "running"
        self.say("Running. The dark blue circle is the robot. Press Stop route to halt it.", "info")

    def stop_robot(self):
        if not self.running or self.robot is None:
            return
        try:
            self.robot.stop()           # ticket not needed
        except Exception as err:
            self.ticket = None
            self.robot_state = "stopped"
            self.finish_run("STOP FAILED: %s. Pick up the robot or power it off." % err, "error")
            return
        self.ticket = None              # Drop the step in progress
        self.robot_state = "stopped"
        self.finish_run("Stopped at (%d, %d). Move the robot back to the start, then press "
                        "'Robot is back at start' and upload again." % self.robot_pos, "error")

    def reset_robot(self):
        if self.robot is None:
            self.say("Robot API not running. Check the paths, then restart.", "error")
            return
        try:
            self.robot.clear_fault()    # ticket not needed
        except Exception as err:
            self.say("Reset failed: %s" % err, "error")
            return
        self.robot_pos, self.robot_heading = START, 0
        self.robot_state, self.uploaded, self.steps = "idle", False, []
        self.say("Robot reset to the start cell.", "info")

    def clear(self):
        if self.running:
            return
        self.matrix = [[FREE] * WIDTH for _ in range(HEIGHT)]
        self.stop = None
        self.invalidate_route()
        self.say("Cleared: obstacles, stop, and route removed.", "info")

    def poll(self):
        """Check the step in progress. When it finishes, update where the robot is
        and send the next one."""
        if not self.running or self.robot is None or self.ticket is None:
            return
        try:
            if not self.ticket.done:
                if time.monotonic() > self.deadline:    # Took too long
                    self.robot.stop()
                    raise TimeoutError("command timed out; STOP sent")
                return
            self.ticket.wait(0)         # Raises if the step was rejected / failed
            step = self.steps[self.step_i]
            if step == "MOVE":          # Update position / heading from finished step
                dx, dy = DIRS[self.robot_heading]
                self.robot_pos = (self.robot_pos[0] + dx, self.robot_pos[1] + dy)
            else:
                self.robot_heading = (self.robot_heading + (1 if step == "CCW" else -1)) % 4
            self.step_i += 1
            self.changed()
            if self.step_i >= len(self.steps):
                self.ticket = None
                self.robot_state = "done"
                self.finish_run("Run complete. Robot is at (%d, %d)." % self.robot_pos, "ok")
            else:
                self.send_step()
        except Exception as err:
            self.ticket = None
            self.robot_state = "stopped"
            self.finish_run("Robot stopped at (%d, %d): %s" % (self.robot_pos[0], self.robot_pos[1], err), "error")

    def finish_run(self, message, kind):
        self.running = False
        self.uploaded = False          # Route used, upload again to rerun
        self.say(message, kind)

    # Image drawing
    def svg(self):
        """The whole board as SVG shapes"""
        on_path = set(self.path)
        out = []
        for y in range(HEIGHT):
            for x in range(WIDTH):
                px, py = x * CELL, (HEIGHT - 1 - y) * CELL
                label = ""
                if (x, y) == START:
                    color, label = C_START, "START"
                elif (x, y) == self.stop:
                    color, label = C_STOP, "STOP"
                elif self.matrix[y][x] == BLOCKED:
                    color = C_BLOCKED
                elif (x, y) in on_path:
                    color = C_PATH
                else:
                    color = C_FREE
                out.append(f'<rect x="{px}" y="{py}" width="{CELL}" height="{CELL}" '
                           f'fill="{color}" stroke="#bfbfbf"/>')
                if label:
                    out.append(f'<text x="{px + CELL / 2}" y="{py + 11}" fill="white" font-size="9" '
                               f'font-weight="bold" text-anchor="middle">{label}</text>')
        rx, ry = self.robot_pos
        out.append(f'<circle cx="{rx * CELL + CELL / 2}" cy="{(HEIGHT - 1 - ry) * CELL + CELL / 2}" '
                   f'r="{CELL * 0.24}" fill="{C_ROBOT}" stroke="white" stroke-width="2"/>')
        return "".join(out)

    def route_text(self):
        if self.search_failed:
            return "Route: none   |   Search took %.3f ms" % self.calc_ms
        if self.route_ready:
            moves = (len(self.path) - 1) * (2 if self.return_to_start else 1)
            return "Route: %d moves%s   |   Calculated in %.3f ms" % (
                moves, " (out and back)" if self.return_to_start else "", self.calc_ms)
        return "Route: not calculated"

    def robot_text(self):
        if self.robot is None:
            return "Robot: not connected"
        return "Robot: %s at (%d, %d)" % (self.robot_state, self.robot_pos[0], self.robot_pos[1])


course = Course()

MODE_TEXT = {
    "obstacle": ("MODE: PLACE OBSTACLES  -  click or drag on the grid (click again to remove it)",
                 "bg-gray-800 text-white"),
    "stop":     ("MODE: SET STOP  -  click the cell where the Roomba should stop",
                 "bg-red-700 text-white"),
}
KIND_CLASSES = {"info": "bg-gray-200 text-black", "ok": "bg-green-100 text-green-900",
                "error": "bg-red-100 text-red-800"}


def index():

    ui.label("Roomba route planner").classes("text-2xl font-bold")

    def act(fn, *args):                 # Redraw page after.
        fn(*args)
        refresh()

    def set_mode(mode):
        course.mode = mode
        course.say("Switched to: " + ("Place obstacles" if mode == "obstacle" else "Set stop"))
        refresh()

    def set_return(e):
        if e.value != course.return_to_start:
            course.return_to_start = e.value
            course.invalidate_route()
            refresh()

    # Map editing tools
    with ui.row().classes("items-center"):
        mode_btns = {
            "obstacle": ui.button("Place obstacles", on_click=lambda: set_mode("obstacle")),
            "stop": ui.button("Set stop", on_click=lambda: set_mode("stop")),
        }
        clear_btn = ui.button("Clear", on_click=lambda: act(course.clear)).props("outline")

    # "Button Press" Workflow
    with ui.row().classes("items-center"):
        flow = {
            "calc": ui.button("1. Calculate route", on_click=lambda: act(course.calculate)),
            "upload": ui.button("2. Upload route", on_click=lambda: act(course.upload)),
            "run": ui.button("3. Run route", on_click=lambda: act(course.run)),
            "stop": ui.button("Stop route", on_click=lambda: act(course.stop_robot)),
            "reset": ui.button("Robot is back at start", on_click=lambda: act(course.reset_robot)),
        }
        ret_box = ui.checkbox("Return to start after stop", value=course.return_to_start,
                              on_change=set_return)

    banner = ui.label().classes("w-full p-2 font-bold")

    board = ui.interactive_image(
        size=(WIDTH * CELL, HEIGHT * CELL), on_mouse=lambda e: act(course.mouse, e),
        events=["mousedown", "mousemove"], sanitize=False
    ).style(f"width: {WIDTH * CELL}px; height: {HEIGHT * CELL}px;")

    with ui.row().classes("w-full justify-between"):
        route_label = ui.label().classes("font-bold")
        robot_label = ui.label().classes("font-bold text-blue-900")
    status = ui.label().classes("w-full p-2 rounded")

    seen = {"version": -1}

    def refresh():
        """Update everything on this page from `course`."""
        seen["version"] = course.version
        board.set_content(course.svg())
        text, classes = MODE_TEXT[course.mode]
        banner.set_text(text)
        banner.classes(replace="w-full p-2 font-bold " + classes)
        for key, b in mode_btns.items():
            b.props("color=amber text-color=black" if key == course.mode else "color=grey-4 text-color=black")
            b.set_enabled(not course.running)
        clear_btn.set_enabled(not course.running)
        en, nxt = course.enabled(), course.next_step()
        for key, b in flow.items():
            color = "negative" if (key == "stop" and en["stop"]) else ("positive" if key == nxt else "primary")
            b.props(f"color={color}")
            b.set_enabled(en[key])
        ret_box.set_enabled(not course.running)
        if ret_box.value != course.return_to_start:
            ret_box.value = course.return_to_start
        route_label.set_text(course.route_text())
        robot_label.set_text(course.robot_text())
        text, kind = course.message
        status.set_text(text)
        status.classes(replace="w-full p-2 rounded " + KIND_CLASSES[kind])

    def tick():                          # Ping location
        course.poll()
        if seen["version"] != course.version:
            refresh()

    ui.timer(POLL_S, tick)
    refresh()


def shutdown():                          # Send STOP and close robot API on exit
    if course.robot is not None:
        course.robot.close()


app.on_shutdown(shutdown)

if __name__ in {"__main__", "__mp_main__"}:

    # host 0.0.0.0 = reachable from any device on the Roomba's network
    ui.run(index, host="0.0.0.0", port=WEB_PORT, title="Roomba Pathfinding", show=False, reload=False)
