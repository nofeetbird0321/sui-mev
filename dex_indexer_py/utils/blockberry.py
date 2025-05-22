# coding: utf-8
# Copyright (c) Mysten Labs, Inc.
# SPDX-License-Identifier: Apache-2.0

"""
Utility for fetching coin metadata, specifically decimals, from the Blockberry API.
"""

import asyncio
import httpx # Add 'httpx' to requirements.txt
import itertools
import json
import logging
from typing import Optional, List, Any

logger = logging.getLogger(__name__)

API_URL = "https://api.blockberry.one/sui/v1/coins"

# List of API keys for Blockberry
BLOCKBERRY_API_KEYS: List[str] = [
    "BA4o88XzEY2G5r65V2R7W8Zqj3x9Y6C1", "BB4o88XzEY2G5r65V2R7W8Zqj3x9Y6C2",
    "BC4o88XzEY2G5r65V2R7W8Zqj3x9Y6C3", "BD4o88XzEY2G5r65V2R7W8Zqj3x9Y6C4",
    "BE4o88XzEY2G5r65V2R7W8Zqj3x9Y6C5", "BF4o88XzEY2G5r65V2R7W8Zqj3x9Y6C6",
    "BG4o88XzEY2G5r65V2R7W8Zqj3x9Y6C7", "BH4o88XzEY2G5r65V2R7W8Zqj3x9Y6C8",
    "BI4o88XzEY2G5r65V2R7W8Zqj3x9Y6C9", "BJ4o88XzEY2G5r65V2R7W8Zqj3x9Y6D1",
    "BK4o88XzEY2G5r65V2R7W8Zqj3x9Y6D2", "BL4o88XzEY2G5r65V2R7W8Zqj3x9Y6D3",
    "BM4o88XzEY2G5r65V2R7W8Zqj3x9Y6D4", "BN4o88XzEY2G5r65V2R7W8Zqj3x9Y6D5",
    "BO4o88XzEY2G5r65V2R7W8Zqj3x9Y6D6",
]

class BlockberryClient:
    """
    An asynchronous client for interacting with the Blockberry API
    to fetch coin metadata.
    """

    def __init__(self, http_client: Optional[httpx.AsyncClient] = None):
        """
        Initializes the BlockberryClient.

        Args:
            http_client: Optional. An httpx.AsyncClient instance. If None,
                         a new one is created.
        """
        if http_client:
            self.http_client = http_client
            self._created_client = False
        else:
            # Default timeout of 30 seconds for requests
            self.http_client = httpx.AsyncClient(timeout=30.0)
            self._created_client = True
        
        if not BLOCKBERRY_API_KEYS:
            logger.warning("Blockberry API keys list is empty. API calls will likely fail.")
            # Create a dummy cycle to prevent errors if list is empty, though calls will fail without keys
            self._api_key_cycle = itertools.cycle([""])
        else:
            self._api_key_cycle = itertools.cycle(BLOCKBERRY_API_KEYS)

    async def get_coin_decimals(self, coin_type: str) -> Optional[int]:
        """
        Fetches the number of decimals for a given coin type from the Blockberry API.

        Args:
            coin_type: The type of the coin (e.g., "0x2::sui::SUI").

        Returns:
            The number of decimals as an integer if successful, otherwise None.
        """
        # TODO: Implement proper rate limiting. Blockberry API documentation
        # mentions a rate limit of 1 request per 15 seconds per API key.
        # This client currently does not enforce this across multiple calls
        # or instances, relying on the user to manage call frequency or
        # hoping round-robin is sufficient for non-intensive use.

        api_key = next(self._api_key_cycle)
        if not api_key: # Should only happen if BLOCKBERRY_API_KEYS was empty
            logger.error("No API key available for Blockberry request.")
            return None

        request_url = f"{API_URL}/{coin_type}"
        headers = {"x-api-key": api_key}

        logger.debug(f"Requesting coin decimals for {coin_type} from {request_url} using key ending with ...{api_key[-4:]}")

        try:
            response = await self.http_client.get(request_url, headers=headers)
            logger.debug(f"Blockberry API response for {coin_type}: Status {response.status_code}")

            response.raise_for_status()  # Raises HTTPStatusError for 4xx/5xx responses

            response_json: Any = response.json() # Type as Any, then check structure

            if isinstance(response_json, dict) and "decimals" in response_json:
                decimals_val = response_json["decimals"]
                if isinstance(decimals_val, int):
                    return decimals_val
                elif isinstance(decimals_val, str) and decimals_val.isdigit():
                    return int(decimals_val)
                else:
                    logger.error(f"Decimals field for {coin_type} is not a valid integer: {decimals_val}")
                    return None
            else:
                logger.error(f"Failed to find 'decimals' field in Blockberry response for {coin_type}. Response: {response_json}")
                return None

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching decimals for {coin_type}: {e.response.status_code} - {e.response.text[:200]}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Request error fetching decimals for {coin_type}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error fetching decimals for {coin_type}: {e}. Response text: {response.text[:200]}")
            return None
        except KeyError: # Should be caught by the "decimals" in response_json check
            logger.error(f"KeyError: 'decimals' field missing in response for {coin_type}.")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred fetching decimals for {coin_type}: {e}")
            return None

    async def close(self):
        """
        Closes the underlying httpx.AsyncClient if it was created by this instance.
        """
        if self._created_client:
            await self.http_client.aclose()
            logger.info("BlockberryClient closed its internally created HTTP client.")


