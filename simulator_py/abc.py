# coding: utf-8
# Copyright (c) Mysten Labs, Inc.
# SPDX-License-Identifier: Apache-2.0

"""
Abstract Base Class for a transaction simulator.
"""

import abc
from typing import Any, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .types import SimulateCtx, SimulateResult

class Simulator(abc.ABC):
    """
    Abstract Base Class for a transaction simulator.
    Defines the interface for different simulation strategies (e.g., local, RPC-based).
    """

    @abc.abstractmethod
    async def simulate(self, tx_data: Any, ctx: 'SimulateCtx') -> 'SimulateResult':
        """
        Simulates a transaction.

        Args:
            tx_data: The transaction data to simulate. The type will depend on the
                     underlying Sui SDK (e.g., a transaction block builder object or
                     serialized transaction).
            ctx: The simulation context, including epoch information, object overrides, etc.

        Returns:
            A SimulateResult object containing the effects, events, and other outcomes
            of the simulation.
        """
        pass

    @abc.abstractmethod
    async def get_object(self, object_id: str) -> Optional[Any]:
        """
        Retrieves an object by its ID, potentially from a cache or by fetching.

        Args:
            object_id: The ID of the object to retrieve.

        Returns:
            The object data if found, otherwise None. The type of the returned object
            will depend on the Sui SDK (e.g., a SuiObjectResponse).
        """
        pass

    @abc.abstractmethod
    def name(self) -> str:
        """
        Returns the name of the simulator implementation.
        """
        pass

    def get_object_layout(self, object_id: str) -> Optional[Any]:
        """
        Retrieves the layout for a given object ID.
        This is optional and can be implemented by simulators that have access
        to object layout information (e.g., for Move objects).

        Args:
            object_id: The ID of the object whose layout is requested.

        Returns:
            The object layout information if available, otherwise None.
        """
        return None

if __name__ == '__main__':
    # This module defines an ABC, so direct instantiation or usage is not the primary goal here.
    # However, we can define a dummy implementation for basic verification.
    from simulator_py.types import SimulateCtx, SimulateResult, SimEpoch # For dummy implementation

    class DummySimulator(Simulator):
        def __init__(self, sim_name: str = "DummySim"):
            self._name = sim_name

        async def simulate(self, tx_data: Any, ctx: SimulateCtx) -> SimulateResult:
            print(f"{self.name()}: Simulating tx_data: {tx_data} with context: {ctx}")
            # Return a dummy result
            return SimulateResult(
                effects=f"Simulated effects for {tx_data}",
                events=f"Simulated events for {tx_data}",
                object_changes=[],
                balance_changes=[],
                cache_misses=0
            )

        async def get_object(self, object_id: str) -> Optional[Any]:
            print(f"{self.name()}: Getting object with ID: {object_id}")
            if object_id == "0xEXISTS":
                return {"id": object_id, "data": "dummy_object_data"}
            return None

        def name(self) -> str:
            return self._name

        def get_object_layout(self, object_id: str) -> Optional[Any]:
            print(f"{self.name()}: Getting object layout for ID: {object_id}")
            if object_id == "0xEXISTS_WITH_LAYOUT":
                return {"type": "0x1::coin::Coin<0x2::sui::SUI>", "fields": {"balance": "u64"}}
            return None

    async def run_dummy_sim_test():
        print("--- Testing DummySimulator (ABC implementation) ---")
        dummy_sim = DummySimulator()
        
        print(f"Simulator Name: {dummy_sim.name()}")
        assert dummy_sim.name() == "DummySim"

        # Test get_object
        obj_exists = await dummy_sim.get_object("0xEXISTS")
        print(f"Get object '0xEXISTS': {obj_exists}")
        assert obj_exists is not None
        obj_none = await dummy_sim.get_object("0xDOES_NOT_EXIST")
        print(f"Get object '0xDOES_NOT_EXIST': {obj_none}")
        assert obj_none is None

        # Test get_object_layout
        layout_exists = dummy_sim.get_object_layout("0xEXISTS_WITH_LAYOUT")
        print(f"Get layout '0xEXISTS_WITH_LAYOUT': {layout_exists}")
        assert layout_exists is not None
        layout_none = dummy_sim.get_object_layout("0xNO_LAYOUT")
        print(f"Get layout '0xNO_LAYOUT': {layout_none}")
        assert layout_none is None

        # Test simulate
        dummy_epoch = SimEpoch(epoch_id=1, epoch_start_timestamp_ms=int(time.time()*1000), epoch_duration_ms=3600000, reference_gas_price=1000)
        dummy_ctx = SimulateCtx(epoch=dummy_epoch)
        sim_res = await dummy_sim.simulate(tx_data="dummy_tx", ctx=dummy_ctx)
        print(f"Simulation result: {sim_res}")
        assert "Simulated effects" in str(sim_res.effects)

        print("DummySimulator tests passed.")

    import asyncio
    import time # Needed for dummy_epoch
    asyncio.run(run_dummy_sim_test())
    print("\nAll simulator_py.abc tests executed (via DummySimulator).")
