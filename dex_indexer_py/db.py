# coding: utf-8
# Copyright (c) Mysten Labs, Inc.
# SPDX-License-Identifier: Apache-2.0

"""
Database interfaces and file-based implementation for storing and retrieving DEX pool data.
"""

import abc
import asyncio
import json
import logging
from pathlib import Path
import shutil # For cleaning up in tests
from typing import Dict, List, Optional, Tuple, Union, TYPE_CHECKING

import aiofiles
import aiofiles.os

# Add 'aiofiles' to requirements.txt

if TYPE_CHECKING:
    from dex_indexer_py.types import Protocol, Pool, PoolCache, Token

logger = logging.getLogger(__name__)

class DB(abc.ABC):
    """Abstract Base Class for a database storing pool information."""

    @abc.abstractmethod
    async def flush(self, protocol: 'Protocol', pools: List['Pool'], cursor: Optional[str]) -> None:
        """
        Writes a list of pools and updates the processed cursor for a given protocol.
        """
        pass

    @abc.abstractmethod
    async def load_token_pools(self, protocols: List['Protocol']) -> 'PoolCache':
        """
        Loads all pools for the given protocols and organizes them into a PoolCache.
        """
        pass

    @abc.abstractmethod
    async def get_processed_cursors(self) -> Dict['Protocol', Optional[str]]:
        """
        Retrieves the last processed cursor for each protocol.
        """
        pass

    @abc.abstractmethod
    async def pool_count(self, protocol: 'Protocol') -> int:
        """
        Counts the number of stored pools for a given protocol.
        """
        pass

    @abc.abstractmethod
    async def get_all_pools(self, protocol: 'Protocol') -> List['Pool']:
        """
        Retrieves all stored pools for a given protocol.
        """
        pass


