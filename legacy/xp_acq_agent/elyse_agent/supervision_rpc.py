"""Signed named intents inside the existing length-prefixed agent protocol.

One agent, one runtime, one listener. No HTTP server or hardware driver.
"""
import re

from .supervision_runtime import Rejected
from .saved_xnode import replay_saved_xnode
from .saved_timing import replay_saved_timing
from .saved_ni6220 import replay_saved_ni6220_read
from .saved_initializer import replay_saved_initializer
from .saved_cleanup import replay_saved_cleanup
from .saved_requests import replay_saved_requests
from .saved_dispatch import replay_saved_dispatch
from .saved_psp_reads import replay_saved_psp_reads
from .saved_sup_reads import replay_saved_sup_reads
from .saved_stop import replay_saved_stop
from .saved_numeric import replay_payload as replay_saved_numeric
from .saved_card_replay import replay_saved_card_init
from .saved_sup_replay import replay_saved_sup_helpers
from .saved_acq_event_33620 import replay_saved_acq_event_33620
from .saved_sup_frequency import replay_saved_sup_frequency
from .saved_acq_event_22879 import replay_saved_acq_event_22879
from .saved_sup_gain import replay_saved_sup_gain
from .saved_acq_event_26012 import replay_saved_acq_event_26012
from .saved_sup_position_t2 import replay_saved_sup_position_t2
from .saved_acq_event_23449 import replay_saved_acq_event_23449
from .saved_sup_position_t3 import replay_saved_sup_position_t3
from .saved_acq_event_34531 import replay_saved_acq_event_34531
from .saved_sup_event_30817 import replay_saved_sup_event_30817
from .saved_acq_event_42457 import replay_saved_acq_event_42457
from .saved_sup_event_47072 import replay_saved_sup_event_47072
from .saved_acq_event_40079 import replay_saved_acq_event_40079
from .saved_sup_event_53656 import replay_saved_sup_event_53656
from .saved_acq_event_35942 import replay_saved_acq_event_35942
from .saved_sup_event_56943 import replay_saved_sup_event_56943
from .saved_acq_event_23143 import replay_saved_acq_event_23143
from .saved_sup_event_23770 import replay_saved_sup_event_23770
from .saved_acq_event_17899 import replay_saved_acq_event_17899
from .saved_sup_event_53772 import replay_saved_sup_event_53772
from .saved_acq_event_37991 import replay_saved_acq_event_37991
from .saved_sup_event_23880 import replay_saved_sup_event_23880
from .saved_acq_event_38732 import replay_saved_acq_event_38732
from .saved_sup_event_26490 import replay_saved_sup_event_26490
from .saved_acq_event_23113 import replay_saved_acq_event_23113
from .saved_sup_event_5847 import replay_saved_sup_event_5847
from .saved_acq_event_8896 import replay_saved_acq_event_8896
from .saved_sup_event_38707 import replay_saved_sup_event_38707
from .saved_acq_event_48846 import replay_saved_acq_event_48846
from .saved_sup_event_33463 import replay_saved_sup_event_33463
from .saved_acq_event_31552 import replay_saved_acq_event_31552
from .saved_sup_event_18780 import replay_saved_sup_event_18780
from .saved_acq_event_43634 import replay_saved_acq_event_43634
from .saved_sup_event_53716 import replay_saved_sup_event_53716
from .saved_acq_event_34191 import replay_saved_acq_event_34191
from .saved_sup_event_38030 import replay_saved_sup_event_38030
from .saved_acq_event_45123 import replay_saved_acq_event_45123
from .saved_sup_event_65050 import replay_saved_sup_event_65050
from .supervision_wire import MAX_BYTES, RequestGuard, json_bytes, response_mac


