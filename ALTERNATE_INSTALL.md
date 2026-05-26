# Alternate Installation Methods

The supported and recommended way to run gamma-launcher is the container workflow in
[README.md](README.md). These alternate methods are kept for users who explicitly
want to manage native dependencies themselves.

## Using pip from source

It is strongly advised to install this in a
[venv](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/#creating-a-virtual-environment)
(Python Virtual Environment).

Open a terminal in the downloaded `gamma-launcher` folder and create a virtual
environment:

```sh
python3 -m venv env
```

On Windows, use:

```sh
py -m venv env
```

Enter the virtual environment:

```sh
source env/bin/activate
```

On Windows, use:

```powershell
.\env\Scripts\activate
```

To confirm that you are in the right place, run `which python` on Linux or
`where python` on Windows. It should print a path under the virtual environment.

You may need to upgrade pip first:

```sh
pip install --upgrade pip
```

Then install gamma-launcher:

```sh
pip install .
```

You can leave the virtual environment with:

```sh
deactivate
```

## Using easy-install

`easy-install` builds and installs a local Python environment, `7z`, and
`libunrar.so`. It downloads source archives directly from the dependency
maintainer sites, so prefer the container workflow when reproducibility and
supply-chain control matter.

Make sure you have a toolchain available to compile `7z` and `libunrar.so`, and
that `python3-venv` is installed:

```sh
cd easy-install
make -j$(nproc)
sudo make install
```

For more details, see [easy-install/README.md](easy-install/README.md).

## Using release

By downloading gamma-launcher from the
[latest release](https://github.com/Mord3rca/gamma-launcher/releases/latest), you
can use it without installing Python dependencies yourself. Everything is self
contained in an executable. Releases are built with Ubuntu.

Use the `--cache-directory` option to reuse previously downloaded files.

## Using AUR (Arch Linux)

This installation method is not supported on this repo. Contact the
[AUR maintainers](https://aur.archlinux.org/packages/gamma-launcher) for issues
with this package.

On Arch Linux and Arch-based operating systems, you can install the AUR package:

```sh
yay -S gamma-launcher
```

Use at your own risk.

Or build it yourself:

```sh
git clone https://aur.archlinux.org/gamma-launcher.git
cd gamma-launcher
makepkg -sri
```

## Native dependency troubleshooting

### Glibc Errors

Install gamma-launcher in a venv. See [Using pip from source](#using-pip-from-source).

### ModuleNotFoundError: No module named 'distutils'

The `distutils` module is required to install Python packages but was removed in
Python 3.12. You can still use it by installing `setuptools` inside the venv:

```sh
pip install setuptools
```

### LookupError: Couldn't find path to unrar library.

You are missing a library that extracts RAR files. You can use something like
`libunrar` on Linux:

- On Debian, with the non-free APT repository enabled: `sudo apt install libunrar5`
- On Ubuntu: `sudo apt install libunrar5t64`
- On Fedora, with non-free RPM Fusion enabled: `sudo dnf install libunrar`
- On Arch/Manjaro: `sudo pacman -S libunrar`
