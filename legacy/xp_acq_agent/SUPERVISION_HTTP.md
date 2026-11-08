# Retired standalone HTTP prototype

The independent HTTP acquisition prototype on port 8768 is no longer the
application entry point. `supervision_server.py` now forwards to the existing
`main.py --supervision` agent on its original TCP listener.

See [SUPERVISION.md](SUPERVISION.md) for shared simulation state, the Everest
launcher, signed TCP extension, recovery semantics, and software qualification.
