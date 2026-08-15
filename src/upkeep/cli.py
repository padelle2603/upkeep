# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 padelle2603
# Upkeep: automatically update AppImages from GitHub releases.
# Licensed under the GNU GPL v3 or later; see LICENSE and NOTICE.

import argparse
import sys

from . import config
from . import updater
from . import github
from . import term

STATE_ICON = {
    "outdated": "\U0001f4e6",
    "uptodate": "\u2705",
    "error": "\u274c",
    "updated": "\u2705",
    "skipped": "\u23ed\ufe0f",
    "missing": "\u26a0\ufe0f",
}


def cmd_list(cfg, args):
    apps = cfg["apps"]
    if not apps:
        print("No apps configured. Use 'add' or the GUI.")
        return 0
    rows = []
    for a in apps:
        local = config.read_local_version(a, cfg["settings"]) or "-"
        target = config.app_target_path(a)
        exists = __import__("os").path.exists(target)
        installed = term.green("yes") if exists else term.red("no")
        rows.append((a["name"], a["repo"], a.get("arch") or "x86_64", local, target, installed))
    term.print_table(rows, ["Name", "Repo", "Arch", "Local", "Path", "Installed"])
    return 0


def cmd_check(cfg, args):
    apps = cfg["apps"]
    if not apps:
        print("No apps configured. Use 'add' or the GUI.")
        return 0
    rows = []
    errors = 0
    outdated = 0
    for a in apps:
        if not a.get("enabled", True):
            continue
        r = updater.check_app(a, cfg["settings"])
        remote = (r.info or {}).get("tag") if r.info else None
        name = term.state_color(r.state)(STATE_ICON[r.state] + " " + a["name"])
        if r.state == "error":
            errors += 1
            rows.append((name, a["repo"], term.red(r.message or "error")))
        else:
            if r.state in ("outdated", "missing"):
                outdated += 1
            status = term.state_color(r.state)(r.message)
            rows.append((name, r.version or "-", remote or "-", status))
    term.print_table([r for r in rows if len(r) == 4], ["App", "Local", "Remote", "Status"])
    if errors:
        term.print_table([r for r in rows if len(r) == 3], ["App", "Repo", "Error"])
    summary = f"{len(rows)} apps checked"
    if outdated:
        summary += f", {term.yellow(str(outdated) + ' to fix')}"
    if errors:
        summary += f", {term.red(str(errors) + ' errors')}"
    print("\n" + summary + ".")
    if errors:
        return 1
    return 2 if outdated else 0


def _confirm(app, info, missing=False):
    verb = "Reinstall" if missing else "Update"
    print(f"\n\U0001f680 {verb} {app['name']} to version {info['tag']}? [y/N]: ", end="", flush=True)
    ans = input().strip().lower()
    return ans in ("y", "yes")


def cmd_update(cfg, args, skip_confirm=False):
    apps = cfg["apps"]
    if not apps:
        print("No apps configured.")
        return 1
    names = set(args.names)
    targets = [a for a in apps if (not names or a["name"] in names) and a.get("enabled", True)]
    if names:
        missing = names - {a["name"] for a in apps}
        if missing:
            print("Apps not found: " + ", ".join(sorted(missing)))
    if not targets:
        print("No apps to update.")
        return 0
    result = 0
    applied = 0
    uptodate = 0
    errors = 0
    had_auto = False
    bar = term.Progress()
    for a in targets:
        confirm = None if (skip_confirm or a.get("auto_update")) else _confirm
        is_auto = confirm is None

        def _progress(done, total, label=a["name"]):
            bar.update(done, total, label=label)

        r = updater.update_app(a, cfg["settings"], confirm_fn=confirm, progress_cb=_progress)
        if is_auto:
            had_auto = True
            if r.state == "updated":
                applied += 1
            elif r.state == "uptodate":
                uptodate += 1
            elif r.state == "error":
                errors += 1
                result = 1
                print(f"{term.red(STATE_ICON['error'])} {term.bold(a['name'])}: {r.message}", file=sys.stderr)
            elif r.state == "skipped":
                pass
            continue
        if r.state == "updated":
            applied += 1
            print(f"{term.green(STATE_ICON['updated'])} {term.bold(a['name'])} -> {term.green(r.version)}")
        elif r.state == "uptodate":
            print(f"{term.green(STATE_ICON['uptodate'])} {term.bold(a['name'])}: up to date ({r.version})")
        elif r.state == "skipped":
            print(f"{term.yellow(STATE_ICON['skipped'])} {term.bold(a['name'])}: skipped")
        elif r.state == "error":
            result = 1
            print(f"{term.red(STATE_ICON['error'])} {term.bold(a['name'])}: {r.message}", file=sys.stderr)
    if had_auto:
        bar.finish()
        parts = [term.green(str(applied) + " aggiornate")]
        if uptodate:
            parts.append(term.yellow(str(uptodate) + " già aggiornate"))
        if errors:
            parts.append(term.red(str(errors) + " errori"))
        print("\n" + ", ".join(parts) + ".")
    if applied:
        return 2
    return result


