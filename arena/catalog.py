"""
    model catalog displayed in the "ava" (AI vs AI) menu
"""

# library imports
from __future__ import annotations

from typing import List

# module imports
from engine import EngineSpec


MODEL_CATALOG: List[EngineSpec] = [
    # main production version: depth and all parameters as configured
    EngineSpec(
        id="1.0",
        blurb="PROD",
        params={
            "depth": 4
        }
    ),

    # model implementing the centrality evaluation term
    EngineSpec(
        id="1.0.1",
        blurb="+c",
        params={
            "depth": 1,
        }
    )
]