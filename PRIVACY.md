# Privacy Policy — Upkeep

_Last updated: 16 August 2026_

> **Disclaimer.** This policy may be updated from time to time. The current
> version is the one published in this document.

This policy describes how Upkeep handles data when you use it. The short
answer: **Upkeep collects nothing. It has no account, no telemetry, no
analytics and no tracking. The only data that exists is the configuration you
create locally, and the only network traffic is a check against GitHub — the
service you asked it to talk to.**

## 1. What Upkeep is

Upkeep is a local Linux desktop utility (GUI + CLI) that updates AppImages from
their GitHub releases. It runs on your machine, is installed under `~/.local`,
and does not require root privileges.

## 2. Data stored locally

Upkeep stores only the configuration and state needed for its function, all on
**your machine**:

- **Configuration** — `~/.config/upkeep/config.json` (or
  `$XDG_CONFIG_HOME/upkeep/config.json`), containing:
  - your settings (default install folder, tracker folder, default
    architecture, check-on-startup, confirm-download, create-desktop-entries);
  - the list of managed apps: display name, GitHub repository (`owner/repo`),
    install folder, optional custom path, optional asset filter (regex), target
    architecture, auto-update flag and enabled flag.
- **Version tracker files** — one plain-text file per app under
  `~/.cache/appimage_tracker_<name>.txt` (or your tracker folder), containing
  the last installed version tag, so Upkeep knows when an update is available.
- **Downloaded AppImages** — the binaries themselves, in your install folder
  (default: `~/.local/share/applications/Appimages/`), plus extracted icons
  under `~/.local/share/upkeep/icons/` and `.desktop` menu entries under
  `~/.local/share/applications/`.
- **Installed program files** — Upkeep's own code and launchers under
  `~/.local/lib/upkeep` and `~/.local/bin`, plus its icons and menu entry.

This data is purely functional. Upkeep stores **no secrets, tokens, credentials
or personal information**. The uninstaller removes Upkeep's own files and asks
before deleting your configuration and tracker files; the AppImage binaries
themselves are never touched.

## 3. Network access

Upkeep's only outbound traffic occurs when you run a check or an update:

- **GitHub REST API** (`https://api.github.com/repos/{owner}/{repo}/releases/latest`):
  Upkeep asks GitHub for the latest release of each configured repository. The
  request identifies the app by a simple `User-Agent: upkeep/1.0.0` header and
  is made **without authentication**. GitHub's servers may observe routine
  connection data (such as your IP address) and apply its public rate limits,
  under GitHub's own privacy practices and Terms of Service.
- **Asset downloads**: the download URL returned by GitHub
  (`browser_download_url`, typically under `github.com`, possibly redirecting
  to `objects.githubusercontent.com`). The AppImage binary is downloaded over
  **HTTPS**.

There is **no telemetry, no analytics, no crash reporting and no other
endpoint**. Upkeep does not contact any server of its own — the author runs no
server and receives no data from you. The only remote party in the loop is
**GitHub**, and only because that is where the applications you configured
publish their releases.

## 4. Data shared with third parties

- **GitHub**: receives the repository identifiers you configured (embedded in
  the API URL) and observes routine connection data during checks and
  downloads. This is inherent to the tool's function.
- **No one else**: Upkeep shares nothing with any other party. It contains no
  advertising, analytics or tracking code.

## 5. Permissions

Upkeep requests **no special permissions**. It operates within your normal user
account on:

- your configuration and cache directories;
- the folders where you install AppImages;
- the GitHub API (outbound HTTPS).

It never runs with elevated privileges and never installs anything
system-wide.

## 6. Backup and deletion

Upkeep does not back up or transmit your data anywhere. To remove all traces of
it, run `uninstall.sh`: it removes Upkeep's own files, and — after asking you —
your configuration and tracker files. Downloaded AppImages are yours and are
left untouched.

## 7. Children's privacy

Upkeep is a developer/system utility. It does not target children and does not
collect any personal data from any user, regardless of age.

## 8. Good faith

Upkeep is designed and maintained in good faith:

- it collects **nothing** from you and runs **no server** of its own;
- it communicates only with GitHub, and only to check for and apply updates to
  the repositories **you** configured;
- it is fully open source under the **GPL-3.0-or-later**, so anyone can verify
  what it does (or does not) do with data;
- it transparently documents that downloaded applications are **not
  signature-verified** and that you should only use sources you trust.

For the legal assessment of the project, its licensing, and your responsibility
for the software you download, see **[LEGAL.md](LEGAL.md)**.