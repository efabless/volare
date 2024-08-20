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
from typing import Iterable, List, Dict, Optional, Set


class Family(object):
    by_name: Dict[str, "Family"] = {}

    def __init__(
        self,
        *,
        name: str,
        variants: List[str],
        all_libraries: List[str],
        default_variant: Optional[str] = None,
        default_includes: Optional[List[str]] = None,
    ):
        self.name = name
        self.variants = variants
        self.all_libraries = all_libraries
        self.default_variant = default_variant or variants[0]
        self.default_includes = default_includes or all_libraries.copy()

    def resolve_libraries(
        self,
        input: Optional[Iterable[str]],
    ) -> Set[str]:
        if input is None:
            input = ("default",)
        final_set: Set[str] = set()
        for element in input:
            if element.lower() == "all":
                final_set = set(self.all_libraries)
                return final_set
            elif element.lower() == "default":
                final_set = final_set.union(set(self.default_includes))
            elif element in self.all_libraries:
                final_set.add(element)
            else:
                raise ValueError(f"Unknown library {element} for PDK {self.name}")
        return final_set


Family.by_name = {}
Family.by_name["sky130"] = Family(
    name="sky130",
    variants=["sky130A", "sky130B"],
    default_variant="sky130A",
    all_libraries=[
        "sky130_fd_io",
        "sky130_fd_pr",
        "sky130_ml_xx_hd",
        "sky130_fd_sc_hd",
        "sky130_fd_sc_hdll",
        "sky130_fd_sc_lp",
        "sky130_fd_sc_hvl",
        "sky130_fd_sc_ls",
        "sky130_fd_sc_ms",
        "sky130_fd_sc_hs",
        "sky130_sram_macros",
        "sky130_fd_pr_reram",
    ],
    default_includes=[
        "sky130_fd_io",
        "sky130_fd_pr",
        "sky130_fd_sc_hd",
        "sky130_fd_sc_hvl",
        "sky130_ml_xx_hd",
        "sky130_sram_macros",
    ],
)
Family.by_name["gf180mcu"] = Family(
    name="gf180mcu",
    variants=["gf180mcuA", "gf180mcuB", "gf180mcuC", "gf180mcuD"],
    default_variant="gf180mcuD",
    all_libraries=[
        "gf180mcu_fd_io",
        "gf180mcu_fd_pr",
        "gf180mcu_fd_sc_mcu7t5v0",
        "gf180mcu_fd_sc_mcu9t5v0",
        "gf180mcu_fd_ip_sram",
        "gf180mcu_osu_sc_gp12t3v3",
        "gf180mcu_osu_sc_gp9t3v3",
    ],
    default_includes=[
        "gf180mcu_fd_io",
        "gf180mcu_fd_pr",
        "gf180mcu_fd_sc_mcu7t5v0",
        "gf180mcu_fd_sc_mcu9t5v0",
        "gf180mcu_fd_ip_sram",
    ],
)