class FileDB(DB):
    """
    A file-based implementation of the DB interface.
    Pools for each protocol are stored in a text file (one pool per line).
    Processed cursors are stored in a JSON file.
    """

    def __init__(self, base_path: Union[str, Path], protocols: List['Protocol']):
        """
        Initializes the FileDB.

        Args:
            base_path: The directory where data files will be stored.
            protocols: A list of protocols this DB instance will manage.
        """
        # Required here due to potential for this module to be imported before types
        from dex_indexer_py.types import Protocol as ProtocolConcrete, Pool as PoolConcrete, PoolCache as PoolCacheConcrete

        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        self.pools_paths: Dict[ProtocolConcrete, Path] = {}
        for p in protocols:
            if not isinstance(p, ProtocolConcrete): # Ensure correct type if forward refs are used
                raise TypeError(f"Protocol must be an instance of dex_indexer_py.types.Protocol, got {type(p)}")
            self.pools_paths[p] = self.base_path / f"{p.to_str()}_pools.txt"

        self.cursors_path: Path = self.base_path / "processed_cursors.json"
        
        self.processed_cursors: Dict[ProtocolConcrete, Optional[str]] = {}
        try:
            with open(self.cursors_path, 'r') as f:
                loaded_cursors_str_keys = json.load(f)
                # Convert string keys back to Protocol enum members
                for p_str, cursor_val in loaded_cursors_str_keys.items():
                    try:
                        proto_enum = ProtocolConcrete.from_str(p_str)
                        if proto_enum != ProtocolConcrete.UNKNOWN : #Only load known protocols
                             self.processed_cursors[proto_enum] = cursor_val
                        else:
                            logger.warning(f"Found unknown protocol '{p_str}' in cursors file. Ignoring.")
                    except ValueError: # Should be caught by from_str returning UNKNOWN mostly
                        logger.warning(f"Could not parse protocol string '{p_str}' from cursors file. Ignoring.")

        except FileNotFoundError:
            logger.info(f"Cursors file {self.cursors_path} not found. Initializing empty cursors.")
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {self.cursors_path}. Initializing empty cursors.")
        except Exception as e:
            logger.error(f"Unexpected error loading cursors from {self.cursors_path}: {e}. Initializing empty cursors.")

        self._lock = asyncio.Lock()

    @staticmethod
    def _token01_key(token0_type: str, token1_type: str) -> Tuple[str, str]:
        """
        Creates a sorted key for a token pair.
        Mirrors token01_key from dex_indexer.lib.rs.
        """
        if token0_type <= token1_type:
            return (token0_type, token1_type)
        else:
            return (token1_type, token0_type)

    async def flush(self, protocol: 'Protocol', pools: List['Pool'], cursor: Optional[str]) -> None:
        from dex_indexer_py.types import Protocol as ProtocolConcrete

        if not isinstance(protocol, ProtocolConcrete):
             raise TypeError(f"Protocol must be an instance of dex_indexer_py.types.Protocol, got {type(protocol)}")

        pool_file_path = self.pools_paths.get(protocol)
        if not pool_file_path:
            logger.error(f"Attempted to flush for unconfigured protocol: {protocol}. Initialize FileDB with this protocol.")
            return

        async with self._lock:
            try:
                async with aiofiles.open(pool_file_path, mode='a', encoding='utf-8') as f:
                    for pool in pools:
                        await f.write(pool.to_line() + "\n")
                
                self.processed_cursors[protocol] = cursor

                # Serialize cursors with protocol enum keys as strings
                cursors_to_save = {p.to_str(): c for p, c in self.processed_cursors.items()}
                async with aiofiles.open(self.cursors_path, mode='w', encoding='utf-8') as f:
                    await f.write(json.dumps(cursors_to_save, indent=2))
                
                logger.info(f"Flushed {len(pools)} pools for {protocol.to_str()} and updated cursor to {cursor}. File: {pool_file_path}")

            except Exception as e:
                logger.error(f"Error during flush for protocol {protocol.to_str()}: {e}")
                # Potentially re-raise or handle more gracefully

    async def load_token_pools(self, protocols: List['Protocol']) -> 'PoolCache':
        from dex_indexer_py.types import Pool, PoolCache, Protocol as ProtocolConcrete

        token_pools_map: Dict[str, set['Pool']] = {}
        token01_pools_map: Dict[Tuple[str, str], set['Pool']] = {}
        pool_object_map: Dict[str, 'Pool'] = {}

        async with self._lock:
            for protocol in protocols:
                if not isinstance(protocol, ProtocolConcrete):
                    raise TypeError(f"Protocol must be an instance of dex_indexer_py.types.Protocol, got {type(protocol)}")

                pool_file_path = self.pools_paths.get(protocol)
                if not pool_file_path or not await aiofiles.os.path.exists(pool_file_path):
                    logger.warning(f"Pool file for protocol {protocol.to_str()} not found at {pool_file_path}. Skipping.")
                    continue
                
                try:
                    async with aiofiles.open(pool_file_path, mode='r', encoding='utf-8') as f:
                        async for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                pool = Pool.from_line(line)
                                pool_object_map[pool.pool_id] = pool
                                for token in pool.tokens:
                                    token_pools_map.setdefault(token.token_type, set()).add(pool)
                                
                                # For token01_pools_map, iterate through unique pairs
                                for t0_type, t1_type in pool.token01_pairs():
                                    key = self._token01_key(t0_type, t1_type)
                                    token01_pools_map.setdefault(key, set()).add(pool)

                            except ValueError as ve:
                                logger.error(f"Skipping invalid line in {pool_file_path}: '{line[:100]}...' - Error: {ve}")
                            except Exception as e: # Catch broader exceptions during line processing
                                logger.error(f"Unexpected error processing line in {pool_file_path}: '{line[:100]}...' - Error: {e}")
                except Exception as e:
                    logger.error(f"Error reading pool file {pool_file_path} for protocol {protocol.to_str()}: {e}")

        return PoolCache(
            token_pools=token_pools_map, 
            token01_pools=token01_pools_map, 
            pool_map=pool_object_map
        )

    async def get_processed_cursors(self) -> Dict['Protocol', Optional[str]]:
        async with self._lock:
            # Return a copy to prevent external modification of the internal state
            return self.processed_cursors.copy()

    async def pool_count(self, protocol: 'Protocol') -> int:
        from dex_indexer_py.types import Protocol as ProtocolConcrete
        if not isinstance(protocol, ProtocolConcrete):
             raise TypeError(f"Protocol must be an instance of dex_indexer_py.types.Protocol, got {type(protocol)}")

        pool_file_path = self.pools_paths.get(protocol)
        if not pool_file_path or not await aiofiles.os.path.exists(pool_file_path):
            return 0
        
        count = 0
        async with self._lock: # Lock ensures consistent read if flush is happening.
            try:
                async with aiofiles.open(pool_file_path, mode='r', encoding='utf-8') as f:
                    async for line in f:
                        if line.strip(): # Count non-empty lines
                            count += 1
            except Exception as e:
                logger.error(f"Error counting pools in {pool_file_path} for protocol {protocol.to_str()}: {e}")
                return 0 # Or raise
        return count

    async def get_all_pools(self, protocol: 'Protocol') -> List['Pool']:
        from dex_indexer_py.types import Pool, Protocol as ProtocolConcrete
        if not isinstance(protocol, ProtocolConcrete):
             raise TypeError(f"Protocol must be an instance of dex_indexer_py.types.Protocol, got {type(protocol)}")

        pools: List[Pool] = []
        pool_file_path = self.pools_paths.get(protocol)

        if not pool_file_path or not await aiofiles.os.path.exists(pool_file_path):
            logger.warning(f"Pool file for protocol {protocol.to_str()} not found at {pool_file_path}. Returning empty list.")
            return pools

        async with self._lock: # Lock ensures consistent read if flush is happening.
            try:
                async with aiofiles.open(pool_file_path, mode='r', encoding='utf-8') as f:
                    async for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            pool = Pool.from_line(line)
                            pools.append(pool)
                        except ValueError as ve:
                            logger.error(f"Skipping invalid line in {pool_file_path} during get_all_pools: '{line[:100]}...' - Error: {ve}")
                        except Exception as e:
                             logger.error(f"Unexpected error processing line in {pool_file_path} for get_all_pools: '{line[:100]}...' - Error: {e}")
            except Exception as e:
                logger.error(f"Error reading all pools from {pool_file_path} for protocol {protocol.to_str()}: {e}")
                # Depending on desired behavior, could return partially loaded pools or empty / raise
        return pools


