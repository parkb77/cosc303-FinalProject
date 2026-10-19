# COSC 303 Challenge 06 starter - C++ vacuum API and Python connector

Prepared for [Your name] (CH), with [Partner name(s)].

**This is an explicit mock prototype. It contains no j8 Wi-Fi client and does
not move a physical vacuum.** It is a compilable early contribution toward the
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
failure cleanup. This session's prepared version passed nine tests in a Linux
container. You must run it on your actual lab/Pi system; no target build or
hardware test is claimed.

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

## Before lab / submission

1. Replace author/partner and deadline placeholders. Review all generated code,
   explain it, and make any individual implementation changes needed. Follow
   your course policy for assistance and document your actual contribution.
2. Run `make test` and `make demo` yourself. Record your system, actual results,
   and personal review/development time. Do not claim assistant runtime as hours.
3. Add these files to your team's existing repository. Do not replace a teammate's
   Makefile, README, or source tree wholesale: merge this starter deliberately.
4. Commit and push; then fill the repository/commit links in both text files.
   This package has NOT been committed to a shared repository.
5. Discuss the plan and current working code with a TA. Record actual feedback
   and lab attendance. An outside-lab time total does not prove lab participation.
6. Upload only `challenge06-CH-submission.txt` to Canvas after updating it. It
   already includes the complete milestone rubric. If you revise the rubric,
   update the appended copy too and retain the original lab version in Git.

Suggested commands from your shared repository root, after merging files:
```sh
git status
git switch -c ch06-ch
make test
make demo
git add milestones-CH.txt challenge06-CH-submission.txt Makefile .gitignore README.md cpp python tests docs
git diff --cached
git commit -m "Add CH milestones and C++ mock vacuum API with Python bridge"
git push -u origin ch06-ch
git rev-parse HEAD
```
Use your team's actual branch workflow; branch and commit names above are
suggestions. Do not stage binaries, credentials, or unrelated teammate changes.
For a commit link use your repository provider's actual commit URL. Branch
creation/push require the existing team repository and your access; none was
attempted here because no repository URL was provided.

## What remains

Real j8 connection/authentication, supported motion commands, live pose/bumper
feedback, telemetry calibration, physical route following, Pi deployment, and
partner simulator integration are not implemented. Hardware stop/preemption
and command-completion handling need separate work: closing a child process
cannot guarantee a real robot stopped. See the dependency gate in the rubric.
