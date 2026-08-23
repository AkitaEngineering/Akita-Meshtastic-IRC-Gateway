"""Command-line entry point for the Akita Meshtastic IRC Gateway."""

from __future__ import annotations

import argparse
import importlib
import ipaddress
import logging
import pkgutil
import signal
import ssl
import time
from typing import Any

from gateway import config
from gateway.server import MeshtasticGatewayServer, MockMeshtasticInterface

try:
    import meshtastic.serial_interface
    import meshtastic.tcp_interface
    from pubsub import pub
except ImportError as exc:
    MESHTASTIC_IMPORT_ERROR: ImportError | None = exc
    pub = None
else:
    MESHTASTIC_IMPORT_ERROR = None


def setup_logging(log_level: int) -> None:
    logging.basicConfig(
        level=log_level,
        format=config.LOG_FORMAT,
        datefmt=config.LOG_DATE_FORMAT,
        force=True,
    )
    if log_level > logging.DEBUG:
        for logger_name in ("irc", "pubsub", "meshtastic"):
            logging.getLogger(logger_name).setLevel(logging.WARNING)


def initialize_meshtastic_interface(
    mesh_port: str | None,
    mesh_host: str | None,
    use_mock: bool,
) -> Any:
    """Create an explicit test interface or connect to a configured radio."""
    if use_mock:
        return MockMeshtasticInterface()
    if not mesh_port and not mesh_host:
        raise RuntimeError("configure --mesh-port or --mesh-host, or use --mock explicitly")
    if MESHTASTIC_IMPORT_ERROR:
        raise RuntimeError(f"Meshtastic dependency is unavailable: {MESHTASTIC_IMPORT_ERROR}")

    description = f"serial device {mesh_port}" if mesh_port else f"TCP host {mesh_host}"
    last_error: Exception | None = None
    for attempt in range(1, config.MESH_CONNECT_RETRIES + 1):
        interface = None
        try:
            logging.info(
                "Connecting to Meshtastic %s (attempt %d/%d)",
                description,
                attempt,
                config.MESH_CONNECT_RETRIES,
            )
            if mesh_port:
                interface = meshtastic.serial_interface.SerialInterface(
                    devPath=mesh_port,
                    noNodes=False,
                    timeout=config.MESH_CONNECT_TIMEOUT,
                )
            else:
                interface = meshtastic.tcp_interface.TCPInterface(
                    hostname=mesh_host,
                    noNodes=False,
                    timeout=config.MESH_CONNECT_TIMEOUT,
                )
            logging.info("Connected to Meshtastic %s", description)
            return interface
        except Exception as exc:
            last_error = exc
            logging.warning("Meshtastic connection attempt %d failed: %s", attempt, exc)
            if interface is not None:
                try:
                    interface.close()
                except Exception:
                    logging.debug("Failed interface cleanup", exc_info=True)
            if attempt < config.MESH_CONNECT_RETRIES:
                time.sleep(config.MESH_RETRY_DELAY)
    raise RuntimeError(
        f"could not connect to Meshtastic {description} after {config.MESH_CONNECT_RETRIES} attempts: {last_error}"
    )


def load_and_register_commands(server: MeshtasticGatewayServer) -> None:
    """Discover command modules and fail startup if any are invalid."""
    import gateway.commands

    module_names = sorted(
        module.name for module in pkgutil.iter_modules(gateway.commands.__path__) if module.name.startswith("cmd_")
    )
    if not module_names:
        raise RuntimeError("no command modules were found")
    for module_name in module_names:
        full_name = f"gateway.commands.{module_name}"
        module = importlib.import_module(full_name)
        try:
            name = module.COMMAND_NAME
            execute = module.execute
            help_text = module.COMMAND_HELP
        except AttributeError as exc:
            raise RuntimeError(f"command module {full_name} is incomplete") from exc
        server.register_command(name, execute, help_text)
    logging.info("Registered %d commands: %s", len(server.commands), ", ".join(sorted(server.commands)))


def setup_pubsub_listeners(server: MeshtasticGatewayServer, interface: Any) -> list[tuple[Any, str]]:
    """Subscribe the real interface to the Meshtastic event bus."""
    if pub is None or isinstance(interface, MockMeshtasticInterface):
        return []

    def connection_established(interface: Any = None, topic: Any = None, **_: Any) -> None:
        logging.info("Meshtastic connection established")
        server._send_server_message_to_control_channel("Connection established", "[MESH]")

    def connection_lost(interface: Any = None, topic: Any = None, **kwargs: Any) -> None:
        reason = kwargs.get("reason", "connection lost")
        logging.warning("Meshtastic connection lost: %s", reason)
        server.stop_after_mesh_failure(reason)

    subscriptions = [
        (server.on_meshtastic_receive, "meshtastic.receive"),
        (connection_established, "meshtastic.connection.established"),
        (connection_lost, "meshtastic.connection.lost"),
    ]
    for listener, topic_name in subscriptions:
        pub.subscribe(listener, topic_name)
    return subscriptions