def cmd_add(cfg, args):
    name = args.name
    if not name:
        print("Specify --name", file=sys.stderr)
        return 1
    if not args.repo:
        print("Specify --repo (owner/repo format)", file=sys.stderr)
        return 1
    if args.repo.startswith("http"):
        parts = [p for p in args.repo.split("/") if p]
        if len(parts) >= 2:
            args.repo = parts[-2] + "/" + parts[-1]
    app = config.normalize_app({
        "name": name,
        "repo": args.repo,
        "install_dir": config.expand(args.dir) if args.dir else None,
        "custom_path": config.expand(args.path) if args.path else None,
        "asset_filter": args.filter or "",
        "arch": args.arch or cfg["settings"].get("default_arch") or "x86_64",
        "auto_update": args.auto,
        "enabled": True,
    })
    for i, a in enumerate(cfg["apps"]):
        if a["name"] == name:
            cfg["apps"][i] = app
            config.save_config(cfg)
            print(term.green("Updated app") + f" '{term.bold(name)}'.")
            return 0
    cfg["apps"].append(app)
    config.save_config(cfg)
    print(term.green("Added app") + f" '{term.bold(name)}' ({args.repo}).")
    return 0


def cmd_remove(cfg, args):
    before = len(cfg["apps"])
    found = [a for a in cfg["apps"] if a["name"] == args.name]
    cfg["apps"] = [a for a in cfg["apps"] if a["name"] != args.name]
    if len(cfg["apps"]) == before:
        print(term.red(f"App '{args.name}' not found."))
        return 1
    for a in found:
        updater.remove_desktop_entry(a)
    config.save_config(cfg)
    print(term.green("Removed app") + f" '{term.bold(args.name)}'.")
    return 0


def cmd_show(cfg, args):
    for a in cfg["apps"]:
        if a["name"] == args.name:
            local = config.read_local_version(a, cfg["settings"]) or "-"
            target = config.app_target_path(a)

            def kv(label, value, color=term.cyan):
                return f"{term.bold(label):<14}{color(value)}"

            print(kv("Name:", a["name"], term.bold))
            print(kv("Repo:", a["repo"], term.bold))
            print(kv("Arch:", a.get("arch")))
            print(kv("Filter:", a.get("asset_filter") or "-"))
            print(kv("Install dir:", a.get("install_dir") or "(default)"))
            print(kv("Custom path:", a.get("custom_path") or "-"))
            print(kv("Path:", target))
            print(kv("Version:", local))
            print(kv("Auto:", "yes" if a.get("auto_update") else "no"))
            try:
                info = updater.latest_info(a)
                print(kv("Latest:", f"{info['tag']} ({info['asset_name']})"))
            except github.GitHubError as e:
                print(kv("Latest:", f"error -> {e}", term.red))
            return 0
    print(term.red(f"App '{args.name}' not found."))
    return 1


def build_parser():
    p = argparse.ArgumentParser(prog="upkeep", description="AppImage update manager from GitHub.")
    sub = p.add_subparsers(dest="command")

    sub.add_parser("list", help="List configured apps and their local version.")

    c = sub.add_parser("check", help="Check GitHub for available updates.")
    c.set_defaults(fn=cmd_check)

    c = sub.add_parser("update", help="Update one or more apps (all if no name).")
    c.add_argument("names", nargs="*")
    c.add_argument("-y", "--yes", action="store_true", help="Do not ask for confirmation")
    c.set_defaults(fn=cmd_update)

    c = sub.add_parser("sync", help="Sync local versions with the latest releases (update all without confirmation).")
    c.add_argument("-y", "--yes", action="store_true")
    c.set_defaults(fn=cmd_sync)

    c = sub.add_parser("add", help="Add or update an app.")
    c.add_argument("--name", required=True)
    c.add_argument("--repo", required=True)
    c.add_argument("--dir", help="Installation folder")
    c.add_argument("--path", help="Custom AppImage file path")
    c.add_argument("--filter", help="Regex to select the asset")
    c.add_argument("--arch", choices=config.ARCHS)
    c.add_argument("--auto", action="store_true", help="Update without asking for confirmation")
    c.set_defaults(fn=cmd_add)

    c = sub.add_parser("remove")
    c.add_argument("name")
    c.set_defaults(fn=cmd_remove)

    c = sub.add_parser("show")
    c.add_argument("name")
    c.set_defaults(fn=cmd_show)

    return p


def cmd_sync(cfg, args):
    args.names = []
    return cmd_update(cfg, args, skip_confirm=True)


def main(argv=None):
    try:
        parser = build_parser()
        args = parser.parse_args(argv)
        cfg = config.load_config()
        if not args.command:
            parser.print_help()
            return 0
        if args.command == "list":
            return cmd_list(cfg, args)
        return args.fn(cfg, args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())