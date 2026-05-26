# Contributing

Feel free to contribute to this project by creating a pull request or an issue.

However, some listed subject here are not welcome...

## Packaging

The de-facto installation and test environment for this project is the bundled
Podman/Docker image. It is the preferred way to run gamma-launcher because it
keeps `7z`, `libunrar`, Firefox, noVNC, and Python dependencies reproducible
without relying on distro-specific packages.

Adding a new packaging system should be avoided. The only packaging maintained
by this project is:

* Podman/Docker image
* pip installation
* pyinstaller release builds
* easy-install, as an alternate native install path

If you want to add your own, fork this repo and add it. The only thing you will be allowed
to merge to this is a reference in README.md to point to your new packaging system (ex: AUR packaging).

In any case, no issues / PR related to your installation method will be accepted here.

Native installation methods belong in [ALTERNATE_INSTALL.md](ALTERNATE_INSTALL.md).
Do not make native distro setup the primary README flow.

## Libunrar

Yes, **libunrar** can be a pain for some distros. That is why the container
workflow is the default documented installation path.

If your distro does not distribute it, prefer the Podman/Docker workflow. Use
*easy-install* only when you explicitly want a native install and accept that it
downloads dependency source archives directly from upstream maintainer sites.

### But why not rarfile ?

Slow as fuck. Will decompress each file one by one ... making a `fork()` for each one.
See [#127 (comment)](https://github.com/Mord3rca/gamma-launcher/issues/127#issuecomment-2197656991)

### And why not 7z for all type of archive ?

Yeah ... It may work on your distro, but you are not alone.
See [#240 (comment)](https://github.com/Mord3rca/gamma-launcher/pull/240#issuecomment-3482497749)