if __name__ == '__main__':
    # This block is for basic demonstration and testing.
    # It requires types from dex_indexer_py.types to be fully defined.
    # For this subtask, we assume they are available for the test.
    from dex_indexer_py.types import Protocol, Pool, Token, CetusPoolExtra, PoolCache

    async def test_file_db():
        TEST_BASE_PATH = Path("./test_db_data")
        # Clean up previous test run
        if TEST_BASE_PATH.exists():
            shutil.rmtree(TEST_BASE_PATH)
        TEST_BASE_PATH.mkdir(parents=True, exist_ok=True)

        protocols_to_test = [Protocol.CETUS, Protocol.TURBOS]
        db = FileDB(base_path=TEST_BASE_PATH, protocols=protocols_to_test)

        print("--- Initial State ---")
        initial_cursors = await db.get_processed_cursors()
        print(f"Initial cursors: {initial_cursors}")
        assert initial_cursors == {} # Or reflects pre-existing if not cleaned

        cetus_pool_count = await db.pool_count(Protocol.CETUS)
        print(f"Initial Cetus pool count: {cetus_pool_count}")
        assert cetus_pool_count == 0

        print("\n--- Flushing Some Pools (Cetus) ---")
        token_sui = Token(token_type="0x2::sui::SUI", decimals=9)
        token_usdc = Token(token_type="0xUSDC::usdc::USDC", decimals=6)
        cetus_extra1 = CetusPoolExtra(fee_rate=30)
        pool_c1 = Pool(protocol=Protocol.CETUS, pool_id="cetus_pool_1", tokens=[token_sui, token_usdc], extra=cetus_extra1)
        
        await db.flush(Protocol.CETUS, [pool_c1], "cetus_cursor_123")
        
        cetus_pool_count_after_flush = await db.pool_count(Protocol.CETUS)
        print(f"Cetus pool count after flush: {cetus_pool_count_after_flush}")
        assert cetus_pool_count_after_flush == 1

        cursors_after_flush = await db.get_processed_cursors()
        print(f"Cursors after flush: {cursors_after_flush}")
        assert cursors_after_flush.get(Protocol.CETUS) == "cetus_cursor_123"

        print("\n--- Loading Token Pools ---")
        pool_cache: PoolCache = await db.load_token_pools(protocols_to_test)
        print(f"Pool cache - pool_map keys: {list(pool_cache.pool_map.keys())}")
        assert "cetus_pool_1" in pool_cache.pool_map
        assert pool_cache.pool_map["cetus_pool_1"].protocol == Protocol.CETUS
        
        sui_pools = pool_cache.token_pools.get(token_sui.token_type)
        print(f"Pools containing SUI: {sui_pools}")
        assert sui_pools and pool_c1 in sui_pools

        sui_usdc_pair_key = FileDB._token01_key(token_sui.token_type, token_usdc.token_type)
        sui_usdc_pools = pool_cache.token01_pools.get(sui_usdc_pair_key)
        print(f"Pools for SUI-USDC pair: {sui_usdc_pools}")
        assert sui_usdc_pools and pool_c1 in sui_usdc_pools


        print("\n--- Getting All Pools (Cetus) ---")
        all_cetus_pools = await db.get_all_pools(Protocol.CETUS)
        print(f"All Cetus pools retrieved: {len(all_cetus_pools)}")
        assert len(all_cetus_pools) == 1
        assert all_cetus_pools[0].pool_id == "cetus_pool_1"

        print("\n--- Testing with another protocol (Turbos) ---")
        token_eth = Token(token_type="0xETH::eth::ETH", decimals=8)
        # TurbosPoolExtra would be defined in types.py, for now use Cetus as placeholder if not fully mocked
        from dex_indexer_py.types import TurbosPoolExtra # Assuming this exists
        turbos_extra1 = TurbosPoolExtra(fee_rate=10, sqrt_price="dummy_sqrt_price_1")
        pool_t1 = Pool(protocol=Protocol.TURBOS, pool_id="turbos_pool_1", tokens=[token_sui, token_eth], extra=turbos_extra1)
        await db.flush(Protocol.TURBOS, [pool_t1], "turbos_cursor_abc")

        turbos_pool_count = await db.pool_count(Protocol.TURBOS)
        assert turbos_pool_count == 1
        
        cursors_after_turbos_flush = await db.get_processed_cursors()
        assert cursors_after_turbos_flush.get(Protocol.TURBOS) == "turbos_cursor_abc"

        print("\n--- Reloading DB instance to test persistence ---")
        db_reloaded = FileDB(base_path=TEST_BASE_PATH, protocols=protocols_to_test)
        reloaded_cursors = await db_reloaded.get_processed_cursors()
        print(f"Reloaded cursors: {reloaded_cursors}")
        assert reloaded_cursors.get(Protocol.CETUS) == "cetus_cursor_123"
        assert reloaded_cursors.get(Protocol.TURBOS) == "turbos_cursor_abc"

        reloaded_pool_cache = await db_reloaded.load_token_pools(protocols_to_test)
        assert "cetus_pool_1" in reloaded_pool_cache.pool_map
        assert "turbos_pool_1" in reloaded_pool_cache.pool_map
        assert len(reloaded_pool_cache.pool_map) == 2

        print("\n--- Test _token01_key static method ---")
        key1 = FileDB._token01_key("A", "B")
        assert key1 == ("A", "B")
        key2 = FileDB._token01_key("B", "A")
        assert key2 == ("A", "B")
        print("_token01_key tests passed.")

        print("\nFileDB tests completed.")
        
        # Clean up test directory
        # Comment out to inspect files after test
        # if TEST_BASE_PATH.exists():
        #     shutil.rmtree(TEST_BASE_PATH)
        # print(f"Cleaned up test directory: {TEST_BASE_PATH}")

    if __name__ == "__main__": # Check to ensure this is the main execution
        # The check `if __name__ == '__main__':` inside an `if __name__ == '__main__':`
        # is redundant but harmless. The outer one is standard.
        asyncio.run(test_file_db())
