# Connecting with an IRC Client

Configure any standard IRC client with:

- Host: `127.0.0.1` for the default local listener, or the configured gateway hostname.
- Port: `6667` by default.
- TLS: enabled whenever `AMIG_TLS_CERTFILE` and `AMIG_TLS_KEYFILE` are configured.
- Server password: the value configured in `AMIG_IRC_PASSWORD`.
- Nickname and username: 1–30 character IRC-compatible values.

After connecting, join the sole control channel:

```irc
/join #meshtastic-ctrl
```

Use the channel selected by `AMIG_CONTROL_CHANNEL` or `--control-channel` if it was changed.

Type `HELP` to list commands. Text that does not begin with a registered command is relayed as IRC chat to other users in the channel. Mesh broadcasts and direct messages addressed to the gateway are only sent to clients currently joined to the control channel.
