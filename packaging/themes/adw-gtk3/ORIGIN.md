# adw-gtk3 — vendored GTK3 theme

This directory is a **verbatim, unmodified** copy of the `adw-gtk3` GTK3
theme. Upkeep ships it inside the AppImage so the window has the GNOME 45
look on every machine, not only on the ones where the theme is packaged.

| | |
|---|---|
| Upstream | https://github.com/lassekongo83/adw-gtk3 |
| Version | 6.5 (Arch package `adw-gtk-theme` 6.5-1) |
| License | LGPL-2.1-only (see `LICENSE`) |
| Modifications | none |
| What is copied | `index.theme`, `gtk-3.0/gtk.css`, `gtk-3.0/gtk-dark.css`, `gtk-3.0/assets/` |

`gtk-3.0/thumbnail.png` is not copied: it is a preview for theme choosers and
GTK never loads it. The `gtk-4.0/` directory of the upstream theme is not
copied either — Upkeep is a GTK3 application.

## Why the whole CSS is vendored

The theme is not a library: no code is linked, only CSS that GTK reads at
runtime. What LGPL-2.1 asks for is followed literally — this notice, a copy of
the license next to the files, and the license also travels inside the
AppImage, in `usr/share/doc/upkeep/`.

## How to update it

Replace the files with the ones from a newer release of the theme and
update the version above. The copy must stay verbatim: any modification
would make the modified files the work of whoever modified them, with its
own obligations.

## Why a theme and not libadwaita

Upkeep is GTK3. The GTK3 build of libadwaita is an unofficial port that is
not packaged on Debian or Ubuntu, and its typelib has the same name and
version as the GTK4 one, so `from gi.repository import Adw` succeeds there and
then fails at runtime. A stylesheet has no such problem: if it is missing GTK
falls back to another theme and nothing crashes.