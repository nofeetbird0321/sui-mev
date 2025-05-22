# coding: utf-8
# Copyright (c) Mysten Labs, Inc.
# SPDX-License-Identifier: Apache-2.0

"""
Strategies for the DEX indexer, including pool creation detection.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

import httpx # For type hinting http_client_for_blockberry

# Assuming burberry_engine_py is installed or in PYTHONPATH
from burberry_engine_py.interfaces import StrategyInterface, ActionSubmitterInterface

# Relative imports for types and DB interface
from .types import Event, NoAction, Pool, PoolCache, Protocol
from .db import DB # Assuming DB is the ABC defined in db.py

if TYPE_CHECKING:
    # Mock pysui client for type hinting if not installed
    # In a real environment, pysui would be a dependency.
    class SuiClient: # type: ignore
        async def query_events(self, query: Dict[str, Any], cursor: Optional[Dict[str, str]], limit: int, descending_order: bool) -> Any: pass
    
    # Placeholder for protocol parser modules/objects
    class ProtocolParserModule:
        def cetus_event_filter(self) -> Dict[str, str]: pass # Example filter method name
        async def sui_event_to_pool(self, tx_digest: str, parsed_json: Dict[str, Any], sui_client: 'SuiClient', http_client: httpx.AsyncClient) -> Optional[Pool]: pass

logger = logging.getLogger(__name__)

# TODO: Move _token01_key to a shared utils module within dex_indexer_py
def _token01_key(token0_type: str, token1_type: str) -> Tuple[str, str]:
    """
    Creates a sorted key for a token pair.
    (Temporary duplication from FileDB, to be moved)
    """
    if token0_type <= token1_type:
        return (token0_type, token1_type)
    else:
        return (token1_type, token0_type)


class PoolCreatedStrategy(StrategyInterface[Event, NoAction]):
    """
    A strategy that detects new pool creation events by backfilling from supported protocols.
    """

    def __init__(
        self, 
        db: DB, 
        sui_client: Any, # Should be 'SuiClient' from pysui
        pool_cache: PoolCache, 
        http_client_for_blockberry: httpx.AsyncClient,
        dex_protocol_parsers: Dict[Protocol, Any] # Any is placeholder for ProtocolParserModule
    ):
        """
        Initializes the PoolCreatedStrategy.

        Args:
            db: The database interface for storing pools and cursors.
            sui_client: The Sui client for querying events.
            pool_cache: The cache for storing loaded pools.
            http_client_for_blockberry: HTTP client for Blockberry API calls.
            dex_protocol_parsers: A dictionary mapping Protocol enums to their
                                  respective parser modules/objects.
        """
        self.db = db
        self.sui_client = sui_client # Should be pysui's AsyncSuiClient
        self.pool_cache = pool_cache
        self.http_client_for_blockberry = http_client_for_blockberry
        self.dex_protocol_parsers = dex_protocol_parsers
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"PoolCreatedStrategy initialized for protocols: {[p.to_str() for p in dex_protocol_parsers.keys()]}")

    def name(self) -> str:
        """Returns the name of the strategy."""
        return "PoolCreatedStrategy"

    async def _backfill_pools_for_protocol(
        self, 
        protocol: Protocol, 
        parser: Any, # Placeholder for ProtocolParserModule
        cursor: Optional[str] # This should be the string cursor, not Dict[str, str]
    ) -> None:
        """
        Backfills pool creation events for a single protocol.
        """
        self.logger.info(f"Starting backfill for protocol: {protocol.to_str()} from cursor: {cursor}")
        
        # Adapt parser call based on actual structure. Assuming direct method call for now.
        # e.g., if parser is cetus_parser module, it would be parser.cetus_event_filter()
        # If parser is an object: parser.event_filter()
        # For this example, we'll assume method names are consistent or adapted.
        # Let's assume each parser module has a function like `get_pool_created_event_filter`
        # and `parse_sui_event_to_pool`.
        if not hasattr(parser, 'event_filter') or not hasattr(parser, 'sui_event_to_pool'):
             # Fallback to cetus_event_filter if specific methods aren't on the parser object
             # This is a simplification for the example. Real parsers would have consistent interface.
            if protocol == Protocol.CETUS and hasattr(parser, 'cetus_event_filter'):
                event_filter_query = parser.cetus_event_filter()
                sui_event_to_pool_func = parser.sui_event_to_pool # Assuming this matches signature
            else:
                self.logger.error(f"Parser for protocol {protocol.to_str()} does not have required 'event_filter' or 'sui_event_to_pool' methods.")
                return
        else: # Ideal case: parser object has standardized methods
            event_filter_query = parser.event_filter()
            sui_event_to_pool_func = parser.sui_event_to_pool


        page_limit = 10 # Number of events per query page
        current_cursor_for_pysui: Optional[Dict[str, str]] = None
        if cursor: # Convert string cursor to dict for pysui if needed
            # Pysui query_events cursor is Dict[str,str] with "txDigest" and "eventSeq"
            # This part depends heavily on how cursors are stored and used by pysui.
            # For this example, let's assume the stored cursor is a string that can be split
            # or is directly usable if pysui supports string cursor.
            # If cursor is "txDigest_eventSeq":
            try:
                if "_" in cursor:
                    tx_d, ev_s = cursor.split("_", 1)
                    current_cursor_for_pysui = {"txDigest": tx_d, "eventSeq": ev_s}
                else:
                    # If cursor is just txDigest (less common for event pagination)
                    # This is a simplification; robust cursor handling is needed.
                    current_cursor_for_pysui = {"txDigest": cursor, "eventSeq": "0"} 
            except ValueError:
                 self.logger.warning(f"Could not parse string cursor '{cursor}' into dict for pysui. Querying from start for {protocol.to_str()}.")
                 current_cursor_for_pysui = None


        last_processed_event_id_str: Optional[str] = cursor # Keep track of the last event ID string for DB flush

        try:
            while True:
                self.logger.debug(f"Querying events for {protocol.to_str()} with cursor: {current_cursor_for_pysui}, limit: {page_limit}")
                
                # page = await self.sui_client.query_events(query=event_filter_query, cursor=current_cursor_for_pysui, limit=page_limit, descending_order=False)
                # MOCKING pysui query_events call for now
                # Simulate a page of events; actual structure depends on pysui
                # SuiEvent has: id (EventID with txDigest, eventSeq), packageId, transactionModule, sender, type, parsedJson, bcs, timestampMs
                
                # --- MOCK RESPONSE from self.sui_client.query_events ---
                # Replace this with actual pysui call:
                # page = await self.sui_client.query_events(...) 
                mock_page_data = []
                if protocol == Protocol.CETUS and (current_cursor_for_pysui is None or current_cursor_for_pysui.get("txDigest") != "mocktx_final"): # Simulate one page
                    mock_page_data = [
                        {
                            "id": {"txDigest": "mocktx1", "eventSeq": "0"},
                            "packageId": "0xPKG_CETUS", "transactionModule": "factory", "sender": "0xSENDER1",
                            "type": "event_type_string_for_cetus_pool_created",
                            "parsedJson": {"pool_id": f"{protocol.to_str()}_pool_1", "coin_type_a": "0x2::sui::SUI", "coin_type_b": "0xUSDC::usdc::USDC"},
                            "bcs": "...", "timestampMs": str(int(asyncio.get_event_loop().time() * 1000))
                        },
                        {
                            "id": {"txDigest": "mocktx2", "eventSeq": "1"},
                            "packageId": "0xPKG_CETUS", "transactionModule": "factory", "sender": "0xSENDER2",
                            "type": "event_type_string_for_cetus_pool_created",
                            "parsedJson": {"pool_id": f"{protocol.to_str()}_pool_2", "coin_type_a": "0x2::sui::SUI", "coin_type_b": "0xETH::eth::ETH"},
                            "bcs": "...", "timestampMs": str(int(asyncio.get_event_loop().time() * 1000) + 10)
                        }
                    ]
                    # Simulate next_cursor for pysui
                    # Pysui's next_cursor is also a Dict[str, str] or None
                    mock_next_cursor_dict = {"txDigest": "mocktx_final", "eventSeq": "0"}
                    mock_has_next_page = True
                else:
                    mock_next_cursor_dict = None
                    mock_has_next_page = False
                
                # Mock object for page, assuming it has 'data', 'next_cursor', 'has_next_page'
                class MockPage:
                    def __init__(self, data, next_cursor_dict, has_next_page_flag):
                        self.data = [type('EventData', (), item) for item in data] # Convert dicts to objects with attributes
                        self.next_cursor = next_cursor_dict
                        self.has_next_page = has_next_page_flag
                page = MockPage(mock_page_data, mock_next_cursor_dict, mock_has_next_page)
                # --- END MOCK RESPONSE ---


                if not page.data:
                    self.logger.info(f"No more events found for {protocol.to_str()}.")
                    break

                newly_added_pools: List[Pool] = []
                latest_event_id_this_page_str: Optional[str] = None

                for event_data in page.data:
                    # Adapt based on actual parser function signature and event_data structure from pysui
                    # Assuming event_data has .id.tx_digest, .id.event_seq, .parsedJson
                    # The parser might need event_data.id (which is EventID type) or specific fields from it.
                    # For sui_event_to_pool, we used (tx_digest, parsed_json, ...), so adapt:
                    tx_d = event_data.id.txDigest # type: ignore
                    parsed_j = event_data.parsedJson # type: ignore
                    
                    pool = await sui_event_to_pool_func(tx_d, parsed_j, self.sui_client, self.http_client_for_blockberry)
                    
                    if pool:
                        if pool.pool_id not in self.pool_cache.pool_map:
                            self.pool_cache.pool_map[pool.pool_id] = pool
                            for token in pool.tokens:
                                self.pool_cache.token_pools.setdefault(token.token_type, set()).add(pool)
                            for t0_type, t1_type in pool.token01_pairs():
                                key = _token01_key(t0_type, t1_type)
                                self.pool_cache.token01_pools.setdefault(key, set()).add(pool)
                            newly_added_pools.append(pool)
                            self.logger.info(f"Discovered new pool for {protocol.to_str()}: {pool.pool_id}")
                        else:
                            self.logger.debug(f"Pool {pool.pool_id} already in cache. Skipping addition.")
                    
                    # Update latest_event_id_this_page_str for cursor management
                    # Pysui cursor is based on EventID (txDigest, eventSeq)
                    latest_event_id_this_page_str = f"{event_data.id.txDigest}_{event_data.id.eventSeq}" # type: ignore


                if newly_added_pools:
                    # The cursor for db.flush should be the ID of the *last successfully processed event* in this batch.
                    # If latest_event_id_this_page_str is set, it means we processed events.
                    if latest_event_id_this_page_str:
                        await self.db.flush(protocol, newly_added_pools, latest_event_id_this_page_str)
                        last_processed_event_id_str = latest_event_id_this_page_str # Update overall last processed
                        self.logger.info(f"Flushed {len(newly_added_pools)} new pools for {protocol.to_str()}. New cursor: {last_processed_event_id_str}")
                    else:
                        # Should not happen if newly_added_pools is not empty.
                        self.logger.warning("newly_added_pools is not empty, but latest_event_id_this_page_str was not updated.")

                if not page.has_next_page:
                    self.logger.info(f"No next page of events for {protocol.to_str()}. Backfill for this protocol complete.")
                    break
                
                current_cursor_for_pysui = page.next_cursor # This is Dict[str,str] or None

        except Exception as e:
            self.logger.error(f"Error during backfill for protocol {protocol.to_str()}: {e}", exc_info=True)
        
        self.logger.info(f"Backfill for protocol {protocol.to_str()} finished. Final cursor recorded for DB (if any events processed): {last_processed_event_id_str}")


    async def backfill_all_protocols(self) -> None:
        """
        Initiates backfill for all configured DEX protocols concurrently.
        """
        self.logger.info("Starting backfill for all configured protocols.")
        try:
            cursors = await self.db.get_processed_cursors()
            self.logger.debug(f"Retrieved processed cursors: {cursors}")
        except Exception as e:
            self.logger.error(f"Failed to get processed cursors from DB: {e}. Cannot proceed with backfill.", exc_info=True)
            return

        tasks = []
        for protocol_enum, parser_module in self.dex_protocol_parsers.items():
            protocol_cursor = cursors.get(protocol_enum) # This will be string cursor or None
            tasks.append(
                self._backfill_pools_for_protocol(protocol_enum, parser_module, protocol_cursor)
            )

        if not tasks:
            self.logger.info("No protocols configured for backfill.")
            return

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            # Log exceptions from individual backfill tasks
            # Task order is preserved from `tasks` list.
            # Find corresponding protocol for logging:
            protocol_for_task = list(self.dex_protocol_parsers.keys())[i]
            if isinstance(result, Exception):
                self.logger.error(f"Exception during backfill task for protocol {protocol_for_task.to_str()}: {result}", exc_info=result)
        
        self.logger.info("Backfill for all protocols completed (or attempted).")


    async def sync_state(self, submitter: ActionSubmitterInterface[NoAction]) -> None:
        """
        Synchronizes state by backfilling pools from all configured protocols.
        """
        self.logger.info(f"{self.name()}: Syncing state...")
        await self.backfill_all_protocols()
        self.logger.info(f"{self.name()}: State sync finished.")
        # submitter is not used in this strategy as it produces NoAction


    async def process_event(self, event: Event, submitter: ActionSubmitterInterface[NoAction]) -> None:
        """
        Processes an event. If it's a QUERY_EVENT_TRIGGER, initiates backfill.
        """
        if event == Event.QUERY_EVENT_TRIGGER:
            self.logger.info(f"{self.name()}: Received {Event.QUERY_EVENT_TRIGGER}. Triggering backfill for all protocols.")
            await self.backfill_all_protocols()
        else:
            self.logger.debug(f"{self.name()}: Received unhandled event type: {event}. Ignoring.")
        # submitter is not used


if __name__ == '__main__':
    import dataclasses # For dummy types
    from .db import FileDB # For concrete DB
    from pathlib import Path
    import shutil

    # --- Mock Implementations for Dependencies ---
    class MockSuiClient: # Simpler mock for strategy test
        async def query_events(self, query: Dict[str, Any], cursor: Optional[Dict[str, str]], limit: int, descending_order: bool) -> Any:
            logger.info(f"MockSuiClient.query_events called: query={query}, cursor={cursor}, limit={limit}, desc={descending_order}")
            # Simulate one page of data for CETUS, then no more.
            if query.get("MoveEventType") == "CETUS_POOL_CREATED_EVENT_TYPE_MOCK" and (cursor is None or cursor.get("txDigest") != "final_mock_tx"):
                class MockEventData:
                    def __init__(self, tx_digest, event_seq, parsed_json_data):
                        self.id = type('EventID', (), {'txDigest': tx_digest, 'eventSeq': str(event_seq)})()
                        self.packageId = "0xPKG_CETUS_MOCK"
                        self.transactionModule = "factory"
                        self.sender = "0xSENDER_MOCK"
                        self.type = "CETUS_POOL_CREATED_EVENT_TYPE_MOCK"
                        self.parsedJson = parsed_json_data
                        self.bcs = "mock_bcs"
                        self.timestampMs = str(int(asyncio.get_event_loop().time() * 1000))
                
                class MockPageResponse:
                    def __init__(self):
                        self.data = [
                            MockEventData("mocktx_page1_event1", 0, {"pool_id": "cetus_pool_mock_1", "coin_type_a": "0x2::sui::SUI", "coin_type_b": "0xUSDC::usdc::USDC"}),
                            MockEventData("mocktx_page1_event2", 1, {"pool_id": "cetus_pool_mock_2", "coin_type_a": "0x2::sui::SUI", "coin_type_b": "0xETH::eth::ETH"})
                        ]
                        self.next_cursor = {"txDigest": "final_mock_tx", "eventSeq": "0"} # Simulate next page cursor
                        self.has_next_page = True
                return MockPageResponse()
            
            # If cursor indicates last page or different query type
            class EmptyMockPageResponse:
                 def __init__(self):
                    self.data = []
                    self.next_cursor = None
                    self.has_next_page = False
            return EmptyMockPageResponse()

        async def get_coin_metadata(self, coin_type: str) -> Optional[Dict[str, Any]]:
            if coin_type == "0x2::sui::SUI": return {"decimals": 9}
            if "USDC" in coin_type: return {"decimals": 6}
            if "ETH" in coin_type: return {"decimals": 8}
            return None

        async def get_object(self, object_id: str, options: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
            # Simulate returning fee_rate for Cetus pools
            if "cetus_pool_mock" in object_id:
                return {"data": {"content": {"fields": {"fee_rate": "3000"}}}} # fee_rate as string
            return None


    # Mock Cetus Parser Module (as an object with methods for this demo)
    class MockCetusParser:
        def event_filter(self) -> Dict[str, str]: # Renamed for consistency
            return {"MoveEventType": "CETUS_POOL_CREATED_EVENT_TYPE_MOCK"}

        async def sui_event_to_pool(self, tx_digest: str, parsed_json: Dict[str, Any], sui_client: Any, http_client: httpx.AsyncClient) -> Optional[Pool]:
            from .types import Token, CetusPoolExtra # Local import for demo
            
            coin_a_type = parsed_json['coin_type_a']
            coin_b_type = parsed_json['coin_type_b']
            
            deca_a = await sui_client.get_coin_metadata(coin_a_type)
            deca_b = await sui_client.get_coin_metadata(coin_b_type)
            
            if deca_a is None or deca_b is None: return None
            
            token_a = Token(coin_a_type, deca_a['decimals'])
            token_b = Token(coin_b_type, deca_b['decimals'])
            
            pool_obj_data = await sui_client.get_object(parsed_json['pool_id'])
            fee_rate = 0
            if pool_obj_data and pool_obj_data.get('data', {}).get('content', {}).get('fields', {}).get('fee_rate'):
                fee_rate = int(pool_obj_data['data']['content']['fields']['fee_rate'])

            return Pool(
                protocol=Protocol.CETUS,
                pool_id=parsed_json['pool_id'],
                tokens=sorted([token_a, token_b]),
                extra=CetusPoolExtra(fee_rate=fee_rate)
            )

    @dataclasses.dataclass
    class MockActionSubmitter(ActionSubmitterInterface[NoAction]):
        async def submit(self, action: NoAction) -> None:
            logger.info(f"MockActionSubmitter: NoAction submitted (type: {type(action)}).")


    async def demo_pool_created_strategy():
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logger.info("--- PoolCreatedStrategy Demonstration ---")

        TEST_DB_PATH = Path("./test_strategy_db_data")
        if TEST_DB_PATH.exists():
            shutil.rmtree(TEST_DB_PATH)
        
        mock_sui_client = MockSuiClient()
        mock_http_client = httpx.AsyncClient() # For blockberry, though mock parser doesn't use it here
        
        # Setup DB and PoolCache
        # For FileDB, list all protocols it might manage.
        # The strategy will only operate on protocols passed in dex_protocol_parsers.
        db_instance = FileDB(base_path=TEST_DB_PATH, protocols=[Protocol.CETUS, Protocol.TURBOS]) # Example
        pool_cache_instance = PoolCache()

        # Setup parsers
        cetus_parser_instance = MockCetusParser()
        protocol_parsers = {Protocol.CETUS: cetus_parser_instance}

        # Initialize Strategy
        strategy = PoolCreatedStrategy(
            db=db_instance,
            sui_client=mock_sui_client,
            pool_cache=pool_cache_instance,
            http_client_for_blockberry=mock_http_client,
            dex_protocol_parsers=protocol_parsers
        )
        logger.info(f"Strategy Name: {strategy.name()}")

        # 1. Test sync_state (which calls backfill_all_protocols)
        logger.info("\n--- Testing sync_state ---")
        mock_submitter = MockActionSubmitter()
        await strategy.sync_state(mock_submitter)
        
        # Verify cache and DB state after sync
        logger.info(f"Pool Cache after sync (pool_map keys): {list(strategy.pool_cache.pool_map.keys())}")
        assert "cetus_pool_mock_1" in strategy.pool_cache.pool_map
        assert "cetus_pool_mock_2" in strategy.pool_cache.pool_map
        
        db_cursors = await db_instance.get_processed_cursors()
        logger.info(f"DB cursors after sync: {db_cursors}")
        assert db_cursors.get(Protocol.CETUS) == "final_mock_tx_0" # Based on mock pagination

        # 2. Test process_event with QUERY_EVENT_TRIGGER
        logger.info("\n--- Testing process_event (QUERY_EVENT_TRIGGER) ---")
        # Simulate a new event arriving after initial sync, should re-trigger backfill
        # For this demo, the mock sui_client won't return new data unless cursor logic is reset/changed.
        # So, this will mostly test the call path.
        await strategy.process_event(Event.QUERY_EVENT_TRIGGER, mock_submitter)
        # No new pools expected from mock, but backfill should run.
        logger.info("process_event with QUERY_EVENT_TRIGGER completed.")

        # 3. Test with an empty protocol list (optional, for robustness)
        logger.info("\n--- Testing with no configured protocols ---")
        empty_strategy = PoolCreatedStrategy(db_instance, mock_sui_client, PoolCache(), mock_http_client, {})
        await empty_strategy.sync_state(mock_submitter) # Should complete without error
        logger.info("Sync_state with no protocols completed.")


        # Cleanup
        await mock_http_client.aclose()
        if TEST_DB_PATH.exists(): # Clean up test DB
            shutil.rmtree(TEST_DB_PATH)
        logger.info("--- PoolCreatedStrategy Demonstration Finished ---")

    asyncio.run(demo_pool_created_strategy())
