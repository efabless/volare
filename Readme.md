# [WIP] Volare
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0) [![Slack Invite](https://img.shields.io/badge/Community-Skywater%20PDK%20Slack-ff69b4?logo=slack)](https://invite.skywater.tools)  [![code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) <!-- ![CI Badge](https://github.com/efabless/volare/actions/workflows/ci.yml/badge.svg?branch=main)  -->

Volare is a work-in-progress builder and version manager for the builds of the sky130 pdk.

It only works with portable versions of the sky130 open_pdk builds.

# Requirements
* Python 3.6+ with PIP

# Installation
```sh
python3 -m pip install git+https://github.com/efabless/volare
```

We're looking to make it available in the primary PIP repositories as soon as CI is finished.

# Usage
Volare requires a so-called **PDK Root**. This PDK root can be anywhere on your computer, but by default it's the folder `pdks` in your home directory. If you have the variable `PDK_ROOT` set, volare will use that instead. You can also manually override both values by supplying the `--pdk-root` commandline argument.

## Downloading and Enabling PDKs
In its current inception, volare supports builds of the sky130 PDK using [Open_PDKs](https://github.com/RTimothyEdwards/), including the following libraries:
* sky130_fd_io
* sky130_fd_pr
* sky130_fd_sc_hd
* sky130_fd_sc_hvl
* sky130 sram modules

You can enable a particular sky130 PDK by invoking `volare enable <open_pdks version>`. This will automatically download that particular version of the PDK, if found, and set it as your currently used PDK.

For example, to enable open_pdks `4040b7ca03d03bbbefbc8b1d0f7016cc04275c24`, you invoke `volare enable 4040b7ca03d03bbbefbc8b1d0f7016cc04275c24`.

Of course, this isn't 100% ideal. If you're using a repository with a tool_metadata.yml file, such as [OpenLane](https://github.com/The-OpenROAD-Project/OpenLane) or [DFFRAM](https://github.com/Cloud-V/DFFRAM), you can just invoke `volare enable` and Volare will automatically infer the version you're looking folder.

## Listing PDKs
Invoking Volare in a terminal will look something like this:

```
/usr/local/pdk/volare/versions
├── 4040b7ca03d03bbbefbc8b1d0f7016cc04275c24 (enabled)    
└── 34eeb2743e99d44a21c2cedd467675a2e0f3bb91
```

Where the first path has all the versions installed.

## Building PDKs
For special cases, i.e. you require other libraries, you'll have to build the PDK yourself, which Volare does support.

It does require Docker 19.04 or higher, however. 

You can invoke `volare build --help` for more options. Be aware, the built PDK won't automatically be enabled and you'll have to `volare enable` the appropriate version.

# License
The Apache License, version 2.0. See 'License'.