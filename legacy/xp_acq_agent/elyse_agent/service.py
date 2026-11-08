from __future__ import print_function

import socket
import socketserver

from .protocol import recv_message, send_message


class AgentRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        peer = "{0}:{1}".format(self.client_address[0], self.client_address[1])
        self.request.settimeout(self.server.socket_timeout_seconds)
        while True:
            try:
                request = recv_message(self.request, self.server.max_frame_bytes)
            except EOFError:
                return
            except socket.timeout:
                return
            except Exception as error:
                response = {
                    "id": None,
                    "ok": False,
                    "error": {"code": "protocol_error", "message": str(error)},
                }
                send_message(self.request, response, self.server.max_frame_bytes)
                return
            response = self.server.router.dispatch(request, peer=peer)
            send_message(self.request, response, self.server.max_frame_bytes)


class AgentServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, router, max_frame_bytes, socket_timeout_seconds):
        self.router = router
        self.max_frame_bytes = int(max_frame_bytes)
        self.socket_timeout_seconds = float(socket_timeout_seconds)
        socketserver.TCPServer.__init__(self, address, AgentRequestHandler)

    def server_close(self):
        socketserver.TCPServer.server_close(self)
        close = getattr(self.router, "close", None)
        if callable(close):
            close()
