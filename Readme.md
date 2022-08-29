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
# To install
python3 -m pip install --upgrade --no-cache-dir volare

# To verify it works
volare --version
```

## Troubleshooting
With a typical Python 3.6 or higher installation with PIP, installing `volare` is as simple as a `pip install`. Despite that, there are some peculiarities with PIP itself: For example, you may see an error among these lines:

```sh
  WARNING: The script volare is installed in '/home/test/.local/bin' which is not on PATH.
  Consider adding this directory to PATH or, if you prefer to suppress this warning, use --no-warn-script-location.
```

The solution is as simple as adding something like this to your shell's profile:

```sh
export PATH="/home/test/.local/bin:$PATH"
```

Do note that the path (`/home/test/.local/bin` in this example) varies depending on your operating system and version of Python you install, and whether you use `sudo` (absolutely not recommended) or not, so ensure that you actually read the warning and add the correct path.

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

## Listing All Available PDKs
To list all available pre-built PDKs hosted in this repository, you can just invoke `volare ls-remote`.

```sh
$ volare ls-remote
Pre-built sky130 PDK versions
├── 44a43c23c81b45b8e774ae7a84899a5a778b6b0b (2022.08.16) (enabled)
├── e8294524e5f67c533c5d0c3afa0bcc5b2a5fa066 (2022.07.29) (installed)
├── 41c0908b47130d5675ff8484255b43f66463a7d6 (2022.04.14) (installed)
├── 660c6bdc8715dc7b3db95a1ce85392bbf2a2b195 (2022.04.08)
├── 5890e791e37699239abedfd2a67e55162e25cd94 (2022.04.06)
├── 8fe7f760ece2bb49b1c310e60243f0558977dae5 (2022.04.06)
└── 7519dfb04400f224f140749cda44ee7de6f5e095 (2022.02.10)
```

It includes a commit hash, which is the `open_pdks` version used to build this particular PDK, the date that this commit was created, and whether you already installed this PDK and/or if it is the currently enabled PDK.

## Listing Installed PDKs
Simply typing `volare` in the terminal shows you your PDK Root and the PDKs you currently have installed.

```sh
$ volare ls
/home/test/volare/sky130/versions
├── 44a43c23c81b45b8e774ae7a84899a5a778b6b0b (2022.08.16) (enabled)
├── e8294524e5f67c533c5d0c3afa0bcc5b2a5fa066 (2022.07.29)
└── 41c0908b47130d5675ff8484255b43f66463a7d6 (2022.04.14)
```

(If you're not connected to the Internet, the release date of the commit will not be included.)


## Downloading and Enabling PDKs
You can enable a particular sky130 PDK by invoking `volare enable <open_pdks version>`. This will automatically download that particular version of the PDK, if found, and set it as your currently used PDK.

For example, to enable open_pdks `7519dfb04400f224f140749cda44ee7de6f5e095`, you invoke `volare enable 7519dfb04400f224f140749cda44ee7de6f5e095`, as shown below:

```sh
$ volare enable 7519dfb04400f224f140749cda44ee7de6f5e095
Downloading pre-built tarball for 7519dfb04400f224f140749cda44ee7de6f5e095… ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
Unpacking…                                                                  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
PDK version 7519dfb04400f224f140749cda44ee7de6f5e095 enabled.
```

What's more is: if you're using a repository with a `tool_metadata.yml` file, such as [OpenLane](https://github.com/The-OpenROAD-Project/OpenLane) or [DFFRAM](https://github.com/Cloud-V/DFFRAM), you can just invoke `volare enable` without any arguments and Volare will automatically extract the version required by the utility.

## Building PDKs
For special cases, i.e. you require other libraries, you'll have to build the PDK yourself, which Volare does support.

It does require Docker 19.04 or higher, however.

You can invoke `volare build --help` for more options. Be aware, the built PDK won't automatically be enabled and you'll have to `volare enable` the appropriate version.

# License
The Apache License, version 2.0. See 'License'.
