# Makefile walkthrough

Waydroid is pure Python plus shell scripts — there is nothing to compile, so
the Makefile is install plumbing only. `make build` is a stub; the real work
happens in `make install` (and `make install_apparmor`), with `make check`
for local validation that mirrors CI.

## Variables

| Variable | Default | Meaning |
| --- | --- | --- |
| `PREFIX` | `/usr` | Install prefix; nearly every other path derives from it. |
| `SYSCONFDIR` | `/etc` | System config dir; used only for xdg menus and AppArmor. |
| `USE_SYSTEMD` | `1` | Install `systemd/waydroid-container.service`. |
| `USE_DBUS_ACTIVATION` | `1` | Install the D-Bus `system-services` activation file. |
| `USE_NFTABLES` | `0` | Flip `data/scripts/waydroid-net.sh` to nftables at install time. |
| `PYTHON` | `python3` | Interpreter used by `make check` (override for a venv). |
| `DESTDIR` | *(unset)* | Packaging prefix; honored but not declared. |

The `?=` variables can be overridden per invocation, e.g.:

```sh
make install USE_SYSTEMD=0
make check PYTHON=/path/to/venv/bin/python
```

## Derived paths

`WAYDROID_DIR = $(PREFIX)/lib/waydroid`, `BIN_DIR = $(PREFIX)/bin`,
`APPS_DIR = $(PREFIX)/share/applications`, `APPS_DIRECTORY_DIR`,
`APPS_MENU_DIR = $(SYSCONFDIR)/xdg/menus/applications-merged`,
`METAINFO_DIR`, `ICONS_DIR`, `SYSD_DIR = $(PREFIX)/lib/systemd/system`,
`DBUS_DIR = $(PREFIX)/share/dbus-1`, `POLKIT_DIR = $(PREFIX)/share/polkit-1`,
`APPARMOR_DIR = $(SYSCONFDIR)/apparmor.d`.

Each has a `INSTALL_* = $(DESTDIR)$(...)` counterpart, which is what makes
`make install DESTDIR=...` work for packaging.

## Targets

### `make build`

Placeholder: prints "Nothing to build, run 'make install' to copy the files!".

### `make check`

Runs `ruff check .` followed by `$(PYTHON) -m pytest -q`. This mirrors the
`lint` and `test` jobs in `.github/workflows/check.yaml` (which additionally
run CodeQL). Use `PYTHON=...` to point at a specific interpreter.

### `make install`

Runs in this order:

1. **Create directories** — the full install tree (lib/waydroid, bin, dbus
   system.d, polkit actions, applications, xdg menu/directory dirs, metainfo,
   hicolor 512x512 icons).
2. **Copy the source tree** — `cp -a data tools waydroid.py` into
   `$(PREFIX)/lib/waydroid`.
3. **Create the `waydroid` binary** — a *relative* symlink
   (`bin/waydroid -> ../lib/waydroid/waydroid.py`, computed with
   `realpath --relative-to`), so it survives `DESTDIR` relocation.
4. **Move data files to their destinations** — AppIcon.png to the hicolor
   icon theme, `*.desktop` to applications, `*.menu`/`*.directory` to the xdg
   dirs, `*.metainfo.xml` to metainfo. These are *moved*, so after install
   the copy of `data/` under `lib/waydroid` no longer contains them.
5. **D-Bus + polkit** — `id.waydro.Container.conf` to `system.d` and
   `id.waydro.Container.policy` to polkit actions.
6. **Optional: D-Bus activation** (`USE_DBUS_ACTIVATION=1`) — renders
   `id.waydro.Container.service` into `system-services`, substituting the
   `@BINDIR@` placeholder with `$(BIN_DIR)`.
7. **Optional: systemd unit** (`USE_SYSTEMD=1`) — renders
   `waydroid-container.service` into the systemd system dir with the same
   `@BINDIR@` substitution.
8. **Optional: nftables** (`USE_NFTABLES=1`) — `sed` flips `LXC_USE_NFT`
   from `false` to `true` **in the installed copy** of
   `data/scripts/waydroid-net.sh`. The source tree is left untouched, so the
   flag is only visible in the installed file.

### `make install_apparmor`

Installs the `adbd`, `android_app`, and `lxc-waydroid` profiles plus empty
`local/` stubs, then reloads them with `apparmor_parser -r -T -W`. The reload
is skipped when `DESTDIR` is set (packaging) or when AppArmor is not active
on the host.

## Quirks and gotchas

- **No `uninstall`, `clean`, or `dist` targets.**
- **Activation paths follow `PREFIX`**: `systemd/waydroid-container.service`
  and `dbus/id.waydro.Container.service` are templates containing the
  `@BINDIR@` placeholder, substituted with `$(BIN_DIR)` at install time (see
  steps 6–7 above). The checked-in files are therefore *not* valid unit files
  as-is — they resolve only after install (or via the same `sed`).
- **The nftables `sed` edits the installed file only** — inspecting
  `data/scripts/waydroid-net.sh` in the source tree won't show `LXC_USE_NFT=true`.
- **`mv` semantics**: after `make install`, the installed `data/` directory
  is missing the desktop/menu/metainfo files — that is by design; the
  installed tree is a deployment artifact, not a copy of the source tree.
- **AppArmor reload is packaging-safe** — the `apparmor_parser` invocation
  only runs when `DESTDIR` is empty and AppArmor is enabled, so distro builds
  never touch the host's loaded profiles.
