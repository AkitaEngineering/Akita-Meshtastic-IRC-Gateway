from __future__ import annotations

import socket
import threading
import time
from contextlib import contextmanager

from gateway.main import load_and_register_commands
from gateway.server import MESH_PAYLOAD_BYTES, MeshtasticGatewayServer, MockMeshtasticInterface


def receive_until(sock: socket.socket, marker: str, timeout: float = 3.0) -> str:
    deadline = time.monotonic() + timeout
    chunks: list[bytes] = []
    while time.monotonic() < deadline:
        try:
            chunk = sock.recv(4096)
        except TimeoutError:
            continue
        if not chunk:
            break
        chunks.append(chunk)
        text = b"".join(chunks).decode("utf-8", errors="replace")
        if marker in text:
            return text
    text = b"".join(chunks).decode("utf-8", errors="replace")
    raise AssertionError(f"did not receive {marker!r}; received {text!r}")


def send_lines(sock: socket.socket, *lines: str) -> None:
    sock.sendall("".join(f"{line}\r\n" for line in lines).encode())


@contextmanager
def running_server(password: str | None = None):
    mesh = MockMeshtasticInterface()
    server = MeshtasticGatewayServer(
        mesh_interface_ref=mesh,
        control_channel_name="#meshtastic-ctrl",
        default_mesh_channel_index=0,
        bind_address=("127.0.0.1", 0),
        servername="test.gw",
        irc_password=password,
        mesh_send_interval=0,
    )
    load_and_register_commands(server)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.disconnect_all("test complete")
        server.shutdown()
        server.server_close()
        mesh.close()
        thread.join(timeout=2)


def connect_client(server, nick: str, password: str | None = None) -> socket.socket:
    sock = socket.create_connection(server.server_address, timeout=2)
    sock.settimeout(0.1)
    lines = []
    if password:
        lines.append(f"PASS {password}")
    lines.extend((f"NICK {nick}", f"USER {nick} 0 * :Test User", "JOIN #meshtastic-ctrl"))
    send_lines(sock, *lines)
    receive_until(sock, "End of /NAMES list")
    return sock


def test_real_irc_session_loads_commands_and_executes_mesh_operations():
    with running_server() as server:
        sock = connect_client(server, "alice")
        assert len(server.commands) == 12

        send_lines(sock, "PRIVMSG #meshtastic-ctrl :HELP")
        output = receive_until(sock, "PING")
        assert "PING" in output

        send_lines(sock, "PRIVMSG #meshtastic-ctrl :SEND production smoke test")
        assert "Message queued" in receive_until(sock, "Message queued")

        send_lines(sock, "PRIVMSG #meshtastic-ctrl :DM MOCK reliable test")
        assert "awaiting ACK/NAK" in receive_until(sock, "awaiting ACK/NAK")
        assert "acknowledged" in receive_until(sock, "acknowledged")

        send_lines(sock, "PRIVMSG #meshtastic-ctrl :PING MOCK")
        assert "Ping queued" in receive_until(sock, "Ping queued")
        assert "PONG from MOCK" in receive_until(sock, "PONG from MOCK")
        sock.close()


def test_channel_membership_and_relay_are_enforced():
    with running_server() as server:
        alice = connect_client(server, "alice")
        bob = connect_client(server, "bob")
        receive_until(alice, "bob")
        send_lines(alice, "PRIVMSG #meshtastic-ctrl :hello bob")
        assert "PRIVMSG #meshtastic-ctrl :hello bob" in receive_until(bob, "hello bob")
        alice.close()
        bob.close()


def test_password_is_required_before_nickname_registration():
    with running_server(password="correct horse battery staple") as server:
        rejected = socket.create_connection(server.server_address, timeout=2)
        rejected.settimeout(0.1)
        send_lines(rejected, "NICK alice")
        assert " 464 " in receive_until(rejected, " 464 ")
        rejected.close()

        accepted = connect_client(server, "bob", "correct horse battery staple")
        accepted.close()


def test_mesh_message_limit_counts_utf8_bytes():
    mesh = MockMeshtasticInterface()
    mesh.sendText("a" * MESH_PAYLOAD_BYTES)
    try:
        mesh.sendText("é" * MESH_PAYLOAD_BYTES)
    except RuntimeError as exc:
        assert "UTF-8 bytes" in str(exc)
    else:
        raise AssertionError("oversized UTF-8 message was accepted")


def test_mesh_response_timeout_completes_pending_request():
    class SilentMesh(MockMeshtasticInterface):
        def sendData(self, *args, **kwargs):
            return {"id": 42}

    mesh = SilentMesh()
    server = MeshtasticGatewayServer(
        mesh_interface_ref=mesh,
        control_channel_name="#meshtastic-ctrl",
        default_mesh_channel_index=0,
        bind_address=("127.0.0.1", 0),
        servername="test.gw",
        mesh_send_interval=0,
    )
    server.mesh_response_timeout = 0.02
    received = []
    completed = threading.Event()

    def callback(packet):
        received.append(packet)
        completed.set()

    try:
        server.send_mesh_ping("!00000001", callback)
        assert completed.wait(1)
        assert received[0]["decoded"]["routing"]["errorReason"] == "TIMEOUT"
    finally:
        server.disconnect_all()
        server.server_close()
        mesh.close()
