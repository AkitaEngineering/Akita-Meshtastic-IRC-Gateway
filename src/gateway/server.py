"""IRC server and Meshtastic integration for AMIG."""

from __future__ import annotations

import contextlib
import hmac
import logging
import re
import socket
import ssl
import threading
import time
from collections.abc import Callable, Mapping
from typing import Any

import irc.server
import irc.strings

IRC_LINE_BYTES = 510  # Excludes the terminating CRLF.
MESH_PAYLOAD_BYTES = 233
REPLY_APP = 32
TEXT_MESSAGE_APP = 1


class GatewayError(RuntimeError):
    """An expected, user-facing gateway operation error."""


def _clean_irc_text(value: object) -> str:
    """Return text that cannot inject an additional IRC command."""
    return str(value).replace("\r", "").replace("\n", " ").replace("\x00", "")


def _truncate_utf8(value: str, max_bytes: int) -> str:
    """Truncate a string without splitting a UTF-8 character."""
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def _validate_mesh_text(text: str) -> None:
    if not isinstance(text, str) or not text.strip():
        raise GatewayError("message cannot be empty")
    size = len(text.encode("utf-8"))
    if size > MESH_PAYLOAD_BYTES:
        raise GatewayError(f"message is {size} bytes; maximum is {MESH_PAYLOAD_BYTES} UTF-8 bytes")


