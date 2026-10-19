"""Export inert, source-checked lifecycle facets for the stdlib Python 3.4 agent.

Independent native branches use one SERIAL simulation schedule. Stub returns
are synthetic, never evidence of card initialization or physical safe shutdown.
"""


def expected_bundle():
    from DeviceServers.control.elyse_acq.vi_simulation.controlled_stop import CONTROLLED_STOP
    from DeviceServers.control.elyse_acq.vi_simulation.startup_publication import STARTUP_COMMANDS, COMMAND_PUBLICATIONS
    from DeviceServers.control.elyse_acq.vi_simulation.startup_postinit import RESETS, TPG_BRANCHES
    from DeviceServers.control.elyse_acq.vi_simulation.stop_schedule import RUNTIME_LOOPS
    from DeviceServers.control.elyse_acq.vi_simulation.final_cleanup import VARIABLES
    from legacy.xp_acq_agent.elyse_agent.hardware_plan import COUNTERS_STARTED_ON_INIT
    import json

    return json.loads(json.dumps(dict(
        schema_version=1, simulation_only=True,
        source_vi_sha256="6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF",
        startup_commands=STARTUP_COMMANDS,
        command_publications=COMMAND_PUBLICATIONS,
        postinit_resets=RESETS, tpg_branches=TPG_BRANCHES,
        runtime_loops=RUNTIME_LOOPS, cleanup_variables=VARIABLES,
        counters_started=COUNTERS_STARTED_ON_INIT, controlled_stop=CONTROLLED_STOP,
    )))