def remove_pubsub_listeners(subscriptions: list[tuple[Any, str]]) -> None:
    if pub is None:
        return
    for listener, topic_name in subscriptions:
        try:
            pub.unsubscribe(listener, topic_name)
        except Exception:
            logging.debug("Could not unsubscribe from %s", topic_name, exc_info=True)


def _is_loopback_bind(host: str) -> bool:
    if host.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def build_ssl_context(certfile: str | None, keyfile: str | None) -> ssl.SSLContext | None:
    if not certfile and not keyfile:
        return None
    if not certfile or not keyfile:
        raise ValueError("both TLS certificate and key files are required")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certfile=certfile, keyfile=keyfile)
    return context


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Akita Meshtastic IRC Gateway (AMIG)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-H", "--host", default=config.IRC_SERVER_HOST, help="IRC bind address")
    parser.add_argument("-p", "--port", type=int, default=config.IRC_SERVER_PORT, help="IRC listen port")
    parser.add_argument("-n", "--servername", default=config.IRC_SERVER_NAME, help="IRC server name")
    connection = parser.add_mutually_exclusive_group()
    connection.add_argument("--mesh-port", help="Meshtastic serial device (overrides environment)")
    connection.add_argument("--mesh-host", help="Meshtastic TCP hostname (overrides environment)")
    connection.add_argument("--mock", action="store_true", help="Use the in-memory test interface")
    parser.add_argument(
        "--mesh-channel", type=int, default=config.DEFAULT_MESH_CHANNEL_INDEX, help="Meshtastic channel index"
    )
    parser.add_argument("--control-channel", default=config.CONTROL_CHANNEL, help="IRC control channel")
    parser.add_argument("--tls-cert", default=config.TLS_CERTFILE, help="PEM TLS certificate chain")
    parser.add_argument("--tls-key", default=config.TLS_KEYFILE, help="PEM TLS private key")
    parser.add_argument(
        "--allow-insecure-irc",
        action="store_true",
        help="Permit a non-loopback IRC listener without TLS and password (unsafe)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="enable debug logging")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if not 0 <= args.mesh_channel <= 7:
        parser.error("--mesh-channel must be between 0 and 7")
    if not args.control_channel.startswith("#"):
        parser.error("--control-channel must start with '#'")
    if not args.servername or any(character.isspace() for character in args.servername):
        parser.error("--servername must be non-empty and contain no whitespace")
    return args


def _select_mesh_connection(args: argparse.Namespace) -> tuple[str | None, str | None]:
    if args.mock:
        return None, None
    if args.mesh_port:
        return args.mesh_port, None
    if args.mesh_host:
        return None, args.mesh_host
    return config.MESH_DEVICE_PORT, config.MESH_DEVICE_HOST


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    setup_logging(logging.DEBUG if args.verbose else config.LOG_LEVEL)
    ssl_context = build_ssl_context(args.tls_cert, args.tls_key)
    if (
        not _is_loopback_bind(args.host)
        and not args.allow_insecure_irc
        and (ssl_context is None or not config.IRC_PASSWORD)
    ):
        logging.error(
            "Non-loopback IRC requires TLS and AMIG_IRC_PASSWORD; use --allow-insecure-irc only on a trusted network"
        )
        return 2

    mesh_port, mesh_host = _select_mesh_connection(args)
    interface = None
    server = None
    subscriptions: list[tuple[Any, str]] = []
    try:
        interface = initialize_meshtastic_interface(mesh_port, mesh_host, args.mock)
        server = MeshtasticGatewayServer(
            mesh_interface_ref=interface,
            control_channel_name=args.control_channel,
            default_mesh_channel_index=args.mesh_channel,
            bind_address=(args.host, args.port),
            servername=args.servername,
            irc_password=config.IRC_PASSWORD,
            ssl_context=ssl_context,
            mesh_send_interval=config.MESH_SEND_INTERVAL,
            max_clients=config.IRC_MAX_CLIENTS,
            registration_timeout=config.IRC_REGISTRATION_TIMEOUT,
            mesh_response_timeout=config.MESH_RESPONSE_TIMEOUT,
        )
        load_and_register_commands(server)
        subscriptions = setup_pubsub_listeners(server, interface)

        def request_shutdown(signum: int, frame: Any) -> None:
            del frame
            logging.info("Received signal %s; shutting down", signum)
            raise KeyboardInterrupt

        signal.signal(signal.SIGINT, request_shutdown)
        signal.signal(signal.SIGTERM, request_shutdown)
        logging.info(
            "AMIG listening on %s:%s (%s, %s mesh)",
            args.host,
            args.port,
            "TLS" if ssl_context else "plain IRC",
            "mock" if args.mock else "real",
        )
        server.serve_forever(poll_interval=0.25)
        if server.runtime_failure:
            raise RuntimeError(f"Meshtastic connection lost: {server.runtime_failure}")
    except KeyboardInterrupt:
        logging.info("Shutdown requested")
    except (OSError, RuntimeError, ValueError):
        logging.exception("Gateway startup or runtime failure")
        return 1
    finally:
        remove_pubsub_listeners(subscriptions)
        if server is not None:
            server.disconnect_all()
            server.server_close()
        if interface is not None:
            try:
                interface.close()
            except Exception:
                logging.exception("Failed to close Meshtastic interface")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
