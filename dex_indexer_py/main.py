# coding: utf-8
# Copyright (c) Mysten Labs, Inc.
# SPDX-License-Identifier: Apache-2.0

"""
Main class for the DEX Indexer, orchestrating data collection, processing, and storage.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx # For type hinting http_client_for_blockberry

# Assuming burberry_engine_py is installed or in PYTHONPATH
from burberry_engine_py.core import Engine

# Relative imports for types, collectors, strategy, and DB
from .types import Event, NoAction, Pool, PoolCache, Protocol, DummyExecutor # DummyExecutor for now
from .collectors import QueryEventCollector
from .strategy import PoolCreatedStrategy
from .db import DB # Assuming DB is the ABC defined in db.py


class DexIndexer:
    """
    Orchestrates the DEX indexing process by managing collectors, strategies,
    and executors via the Burberry Engine.
    """

    @staticmethod
    def _token01_key(token0_type: str, token1_type: str) -> Tuple[str, str]:
        """
        Sorts token types alphabetically to create a canonical cache key.
        """
        # TODO: Move this to a shared utils module within dex_indexer_py if used elsewhere.
        if token0_type <= token1_type:
            return (token0_type, token1_type)
        else:
            return (token1_type, token0_type)

    def __init__(
        self, 
        sui_client: Any, # Should be 'SuiClient' from pysui
        db: DB, 
        pool_cache: PoolCache, 
        http_client_for_blockberry: httpx.AsyncClient,
        dex_protocol_parsers: Dict[Protocol, Any] # Any is placeholder for ProtocolParserModule
    ):
        """
        Initializes the DexIndexer.

        Args:
            sui_client: The Sui client for interacting with the Sui network.
            db: The database interface for storing and retrieving indexed data.
            pool_cache: The in-memory cache for pools.
            http_client_for_blockberry: HTTP client for Blockberry API calls.
            dex_protocol_parsers: A dictionary mapping Protocol enums to their
                                  respective parser modules/objects.
        """
        self.sui_client = sui_client
        self.db = db
        self.pool_cache = pool_cache
        self.http_client_for_blockberry = http_client_for_blockberry
        self.dex_protocol_parsers = dex_protocol_parsers
        
        self.engine: Engine[Event, NoAction] = Engine()
        self.logger = logging.getLogger(__name__)
        self._tasks: List[asyncio.Task[Any]] = [] # To store tasks from engine.start()
        self._initialized = False # Flag to track if _initialize_components_and_engine was called

    async def _initialize_components_and_engine(self) -> None:
        """
        Initializes and registers components (collectors, strategies, executors) with the engine.
        """
        if self._initialized:
            return

        self.logger.info("Initializing DexIndexer components and engine...")

        # 1. Create Collector
        # For now, using default tick interval. Can be made configurable.
        query_event_collector = QueryEventCollector() 

        # 2. Create Strategy
        pool_created_strategy = PoolCreatedStrategy(
            db=self.db,
            sui_client=self.sui_client,
            pool_cache=self.pool_cache,
            http_client_for_blockberry=self.http_client_for_blockberry,
            dex_protocol_parsers=self.dex_protocol_parsers
        )

        # 3. Create Executor (using DummyExecutor as PoolCreatedStrategy produces NoAction)
        # If strategies were to produce meaningful actions, a real executor would be needed.
        dummy_executor = DummyExecutor() # No name needed if not used significantly

        # 4. Add components to the engine
        self.engine.add_collector(query_event_collector)
        self.engine.add_strategy(pool_created_strategy)
        # Register DummyExecutor for the NoAction type produced by PoolCreatedStrategy
        self.engine.add_executor(NoAction, dummy_executor) 
        
        self.logger.info("DexIndexer components and engine initialized.")
        self._initialized = True


    async def start(self) -> None:
        """
        Initializes components (if not already done) and starts the underlying engine.
        The engine tasks are stored in self._tasks.
        """
        await self._initialize_components_and_engine()
        
        self.logger.info("Starting DexIndexer engine...")
        # Engine.start() now returns None; it manages its tasks internally.
        # We call it to kick off the tasks.
        await self.engine.start() 
        # If we need to wait for tasks from engine.start() to be accessible for some reason:
        # self._tasks = self.engine._running_tasks # Accessing internal list (not ideal)
        # Or, if engine.start() were to return them:
        # self._tasks = await self.engine.start()
        self.logger.info("DexIndexer engine started (background tasks launched).")


    async def run_forever(self) -> None:
        """
        Initializes components (if not already done) and runs the engine indefinitely.
        This method will only return if the engine's run_forever loop terminates
        (e.g., due to an unhandled exception in a core engine task).
        """
        await self._initialize_components_and_engine()
        
        self.logger.info("Running DexIndexer engine forever...")
        await self.engine.run_forever()
        self.logger.info("DexIndexer engine run_forever completed (likely due to stop or error).")


    async def stop(self) -> None:
        """
        Stops the underlying engine gracefully.
        """
        self.logger.info("Stopping DexIndexer engine...")
        await self.engine.stop()
        # self._tasks list might be cleared by engine.stop() or we can clear it here.
        # For now, engine manages its internal task list clearing.
        self.logger.info("DexIndexer engine stopped.")

    # --- Query Methods ---

    def get_pools_by_token(self, token_type: str) -> Optional[Set[Pool]]:
        """
        Retrieves all pools containing the given token type from the cache.
        """
        return self.pool_cache.token_pools.get(token_type)

    def get_pools_by_token01(self, token0_type: str, token1_type: str) -> Optional[Set[Pool]]:
        """
        Retrieves all pools for a specific token pair (order-agnostic) from the cache.
        """
        key = self._token01_key(token0_type, token1_type)
        return self.pool_cache.token01_pools.get(key)

    def get_pool_by_id(self, pool_id_str: str) -> Optional[Pool]:
        """
        Retrieves a specific pool by its ID from the cache.
        """
        return self.pool_cache.pool_map.get(pool_id_str)

    async def pool_count(self, protocol: Protocol) -> int:
        """
        Counts the number of stored pools for a given protocol by querying the database.
        """
        return await self.db.pool_count(protocol)

    async def get_all_pools(self, protocol: Protocol) -> List[Pool]:
        """
        Retrieves all stored pools for a given protocol by querying the database.
        """
        return await self.db.get_all_pools(protocol)


if __name__ == '__main__':
    import dataclasses
    from pathlib import Path
    import shutil
    from .db import FileDB # For concrete DB in demo
    # For mocks/dummies for parser and sui_client:
    from .strategy import MockSuiClient as MockStrategySuiClient # Using the one from strategy.py's demo
    from .strategy import MockCetusParser # Using the one from strategy.py's demo
    from .types import Token, CetusPoolExtra # For manually adding to cache

    async def demo_dex_indexer():
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logger_main_demo = logging.getLogger(__name__ + ".Demo") # Specific logger for demo
        logger_main_demo.setLevel(logging.DEBUG)


        logger_main_demo.info("--- DexIndexer Demonstration ---")

        # --- Setup Mocks and Dependencies ---
        TEST_DB_PATH_MAIN = Path("./test_dex_indexer_main_db_data")
        if TEST_DB_PATH_MAIN.exists():
            shutil.rmtree(TEST_DB_PATH_MAIN)
        
        mock_sui_client_for_indexer = MockStrategySuiClient() # Using the mock from strategy's demo
        db_instance_for_indexer = FileDB(base_path=TEST_DB_PATH_MAIN, protocols=[Protocol.CETUS])
        pool_cache_for_indexer = PoolCache()
        # httpx client is needed by strategy for blockberry (though mock parser might not use it)
        http_client_bb = httpx.AsyncClient() 

        mock_cetus_parser_for_indexer = MockCetusParser()
        dex_protocol_parsers_for_indexer = {Protocol.CETUS: mock_cetus_parser_for_indexer}

        # --- Instantiate DexIndexer ---
        dex_indexer = DexIndexer(
            sui_client=mock_sui_client_for_indexer,
            db=db_instance_for_indexer,
            pool_cache=pool_cache_for_indexer,
            http_client_for_blockberry=http_client_bb,
            dex_protocol_parsers=dex_protocol_parsers_for_indexer
        )
        logger_main_demo.info("DexIndexer instantiated.")

        # --- Test Start (which also initializes components) ---
        logger_main_demo.info("\n--- Testing DexIndexer Start ---")
        await dex_indexer.start() # This will run sync_state of PoolCreatedStrategy
        logger_main_demo.info("DexIndexer started. Initial sync_state (backfill) should have run.")

        # --- Demonstrate Query Methods ---
        # Pool cache should be populated by the initial sync_state triggered by strategy initialization via engine.start()
        logger_main_demo.info("\n--- Demonstrating Query Methods (after initial sync) ---")
        
        # Check for a pool known to be created by the mock parser/strategy
        mock_pool_id_1 = "cetus_pool_mock_1"
        retrieved_pool = dex_indexer.get_pool_by_id(mock_pool_id_1)
        logger_main_demo.info(f"Get pool by ID '{mock_pool_id_1}': {retrieved_pool is not None}")
        assert retrieved_pool is not None, f"Pool {mock_pool_id_1} should be in cache after initial sync."
        if retrieved_pool:
             logger_main_demo.debug(f"Retrieved pool details: {retrieved_pool}")

        sui_token_type = "0x2::sui::SUI"
        pools_with_sui = dex_indexer.get_pools_by_token(sui_token_type)
        logger_main_demo.info(f"Get pools by token '{sui_token_type}': Count = {len(pools_with_sui) if pools_with_sui else 0}")
        assert pools_with_sui and len(pools_with_sui) > 0, "Should find pools with SUI."

        usdc_token_type = "0xUSDC::usdc::USDC"
        sui_usdc_pools = dex_indexer.get_pools_by_token01(sui_token_type, usdc_token_type)
        logger_main_demo.info(f"Get pools by token pair SUI-USDC: Count = {len(sui_usdc_pools) if sui_usdc_pools else 0}")
        assert sui_usdc_pools and any(p.pool_id == mock_pool_id_1 for p in sui_usdc_pools)

        cetus_pool_count_db = await dex_indexer.pool_count(Protocol.CETUS)
        logger_main_demo.info(f"DB pool count for CETUS: {cetus_pool_count_db}")
        # Mock parser creates 2 pools in its first (and only) page
        assert cetus_pool_count_db == 2 

        all_cetus_pools_db = await dex_indexer.get_all_pools(Protocol.CETUS)
        logger_main_demo.info(f"DB get all pools for CETUS: Count = {len(all_cetus_pools_db)}")
        assert len(all_cetus_pools_db) == 2


        # --- Simulate Event Processing via Engine's Event Queue ---
        logger_main_demo.info("\n--- Simulating Event Processing (QUERY_EVENT_TRIGGER) ---")
        # The QueryEventCollector will yield events. We just need to let the engine run.
        # The strategy's backfill will run again. Since mock query_events only returns data once,
        # no new pools should be added, but the logic will be exercised.
        
        # Let the engine run for a short time to process QueryEventCollector's event
        # QueryEventCollector has an initial delay, then yields.
        # Default tick is 10s. For demo, QueryEventCollector in main.py is default.
        # Let's assume a QueryEventCollector with a shorter interval was implicitly created
        # or we wait long enough for one tick.
        # For explicit test, we could create a collector with short tick.
        # Here, we'll just sleep, assuming the initial sync already did its job and
        # another tick might re-run backfill (though it won't find new data with current mocks).
        
        logger_main_demo.info("Simulating a short run for engine to process a QueryEventCollector tick (if interval allows)...")
        await asyncio.sleep(1.5) # Assuming default QEC interval is long, this might not trigger a new tick.
                                # If QEC used in _initialize_components_and_engine has a short tick, this might catch one.
                                # The main point is that the engine is running.

        # To explicitly test `process_event` path for `PoolCreatedStrategy`:
        logger_main_demo.info("Manually putting a QUERY_EVENT_TRIGGER onto engine's event queue for explicit test...")
        await dex_indexer.engine.event_queue.put(Event.QUERY_EVENT_TRIGGER)
        await asyncio.sleep(0.5) # Allow time for the strategy to process this event
        logger_main_demo.info("Manual event processing should have been triggered.")
        # (No new pools expected from mock data, but logs should show activity)


        # --- Test Stop ---
        logger_main_demo.info("\n--- Testing DexIndexer Stop ---")
        await dex_indexer.stop()
        logger_main_demo.info("DexIndexer stopped.")

        # --- Cleanup ---
        await http_client_bb.aclose()
        if TEST_DB_PATH_MAIN.exists():
            shutil.rmtree(TEST_DB_PATH_MAIN)
        logger_main_demo.info("DexIndexer Demonstration Finished.")

    asyncio.run(demo_dex_indexer())