class SupervisionEndpoint(object):
    def __init__(self, runtime, key):
        self.runtime = runtime
        self.guard = RequestGuard(key)

    def _reply(self, status, value, method, path, nonce):
        body = dict(schema_version=1, execution_allowed=False, hardware_writes=False,
                    physical_status="NOT_EXECUTED", **value)
        raw = json_bytes(body)
        if len(raw) > MAX_BYTES:
            raise ValueError("Supervision response exceeds 65536 bytes")
        return dict(status=status, body=body,
                    signature=response_mac(self.guard.key, "RPC/" + method, path, nonce, status, raw))

    def dispatch(self, params):
        if type(params) is not dict or set(params) != {"method", "path", "payload", "timestamp", "nonce", "signature"}:
            raise ValueError("Exact signed supervision envelope required")
        method, path, nonce = params["method"], params["path"], params["nonce"]
        if method not in ("GET", "POST") or not isinstance(path, str) or not 1 <= len(path) <= 256:
            raise ValueError("Invalid supervision method/path")
        if any(not isinstance(params[name], str) for name in ("timestamp", "nonce", "signature")):
            raise ValueError("Authentication fields must be strings")
        if method == "GET" and params["payload"] is not None:
            raise ValueError("Read-only supervision request has no payload")
        raw = b"" if method == "GET" else json_bytes(params["payload"])
        if len(raw) > MAX_BYTES:
            raise ValueError("Supervision body exceeds 65536 bytes")
        try:
            self.guard.verify("RPC/" + method, path, params["timestamp"], nonce, params["signature"], raw)
        except ValueError:
            return self._reply(401, dict(error="ACQ authentication rejected", accepted=False), method, path, nonce)
        try:
            if method == "GET" and path == "/v1/state":
                result = self.runtime.read_state()
            elif method == "GET" and path == "/v1/outputs":
                result = self.runtime.outputs.snapshot()
            elif method == "GET" and path == "/v1/setpoints":
                result = self.runtime.read_setpoints()
            elif method == "GET" and path == "/v1/lifecycle":
                result = self.runtime.read_lifecycle()
            elif method == "GET" and path == "/v1/observation":
                result = self.runtime.read_observation()
            elif method == "GET" and re.match(r"^/v1/(intents|trace)/[A-Za-z0-9_-]{1,128}\Z", path):
                unused, version, resource, intent_id = path.split("/")
                function = self.runtime.read_intent if resource == "intents" else self.runtime.trace
                result = function(intent_id)
            elif method == "POST" and path == "/v1/replay/saved-xnode":
                result = replay_saved_xnode(params["payload"])
            elif method == "POST" and path == "/v1/replay/saved-timing":
                result = replay_saved_timing(params["payload"])
            elif method == "POST" and path == "/v1/replay/ni6220-means":
                result = replay_saved_ni6220_read(params["payload"])
            elif method == "POST" and path == "/v1/replay/initializer-frame":
                result = replay_saved_initializer(params["payload"])
            elif method == "POST" and path == "/v1/replay/cleanup-frame":
                result = replay_saved_cleanup(params["payload"])
            elif method == "POST" and path == "/v1/replay/request-facet":
                result = replay_saved_requests(params["payload"])
            elif method == "POST" and path == "/v1/replay/dispatch-facet":
                result = replay_saved_dispatch(params["payload"])
            elif method == "POST" and path == "/v1/replay/psp-read-frame":
                result = replay_saved_psp_reads(params["payload"])
            elif method == "POST" and path == "/v1/replay/supervision-read-slice":
                result = replay_saved_sup_reads(params["payload"])
            elif method == "POST" and path == "/v1/replay/stop-trace":
                result = replay_saved_stop(params["payload"])
            elif method == "POST" and path == "/v1/replay/numeric-conversion":
                result = replay_saved_numeric(params["payload"])
            elif method == "POST" and path == "/v1/replay/card-initializer":
                result = replay_saved_card_init(params["payload"])
            elif method == "POST" and path == "/v1/replay/supervision-helper":
                result = replay_saved_sup_helpers(params["payload"])
            elif method == "POST" and path == "/v1/replay/acquisition-control-event":
                result = replay_saved_acq_event_33620(params["payload"])
            elif method == "POST" and path == "/v1/replay/supervision-frequency-event":
                result = replay_saved_sup_frequency(params["payload"])
            elif method == "POST" and path == "/v1/replay/acquisition-event-22879":
                result = replay_saved_acq_event_22879(params["payload"])
            elif method == "POST" and path == "/v1/replay/supervision-gain-event":
                result = replay_saved_sup_gain(params["payload"])
            elif method == "POST" and path == "/v1/replay/acquisition-event-45123":
                result = replay_saved_acq_event_45123(params["payload"])
            elif method == "POST" and path == "/v1/replay/supervision-event-65050":
                result = replay_saved_sup_event_65050(params["payload"])
            elif method == "POST" and path == "/v1/replay/acquisition-event-34191":
                result = replay_saved_acq_event_34191(params["payload"])
            elif method == "POST" and path == "/v1/replay/supervision-event-38030":
                result = replay_saved_sup_event_38030(params["payload"])
            elif method == "POST" and path == "/v1/replay/acquisition-event-43634":
                result = replay_saved_acq_event_43634(params["payload"])
            elif method == "POST" and path == "/v1/replay/supervision-event-53716":
                result = replay_saved_sup_event_53716(params["payload"])
            elif method == "POST" and path == "/v1/replay/acquisition-event-31552":
                result = replay_saved_acq_event_31552(params["payload"])
            elif method == "POST" and path == "/v1/replay/supervision-event-18780":
                result = replay_saved_sup_event_18780(params["payload"])
            elif method == "POST" and path == "/v1/replay/acquisition-event-48846":
                result = replay_saved_acq_event_48846(params["payload"])
            elif method == "POST" and path == "/v1/replay/supervision-event-33463":
                result = replay_saved_sup_event_33463(params["payload"])
            elif method == "POST" and path == "/v1/replay/acquisition-event-8896":
                result = replay_saved_acq_event_8896(params["payload"])
            elif method == "POST" and path == "/v1/replay/supervision-event-38707":
                result = replay_saved_sup_event_38707(params["payload"])
            elif method == "POST" and path == "/v1/replay/acquisition-event-23113":
                result = replay_saved_acq_event_23113(params["payload"])
            elif method == "POST" and path == "/v1/replay/supervision-event-5847":
                result = replay_saved_sup_event_5847(params["payload"])
            elif method == "POST" and path == "/v1/replay/acquisition-event-38732":
                result = replay_saved_acq_event_38732(params["payload"])
            elif method == "POST" and path == "/v1/replay/supervision-event-26490":
                result = replay_saved_sup_event_26490(params["payload"])
            elif method == "POST" and path == "/v1/replay/acquisition-event-37991":
                result = replay_saved_acq_event_37991(params["payload"])
            elif method == "POST" and path == "/v1/replay/supervision-event-23880":
                result = replay_saved_sup_event_23880(params["payload"])
            elif method == "POST" and path == "/v1/replay/acquisition-event-17899":
                result = replay_saved_acq_event_17899(params["payload"])
            elif method == "POST" and path == "/v1/replay/supervision-event-53772":
                result = replay_saved_sup_event_53772(params["payload"])
            elif method == "POST" and path == "/v1/replay/acquisition-event-23143":
                result = replay_saved_acq_event_23143(params["payload"])
            elif method == "POST" and path == "/v1/replay/supervision-event-23770":
                result = replay_saved_sup_event_23770(params["payload"])
            elif method == "POST" and path == "/v1/replay/acquisition-event-35942":
                result = replay_saved_acq_event_35942(params["payload"])
            elif method == "POST" and path == "/v1/replay/supervision-event-56943":
                result = replay_saved_sup_event_56943(params["payload"])
            elif method == "POST" and path == "/v1/replay/acquisition-event-40079":
                result = replay_saved_acq_event_40079(params["payload"])
            elif method == "POST" and path == "/v1/replay/supervision-event-53656":
                result = replay_saved_sup_event_53656(params["payload"])
            elif method == "POST" and path == "/v1/replay/acquisition-event-42457":
                result = replay_saved_acq_event_42457(params["payload"])
            elif method == "POST" and path == "/v1/replay/supervision-event-47072":
                result = replay_saved_sup_event_47072(params["payload"])
            elif method == "POST" and path == "/v1/replay/acquisition-event-34531":
                result = replay_saved_acq_event_34531(params["payload"])
            elif method == "POST" and path == "/v1/replay/supervision-event-30817":
                result = replay_saved_sup_event_30817(params["payload"])
            elif method == "POST" and path == "/v1/replay/acquisition-event-23449":
                result = replay_saved_acq_event_23449(params["payload"])
            elif method == "POST" and path == "/v1/replay/supervision-position-t3-event":
                result = replay_saved_sup_position_t3(params["payload"])
            elif method == "POST" and path == "/v1/replay/acquisition-event-26012":
                result = replay_saved_acq_event_26012(params["payload"])
            elif method == "POST" and path == "/v1/replay/supervision-position-t2-event":
                result = replay_saved_sup_position_t2(params["payload"])
            elif method == "POST" and path == "/v1/intents":
                payload = params["payload"]
                if type(payload) is not dict or set(payload) != {"intent_id", "procedure", "expected_revision", "session_id"}:
                    raise ValueError("Exact named procedure intent required")
                if any(not isinstance(value, str) or not 1 <= len(value) <= 128 for value in payload.values()):
                    raise ValueError("Intent fields must be bounded nonempty strings")
                result = self.runtime.submit_procedure(**payload)
            elif method == "POST" and path == "/v1/setpoints":
                payload = params["payload"]
                if type(payload) is not dict or set(payload) != {"intent_id", "page", "control", "base_value", "expected_revision", "session_id"}:
                    raise ValueError("Exact named setpoint intent required")
                if any(not isinstance(payload[key], str) or not 1 <= len(payload[key]) <= 128
                       for key in ("intent_id", "page", "control", "expected_revision", "session_id")):
                    raise ValueError("Setpoint identity fields must be bounded strings")
                result = self.runtime.submit_setpoint(**payload)
            else:
                return self._reply(404, dict(error="Unknown supervision route", accepted=False), method, path, nonce)
            return self._reply(200, dict(result=result), method, path, nonce)
        except Rejected as error:
            return self._reply(409, dict(error=str(error), accepted=False), method, path, nonce)
        except KeyError:
            return self._reply(404, dict(error="Unknown ACQ intent", accepted=False), method, path, nonce)
        except (ValueError, TypeError) as error:
            return self._reply(400, dict(error=str(error), accepted=False), method, path, nonce)
        except Exception:
            # An error after durable acceptance cannot claim non-acceptance.
            return self._reply(503, dict(error="ACQ service unavailable"), method, path, nonce)

    def close(self):
        self.runtime.close()