class MockMeshtasticInterface:
    """Deterministic in-memory Meshtastic interface for explicit test mode."""

    def __init__(self) -> None:
        now = int(time.time())
        self._nodes_data: dict[str, dict[str, Any]] = {
            "!00000001": {
                "user": {"id": "!00000001", "longName": "Mock Node", "shortName": "MOCK"},
                "lastHeard": now - 60,
                "snr": 10.0,
                "position": {},
                "num": 1,
            },
            "!00bc614e": {
                "user": {"id": "!00bc614e", "longName": "Gateway Test Node", "shortName": "GW"},
                "lastHeard": now,
                "snr": 0.0,
                "position": {"latitude": 42.886, "longitude": -79.249, "altitude": 180, "time": now},
                "num": 12_345_678,
            },
        }
        self._on_receive_callback: Callable[[dict[str, Any], Any], None] | None = None
        self._lock = threading.RLock()
        self._closed = False
        self.my_node_num = 12_345_678
        self.my_node_id = "!00bc614e"
        logging.info("Initialized explicit in-memory Meshtastic test interface")

    @property
    def nodes(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {node_id: dict(node) for node_id, node in self._nodes_data.items()}

    def getMyNodeInfo(self) -> dict[str, Any] | None:  # noqa: N802 - upstream API name
        with self._lock:
            info = self._nodes_data.get(self.my_node_id)
            return dict(info) if info else None

    def subscribe_on_receive(self, callback: Callable[[dict[str, Any], Any], None]) -> None:
        if not callable(callback):
            raise TypeError("callback must be callable")
        self._on_receive_callback = callback

    def sendText(  # noqa: N802 - upstream API name
        self,
        text: str,
        destinationId: str = "^all",
        wantAck: bool = False,
        wantResponse: bool = False,
        onResponse: Callable[[dict[str, Any]], None] | None = None,
        channelIndex: int = 0,
        **_: Any,
    ) -> dict[str, Any]:
        if self._closed:
            raise GatewayError("mesh interface is closed")
        _validate_mesh_text(text)
        packet = {"id": int(time.time_ns() & 0xFFFFFFFF), "to": destinationId, "channel": channelIndex}
        logging.info("[Mock Meshtastic] text to %s on channel %s", destinationId, channelIndex)
        if wantAck and onResponse:
            response = {
                "from": destinationId,
                "decoded": {"portnum": "ROUTING_APP", "routing": {"errorReason": "NONE"}},
            }
            threading.Timer(0.01, onResponse, args=(response,)).start()
        return packet

    def sendAlert(self, text: str, channelIndex: int = 0, **_: Any) -> dict[str, Any]:  # noqa: N802
        if self._closed:
            raise GatewayError("mesh interface is closed")
        _validate_mesh_text(text)
        logging.info("[Mock Meshtastic] alert on channel %s", channelIndex)
        return {"id": int(time.time_ns() & 0xFFFFFFFF), "channel": channelIndex}

    def sendData(  # noqa: N802 - upstream API name
        self,
        data: bytes,
        destinationId: str,
        portNum: int,
        wantAck: bool = False,
        wantResponse: bool = False,
        onResponse: Callable[[dict[str, Any]], None] | None = None,
        channelIndex: int = 0,
        **_: Any,
    ) -> dict[str, Any]:
        if self._closed:
            raise GatewayError("mesh interface is closed")
        if len(data) > MESH_PAYLOAD_BYTES:
            raise GatewayError(f"mesh payload exceeds {MESH_PAYLOAD_BYTES} bytes")
        packet = {"id": int(time.time_ns() & 0xFFFFFFFF), "to": destinationId, "channel": channelIndex}
        if onResponse and (wantResponse or wantAck):
            if wantResponse:
                decoded = {"portnum": "REPLY_APP", "payload": data, "text": data.decode(errors="replace")}
            else:
                decoded = {"portnum": "ROUTING_APP", "routing": {"errorReason": "NONE"}}
            response = {
                "from": destinationId,
                "to": self.my_node_num,
                "decoded": decoded,
                "rssi": -65,
                "snr": 9.0,
            }
            threading.Timer(0.01, onResponse, args=(response,)).start()
        return packet

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._on_receive_callback = None


class GatewayIRCClient(irc.server.IRCClient):
    """IRC protocol handler connected to :class:`MeshtasticGatewayServer`."""

    authenticated = False

    def setup(self) -> None:
        self._connected_at = time.monotonic()
        self._password_failures = 0
        self._quit_reason = "EOF from client"

    def _handle_one(self) -> None:
        if not self._is_registered() and time.monotonic() - self._connected_at > self.server.registration_timeout:
            self._send(f":{self.server.servername} ERROR :Registration timeout")
            raise self.Disconnect()
        super()._handle_one()

    def _handle_line(self, line: str) -> None:
        """Dispatch an IRC line without ever logging credentials or message bodies."""
        response = None
        command, _, params = line.partition(" ")
        try:
            handler = getattr(self, f"handle_{command.lower()}", None)
            if not handler:
                raise irc.server.IRCError.from_name("unknowncommand", f"{command} :Unknown command")
            response = handler(params)
        except irc.server.IRCError as exc:
            response = f":{self.server.servername} {exc.code} {exc.value}"
        except self.Disconnect:
            raise
        except Exception:
            logging.exception("IRC command %s failed for %s", command, self.client_address[0])
            response = f":{self.server.servername} ERROR :Internal server error"
        if response:
            self._send(response)

    def _is_registered(self) -> bool:
        return bool(self.nick and self.user and (not self.server.irc_password or self.authenticated))

    def _require_registered(self) -> None:
        if not self._is_registered():
            raise irc.server.IRCError.from_name("notregistered", ":Register with PASS, NICK, and USER first")

    @property
    def nickname(self) -> str | None:
        """Compatibility alias used by command modules."""
        return self.nick

    @property
    def connected(self) -> bool:
        try:
            return self.request.fileno() >= 0
        except OSError:
            return False

    def _handle_incoming(self) -> None:
        """Decode safely and reject oversized IRC input buffers."""
        try:
            data = self.request.recv(1024)
        except OSError as exc:
            raise self.Disconnect() from exc
        if not data:
            raise self.Disconnect()
        self.buffer.feed(data)
        if len(self.buffer) > 8192:
            self._send(f":{self.server.servername} ERROR :Input buffer exceeded 8192 bytes")
            raise self.Disconnect()
        for raw_line in self.buffer:
            if len(raw_line) > IRC_LINE_BYTES:
                self._send(f":{self.server.servername} ERROR :IRC line exceeds {IRC_LINE_BYTES} bytes")
                raise self.Disconnect()
            self._handle_line(raw_line.decode("utf-8", errors="replace"))

    def handle_pass(self, params: str) -> str:
        supplied = params.lstrip(":")
        expected = self.server.irc_password
        if self.nick:
            raise irc.server.IRCError.from_name("alreadyregistered", ":Already registered")
        self.authenticated = bool(expected) and hmac.compare_digest(supplied, expected)
        if expected and not self.authenticated:
            self._password_failures += 1
            if self._password_failures >= 3:
                self._send(f":{self.server.servername} 464 * :Too many password failures")
                raise self.Disconnect()
            raise irc.server.IRCError.from_name("passwdmismatch", ":Password incorrect")
        return ""

    def handle_nick(self, params: str) -> str | None:
        if self.server.irc_password and not self.authenticated:
            raise irc.server.IRCError.from_name("passwdmismatch", ":PASS required before NICK")
        requested = params.strip()
        if not 1 <= len(requested) <= 30 or not re.fullmatch(r"[A-Za-z][A-Za-z0-9\-\[\]`^{}_]*", requested):
            raise irc.server.IRCError.from_name("erroneusnickname", f"{requested} :Invalid nickname")
        collision = next(
            (
                client
                for nick, client in self.server.clients.items()
                if irc.strings.lower(nick) == irc.strings.lower(requested) and client is not self
            ),
            None,
        )
        if collision:
            raise irc.server.IRCError.from_name("nicknameinuse", f"{requested} :Nickname is already in use")
        response = super().handle_nick(params)
        if self.nick and not self.user:
            self.notice(self.nick, f"Welcome to AMIG ({self.server.servername})")
            self.notice(self.nick, f"Join {self.server.control_channel_name} and type HELP for commands")
        return response

    def handle_user(self, params: str) -> str:
        fields = params.split(" ", 3)
        if len(fields) != 4:
            raise irc.server.IRCError.from_name("needmoreparams", "USER :Not enough parameters")
        user, mode, _unused, realname = fields
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,32}", user):
            raise irc.server.IRCError.from_name("notregistered", ":Invalid username")
        self.user = user
        self.mode = mode
        self.realname = _truncate_utf8(realname.removeprefix(":"), 128)
        return ""

    def handle_cap(self, params: str) -> str:
        subcommand = params.split(" ", 1)[0].upper()
        if subcommand == "LS":
            nick = self.nick or "*"
            return f":{self.server.servername} CAP {nick} LS :"
        return ""

    def handle_mode(self, params: str) -> str:
        self._require_registered()
        target, _, modes = params.partition(" ")
        if irc.strings.lower(target) == irc.strings.lower(self.server.control_channel_name):
            if modes:
                raise irc.server.IRCError.from_name("chanoprivsneeded", f"{target} :Channel mode is fixed")
            return f":{self.server.servername} 324 {self.nick} {self.server.control_channel_name} +nt"
        return f":{self.server.servername} 221 {self.nick} +"

    def handle_topic(self, params: str) -> str:
        self._require_registered()
        channel, _, topic = params.partition(" ")
        if irc.strings.lower(channel) != irc.strings.lower(self.server.control_channel_name):
            raise irc.server.IRCError.from_name("nosuchchannel", f"{channel} :No such channel")
        if topic:
            raise irc.server.IRCError.from_name("chanoprivsneeded", f"{channel} :Channel topic is fixed")
        current = self.server.channels.get(self.server.control_channel_name)
        value = current.topic if current else "No topic"
        return f":{self.server.servername} 332 {self.nick} {self.server.control_channel_name} :{value}"

    def handle_quit(self, params: str) -> None:
        self._quit_reason = _truncate_utf8(params.removeprefix(":"), 128) or "Client quit"
        raise self.Disconnect()

    def handle_join(self, params: str) -> None:
        self._require_registered()
        requested = params.split(" ", 1)[0].split(",")
        if len(requested) != 1:
            raise irc.server.IRCError.from_name(
                "nosuchchannel", f"{params} :Only {self.server.control_channel_name} is available"
            )
        channel_name = requested[0].strip()
        if irc.strings.lower(channel_name) != irc.strings.lower(self.server.control_channel_name):
            raise irc.server.IRCError.from_name(
                "nosuchchannel", f"{channel_name} :Only {self.server.control_channel_name} is available"
            )
        if not re.fullmatch(r"#[A-Za-z0-9_\-\[\]{}^`|]+", channel_name):
            raise irc.server.IRCError.from_name("nosuchchannel", f"{channel_name} :Invalid channel name")

        canonical = self.server.control_channel_name
        with self.server.state_lock:
            channel = self.server.channels.setdefault(canonical, irc.server.IRCChannel(canonical))
            channel.topic = "Akita Meshtastic IRC Gateway | Type HELP for commands"
            channel.topic_by = self.server.servername
            channel.clients.add(self)
            self.channels[canonical] = channel
            clients = list(channel.clients)

        join_line = f":{self.client_ident()} JOIN :{canonical}"
        for client in clients:
            client.send_line(join_line)
        self.send_line(f":{channel.topic_by} TOPIC {canonical} :{channel.topic}")
        nicks = " ".join(sorted(client.nick for client in clients if client.nick))
        self.send_line(f":{self.server.servername} 353 {self.nick} = {canonical} :{nicks}")
        self.send_line(f":{self.server.servername} 366 {self.nick} {canonical} :End of /NAMES list")

    def handle_privmsg(self, params: str) -> None:
        self._require_registered()
        target, separator, raw_message = params.partition(" ")
        if not separator or not raw_message:
            raise irc.server.IRCError.from_name("needmoreparams", "PRIVMSG :Not enough parameters")
        message = raw_message.removeprefix(":")
        self.server.process_privmsg(self, target, message)

    def notice(self, target: str, text: object) -> None:
        clean_target = _clean_irc_text(target).replace(" ", "")
        clean_text = _clean_irc_text(text)
        prefix = f":{self.server.servername} NOTICE {clean_target} :"
        clean_text = _truncate_utf8(clean_text, IRC_LINE_BYTES - len(prefix.encode("utf-8")))
        self.send_line(prefix + clean_text)

    def send_line(self, line: str) -> None:
        clean = _clean_irc_text(line)
        self.send_queue.append(_truncate_utf8(clean, IRC_LINE_BYTES))

    def finish(self) -> None:
        if not hasattr(self, "channels"):
            return
        identity = self.client_ident()
        with self.server.state_lock:
            channels = list(self.channels.values())
            for channel in channels:
                channel.clients.discard(self)
            self.channels.clear()
            if self.nick and self.server.clients.get(self.nick) is self:
                self.server.clients.pop(self.nick, None)
        quit_line = f":{identity} QUIT :{_clean_irc_text(self._quit_reason)}"
        notified: set[GatewayIRCClient] = set()
        for channel in channels:
            for client in list(channel.clients):
                if client not in notified:
                    client.send_line(quit_line)
                    notified.add(client)


