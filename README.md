# Upkeep

Automatically update AppImage applications from their GitHub releases, with a
GTK3 graphical interface and a command-line tool. Designed for x86-64
AppImages (filterable via checkbox) and arm64.

> Upkeep was previously known as "AppImage Updater". It is an independent
> implementation inspired by the general concept popularised by Shelly
> and by a personal update script. See [NOTICE](NOTICE).

## Requirements

- Python 3 (>= 3.9)
- PyGObject / `python-gobject` (GUI only, not needed for the AppImage)
- No other tools: it uses the standard library (`urllib`, `http.client`)

## Installation

Download the **AppImage** from [Releases](https://github.com/padelle2603/upkeep/releases):

```bash
chmod +x Upkeep-*-x86_64.AppImage
./Upkeep-*-x86_64.AppImage
```

No installer, no `sudo`, no Python environment: the AppImage carries Python,
PyGObject and GTK3. Run it with arguments for the CLI (`./Upkeep-*.AppImage
list`), without for the GUI.

## Uninstall

Delete the AppImage file. Your configuration lives in `~/.config/upkeep/` and
your version trackers in `~/.cache/appimage_tracker_*.txt`; remove those too if
you want a clean slate. AppImages Upkeep manages are yours and are never
touched.

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
globally with the `create_desktop` setting (default `true`), and per app with
the "Create a .desktop entry for this app" checkbox in the add/edit dialog or
with `upkeep add --no-desktop`.

## CLI

```bash
upkeep list                       # list apps and their local versions
upkeep check                      # check GitHub for updates
upkeep update [-y] [NAME...]      # update (all or only the named ones)
upkeep sync                       # check and update everything without confirmation
upkeep add --name X --repo O/R [--dir DIR] [--path FILE] [--filter REGEX] [--arch x86_64|aarch64|any] [--auto]
upkeep remove NAME
upkeep show NAME
upkeep self                      # is a newer Upkeep release out? 0=no 10=yes 1=offline
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
- The GitHub REST API is used without authentication for the apps you manage:
  you are subject to the public rate limit (60 requests/hour per IP). Exceeding
  it is handled gracefully and reported to the user.
- Upkeep's **own** release check is deliberately not routed through that API,
  so it never spends your rate-limit budget. It is one anonymous `HEAD` to
  `github.com/padelle2603/upkeep/releases/latest`: no token, no cookies, no
  JSON, nothing written to disk. It never downloads or replaces Upkeep itself
  — the "Download" button opens the release page in your browser.
- This tool only automates downloads from the repositories you configure.
  You are responsible for complying with the license of each downloaded
  application.

## Trademark & affiliation

"AppImage" is a trademark of its respective owner. This project is not
affiliated with, endorsed by, or sponsored by the AppImage project, Shelly,
CachyOS, or GitHub.

## License

GNU General Public License v3.0 or later (GPL-3.0-or-later). See
[LICENSE](LICENSE).

*Developed with the assistance of [opencode](https://opencode.ai).*
