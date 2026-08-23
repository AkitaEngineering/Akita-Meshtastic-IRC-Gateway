# Akita Meshtastic IRC Gateway

AMIG is a Python gateway between a single controlled IRC channel and a Meshtastic radio. It supports reliable direct messages, broadcasts, alert packets, echo requests, node inspection, and inbound mesh relaying.

The production defaults are fail-closed: the IRC listener binds only to localhost, real radio failures stop startup, test mode is explicit, and remote IRC requires TLS plus a password.

- [Install AMIG](usage/installation.md)
- [Run it safely](usage/running.md)
- [Connect an IRC client](usage/connecting.md)
- [Command reference](commands.md)

Operators remain responsible for radio regulations, Meshtastic channel security, TLS certificate management, and host hardening.