class MeshtasticGatewayServer(irc.server.IRCServer):
    """Threaded, single-channel IRC gateway backed by a Meshtastic interface."""

    def __init__(
        self,
        mesh_interface_ref: Any,
        control_channel_name: str,
        default_mesh_channel_index: int,
        bind_address: tuple[str, int],
        servername: str,
        irc_password: str | None = None,
        ssl_context: ssl.SSLContext | None = None,
        mesh_send_interval: float = 1.0,
        max_clients: int = 100,
        registration_timeout: float = 30.0,
        mesh_response_timeout: float = 30.0,
    ) -> None:
        if not control_channel_name.startswith("#"):
            raise ValueError("control channel must start with '#'")
        if not re.fullmatch(r"#[A-Za-z0-9_\-\[\]{}^`|]+", control_channel_name):
            raise ValueError("control channel contains invalid IRC characters")
        if not re.fullmatch(r"[A-Za-z0-9.-]+", servername):
            raise ValueError("server name contains invalid IRC characters")
        if not 0 <= default_mesh_channel_index <= 7:
            raise ValueError("mesh channel index must be between 0 and 7")
        if max_clients < 1:
            raise ValueError("max clients must be at least 1")
        self.mesh_interface = mesh_interface_ref
        self.control_channel_name = control_channel_name
        self.default_mesh_channel_index = default_mesh_channel_index
        self.irc_password = irc_password
        self.ssl_context = ssl_context
        self.mesh_send_interval = max(0.0, mesh_send_interval)
        self.registration_timeout = max(1.0, registration_timeout)
        self.mesh_response_timeout = max(1.0, mesh_response_timeout)
        self._client_slots = threading.BoundedSemaphore(max_clients)
        self.started_at = time.monotonic()
        self.state_lock = threading.RLock()
        self._mesh_send_lock = threading.Lock()
        self._last_mesh_send = 0.0
        self._response_timers: set[threading.Timer] = set()
        self.runtime_failure: str | None = None
        self.commands: dict[str, dict[str, Any]] = {}
        super().__init__(bind_address, GatewayIRCClient)
        self.servername = servername
        if hasattr(self.mesh_interface, "subscribe_on_receive"):
            self.mesh_interface.subscribe_on_receive(self.on_meshtastic_receive)
        logging.info("IRC server initialized on %s:%s", *self.server_address)

    def process_request(self, request: socket.socket, client_address: Any) -> None:
        if not self._client_slots.acquire(blocking=False):
            with contextlib.suppress(OSError):
                request.sendall(f":{self.servername} ERROR :Server is at client capacity\r\n".encode())
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._client_slots.release()
            raise

    def process_request_thread(self, request: socket.socket, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._client_slots.release()

    @property
    def connections(self) -> list[GatewayIRCClient]:
        with self.state_lock:
            return list(self.clients.values())

    def get_request(self) -> tuple[socket.socket, Any]:
        request, address = super().get_request()
        if not self.ssl_context:
            return request, address
        request.settimeout(10.0)
        try:
            wrapped = self.ssl_context.wrap_socket(request, server_side=True)
            wrapped.settimeout(None)
            return wrapped, address
        except Exception:
            request.close()
            raise

    def register_command(self, command_name: str, execute_func: Callable[..., None], help_text: str) -> None:
        name = command_name.strip().upper() if isinstance(command_name, str) else ""
        if not name or not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
            raise ValueError(f"invalid command name: {command_name!r}")
        if not callable(execute_func):
            raise TypeError("command execute function must be callable")
        if not isinstance(help_text, str) or not help_text.strip():
            raise ValueError("command help text must be non-empty")
        if name in self.commands:
            raise ValueError(f"duplicate command registration: {name}")
        self.commands[name] = {"execute": execute_func, "help": help_text.strip()}

    def process_privmsg(self, connection: GatewayIRCClient, target: str, message: str) -> None:
        message = _clean_irc_text(message).strip()
        if not message:
            return
        canonical_target = irc.strings.lower(target)
        canonical_control = irc.strings.lower(self.control_channel_name)
        if canonical_target == canonical_control:
            if self.control_channel_name not in connection.channels:
                raise irc.server.IRCError.from_name(
                    "cannotsendtochan", f"{self.control_channel_name} :Cannot send to channel"
                )
            command, _, remainder = message.partition(" ")
            command = command.upper()
            if command in self.commands:
                import shlex

                try:
                    args = shlex.split(remainder) if remainder else []
                except ValueError as exc:
                    connection.notice(connection.nick or "*", f"Invalid command arguments: {exc}")
                    return
                self.handle_control_command(connection, connection.nick or "*", command, args)
                return
            self._relay_channel_message(connection, message)
            return
        if irc.strings.lower(target) == irc.strings.lower(self.servername):
            connection.notice(connection.nick or "*", f"Join {self.control_channel_name} to issue commands")
            return
        recipient = next(
            (client for nick, client in self.clients.items() if irc.strings.lower(nick) == canonical_target), None
        )
        if not recipient:
            raise irc.server.IRCError.from_name("nosuchnick", f"{target} :No such nick")
        recipient.send_line(f":{connection.client_ident()} PRIVMSG {recipient.nick} :{message}")

    def _relay_channel_message(self, sender: GatewayIRCClient, message: str) -> None:
        with self.state_lock:
            channel = self.channels.get(self.control_channel_name)
            recipients = list(channel.clients) if channel else []
        line = f":{sender.client_ident()} PRIVMSG {self.control_channel_name} :{message}"
        for client in recipients:
            if client is not sender:
                client.send_line(line)

    def _send_server_message_to_control_channel(self, message: object, prefix: str = "[GW]") -> None:
        clean = f"{_clean_irc_text(prefix)} {_clean_irc_text(message)}"
        line_prefix = f":{self.servername}!gateway@{self.servername} PRIVMSG {self.control_channel_name} :"
        line = line_prefix + _truncate_utf8(clean, IRC_LINE_BYTES - len(line_prefix.encode("utf-8")))
        with self.state_lock:
            channel = self.channels.get(self.control_channel_name)
            recipients = list(channel.clients) if channel else []
        for client in recipients:
            client.send_line(line)

    def handle_control_command(
        self, connection: GatewayIRCClient, nick: str, command_word: str, args: list[str]
    ) -> None:
        command_info = self.commands.get(command_word)
        if not command_info:
            connection.notice(nick, f"Unknown command: {command_word}. Try HELP.")
            return
        logging.info("Executing command %s for %s", command_word, nick)
        try:
            command_info["execute"](self, connection, nick, args)
        except GatewayError as exc:
            connection.notice(nick, f"Error: {exc}")
        except Exception:
            logging.exception("Command %s failed for %s", command_word, nick)
            connection.notice(nick, f"Command {command_word} failed; see the gateway log")

    def nodes_snapshot(self) -> dict[str, dict[str, Any]]:
        nodes = getattr(self.mesh_interface, "nodes", None)
        if not isinstance(nodes, Mapping):
            return {}
        return {str(key): dict(value) for key, value in nodes.items() if isinstance(value, Mapping)}

    def get_my_node_info(self) -> dict[str, Any] | None:
        getter = getattr(self.mesh_interface, "getMyNodeInfo", None)
        if callable(getter):
            info = getter()
            if isinstance(info, Mapping):
                return dict(info)
        my_info = getattr(self.mesh_interface, "myInfo", None)
        node_num = getattr(my_info, "my_node_num", None)
        if node_num is not None:
            return next((node for node in self.nodes_snapshot().values() if node.get("num") == node_num), None)
        return None

    def get_node_name(self, node_identifier: object) -> str:
        identifier = str(node_identifier)
        for node_id, node in self.nodes_snapshot().items():
            if node_id == identifier or str(node.get("num")) == identifier:
                user = node.get("user", {})
                if isinstance(user, Mapping):
                    return str(user.get("shortName") or user.get("longName") or node_id)
                return node_id
        return identifier

    def _find_node_id(self, node_spec: str) -> str | None:
        wanted = node_spec.strip().casefold()
        if not wanted:
            return None
        for node_id, node in self.nodes_snapshot().items():
            user = node.get("user", {})
            candidates = {node_id.casefold(), str(node.get("num", "")).casefold()}
            if isinstance(user, Mapping):
                candidates.update(str(user.get(field, "")).casefold() for field in ("id", "shortName", "longName"))
            if wanted in candidates:
                return node_id
        return None

    def _reserve_mesh_send(self) -> None:
        with self._mesh_send_lock:
            now = time.monotonic()
            retry_after = self.mesh_send_interval - (now - self._last_mesh_send)
            if retry_after > 0:
                raise GatewayError(f"mesh send rate limited; retry in {retry_after:.1f}s")
            self._last_mesh_send = now

    def send_mesh_text(
        self,
        text: str,
        destination_id: str | None = None,
        response_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> Any:
        _validate_mesh_text(text)
        self._reserve_mesh_send()
        if destination_id is None:
            return self.mesh_interface.sendText(text, channelIndex=self.default_mesh_channel_index)
        return self._send_with_response_timeout(
            lambda callback: self.mesh_interface.sendData(
                text.encode("utf-8"),
                destinationId=destination_id,
                portNum=TEXT_MESSAGE_APP,
                wantAck=True,
                wantResponse=False,
                onResponse=callback,
                onResponseAckPermitted=True,
                channelIndex=self.default_mesh_channel_index,
            ),
            response_callback,
        )

    def send_mesh_alert(self, text: str) -> Any:
        _validate_mesh_text(text)
        self._reserve_mesh_send()
        sender = getattr(self.mesh_interface, "sendAlert", None)
        if not callable(sender):
            raise GatewayError("the installed Meshtastic library does not support alert packets")
        return sender(text, channelIndex=self.default_mesh_channel_index)

    def send_mesh_ping(self, destination_id: str, response_callback: Callable[[dict[str, Any]], None]) -> Any:
        self._reserve_mesh_send()
        return self._send_with_response_timeout(
            lambda callback: self.mesh_interface.sendData(
                b"ping",
                destinationId=destination_id,
                portNum=REPLY_APP,
                wantAck=True,
                wantResponse=True,
                onResponse=callback,
                channelIndex=self.default_mesh_channel_index,
            ),
            response_callback,
        )

    @staticmethod
    def packet_id(packet: object) -> int | None:
        value = packet.get("id") if isinstance(packet, Mapping) else getattr(packet, "id", None)
        return value if isinstance(value, int) else None

    def _send_with_response_timeout(
        self,
        operation: Callable[[Callable[[dict[str, Any]], None]], Any],
        response_callback: Callable[[dict[str, Any]], None],
    ) -> Any:
        callback_lock = threading.Lock()
        completed = False
        timer_holder: list[threading.Timer] = []

        def complete(packet: dict[str, Any]) -> None:
            nonlocal completed
            with callback_lock:
                if completed:
                    return
                completed = True
                timer = timer_holder[0] if timer_holder else None
            if timer:
                timer.cancel()
                with self.state_lock:
                    self._response_timers.discard(timer)
            try:
                response_callback(packet)
            except Exception:
                logging.exception("Mesh response callback failed")

        packet = operation(complete)
        packet_id = self.packet_id(packet)

        def expire() -> None:
            handlers = getattr(self.mesh_interface, "responseHandlers", None)
            if packet_id is not None and isinstance(handlers, dict):
                handlers.pop(packet_id, None)
            complete(
                {
                    "decoded": {
                        "portnum": "ROUTING_APP",
                        "routing": {"errorReason": "TIMEOUT"},
                    }
                }
            )

        timer = threading.Timer(self.mesh_response_timeout, expire)
        timer.name = f"mesh-response-{packet_id or 'unknown'}"
        timer.daemon = True
        with callback_lock:
            timer_holder.append(timer)
            if not completed:
                with self.state_lock:
                    self._response_timers.add(timer)
                timer.start()
        return packet

    def on_meshtastic_receive(self, packet: object, interface: Any = None, **_: Any) -> None:
        if not isinstance(packet, Mapping):
            logging.warning("Ignoring malformed Meshtastic packet: %r", packet)
            return
        try:
            decoded = packet.get("decoded")
            if not isinstance(decoded, Mapping):
                return
            portnum = str(decoded.get("portnum", "UNKNOWN"))
            sender_name = self.get_node_name(packet.get("from", "UNKNOWN"))
            rssi = packet.get("rssi", "N/A")
            snr = packet.get("snr", "N/A")
            if portnum == "TEXT_MESSAGE_APP" and isinstance(decoded.get("text"), str):
                recipient = packet.get("to")
                direct = recipient not in ("^all", 0xFFFFFFFF, "4294967295")
                if direct and not self._is_for_local_node(recipient):
                    return
                channel_index = packet.get("channel", "?")
                label = "DM From" if direct else ""
                body = f"{label} <{sender_name}>: {decoded['text']}" if direct else f"<{sender_name}> {decoded['text']}"
                self._send_server_message_to_control_channel(body, f"[MESH Rx ch{channel_index} RSSI:{rssi} SNR:{snr}]")
            elif portnum == "REPLY_APP":
                self._send_server_message_to_control_channel(
                    f"PONG from <{sender_name}> RSSI:{rssi} SNR:{snr}", "[PING]"
                )
            elif portnum == "POSITION_APP":
                position = decoded.get("position", decoded)
                if not isinstance(position, Mapping):
                    return
                lat = position.get("latitude")
                lon = position.get("longitude")
                if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                    altitude = position.get("altitude")
                    suffix = f", Alt {altitude}m" if isinstance(altitude, (int, float)) else ""
                    self._send_server_message_to_control_channel(
                        f"Position from <{sender_name}>: {lat:.5f}, {lon:.5f}{suffix}", "[POS]"
                    )
            elif portnum == "ROUTING_APP":
                routing = decoded.get("routing")
                if isinstance(routing, Mapping):
                    reason = str(routing.get("errorReason", "UNKNOWN"))
                    status = "ACK" if reason == "NONE" else f"NAK ({reason})"
                    self._send_server_message_to_control_channel(f"{status} from <{sender_name}>", "[MESH]")
        except Exception:
            logging.exception("Failed to process Meshtastic packet")

    def _is_for_local_node(self, recipient: object) -> bool:
        info = self.get_my_node_info() or {}
        identifiers = {str(info.get("num", ""))}
        user = info.get("user", {})
        if isinstance(user, Mapping):
            identifiers.add(str(user.get("id", "")))
        my_info = getattr(self.mesh_interface, "myInfo", None)
        identifiers.add(str(getattr(my_info, "my_node_num", "")))
        identifiers.add(str(getattr(self.mesh_interface, "my_node_num", "")))
        return str(recipient) in identifiers

    def disconnect_all(self, reason: str = "Server shutting down") -> None:
        with self.state_lock:
            timers = list(self._response_timers)
            self._response_timers.clear()
        for timer in timers:
            timer.cancel()
        with self.state_lock:
            clients = list(self.clients.values())
        for client in clients:
            try:
                client._send(f":{self.servername} ERROR :{_clean_irc_text(reason)}")
                client.request.shutdown(socket.SHUT_RDWR)
            except OSError:
                logging.debug("Client socket was already closed during shutdown")
            finally:
                with contextlib.suppress(OSError):
                    client.request.close()

    def stop_after_mesh_failure(self, reason: object) -> None:
        """Stop the IRC loop so a process supervisor can restart a dead radio link."""
        if self.runtime_failure is not None:
            return
        self.runtime_failure = _clean_irc_text(reason)
        self._send_server_message_to_control_channel(self.runtime_failure, "[MESH LOST]")
        threading.Thread(target=self.shutdown, name="irc-shutdown", daemon=True).start()
