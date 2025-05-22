# coding: utf-8
# Copyright (c) Mysten Labs, Inc.
# SPDX-License-Identifier: Apache-2.0

"""
Configuration constants and settings for the Arb Bot.
"""

from typing import Set

# Attempt to import SUI_COIN_TYPE from common_utils_py.coin
# If common_utils_py is not in the PYTHONPATH during isolated execution,
# this will use a placeholder.
try:
    from common_utils_py.coin import SUI_COIN_TYPE
except ImportError:
    # Placeholder if common_utils_py.coin is not found (e.g., during isolated testing)
    # In a real integrated environment, this import should work.
    SUI_COIN_TYPE = "0x2::sui::SUI"
    print(f"Warning: common_utils_py.coin.SUI_COIN_TYPE not found. Using placeholder: {SUI_COIN_TYPE}")


# --- Module-level Constants ---

GAS_BUDGET: int = 10_000_000_000  # 10 SUI

# Constants related to sqrt_price from Cetus SDK / DeepBook SDK
# Max value for Q64.64 representations of sqrt_price
MAX_SQRT_PRICE_X64: int = 79226673515401279992447579055 
# Min value for Q64.64 representations of sqrt_price
MIN_SQRT_PRICE_X64: int = 4295048016         

# TODO: Make these configurable via environment variables or a config file
TEST_HTTP_URL: str = ""  # Example: "https://fullnode.testnet.sui.io:443"
TEST_ATTACKER_ADDRESS: str = "" # Example: "0xYourAddress"


def pegged_coin_types() -> Set[str]:
    """
    Returns a set of coin type strings that are considered pegged coins.
    This list is based on the `pegged_coin_types` function in Rust's `config.rs`.
    """
    # These are examples of commonly recognized stablecoins on Sui.
    # The actual list might vary based on the network (mainnet, testnet, devnet)
    # and the specific assets deployed and recognized by the community.
    # Ensure these type strings are normalized/canonical if needed.
    return {
        SUI_COIN_TYPE, # Native SUI is often included in such lists for reference or specific logic
        "0x5d4b302506645c37ff133b98c4b50a5ae14841659738d6d733d59d0d2177914::coin::COIN", # Wormhole USDC
        "0xe74c26223ab4c70a9fb7cddbd28d05090451691018f07820979cc7afe90709a2::coin::COIN", # Wormhole USDT (eth bridged)
        "0x60813009535c043f1d8a793f73d045540e6345ca1a8f4578831117249670254a::coin::COIN", # Wormhole USDT (sol bridged, example, might vary)
        "0xc060006111016b8a020ad5b33834984a437aaa7d3c74c18e09a95d48aceab54c::coin::COIN", # Wormhole DAI
        # Add other recognized pegged/stable coin types here.
        # These should be the canonical type strings.
    }


if __name__ == '__main__':
    print("--- Arb Bot Configuration ---")
    
    print(f"GAS_BUDGET: {GAS_BUDGET}")
    print(f"MAX_SQRT_PRICE_X64: {MAX_SQRT_PRICE_X64}")
    print(f"MIN_SQRT_PRICE_X64: {MIN_SQRT_PRICE_X64}")
    
    print(f"\nTEST_HTTP_URL: '{TEST_HTTP_URL}' (TODO: Make configurable)")
    print(f"TEST_ATTACKER_ADDRESS: '{TEST_ATTACKER_ADDRESS}' (TODO: Make configurable)")
    
    pegged_coins = pegged_coin_types()
    print("\nPegged Coin Types:")
    for coin_type in pegged_coins:
        print(f"  - {coin_type}")
        
    # Verify SUI_COIN_TYPE is in the set
    assert SUI_COIN_TYPE in pegged_coins, f"SUI_COIN_TYPE ({SUI_COIN_TYPE}) not found in pegged_coin_types."
    print(f"\nSUI_COIN_TYPE ({SUI_COIN_TYPE}) is present in the pegged list.")

    print("\n--- Configuration Loaded ---")
