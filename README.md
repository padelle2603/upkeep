# Upkeep

Automatically update AppImage applications from their GitHub releases, with a
GTK3 graphical interface and a command-line tool. Designed for x86-64
AppImages (filterable via checkbox) and arm64.

> Upkeep was previously known as "AppImage Updater". It is an independent
> implementation inspired by the general concept popularised by Shelly and
> CachyOS and by a personal update script. See [NOTICE](NOTICE).

## Requirements

- Python 3 (>= 3.9)
- PyGObject / `python-gobject` (GUI only)
- No other tools: it uses the standard library (`urllib`)

## Installation

```bash
./install.sh
```

Installs into `~/.local`:

- `~/.local/bin/upkeep` → CLI
- `~/.local/bin/upkeep-gui` → GUI
- "Upkeep" menu entry
- logo in `~/.local/share/icons/hicolor/` (SVG + PNG 48/128/256/512), used by
  the window, HeaderBar, notifications and the menu

## Uninstall

```bash
./uninstall.sh
```

Removes the launchers, the library folder, the menu entries, the icons and
(after confirmation) the configuration and version tracker files. AppImage
files themselves are never touched.

## Configuration

Config in `~/.config/upkeep/config.json`. The version tracker uses the scheme
`~/.cache/appimage_tracker_<name>.txt`, compatible with scripts that follow
the same convention.

Each app has: name, repo (`owner/repo`), install folder, custom path
(optional), asset filter regex, architecture (`x86_64`/`aarch64`/`any`),
auto update.

### Desktop integration

When an AppImage is installed or updated, a menu entry
`~/.local/share/applications/<name>.desktop` is created with `Exec` pointing
to the AppImage and the icon extracted from the AppImage itself (fallback to
a generic icon). The entry is removed if the app is deleted. Can be disabled
with the `create_desktop` setting (default `true`).

## CLI

```bash
upkeep list                       # list apps and their local versions
upkeep check                      # check GitHub for updates
upkeep update [-y] [NAME...]      # update (all or only the named ones)
upkeep sync                       # check and update everything without confirmation
upkeep add --name X --repo O/R [--dir DIR] [--path FILE] [--filter REGEX] [--arch x86_64|aarch64|any] [--auto]
upkeep remove NAME
upkeep show NAME
```

Exit codes: `0` ok, `1` errors, `2` updates applied.

## Example

```bash
# configure an app from the console
upkeep add --name <appimage-name> --repo <user>/<repo> --arch x86_64

# sync and update everything (quick command)
upkeep sync
```

## Security & limitations

- Updates are downloaded over HTTPS from the official GitHub release assets.
- Downloaded AppImages are **not** verified against a signature or checksum;
  you should verify the integrity of the software you run yourself.
- When creating a `.desktop` entry, the AppImage is executed with
  `--appimage-extract` to extract an icon.
- The GitHub REST API is used without authentication: you are subject to the
  public rate limit (60 requests/hour per IP). Exceeding it is handled
  gracefully and reported to the user.
- This tool only automates downloads from the repositories you configure.
  You are responsible for complying with the license of each downloaded
  application.

## Trademark & affiliation

"AppImage" is a trademark of its respective owner. This project is not
affiliated with, endorsed by, or sponsored by the AppImage project, Shelly,
CachyOS, or GitHub.

## License

GNU General Public License v3.0 or later (GPL-3.0-or-later). See
[LICENSE](LICENSE) and [NOTICE](NOTICE).

## Test

```bash
PYTHONPATH=src python3 -m unittest discover tests
```
