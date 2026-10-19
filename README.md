# COSC 303 - C++ vacuum API and Python connector


This is an early contribution toward the
C++ interface and Python integration milestones. Hardware capabilities are
unverified; see `docs/feasibility.md` before promising route-following.

## Files

- `milestones-CH.txt`: standalone individual 40-point planning rubric.
- `challenge06-CH-submission.txt`: single-file Canvas submission draft with the
  complete rubric appended, reported time log, reflection, and evidence fields.
- `cpp/include/robot_api.hpp`: C++ interface and mock declaration.
- `cpp/src/`: C++ mock backend and request/response executable.
- `python/connector.py`: persistent subprocess connector and small demo.
- `docs/protocol.md`: IPC contract, units, errors, and extension limitations.
- `docs/feasibility.md`: hardware research notes and experiment plan.
- `tests/test_api.py`: actual executable/connector integration tests.
- `docs/verification.txt`: captured preparation-environment build/test/demo log.

## Build and demonstrate

Requires GNU Make, a C++11-capable compiler, and Python 3.7+ on Linux/Pi OS.
No Python third-party packages, MQTT library, or network access is needed for
the mock. The selector-based connector is intended for Linux pipes.

```sh
make
make test
make demo
```

Or interact manually (one request per line):
```sh
./build/vacuum_api --backend mock
```
Then type:
```text
1 CAPABILITIES
2 CONNECT
3 DRIVE 1
4 ROTATE 1.5707963267948966
5 DRIVE 0.5
6 POSE
7 STOP
8 QUIT
```
Expected final mock pose before quit: x=1m, y=0.5m, heading=pi/2 radians.
Each reply labels `backend` and `pose_source` as `mock`. Disconnected pose and
unavailable bumper are null. Hardware mode is deliberately rejected.

The test suite checks the idealized route, connection lifecycle, units/heading,
input failures without mutation, explicit mock capabilities, protocol recovery,
rejection of nonexistent hardware mode, nonfinite input, and timeout/protocol
failure cleanup. Test passed in linux not on pi.

## Proposed system design

Partner's Python UI/grid/planner -> your Python connector -> one persistent
C++ process -> selected backend. Initially the backend is the mock. A native
C++ hardware backend is future work, contingent on verified capabilities.
Keep C++ sources in `cpp/`, interpreted code in `python/`, and protocol docs in
`docs/`. Pipes carry IPC; there is no separate "socket source" or socket build
step. `make` builds C++ before `make demo` launches the Python caller.

The mock only implements idealized pose updates. It is not the partner's maze
simulator; it has no walls, collision detection, pathfinding, timing, drift, or
physical execution. Python retains algorithm/decision ownership; C++ implements
supported operations. No start-cleaning command substitutes for drive/rotate.




## What remains

Real j8 connection/authentication, supported motion commands, live pose/bumper
feedback, telemetry calibration, physical route following, Pi deployment, and
partner simulator integration are not implemented. Hardware stop/preemption
and command-completion handling need separate work: closing a child process
cannot guarantee a real robot stopped. See the dependency gate in the rubric.
