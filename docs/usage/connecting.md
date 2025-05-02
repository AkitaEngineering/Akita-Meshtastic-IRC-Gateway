# Connecting with an IRC Client

To interact with the Akita Meshtastic IRC Gateway (AMIG), you need an IRC client application.

## Popular IRC Clients

* **HexChat:** (Windows, Linux) - User-friendly graphical client.
* **WeeChat:** (Linux, macOS, Windows via WSL/Cygwin) - Powerful text-based client.
* **mIRC:** (Windows) - Long-standing graphical client (shareware).
* **irssi:** (Linux, macOS, Windows via WSL/Cygwin) - Popular text-based client.
* **LimeChat:** (macOS) - Graphical client.
* **Konversation:** (Linux/KDE) - Graphical client.

## Connection Details

Configure your IRC client to connect to the gateway using these details:

* **Server / Hostname:** The IP address or hostname where the gateway script (`main.py`) is running.
    * If running on the *same machine* as your client: use `localhost` or `127.0.0.1`.
    * If running on *another machine* on your local network: use its IP address (e.g., `192.168.1.50`).
    * If running on a *remote server*: use its public IP address or domain name.
* **Port:** The port the gateway is listening on.
    * Default: `6667` (from `config.py` or default).
    * Use the value specified with the `-p` command-line option if you changed it.
* **SSL/TLS:** **Disable** SSL/TLS connections. The gateway does not currently support encrypted IRC connections. Look for settings like "Use SSL", "Enable TLS/SSL" and make sure they are unchecked.
* **Nickname:** Choose any nickname you like (e.g., `meshuser`).
* **Username / Ident:** Usually optional, can often be the same as your nickname.
* **Password:** No password is required by the gateway. Leave blank.

## Joining the Control Channel

Once your IRC client successfully connects to the gateway server, you need to join the designated control channel to send commands and see messages.

In your client's input bar, type the `/join` command followed by the channel name:

```irc
/join #meshtastic-ctrl
(Use the channel name specified by the --control-channel argument or the CONTROL_CHANNEL setting in config.py if you changed it from the default.)You should now be in the channel. You'll typically see:A message confirming you joined the channel.The channel topic set by the gateway (e.g., Akita Meshtastic IRC Gateway (AMIG) | Type HELP for commands).A list of users currently in the channel (initially, likely just you).InteractingYou can now interact with the gateway and the mesh:Type HELP and press Enter to see the list of available commands.Send commands: e.g., NODES, SEND Hello Mesh!, DM MK1 How are you?.Chat: Messages you type that are not recognized commands will be relayed to other IRC users currently connected to this specific gateway instance and joined to the #meshtastic-ctrl channel.Receive Mesh Messages: Messages received from the Meshtastic network (broadcasts on configured channels or DMs addressed to the gateway node) will appear in the channel, usually prefixed with details like `[MESH Rx
