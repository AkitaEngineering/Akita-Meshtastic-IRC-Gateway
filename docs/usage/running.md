# Running the Gateway

Start the installed command:

```bash
amig
```

Use `amig --help` for all command-line overrides. Environment variables are documented in the project README.

## Local validation

Run without radio hardware using the explicit in-memory interface:

```bash
amig --mock
```

The default IRC listener is `127.0.0.1:6667`.

## Remote clients

A listener outside the loopback interface requires a TLS certificate, TLS private key, and IRC password:

```bash
export AMIG_IRC_PASSWORD='use-a-long-random-secret'
export AMIG_TLS_CERTFILE=/etc/amig/fullchain.pem
export AMIG_TLS_KEYFILE=/etc/amig/privkey.pem
amig --host 0.0.0.0
```

AMIG rejects an unprotected non-loopback listener unless `--allow-insecure-irc` is explicitly supplied. That override is only appropriate on a separately secured trusted network.

## Service management

Use systemd or another process supervisor in production. Run under a dedicated unprivileged account, grant only the necessary serial-device access, enable restart-on-failure, and capture stdout/stderr in the service manager. Stop with `SIGTERM`; AMIG disconnects IRC users, unsubscribes event listeners, closes the server socket, and closes the radio interface.
