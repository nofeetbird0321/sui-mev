# coding: utf-8
# Copyright (c) Mysten Labs, Inc.
# SPDX-License-Identifier: Apache-2.0

"""
Utility function for fetching the latest epoch information.
"""

import asyncio
import logging
import time # For __main__ demo
from typing import Any, Optional, TYPE_CHECKING

# Assuming simulator_py is in PYTHONPATH or a sibling directory correctly configured
from simulator_py.types import SimEpoch

if TYPE_CHECKING:
    # For type hinting, assume pysui client types are available
    # In a real setup, these would be concrete types from pysui
    from pysui.sui.sui_clients.async_client import SuiClient as AsyncSuiClient
    # If using builder pattern:
    # from pysui.sui.sui_builders.get_builders import GetLatestSuiSystemState
    # from pysui.sui.sui_types.system_events import SuiSystemStateSummary # Actual response type
else:
    # Define a placeholder for AsyncSuiClient if not type checking, to allow module to load
    # This allows the file to be parsed without pysui installed, but it won't run correctly without mocks.
    class AsyncSuiClient:
        async def get_latest_sui_system_state(self) -> Any:
            raise NotImplementedError("This is a placeholder mock.")

logger = logging.getLogger(__name__)

async def get_latest_epoch(sui_client: 'AsyncSuiClient') -> Optional[SimEpoch]:
    """
    Fetches the latest Sui system state summary from the RPC node and converts
    it into a SimEpoch object.

    Args:
        sui_client: An instance of a Sui client (e.g., pysui's AsyncSuiClient)
                    capable of fetching system state.

    Returns:
        A SimEpoch object representing the latest epoch information, or None
        if fetching or parsing fails.
    """
    if not hasattr(sui_client, 'get_latest_sui_system_state'):
        logger.error("Provided sui_client does not have 'get_latest_sui_system_state' method.")
        # Fallback to SimEpoch's default if client is unusable
        return SimEpoch.from_sui_system_state_summary(None) 

    try:
        logger.debug("Fetching latest Sui system state summary...")
        # Using a direct method call example. If pysui uses a builder pattern:
        # from pysui.sui.sui_builders.get_builders import GetLatestSuiSystemState
        # system_state_summary_response = await sui_client.execute(GetLatestSuiSystemState())
        # And then extract the actual summary object from the response, e.g., system_state_summary_response.result_data
        
        # Assuming a direct method like this exists in pysui or is adapted:
        system_state_summary: Optional[Any] = await sui_client.get_latest_sui_system_state()
        # The actual type of system_state_summary would be something like pysui's SuiSystemStateSummary

        if system_state_summary is None:
            logger.warning("Received None from sui_client.get_latest_sui_system_state().")
            # SimEpoch.from_sui_system_state_summary can handle None and return a default
            return SimEpoch.from_sui_system_state_summary(None)

        logger.debug(f"Successfully fetched system state summary. Type: {type(system_state_summary)}")
        
        # Convert the raw summary object (potentially a dict or a pysui specific type)
        # SimEpoch.from_sui_system_state_summary is designed to handle this.
        sim_epoch = SimEpoch.from_sui_system_state_summary(system_state_summary)
        logger.info(f"Latest epoch fetched and converted: Epoch ID {sim_epoch.epoch_id}, RGP {sim_epoch.reference_gas_price}")
        return sim_epoch

    except Exception as e:
        logger.error(f"Error fetching or processing latest Sui system state: {e}", exc_info=True)
        # Fallback to SimEpoch's default in case of any error during fetch/parse
        logger.warning("Returning default SimEpoch due to error.")
        return SimEpoch.from_sui_system_state_summary(None)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # --- Mock AsyncSuiClient for Demonstration ---
    class MockAsyncSuiClient:
        async def get_latest_sui_system_state(self) -> Optional[Dict[str, Any]]:
            """Mocks the behavior of pysui's get_latest_sui_system_state."""
            logger.info("MockAsyncSuiClient: get_latest_sui_system_state called.")
            # Simulate a successful response (structure should match what SimEpoch.from_sui_system_state_summary expects)
            # SimEpoch.from_sui_system_state_summary expects keys like 'epoch', 'epochStartTimestampMs', etc.
            current_ts_ms = int(time.time() * 1000)
            return {
                "epoch": "123", # Typically a string from JSON RPC
                "protocolVersion": "28",
                "systemStateVersion": "123", # Example, might not be directly used by SimEpoch
                "storageFundTotalObjectStorageRebates": "100000000000",
                "storageFundNonRefundableBalance": "10000000",
                "referenceGasPrice": "1000", # Typically a string
                "safeMode": False,
                "safeModeStorageRewards": "0",
                "safeModeComputationRewards": "0",
                "safeModeStorageRebates": "0",
                "safeModeNonRefundableStorageFee": "0",
                "epochStartTimestampMs": str(current_ts_ms - (2 * 60 * 60 * 1000)), # 2 hours ago
                "epochDurationMs": str(24 * 60 * 60 * 1000), # 24 hours
                "stakeSubsidyStartEpoch": "2",
                # ... other fields that might be part of SuiSystemStateSummary
                # Only fields used by SimEpoch.from_sui_system_state_summary are strictly necessary for the mock
                # to make that specific function work.
            }

    class FailingMockAsyncSuiClient:
         async def get_latest_sui_system_state(self) -> Optional[Dict[str, Any]]:
            logger.info("FailingMockAsyncSuiClient: get_latest_sui_system_state called, will raise exception.")
            raise ConnectionError("Simulated network failure")


    async def demo_get_latest_epoch():
        logger.info("--- Demonstrating get_latest_epoch ---")

        # Test with successful mock client
        mock_client_success = MockAsyncSuiClient()
        logger.info("\nCalling get_latest_epoch with successful mock client...")
        latest_epoch_success = await get_latest_epoch(sui_client=mock_client_success) # type: ignore
        
        if latest_epoch_success:
            print(f"Successfully fetched SimEpoch: {latest_epoch_success}")
            assert latest_epoch_success.epoch_id == 123
            assert latest_epoch_success.reference_gas_price == 1000
            assert not latest_epoch_success.is_stale() # Based on mock data, should not be stale
        else:
            print("Failed to fetch SimEpoch with successful mock (this shouldn't happen).")

        # Test with a client that simulates an RPC failure
        mock_client_failure = FailingMockAsyncSuiClient()
        logger.info("\nCalling get_latest_epoch with failing mock client...")
        latest_epoch_failure = await get_latest_epoch(sui_client=mock_client_failure) # type: ignore

        if latest_epoch_failure:
            print(f"Fetched SimEpoch despite error (using default): {latest_epoch_failure}")
            # Check if it's a default/fallback epoch from SimEpoch.from_sui_system_state_summary(None)
            assert latest_epoch_failure.epoch_id == 0 # Default epoch_id in SimEpoch if None is passed
            assert latest_epoch_failure.reference_gas_price == 1000 # Default RGP
        else:
            # This case (returning None directly from get_latest_epoch) is less likely
            # if SimEpoch.from_sui_system_state_summary always returns a default on None input.
            # The current implementation of get_latest_epoch ensures it returns SimEpoch.from_sui_system_state_summary(None)
            # on error, which should return a default SimEpoch.
            print("get_latest_epoch returned None on failure (unexpected if SimEpoch provides defaults).")


        # Test with a client that returns None (e.g., object not found, not applicable here but good pattern)
        class NoneReturningMockClient:
            async def get_latest_sui_system_state(self) -> Optional[Dict[str, Any]]:
                logger.info("NoneReturningMockClient: Returning None for system state.")
                return None
        
        mock_client_none = NoneReturningMockClient()
        logger.info("\nCalling get_latest_epoch with None-returning mock client...")
        latest_epoch_none = await get_latest_epoch(sui_client=mock_client_none) # type: ignore
        if latest_epoch_none:
            print(f"Fetched SimEpoch with None-returning client (using default): {latest_epoch_none}")
            assert latest_epoch_none.epoch_id == 0 
        else:
            print("get_latest_epoch returned None with None-returning client (unexpected).")


        logger.info("\n--- Demonstration Finished ---")

    asyncio.run(demo_get_latest_epoch())
