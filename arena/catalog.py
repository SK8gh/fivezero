"""
    model catalog displayed in the "ava" (AI vs AI) menu
"""

# library imports
from __future__ import annotations

from typing import List

# module imports
from engine import EngineSpec


MODEL_CATALOG: List[EngineSpec] = [
    # main production version: full-board scan at every leaf
    EngineSpec(
        id="1.0",
        blurb="PROD",
        params={}
    ),

    EngineSpec(
        id="1.0",
        blurb="PROD",
        params={}
    ),
]
