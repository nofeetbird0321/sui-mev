# coding: utf-8
# Copyright (c) Mysten Labs, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Miscellaneous utility functions."""

import time
import os
import logging

# Placeholder for pysui imports.
# Add 'pysui' to your project's requirements.txt
try:
    from pysui.sui.sui_config import SuiConfig
    from pysui.sui.sui_clients.async_client import SuiClient as AsyncSuiClient # Renaming to avoid confusion if a sync client exists
    PYSUI_AVAILABLE = True
except ImportError:
    PYSUI_AVAILABLE = False
    logging.warning("pysui library is not installed. create_sui_client will not function correctly.")
    # Define mock objects for type hinting and basic structure if pysui is not available
    class SuiConfig: # type: ignore
        def __init__(self):
            self.rpc_url = ""
            self.environment = "" # e.g. "testnet", "mainnet", "devnet"

        @classmethod
        def default_config(cls) -> 'SuiConfig':
            # This mock won't actually load from a real default sui.yaml
            # It's just to allow the code structure to be similar
            cfg = cls()
            cfg.rpc_url = "http://localhost:9000" # A common local default
            cfg.environment = "local"
            return cfg

    class AsyncSuiClient: # type: ignore
        def __init__(self, config: SuiConfig):
            self.config = config
            logging.info(f"Mock AsyncSuiClient initialized with RPC URL: {config.rpc_url}")

        async def __aenter__(self):
            # Mock async context manager entry
            logging.info("Mock AsyncSuiClient entered context.")
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            # Mock async context manager exit
            logging.info("Mock AsyncSuiClient exited context.")
            pass


logger = logging.getLogger(__name__)

DEFAULT_SUI_RPC_URL = "https://rpc.testnet.sui.io/" # Placeholder default

def current_time_ms() -> int:
    """
    Returns the current time in milliseconds since the UNIX epoch.
    """
    return int(time.time() * 1000)

