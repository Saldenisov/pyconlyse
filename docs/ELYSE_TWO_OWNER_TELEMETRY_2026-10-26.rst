Two local orchestrators, one telemetry Device Server
==================================================

Acquisition (10.20.30.10) and SuperVision (10.20.30.2) remain independent card
owners. Neither host relays the other's hardware data. Everest receives both
sources and projects the existing 27-bank view. Starting or restarting one
host does not erase the other host's live session or source age. All displayed
data remain non-atomic across cards, hosts and publications.

Optional configuration and compatibility
---------------------------------------

``DS_AcqTelemetry.federation_config_file`` defaults to an empty string. With
that default, existing source filters, keys, receiver and command transport
are unchanged. Do not enable federation in a live deployment until both owner
publishers are configured and their cold connection is qualified. The existing
Acquisition VI bridge can still contain SuperVision PSP fields; that fact does
not grant it authority to overwrite the SuperVision owner in federated mode.

The new local configuration has the following structure; values are key-file
paths, never inline credentials::

    {
      "schema_version": 1,
      "owners": {
        "acquisition": {
          "host": "10.20.30.10", "port": 8772,
          "read_key_file": "acquisition.read.key",
          "command_key_file": "acquisition.command.key",
          "commands_enabled": false
        },
        "supervision": {
          "host": "10.20.30.2", "port": 8772,
          "read_key_file": "supervision.read.key",
          "command_key_file": "supervision.command.key",
          "commands_enabled": false
        }
      }
    }

Read/telemetry keys must differ between owners. Every enabled command key must
also differ from every active read/command key. The Device Server's existing
global ``commands_enabled`` switch remains required. Peer IP addresses restrict
network ingress but do not authenticate ownership. Authentication uses the
key bound to the signed frame's declared owner.

Wire contract and authority
---------------------------

The existing signed relay request/ACK envelope carries a new
``ELYSE_OWNER_SNAPSHOT`` packet. ``federation_wire.owner_frame`` and
``validate_owner_frame`` run on Python 3.4 without driver imports. Each record
has its own captured ``source_age_seconds``. The relay body's age represents
queue/delivery age only, so publishers must not add source age twice.

Acquisition owns the five native input banks, seven output-command banks and
EPS/DPS software memory. SuperVision owns ``C12NI1409``. Unqualified remaining
banks stay null with explicit errors. Foreign bank records are rejected even
when their value is unavailable. Fixed LabVIEW type descriptors are retained.

``C12NI1409`` is a String in the pinned schema. This implementation carries an
opaque string of at most 4096 characters, not a fabricated pixel array or a
claim that a native camera has been exercised.

An optional separate ``video_frame`` field transports raw NI1409 U8 pixels as
strict base64 row-major bytes. Decoded payload is bounded to 512 KiB and the
whole owner frame to 900 KiB, below the existing 1-MiB relay limit. Width times
height must equal the decoded byte count. Capture-session UUID, software grab
sequence, observation UTC and source age are explicit; no JPEG conversion,
rescaling, legacy Vision processing or physical frame timestamp is invented.
Only the native SuperVision owner may publish it. ``video_json`` exposes the
bounded pixels separately, while the 27-bank view contains video metadata only.
A repeated capture cannot become fresh merely because it is repeated in a new
status frame. Camera-process restarts use a new capture session; old captures
cannot overwrite its successor. Missing/stale images return ``frame=null``.
The image fields are independently validated by the actual Python 3.4 codec;
driver execution and physical image correspondence remain live-test obligations.

``C1011NI6602`` is composed only from two authenticated 16-value counter-memory
parts. Both must be current and explicitly report selector -1 with
``pending_selector=False``. The result is 16 Acquisition values, 16 SuperVision
values and selector -1. Its metadata retains both component boots, source
sequences and ages, and explicitly denies atomicity and hardware acknowledgment.
Missing, stale or pending parts leave the whole legacy bank unavailable.

Relay FIFO and source-sequence state are scoped to each owner. One owner cannot
retire the other owner's boot. A new boot carrying unavailable or already-stale
data is recorded as a candidate but cannot retire or replace the healthy active
generation. Its first current owned data promotes it. Old generations cannot
return after promotion. Retries do not refresh the original receipt timestamp.
The receiver keeps bounded replay state in RAM; a receiver restart clears live
state and requires new authenticated incoming data rather than replaying the
database as fresh telemetry.

Control and archival
--------------------

``ExecuteCommand`` continues to mean Acquisition. ``ExecuteOwnerCommand`` adds
an exact ``{"owner": ..., "request": ...}`` envelope around the existing named
command protocol. ``orchestrators_json`` exposes separate runtime views. Each
request retains the target owner's boot/revision and uses that owner's separate
command credential. Unknown or VI bridge modes cannot authorize hardware
commands. SuperVision is restricted to ``counter_timing.set`` even if an invalid
runtime advertises machine-stage capabilities. Its current-owner memory is
reported as READY, without inventing six Acquisition input banks or calling it
independent physical measurement.

Ingress is durably spooled before RAM acceptance when the existing archive is
configured. Archive IDs include the owner, so identical relay/message IDs from
different owners cannot collide. Raw signed frame bodies retain both counter
component memories. Owner frames archive only their actual owned-bank subset;
they do not invent an atomic merged row. Numeric composite-counter history is
not synthesized into the legacy C1011 bank table by this change; reconstructing
that merged history requires the archived component stream and its source ages.

No XP server, VI, NI resource, live Device Server or archive was accessed or
restarted during these software-only changes.
