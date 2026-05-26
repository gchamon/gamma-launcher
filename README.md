# GAMMA Launcher

Starting G.A.M.M.A. .NET Launcher is not possible on GNU/Linux because of .NET / powershell scripts

This is a reimplementation of G.AM.M.A. launcher used for the first setup.
You will need to follow [DravenusRex's guide](https://github.com/DravenusRex/stalker-gamma-linux-guide) or
the newer [Red007Master's guide](https://github.com/Red007Master/Red-s-Guide-on-Installing-G.A.M.M.A.-on-Linux)
to have a working game.

## Table of contents

* [Installation](#installation)
  * [Build](#build)
  * [Run](#run)
  * [ModDB browser check](#moddb-browser-check)
* [Commands](#commands)
* [Troubleshoot](#troubleshoot)
* [Alternate installation methods](ALTERNATE_INSTALL.md)
* [Contributing](CONTRIBUTING.md)

## Installation

The recommended installation method is the container workflow with Podman or
Docker. It gives the launcher a reproducible Ubuntu 24.04 runtime with
`gamma-launcher`, `7z`, `libunrar`, Firefox, and noVNC already configured.

This avoids distro-specific dependency setup and avoids `easy-install`, which
downloads dependency source archives directly from upstream maintainer sites.

Native and community packaging methods are documented separately in
[ALTERNATE_INSTALL.md](ALTERNATE_INSTALL.md).

### Build

```sh
podman build -t gamma-launcher .
```

The same command works with `docker`.

### Run

Create the local folders the launcher will use, then run a full install:

```sh
mkdir -p cache Anomaly GAMMA
podman run -it --rm -p 127.0.0.1:6080:6080 -v ./:/app:Z gamma-launcher full-install \
  --anomaly ./Anomaly \
  --gamma ./GAMMA \
  --cache-directory ./cache
```

The image uses `/app` as its working directory and `gamma-launcher` as its
entrypoint, so launcher arguments are passed after the image name.

### ModDB browser check

ModDB may block automated downloads with a Cloudflare challenge. When the
launcher hits one, it spawns Firefox inside the container and serves it via
noVNC on port `6080`. Open:

```text
http://localhost:6080/vnc.html?autoconnect=1
```

Solve the challenge and wait for the download to start. The launcher keeps the
browser profile in `.moddb-firefox-profile` (under the mounted `/app`
directory) and stores completed ModDB archives under `cache/moddb/<moddb-id>/`,
so reruns reuse already-downloaded files.

## Commands

### Anomaly Install

Create an usable Anomaly installation is target directory

To setup Anomaly:  `gamma-launcher anomaly-install --anomaly <Anomaly path>`

### Check Anomaly

Verify Anomaly installation with:  `gamma-launcher check-anomaly --anomaly <Anomaly path>`

### Check MD5

This will perform a MD5 check for all ModDB addons

To run it: `gamma-launcher check-md5 --gamma <GAMMA path>`

### Full Install / Update

This will install/update all mods based on [Stalker_GAMMA](https://github.com/Grokitach/Stalker_GAMMA)

To setup/update your GAMMA folder:  `gamma-launcher full-install --anomaly <Anomaly path> --gamma <GAMMA path>`

Afterwards, you will need to start Mod Organizer and set Anomaly Path (launcher can't do that ... yet.)

### Remove ReShade

This will do remove ReShade based on [this guide](https://reshade.me/forum/general-discussion/4398-howto-uninstall-reshade)

To use it: `gamma-launcher remove-reshade --anomaly <Anomaly path>`

### Purge Shader Cache

This will delete cached shaders

To use it: `gamma-launcher purge-shader-cache --anomaly <Anomaly path>`

### USVFS Workaround

This will create a usable GAMMA installation without ModOrganizer.

DO NOT USE IT if wine is compatible with ModOrganizer, this will remove all mods flexibility.

To use it: `gamma-launcher usvfs-workaround --anomaly <Anomaly path> --gamma <GAMMA path> --final <Final Install path>`

### Test Mod Maker

This command will verify if additonal installation directives are valid
(aka folder is in the archive)

To use it: `gamma-launcher test-mod-maker --gamma <GAMMA path>`

## Troubleshoot

### Native dependency errors

If you see errors about `glibc`, `distutils`, `libunrar`, or `7z`, use the
container workflow above. Native dependency troubleshooting for alternate
installation methods lives in [ALTERNATE_INSTALL.md](ALTERNATE_INSTALL.md).

### Shader compilation error

Remove ReShade with: `gamma-launcher remove-reshade --anomaly <Anomaly path>`

Also remove some shaders mods:
* 188- Enhanced Shaders - KennShade
* 189- Beef's NVG - theRealBeef
* 190- Screen Space Shaders - Ascii1457
* 290- Atmospherics Shaders Weathers and Reshade - Hippobot

## Documentation

A documentation of launcher API can be generated with `pdoc3`

```sh
pip install pdoc3
pdoc3 --html -o doc/ launcher
```

Once executed, a *doc/* folder containing a HTML documentation will be created.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)
