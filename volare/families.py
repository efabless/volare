#!/usr/bin/env python3
# Copyright 2022 Efabless Corporation
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

    def __init__(self, name: str, variants: List[str]):
        self.name = name
        self.variants = variants


Family.by_name: Dict[str, Family] = {}
Family.by_name["sky130"] = Family("sky130", ["sky130A", "sky130B"])
Family.by_name["gf180mcu"] = Family("gf180mcu", ["gf180mcuA", "gf180mcuB", "gf180mcuC"])
# Family.by_name["asap7"] = Family("asap7", ["asap7"])