# Module-level default client instance
_default_client = BlockberryClient()

async def get_coin_decimals(coin_type: str) -> Optional[int]:
    """
    Top-level convenience function to fetch coin decimals using the default client.

    Args:
        coin_type: The type of the coin (e.g., "0x2::sui::SUI").

    Returns:
        The number of decimals as an integer if successful, otherwise None.
    """
    return await _default_client.get_coin_decimals(coin_type)


# Ensure the default client is closed on program exit if used implicitly.
# This is a bit tricky for library code. For scripts, atexit can be used,
# but for libraries, explicit close by the application is better.
# For this example, we'll show how it might be used in the __main__ block.

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # SUI coin type (example from Rust code)
    SUI_COIN_TYPE = "0x0000000000000000000000000000000000000000000000000000000000000002::sui::SUI"
    # USDC coin type (example from Rust code, but might vary by network)
    USDC_COIN_TYPE = "0x5d4b302506645c37ff133b98c4b50a5ae14841659738d6d733d59d0d2177914::coin::COIN"


    async def demo_get_decimals():
        # --- Using the module-level function (default client) ---
        print("--- Testing with module-level get_coin_decimals ---")
        
        # Test SUI (Blockberry might expect the short form 0x2::sui::SUI)
        # Let's try the canonical form first, then the short one if BB prefers it.
        sui_decimals_long = await get_coin_decimals(SUI_COIN_TYPE)
        if sui_decimals_long is not None:
            print(f"Decimals for SUI ({SUI_COIN_TYPE}): {sui_decimals_long}")
        else:
            print(f"Could not fetch decimals for SUI ({SUI_COIN_TYPE}).")
            # Try short form if long form failed
            sui_short_form = "0x2::sui::SUI"
            print(f"Trying short form for SUI: {sui_short_form}")
            sui_decimals_short = await get_coin_decimals(sui_short_form)
            if sui_decimals_short is not None:
                 print(f"Decimals for SUI ({sui_short_form}): {sui_decimals_short}")
            else:
                 print(f"Could not fetch decimals for SUI ({sui_short_form}) either.")


        usdc_decimals = await get_coin_decimals(USDC_COIN_TYPE)
        if usdc_decimals is not None:
            print(f"Decimals for USDC ({USDC_COIN_TYPE}): {usdc_decimals}")
        else:
            print(f"Could not fetch decimals for USDC ({USDC_COIN_TYPE}).")

        # Test a non-existent coin
        non_existent_coin = "0x123::nonexistent::NONEXISTENT"
        non_existent_decimals = await get_coin_decimals(non_existent_coin)
        if non_existent_decimals is None:
            print(f"Correctly failed to fetch decimals for non-existent coin: {non_existent_coin}")
        else:
            print(f"Unexpectedly found decimals for {non_existent_coin}: {non_existent_decimals}")


        # --- Using a manually created client instance ---
        print("\n--- Testing with manually created BlockberryClient ---")
        manual_client = BlockberryClient()
        try:
            sui_decimals_manual = await manual_client.get_coin_decimals("0x2::sui::SUI") # Using short form
            if sui_decimals_manual is not None:
                print(f"Decimals for SUI (manual client, 0x2::sui::SUI): {sui_decimals_manual}")
            else:
                print(f"Could not fetch decimals for SUI (manual client, 0x2::sui::SUI).")
        finally:
            await manual_client.close() # Important to close manually created client

        # Example: Test with an external httpx client
        print("\n--- Testing with external httpx.AsyncClient ---")
        async with httpx.AsyncClient(timeout=20.0) as external_http_client:
            client_with_external_session = BlockberryClient(http_client=external_http_client)
            # This client won't close the external_http_client when client_with_external_session.close() is called
            # (though in this example, close() isn't called as it's managed by async with)
            sui_decimals_external = await client_with_external_session.get_coin_decimals("0x2::sui::SUI")
            if sui_decimals_external is not None:
                print(f"Decimals for SUI (external client, 0x2::sui::SUI): {sui_decimals_external}")
            else:
                print(f"Could not fetch decimals for SUI (external client, 0x2::sui::SUI).")
            # No need to call client_with_external_session.close() if you want the external client to remain open.
            # If you do call it, it won't affect external_http_client.

    async def shutdown_default_client():
        """Ensures the default client is closed."""
        await _default_client.close()

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(demo_get_decimals())
    except KeyboardInterrupt:
        print("Demo interrupted by user.")
    finally:
        print("Shutting down default Blockberry client...")
        loop.run_until_complete(shutdown_default_client())
        loop.close()

    print("Blockberry client demo finished.")

# Note: `httpx` library needs to be installed.
# Add 'httpx' to your project's requirements.txt or install with pip.
