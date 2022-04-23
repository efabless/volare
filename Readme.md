<h1 align="center">⛰️ Volare</h1>
<p align="center">
    <a href="https://opensource.org/licenses/Apache-2.0"><img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License: Apache 2.0"/></a>
    <img src="https://github.com/efabless/volare/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI Status" />
    <a href="https://invite.skywater.tools"><img src="https://img.shields.io/badge/Community-Skywater%20PDK%20Slack-ff69b4?logo=slack" alt="Invite to the Skywater PDK Slack"/></a>
    <a href="https://github.com/psf/black"><img src="https://img.shields.io/badge/code%20style-black-000000.svg" alt="Code Style: Black"/></a>
</p>

<p align="center">Volare is a version manager (and builder) for the builds of the Google/Skywater sky130 PDK using open_pdks.</p>

# Requirements
* Python 3.6+ with PIP

# Installation
```sh
python3 -m pip install --upgrade --no-cache-dir volare
```

# About the builds
In its current inception, volare supports builds of the sky130 PDK using [Open_PDKs](https://github.com/efabless/open_pdks), including the following libraries:
* sky130_fd_io
* sky130_fd_pr
* sky130_fd_sc_hd
* sky130_fd_sc_hvl
* sky130 sram modules

All PDKs are identified by their **open_pdks** version.

# Usage
Volare requires a so-called **PDK Root**. This PDK root can be anywhere on your computer, but by default it's the folder `~/.volare` in your home directory. If you have the variable `PDK_ROOT` set, volare will use that instead. You can also manually override both values by supplying the `--pdk-root` commandline argument.

## Listing Installed PDKs
Simply typing `volare` in the terminal shows you your PDK Root and the PDKs you currently have installed.

```sh
$ volare
/home/test/.volare
├── 5890e791e37699239abedfd2a67e55162e25cd94 (enabled)
├── 660c6bdc8715dc7b3db95a1ce85392bbf2a2b195
├── 05af1d05227419f0955cd98610351f4680575b95
└── 8fe7f760ece2bb49b1c310e60243f0558977dae5
```

## Listing All Available PDKs
To list all available pre-built PDKs, you can just invoke `volare list`.

```sh
$ volare list
Pre-built PDKs
├── 8fe7f760ece2bb49b1c310e60243f0558977dae5 (installed)
├── 7519dfb04400f224f140749cda44ee7de6f5e095
├── 660c6bdc8715dc7b3db95a1ce85392bbf2a2b195 (installed)
├── 5890e791e37699239abedfd2a67e55162e25cd94 (enabled)
└── 05af1d05227419f0955cd98610351f4680575b95 (installed)
```

## Downloading and Enabling PDKs
You can enable a particular sky130 PDK by invoking `volare enable <open_pdks version>`. This will automatically download that particular version of the PDK, if found, and set it as your currently used PDK.

For example, to enable open_pdks `7519dfb04400f224f140749cda44ee7de6f5e095`, you invoke `volare enable 7519dfb04400f224f140749cda44ee7de6f5e095`, as shown below:

```sh
$ volare enable 7519dfb04400f224f140749cda44ee7de6f5e095
Downloading pre-built tarball for 7519dfb04400f224f140749cda44ee7de6f5e095… ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
Unpacking…                                                                  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
PDK version 7519dfb04400f224f140749cda44ee7de6f5e095 enabled.
```

What's more is: if you're using a repository with a `tool_metadata.yml` file, such as [OpenLane](https://github.com/The-OpenROAD-Project/OpenLane) or [DFFRAM](https://github.com/Cloud-V/DFFRAM), you can just invoke `volare enable` without any arguments and Volare will automatically infer the version you're looking folder.

## Building PDKs
For special cases, i.e. you require other libraries, you'll have to build the PDK yourself, which Volare does support.

It does require Docker 19.04 or higher, however.

You can invoke `volare build --help` for more options. Be aware, the built PDK won't automatically be enabled and you'll have to `volare enable` the appropriate version.

# License
The Apache License, version 2.0. See 'License'.