# TODO: Replace `object` with `pysui.sui.sui_clients.async_client.SuiClient`
# when pysui is fully integrated and its types are available.
async def create_sui_client(rpc_url: str = None, ipc_path: str = None) -> object:
    """
    Creates and returns an asynchronous SuiClient instance from the pysui SDK.

    Args:
        rpc_url: Optional. The RPC URL to connect to. If None, attempts to use
                 SUI_RPC_URL environment variable, then DEFAULT_SUI_RPC_URL.
        ipc_path: Optional. Path to a Sui Node IPC socket. (Currently ignored as
                  pysui's AsyncSuiClient primarily uses RPC).

    Returns:
        An instance of pysui.sui.sui_clients.async_client.SuiClient, or a mock
        if pysui is not installed.
    """
    if not PYSUI_AVAILABLE:
        logger.error("pysui library is not available. Returning a mock SuiClient.")
        # Fallback to a mock client if pysui is not installed
        # This allows the application to run basic logic without pysui for development/testing.
        mock_config = SuiConfig()
        mock_config.rpc_url = rpc_url or os.getenv("SUI_RPC_URL", DEFAULT_SUI_RPC_URL)
        return AsyncSuiClient(config=mock_config)


    final_rpc_url = rpc_url or os.getenv("SUI_RPC_URL", DEFAULT_SUI_RPC_URL)

    if ipc_path:
        logger.warning("ipc_path parameter is provided but currently not used by pysui's AsyncSuiClient setup in this utility.")

    # Initialize SuiConfig.
    # For pysui, SuiConfig typically loads from a yaml file (e.g., client.yaml)
    # or can be set up programmatically.
    # If a specific rpc_url is given, we prioritize it.
    # Otherwise, default_config() might load from ~/.sui/sui_config/client.yaml or similar.
    try:
        if final_rpc_url:
            # If an RPC URL is specified, we can try to set it directly.
            # pysui's SuiConfig might not allow direct rpc_url setting after init,
            # or it might be set by choosing an "environment" that matches the URL.
            # For this example, we'll assume we can create a config and then set its URL,
            # or that SuiClient can take the URL directly.
            
            # Option 1: Create a default config and try to override RPC URL
            # This is a common pattern but might not be how SuiConfig is designed.
            # sui_config = SuiConfig.default_config()
            # sui_config.rpc_url = final_rpc_url
            
            # Option 2: Pysui might allow creating a config for a specific RPC endpoint directly
            # or by environment name. If final_rpc_url matches a known env, it might pick it.
            # For instance, if final_rpc_url is testnet, it might have a 'testnet' env.
            # For now, we'll assume a generic way to set it.
            # A more robust way would be to check if final_rpc_url corresponds to
            # one of the pre-defined environments in a local client.yaml or if SuiConfig
            # has a method like `SuiConfig.from_rpc_url(final_rpc_url)`.
            # Let's assume SuiConfig can be initialized and then its rpc_url attribute can be set,
            # or that the client can take the url directly.
            
            # Simplest approach if SuiConfig is flexible:
            sui_config = SuiConfig() # Create a blank or default config
            sui_config.rpc_url = final_rpc_url
            # We might need to also set `sui_config.environment` if that dictates client behavior.
            # For example, if final_rpc_url is a mainnet url, environment should be 'mainnet'.
            # This mapping is not done here for simplicity.
            # A common pattern is to have named environments in client.yaml
            # SuiConfig() or SuiConfig.default_config() would load the active one.
            # To switch, you'd typically do sui_config.set_active_env("testnet") for example.
            # If `pysui` is like `sui CLI`, it might require an environment name.

        else: # Should not happen due to defaulting final_rpc_url
            sui_config = SuiConfig.default_config()
        
        final_rpc_url = sui_config.rpc_url # Reflect the URL that will actually be used by the config

    except Exception as e:
        logger.error(f"Failed to initialize SuiConfig: {e}. Using provided/default RPC URL directly for client.")
        # Fallback if SuiConfig setup is complex or fails:
        # Create a minimal config object just to pass the URL if client needs a config object
        sui_config = SuiConfig() 
        sui_config.rpc_url = final_rpc_url


    logger.info(f"Creating SuiClient with RPC URL: {final_rpc_url}")
    
    # Create the AsyncSuiClient instance
    # Assuming AsyncSuiClient constructor takes a SuiConfig object.
    # Some SDKs allow passing the URL string directly, e.g., AsyncSuiClient(rpc_url=final_rpc_url)
    # Based on pysui examples, it usually takes the config.
    client = AsyncSuiClient(config=sui_config)
    return client


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    print(f"Current time in milliseconds: {current_time_ms()}")

    async def test_sui_client():
        print("\nTesting Sui Client Creation:")

        # Test with default RPC URL
        print("\n1. Default RPC URL:")
        client_default = await create_sui_client()
        if PYSUI_AVAILABLE and client_default:
            # TODO: Replace with actual client interaction if possible and safe
            # For now, just check the config URL (if mock allows)
            if hasattr(client_default, 'config'):
                 print(f"   Client configured with RPC URL: {client_default.config.rpc_url}") # type: ignore
            else:
                 print(f"   Client created (type: {type(client_default)})")
        elif not PYSUI_AVAILABLE:
            print(f"   Mock client created (type: {type(client_default)}) with RPC: {client_default.config.rpc_url}") # type: ignore


        # Test with a custom RPC URL
        print("\n2. Custom RPC URL:")
        custom_url = "https://fullnode.mainnet.sui.io:443"
        client_custom = await create_sui_client(rpc_url=custom_url)
        if PYSUI_AVAILABLE and client_custom:
            if hasattr(client_custom, 'config'):
                print(f"   Client configured with RPC URL: {client_custom.config.rpc_url}") # type: ignore
            else:
                print(f"   Client created (type: {type(client_custom)})")

        elif not PYSUI_AVAILABLE:
            print(f"   Mock client created (type: {type(client_custom)}) with RPC: {client_custom.config.rpc_url}") # type: ignore


        # Test with environment variable (manual testing needed by setting the var)
        print("\n3. Environment Variable SUI_RPC_URL (if set):")
        os.environ["SUI_RPC_URL"] = "https://my.custom.sui.node.com"
        client_env = await create_sui_client()
        if PYSUI_AVAILABLE and client_env:
            if hasattr(client_env, 'config'):
                print(f"   Client configured with RPC URL from env: {client_env.config.rpc_url}") # type: ignore
            else:
                print(f"   Client created (type: {type(client_env)})")
        elif not PYSUI_AVAILABLE:
            print(f"   Mock client created (type: {type(client_env)}) with RPC from env: {client_env.config.rpc_url}") # type: ignore
        del os.environ["SUI_RPC_URL"] # Clean up env var

        # Example of using the client as an async context manager (if pysui client supports it)
        print("\n4. Async Context Manager (Mock test):")
        async with await create_sui_client(rpc_url="http://127.0.0.1:9000") as client_ctx:
            if client_ctx:
                print(f"   Client context obtained. Type: {type(client_ctx)}")
                if hasattr(client_ctx, 'config'):
                     print(f"   Client in context using RPC: {client_ctx.config.rpc_url}") # type: ignore

    import asyncio
    asyncio.run(test_sui_client())

# Note: 'pysui' should be added to requirements.txt for this module to be fully functional.
