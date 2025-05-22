# coding: utf-8
# Copyright (c) Mysten Labs, Inc.
# SPDX-License-Identifier: Apache-2.0

"""
Cache for managing overridden objects during transaction simulation.
"""

import dataclasses # Not strictly needed here but often used with types
import logging
import time
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

# Attempt to import SUI_CLOCK_OBJECT_ID from pysui, otherwise use a placeholder
try:
    from pysui.sui.sui_constants import SUI_CLOCK_OBJECT_ID
except ImportError:
    SUI_CLOCK_OBJECT_ID = "0x0000000000000000000000000000000000000000000000000000000000000006"
    logging.warning(f"pysui.sui.sui_constants.SUI_CLOCK_OBJECT_ID not found. Using placeholder: {SUI_CLOCK_OBJECT_ID}")


if TYPE_CHECKING:
    from simulator_py.abc import Simulator
    # For override_objects_data items, assuming they are dicts with 'objectId', 'version', 'data' etc.
    # No specific ObjectReadResult type defined in this project's types.py yet.


class OverrideCache:
    """
    Manages a cache of objects, prioritizing explicitly overridden objects,
    then versioned objects, and finally falling back to a provided data store.
    """

    def __init__(self, fallback_store: Optional['Simulator'] = None, override_objects_data: Optional[List[Any]] = None):
        """
        Initializes the OverrideCache.

        Args:
            fallback_store: Optional. A Simulator instance to fetch objects if not found in overrides.
            override_objects_data: Optional. A list of object data dictionaries to pre-populate
                                   the override cache. Each dict should have at least 'objectId'.
        """
        self.fallback_store: Optional['Simulator'] = fallback_store
        self.overrides: Dict[str, Any] = {}  # Stores object_id -> object_data (latest override)
        self.versioned_cache: Dict[Tuple[str, int], Any] = {}  # Stores (object_id, version) -> object_data
        self.logger = logging.getLogger(__name__)

        if override_objects_data:
            for obj_data in override_objects_data:
                if isinstance(obj_data, dict) and "objectId" in obj_data:
                    self.overrides[obj_data["objectId"]] = obj_data
                    # If version is available, could also populate versioned_cache here,
                    # but overrides typically mean "use this specific state regardless of version".
                    # For now, only populating self.overrides.
                else:
                    self.logger.warning(f"Invalid item in override_objects_data (missing 'objectId' or not a dict): {obj_data}")
        
        self.logger.info(f"OverrideCache initialized. Fallback store: {fallback_store.name() if fallback_store else 'None'}. Overrides count: {len(self.overrides)}")


    def _get_current_clock_object(self) -> Any:
        """
        Helper method to construct a current clock object dictionary.
        This mimics the structure of a Sui Clock object.
        """
        current_timestamp_ms = int(time.time() * 1000)
        # The version of the live Clock object is dynamic and reflects its last update.
        # For a simulated override, version 0 might be misleading if compared to a live object.
        # However, for simulation purposes where we just need a consistent clock value,
        # a fixed or high version number might be acceptable if not interacting with live comparisons.
        # Let's use a high "version" to denote it's a synthetic/current clock.
        # Or, treat it as version-less for override purposes if version matching is strict.
        # For now, let's use a "version" that's unlikely to clash if we were to also cache a real clock.
        # A more robust way might be to have get_override_object not check version for clock.
        # For simplicity, assigning a version, but acknowledging this nuance.
        # The Rust code uses Clock::new_for_testing(timestamp_ms).version(), which might be 0 or 1.
        # Let's use a fixed version for the synthetic clock.
        clock_version = 1 # Arbitrary, but consistent for this synthetic object.

        return {
            "objectId": SUI_CLOCK_OBJECT_ID,
            "version": clock_version, # Or a dynamic version if needed
            "digest": "SIMULATED_CLOCK_DIGEST", # Placeholder
            "type": "0x2::clock::Clock", # Standard type
            "owner": "Shared", # Clock is a shared object
            "previousTransaction": "SIMULATED_CLOCK_TX_DIGEST", # Placeholder
            "storageRebate": "0", # Placeholder
            "content": { # Mimicking SuiObjectContent structure
                "dataType": "moveObject",
                "type": "0x2::clock::Clock",
                "hasPublicTransfer": False,
                "fields": { # Mimicking Move object fields
                    "id": {"id": SUI_CLOCK_OBJECT_ID},
                    "timestamp_ms": str(current_timestamp_ms) # Fields are often strings in JSON
                }
            },
            # Adding 'data' wrapper to somewhat mimic SuiRpcResult/SuiObjectResponse structure
            # if consumers expect obj.data.content etc.
            "data": {
                "objectId": SUI_CLOCK_OBJECT_ID,
                "version": str(clock_version), # Versions from RPC are often strings
                "digest": "SIMULATED_CLOCK_DIGEST",
                "type": "0x2::clock::Clock",
                "owner": "Shared",
                "previousTransaction": "SIMULATED_CLOCK_TX_DIGEST",
                "storageRebate": "0",
                "content": {
                    "dataType": "moveObject",
                    "type": "0x2::clock::Clock",
                    "hasPublicTransfer": False,
                    "fields": {
                        "id": {"id": SUI_CLOCK_OBJECT_ID},
                        "timestamp_ms": str(current_timestamp_ms)
                    }
                }
            }
        }

    def get_override_object(self, object_id: str) -> Optional[Any]:
        """
        Retrieves an object from the override cache.
        Returns a dynamically generated Clock object if SUI_CLOCK_OBJECT_ID is requested.
        """
        if object_id == SUI_CLOCK_OBJECT_ID:
            return self._get_current_clock_object()
        return self.overrides.get(object_id)

    async def get_object(self, object_id: str) -> Optional[Any]:
        """
        Retrieves an object, checking overrides first, then the fallback store.
        Objects retrieved from the fallback store are cached by (id, version).
        """
        override_obj = self.get_override_object(object_id)
        if override_obj is not None:
            self.logger.debug(f"[get_object] Found in overrides: {object_id}")
            return override_obj

        if self.fallback_store:
            self.logger.warning(f"❗️ [get_object] override missing for {object_id}, using fallback.")
            try:
                obj_from_fallback = await self.fallback_store.get_object(object_id)
                if obj_from_fallback:
                    # Assuming obj_from_fallback is a dict-like structure with 'objectId' and 'version'
                    # (or can be adapted if it's a pysui object with attributes)
                    obj_version_str = obj_from_fallback.get('version', obj_from_fallback.get('data', {}).get('version'))
                    
                    if obj_version_str is not None:
                        try:
                            obj_version = int(obj_version_str)
                            self.versioned_cache[(object_id, obj_version)] = obj_from_fallback
                            self.logger.debug(f"[get_object] Cached from fallback: {object_id} v{obj_version}")
                        except ValueError:
                            self.logger.error(f"[get_object] Could not parse version '{obj_version_str}' to int for {object_id} from fallback.")
                    else:
                         self.logger.warning(f"[get_object] Object from fallback {object_id} missing version. Not caching by version.")
                    return obj_from_fallback
            except Exception as e:
                self.logger.error(f"Error fetching object {object_id} from fallback_store: {e}", exc_info=True)
                return None # Or re-raise depending on desired error handling
        
        self.logger.debug(f"[get_object] Not found in overrides or fallback: {object_id}")
        return None

    async def get_object_by_key(self, object_id: str, version: int) -> Optional[Any]:
        """
        Retrieves an object by ID and version, checking overrides (if version matches)
        and then the versioned cache. Fallback is commented out as Simulator ABC
        does not enforce versioned fetching.
        """
        override_obj = self.get_override_object(object_id)
        if override_obj is not None:
            # Check if the override's version matches the requested version.
            # This assumes the override_obj has a 'version' key.
            # For the clock, its "version" is synthetic, so direct version match might be tricky
            # if the requested version is specific from a transaction.
            # If it's the clock, its version is fixed by _get_current_clock_object.
            override_version_str = override_obj.get('version', override_obj.get('data', {}).get('version'))
            if override_version_str is not None:
                try:
                    override_version = int(override_version_str)
                    if override_version == version:
                        self.logger.debug(f"[get_object_by_key] Found in overrides (version match): {object_id} v{version}")
                        return override_obj
                    # If versions don't match, it means the specific override is not for this version.
                    # Fall through to check versioned_cache.
                except ValueError:
                     self.logger.error(f"[get_object_by_key] Could not parse version '{override_version_str}' for override obj {object_id}.")
            else:
                # If override object has no version, it cannot satisfy a versioned request.
                self.logger.debug(f"[get_object_by_key] Override for {object_id} found but has no version info. Cannot match v{version}.")


        cached_obj = self.versioned_cache.get((object_id, version))
        if cached_obj is not None:
            self.logger.debug(f"[get_object_by_key] Found in versioned_cache: {object_id} v{version}")
            return cached_obj

        self.logger.warning(f"❗️ [get_object_by_key] override or versioned_cache missing for {object_id} v{version}.")
        
        # Fallback store for specific version:
        # The Simulator ABC does not currently define a get_object_by_key method.
        # If it did, or if the specific fallback_store type supports it (e.g., via options in get_object):
        # if self.fallback_store:
        #     self.logger.info(f"Attempting fallback for versioned object: {object_id} v{version}")
        #     try:
        #         # obj_versioned_fallback = await self.fallback_store.get_object_by_key(object_id, version) # Hypothetical
        #         # Or, if get_object can take version options (e.g. tryGetPastObject in pysui)
        #         # obj_versioned_fallback = await self.fallback_store.get_object(object_id, options={"version": version})
        #         # if obj_versioned_fallback:
        #         #     self.versioned_cache[(object_id, version)] = obj_versioned_fallback # Cache if found
        #         #     return obj_versioned_fallback
        #         pass # Placeholder for actual versioned fetch logic
        #     except Exception as e:
        #         self.logger.error(f"Error fetching versioned object {object_id} v{version} from fallback_store: {e}")

        return None

    def get_versioned_object_from_cache(self, object_id: str, version: int) -> Optional[Any]:
        """
        Retrieves an object directly from the versioned_cache.
        """
        return self.versioned_cache.get((object_id, version))


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # --- Mock Fallback Store (Simulator implementation) ---
    class MockFallbackSimulator: # Basic implementation for testing
        async def get_object(self, object_id: str) -> Optional[Any]:
            logger.info(f"MockFallbackSimulator: get_object called for {object_id}")
            if object_id == "0xFALLBACK_EXISTS":
                return {"objectId": object_id, "version": "1", "data": "data_from_fallback"}
            if object_id == "0xFALLBACK_EXISTS_V2":
                 return {"objectId": object_id, "version": "2", "data": "data_from_fallback_v2"}
            return None
        
        def name(self) -> str:
            return "MockFallbackSim"
        
        # Other Simulator methods if needed for more complex tests
        async def simulate(self, tx_data: Any, ctx: Any) -> Any: return None 
        def get_object_layout(self, object_id: str) -> Optional[Any]: return None


    async def demo_override_cache():
        print("--- Testing OverrideCache ---")

        # 1. Initialize with override data and a mock fallback store
        override_data_list = [
            {"objectId": "0xOVERRIDE_1", "version": "10", "data": "override_data_1"},
            {"objectId": "0xCLOCK_IS_SPECIAL", "version": "1", "data": "this_should_be_ignored_for_clock"} 
        ]
        mock_fallback = MockFallbackSimulator()
        cache = OverrideCache(fallback_store=mock_fallback, override_objects_data=override_data_list)

        # 2. Test get_override_object
        print("\n--- Testing get_override_object ---")
        obj_override_1 = cache.get_override_object("0xOVERRIDE_1")
        print(f"get_override_object('0xOVERRIDE_1'): {obj_override_1}")
        assert obj_override_1 is not None and obj_override_1["data"] == "override_data_1"

        clock_obj = cache.get_override_object(SUI_CLOCK_OBJECT_ID)
        print(f"get_override_object(SUI_CLOCK_OBJECT_ID): type={type(clock_obj)}, id={clock_obj['objectId']}") # type: ignore
        assert clock_obj is not None and clock_obj["objectId"] == SUI_CLOCK_OBJECT_ID # type: ignore
        assert "timestamp_ms" in clock_obj["content"]["fields"] # type: ignore
        initial_clock_ts = int(clock_obj["content"]["fields"]["timestamp_ms"]) # type: ignore
        await asyncio.sleep(0.01) # Sleep for a tiny bit
        clock_obj_again = cache.get_override_object(SUI_CLOCK_OBJECT_ID)
        new_clock_ts = int(clock_obj_again["content"]["fields"]["timestamp_ms"]) # type: ignore
        assert new_clock_ts > initial_clock_ts, "Clock timestamp should advance"


        # 3. Test async get_object
        print("\n--- Testing async get_object ---")
        # Test overridden object
        obj_async_override = await cache.get_object("0xOVERRIDE_1")
        print(f"await get_object('0xOVERRIDE_1'): {obj_async_override}")
        assert obj_async_override == obj_override_1

        # Test clock object via async get_object
        obj_async_clock = await cache.get_object(SUI_CLOCK_OBJECT_ID)
        print(f"await get_object(SUI_CLOCK_OBJECT_ID): id={obj_async_clock['objectId']}") # type: ignore
        assert obj_async_clock is not None and obj_async_clock["objectId"] == SUI_CLOCK_OBJECT_ID # type: ignore

        # Test object from fallback store
        obj_async_fallback = await cache.get_object("0xFALLBACK_EXISTS")
        print(f"await get_object('0xFALLBACK_EXISTS'): {obj_async_fallback}")
        assert obj_async_fallback is not None and obj_async_fallback["data"] == "data_from_fallback" # type: ignore
        # Check if it was added to versioned_cache
        assert cache.versioned_cache.get(("0xFALLBACK_EXISTS", 1)) == obj_async_fallback

        # Test non-existent object
        obj_async_nonexistent = await cache.get_object("0xNON_EXISTENT")
        print(f"await get_object('0xNON_EXISTENT'): {obj_async_nonexistent}")
        assert obj_async_nonexistent is None

        # 4. Test async get_object_by_key
        print("\n--- Testing async get_object_by_key ---")
        # Test overridden object with matching version (assuming 'version' field exists and matches)
        # Our current get_override_object doesn't check version, but get_object_by_key does.
        # Let's assume "0xOVERRIDE_1" has version "10" as per override_data_list.
        obj_key_override_match = await cache.get_object_by_key("0xOVERRIDE_1", 10)
        print(f"await get_object_by_key('0xOVERRIDE_1', 10): {obj_key_override_match}")
        assert obj_key_override_match is not None and obj_key_override_match["data"] == "override_data_1"

        obj_key_override_mismatch = await cache.get_object_by_key("0xOVERRIDE_1", 11) # Version mismatch
        print(f"await get_object_by_key('0xOVERRIDE_1', 11): {obj_key_override_mismatch}")
        assert obj_key_override_mismatch is None # Should be None as override is v10, not in versioned_cache yet for v11

        # Test object from versioned_cache (populated by previous get_object call)
        obj_key_versioned_cache = await cache.get_object_by_key("0xFALLBACK_EXISTS", 1)
        print(f"await get_object_by_key('0xFALLBACK_EXISTS', 1): {obj_key_versioned_cache}")
        assert obj_key_versioned_cache == obj_async_fallback

        # Test object not in cache for specific version
        obj_key_not_cached_version = await cache.get_object_by_key("0xFALLBACK_EXISTS", 5) # Version 5 not seen
        print(f"await get_object_by_key('0xFALLBACK_EXISTS', 5): {obj_key_not_cached_version}")
        assert obj_key_not_cached_version is None # Fallback for versioned get is commented out

        # Test clock object by key (version is synthetic, should match if requested version is that synthetic one)
        clock_synthetic_version = clock_obj["version"] # type: ignore
        obj_key_clock = await cache.get_object_by_key(SUI_CLOCK_OBJECT_ID, clock_synthetic_version) # type: ignore
        print(f"await get_object_by_key(SUI_CLOCK_OBJECT_ID, {clock_synthetic_version}): id={obj_key_clock['objectId'] if obj_key_clock else 'None'}") # type: ignore
        assert obj_key_clock is not None and obj_key_clock["objectId"] == SUI_CLOCK_OBJECT_ID # type: ignore

        # 5. Test get_versioned_object_from_cache
        print("\n--- Testing get_versioned_object_from_cache ---")
        cached_v_obj = cache.get_versioned_object_from_cache("0xFALLBACK_EXISTS", 1)
        print(f"get_versioned_object_from_cache('0xFALLBACK_EXISTS', 1): {cached_v_obj}")
        assert cached_v_obj == obj_async_fallback

        not_cached_v_obj = cache.get_versioned_object_from_cache("0xFALLBACK_EXISTS", 100)
        print(f"get_versioned_object_from_cache('0xFALLBACK_EXISTS', 100): {not_cached_v_obj}")
        assert not_cached_v_obj is None

        print("\nOverrideCache demo finished.")

    asyncio.run(demo_override_cache())
