# Legal Notice — Upkeep

_Last updated: 16 August 2026_

> **Disclaimer.** This document is provided for **informational purposes only**
> and **does not constitute legal advice**. It was not drafted by a lawyer or a
> qualified professional: the author of this document is not a legal
> practitioner. The assessments contained here are based on a reasoned
> interpretation of the applicable law and may therefore be **revised**, updated
> or corrected at any time. For binding opinions or for specific issues
> (liability, jurisdiction, commercial use) consult a qualified professional.

## 1. Premise

Upkeep is a **Linux desktop utility** that automatically updates **AppImage**
applications from their **GitHub releases**. You configure a list of AppImages
(each identified by its GitHub repository, e.g. `owner/repo`), and Upkeep checks
GitHub for the latest release, downloads the matching AppImage asset over
HTTPS, and atomically replaces the local copy. It offers both a GTK3 graphical
interface and a command-line interface.

Upkeep is an independent, from-scratch implementation inspired by similar tools
(see the NOTICE file for attribution). It is a **per-user** application
installed under `~/.local`; it does not require root privileges to run.

Upkeep is free software, licensed under the **GNU General Public License
version 3 or later (GPL-3.0-or-later)**, Copyright (C) 2026 padelle2603.

## 2. What Upkeep does — and what it does not do

Upkeep:

- checks the **GitHub REST API** for the latest release of each configured
  repository;
- selects the matching AppImage asset (by extension, architecture tokens in the
  filename, an optional regex filter, and name preference);
- **downloads** the asset over HTTPS and replaces the local AppImage;
- creates and manages `.desktop` menu entries for managed apps, extracting the
  icon from the AppImage itself via the standard `--appimage-extract`
  operation;
- tracks the installed version of each app in a plain-text tracker file.

Upkeep is a **software updater**. It does **not**:

- stream, play or download media content;
- scrape or download content from streaming services;
- circumvent technological protection measures, DRM or access controls;
- execute or modify the downloaded applications beyond what AppImage itself
  defines (updates, icon extraction and launching).

## 3. Responsibility for downloaded software

Upkeep downloads **third-party software** from repositories that **you**
configure. Upkeep cannot and does not audit the content, quality, security or
legality of those repositories or applications. You are responsible for:

- the **legality** of the software you choose to install and use;
- **compliance with the license** of each downloaded application;
- the **security** of the sources you configure (a malicious or compromised
  repository would deliver whatever its maintainers publish).

Upkeep checks for updates over **HTTPS** but does **not** verify signatures or
checksums of the downloaded assets; this is documented in the README. Upkeep
accepts **no responsibility** for the content of third-party repositories, for
what they publish, or for the consequences of installing software from them.
Please only configure repositories you trust.

## 4. GitHub and terms of service

Upkeep uses the **GitHub REST API** without authentication. Usage of the GitHub
API and of GitHub's hosting is governed by **GitHub's own Terms of Service**
and API guidelines, which apply to you when you use Upkeep. GitHub applies
public rate limits to unauthenticated requests (60 requests/hour per IP); the
API may also return errors when a release is not found or access is denied.
Upkeep handles these gracefully and reports them to you.

Upkeep is **not affiliated with, endorsed by or connected to GitHub, Inc.** or
to any of the projects it updates.

## 5. AppImage trademark and third-party marks

"AppImage" and the names of the applications Upkeep can manage are trademarks of
their respective owners. Upkeep is **not affiliated with or endorsed by** the
AppImage project or by any application maintainer. All product names, logos and
trademarks mentioned remain the property of their respective owners, and their
use in Upkeep's documentation and interface is limited to identification.

## 6. Copyright and licensing

Upkeep itself is released under the **GPL-3.0-or-later**; every source file
carries the appropriate SPDX license header. This means you may use, study,
modify and redistribute it under the terms of that license, provided you keep
the license and attribution notices intact (see NOTICE).

The applications Upkeep updates are **not part of Upkeep**: they are separate
works distributed by their own authors under their own licenses. Upkeep's
licensing has no effect on the licensing of the software it manages, and vice
versa.

## 7. No warranty

Upkeep is distributed in the hope that it will be useful, **but WITHOUT ANY
WARRANTY**; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
A PARTICULAR PURPOSE, as stated in the GNU General Public License. Use of the
software and of the downloaded applications is entirely at your own risk.

## 8. Good faith

Upkeep is developed and distributed in good faith:

- it performs a standard, openly documented function (software updating);
- it is an independent reimplementation, with proper attribution to the tools
  that inspired it;
- it communicates only with the repositories **you** configure, for the sole
  purpose of checking for and applying updates;
- it collects no data from you (see [PRIVACY.md](PRIVACY.md));
- it explicitly disclaims responsibility for third-party content and asks you
  to use it with sources you trust.