# coding: utf-8
# Copyright (c) Mysten Labs, Inc.
# SPDX-License-Identifier: Apache-2.0

"""
Type definitions for the transaction simulator.
"""

import dataclasses
import time
from typing import Any, List, Optional, Tuple

@dataclasses.dataclass
class SimEpoch:
    """Represents a simplified Epoch for simulation purposes."""
    epoch_id: int
    epoch_start_timestamp_ms: int # Renamed from epoch_start_time_ms
    epoch_duration_ms: int
    reference_gas_price: int # Renamed from rgp

    @classmethod
    def from_sui_system_state_summary(cls, summary: Any) -> 'SimEpoch':
        """
        Placeholder method to create SimEpoch from Sui system state summary.
        TODO: Integrate with pysui's system state object.
        """
        # For now, initialize with dummy values or extract if summary is a dict
        if isinstance(summary, dict):
            return cls(
                epoch_id=int(summary.get("epoch", 0)),
                epoch_start_timestamp_ms=int(summary.get("epochStartTimestampMs", 0)),
                epoch_duration_ms=int(summary.get("epochDurationMs", 1000 * 60 * 60 * 24)), # Default to 24 hours
                reference_gas_price=int(summary.get("referenceGasPrice", 1000))
            )
        # Fallback to dummy values if summary is not a dict or keys are missing
        return cls(
            epoch_id=0,
            epoch_start_timestamp_ms=int(time.time() * 1000), # Current time as start
            epoch_duration_ms=1000 * 60 * 60 * 24, # 24 hours
            reference_gas_price=1000 # Default RGP
        )

    def is_stale(self) -> bool:
        """
        Checks if the epoch is stale based on current time.
        An epoch is stale if current_time_ms > epoch_start_timestamp_ms + epoch_duration_ms.
        """
        current_time_ms = int(time.time() * 1000)
        return current_time_ms > (self.epoch_start_timestamp_ms + self.epoch_duration_ms)

@dataclasses.dataclass
class SimulateResult:
    """Represents the result of a transaction simulation."""
    effects: Any # Placeholder for actual SuiTransactionBlockEffects
    events: Any  # Placeholder for actual SuiTransactionBlockEvents
    object_changes: List[Any] = dataclasses.field(default_factory=list)
    balance_changes: List[Any] = dataclasses.field(default_factory=list)
    cache_misses: int = 0

@dataclasses.dataclass
class SimulateCtx:
    """Context for a single transaction simulation call."""
    epoch: SimEpoch
    override_objects: List[Any] = dataclasses.field(default_factory=list)
    # borrowed_coin: Tuple (object_id_str, amount_int)
    borrowed_coin: Optional[Tuple[str, int]] = None # Changed Any to str for object_id

    def with_borrowed_coin(self, borrowed_coin_obj_id: str, borrowed_amount: int) -> 'SimulateCtx':
        """Sets the borrowed coin for the simulation context."""
        # Assuming borrowed_coin_obj_id is the ID string.
        # If borrowed_coin_obj was meant to be the full object, adjust type and storage.
        self.borrowed_coin = (borrowed_coin_obj_id, borrowed_amount)
        return self

    def with_gas_price(self, gas_price: int) -> 'SimulateCtx':
        """Sets the reference gas price in the epoch context."""
        self.epoch.reference_gas_price = gas_price
        return self


if __name__ == '__main__':
    print("--- Testing SimEpoch ---")
    # Test from_sui_system_state_summary (placeholder behavior)
    dummy_summary_dict = {
        "epoch": "10",
        "epochStartTimestampMs": str(int(time.time() * 1000) - 3600000), # 1 hour ago
        "epochDurationMs": str(24 * 3600 * 1000), # 24 hours
        "referenceGasPrice": "1100"
    }
    epoch_from_dict = SimEpoch.from_sui_system_state_summary(dummy_summary_dict)
    print(f"Epoch from dict: {epoch_from_dict}")
    assert epoch_from_dict.epoch_id == 10
    assert epoch_from_dict.reference_gas_price == 1100

    epoch_default = SimEpoch.from_sui_system_state_summary(None) # Test with non-dict input
    print(f"Epoch default: {epoch_default}")
    assert epoch_default.epoch_id == 0

    # Test is_stale
    current_ts = int(time.time() * 1000)
    stale_epoch = SimEpoch(epoch_id=1, epoch_start_timestamp_ms=current_ts - 2000, epoch_duration_ms=1000, reference_gas_price=1000)
    active_epoch = SimEpoch(epoch_id=2, epoch_start_timestamp_ms=current_ts - 500, epoch_duration_ms=1000, reference_gas_price=1000)
    print(f"Stale epoch is_stale(): {stale_epoch.is_stale()} (should be True)")
    assert stale_epoch.is_stale() is True
    print(f"Active epoch is_stale(): {active_epoch.is_stale()} (should be False)")
    assert active_epoch.is_stale() is False
    print("SimEpoch tests passed.")

    print("\n--- Testing SimulateResult ---")
    sim_result = SimulateResult(effects="dummy_effects", events="dummy_events", cache_misses=1)
    print(f"SimulateResult: {sim_result}")
    assert sim_result.object_changes == []
    assert sim_result.balance_changes == []
    assert sim_result.cache_misses == 1
    print("SimulateResult tests passed.")

    print("\n--- Testing SimulateCtx ---")
    ctx_epoch = SimEpoch(epoch_id=5, epoch_start_timestamp_ms=int(time.time() * 1000), epoch_duration_ms=3600000, reference_gas_price=1000)
    sim_ctx = SimulateCtx(epoch=ctx_epoch)
    print(f"Initial SimulateCtx: {sim_ctx}")
    assert sim_ctx.override_objects == []
    assert sim_ctx.borrowed_coin is None

    # Test with_borrowed_coin
    sim_ctx.with_borrowed_coin(borrowed_coin_obj_id="0xBORROWED_COIN_ID", borrowed_amount=10000)
    print(f"SimulateCtx after with_borrowed_coin: {sim_ctx}")
    assert sim_ctx.borrowed_coin == ("0xBORROWED_COIN_ID", 10000)

    # Test with_gas_price
    sim_ctx.with_gas_price(gas_price=1500)
    print(f"SimulateCtx after with_gas_price: {sim_ctx}")
    assert sim_ctx.epoch.reference_gas_price == 1500
    print("SimulateCtx tests passed.")

    print("\nAll simulator_py.types tests executed.")
