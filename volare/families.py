# Copyright 2022-2023 Efabless Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from typing import List, Dict


class Family(object):
    by_name: Dict[str, "Family"] = {}

    def __init__(
        self,
        name: str,
        variants: List[str],
        default_includes: List[str],
        all_libraries: List[str],
    ):
        self.name = name
        self.variants = variants
        self.default_includes = default_includes
        self.all_libraries = all_libraries


Family.by_name = {}
Family.by_name["sky130"] = Family(
    "sky130",
    ["sky130A", "sky130B"],
    [
        "sky130_fd_io",
        "sky130_fd_pr",
        "sky130_fd_pr_reram",
        "sky130_fd_sc_hd",
        "sky130_fd_sc_hvl",
        "sky130_ml_xx_hd",
        "sky130_sram_macros",
    ],
    [
        "sky130_fd_io",
        "sky130_fd_pr",
        "sky130_fd_pr_reram",
        "sky130_ml_xx_hd",
        "sky130_fd_sc_hd",
        "sky130_fd_sc_hdll",
        "sky130_fd_sc_lp",
        "sky130_fd_sc_hvl",
        "sky130_fd_sc_ls",
        "sky130_fd_sc_ms",
        "sky130_fd_sc_hs",
        "sky130_sram_macros",
    ],
)
Family.by_name["gf180mcu"] = Family(
    "gf180mcu",
    ["gf180mcuA", "gf180mcuB", "gf180mcuC", "gf180mcuD"],
    [
        "gf180mcu_fd_io",
        "gf180mcu_fd_pr",
        "gf180mcu_fd_sc_mcu7t5v0",
        "gf180mcu_fd_sc_mcu9t5v0",
        "gf180mcu_fd_ip_sram",
    ],
    [
        "gf180mcu_fd_io",
        "gf180mcu_fd_pr",
        "gf180mcu_fd_sc_mcu7t5v0",
        "gf180mcu_fd_sc_mcu9t5v0",
        "gf180mcu_fd_ip_sram",
        "gf180mcu_osu_sc_gp12t3v3",
        "gf180mcu_osu_sc_gp9t3v3",
    ],
)
Family.by_name["asap7"] = Family(
    "asap7", ["asap7"], default_includes=[], all_libraries=[]
)
