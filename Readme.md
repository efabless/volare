# [WIP] Volare
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0) [![Slack Invite](https://img.shields.io/badge/Community-Skywater%20PDK%20Slack-ff69b4?logo=slack)](https://invite.skywater.tools)  [![code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) <!-- ![CI Badge](https://github.com/efabless/volare/actions/workflows/ci.yml/badge.svg?branch=main)  -->

Volare is a work-in-progress builder and version manager for the builds of the sky130 pdk.

It only works with portable versions of the sky130 open_pdk builds.

# Requirements
## Getting and Using PDKs
* Python 3.6+ with PIP

## Building PDKs:
* Python 3.6+ with PIP
* Docker 19+

# Installation
```sh
python3 -m pip install volare
```

# Usage
**tl;dr invoke `volare enable` in your OpenLane repository**

In its current inception, volare supports builds of the sky130** PDK using [Open_PDKs](https://github.com/RTimothyEdwards/), including the following libraries:
* sky130_fd_io
* sky130_fd_pr
* sky130_fd_sc_hd
* sky130_fd_sc_hvl
* sky130 sram modules

(to be continued)


# License
The Apache License, version 2.0. See 'License'.