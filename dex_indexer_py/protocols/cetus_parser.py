# coding: utf-8
# Copyright (c) Mysten Labs, Inc.
# SPDX-License-Identifier: Apache-2.0

"""
Cetus protocol specific parsing logic for dex_indexer_py.
"""

import dataclasses
import json
import logging
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

import httpx # For blockberry client

# Assuming common_utils_py.coin and dex_indexer_py.utils.blockberry are available
try:
    from common_utils_py.coin import normalize_coin_type
except ImportError:
    def normalize_coin_type(coin_type: str) -> str: # Placeholder
        if coin_type == "0x0000000000000000000000000000000000000000000000000000000000000002::sui::SUI":
            return "0x2::sui::SUI"
        return coin_type

try:
    from dex_indexer_py.utils import blockberry
except ImportError:
    # Mock blockberry if not available for isolated testing
    class MockBlockberry:
        async def get_coin_decimals(self, coin_type: str, http_client: Optional[httpx.AsyncClient] = None) -> Optional[int]:
            logger.warning(f"MockBlockberry: get_coin_decimals called for {coin_type}. Returning None or default.")
            if coin_type == "0x2::sui::SUI": return 9
            return None # Default mock behavior
    blockberry = MockBlockberry() # type: ignore


if TYPE_CHECKING:
    from dex_indexer_py.types import Pool, Token, CetusPoolExtra, Protocol, SwapEvent
    # Mock pysui client for type hinting if not installed
    # In a real environment, pysui would be a dependency.
    class SuiClient: # type: ignore
        async def get_coin_metadata(self, coin_type: str) -> Optional[Dict[str, Any]]: pass
        async def get_object(self, object_id: str, options: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]: pass
        async def get_dynamic_fields(self, parent_id: str, cursor: Optional[str] = None, limit: Optional[int] = None) -> Optional[Dict[str, Any]]: pass
else:
    # Define a placeholder for SuiClient if not type checking, to allow module to load
    # This allows the file to be parsed without pysui installed, but it won't run correctly.
    class SuiClient:
        def __init__(self, *args, **kwargs):
            logger.warning("Real pysui.SuiClient not available. Using placeholder mock.")
        async def get_coin_metadata(self, coin_type: str) -> Optional[Dict[str, Any]]:
            logger.warning(f"MockSuiClient: get_coin_metadata called for {coin_type}")
            if coin_type == "0x2::sui::SUI": return {"decimals": 9}
            if "usdc" in coin_type.lower(): return {"decimals": 6}
            if "eth" in coin_type.lower(): return {"decimals": 8}
            return None
        async def get_object(self, object_id: str, options: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
            logger.warning(f"MockSuiClient: get_object called for {object_id}")
            # Simulate Cetus pool object structure
            if "pool" in object_id: # Very basic mock
                return {
                    "data": {
                        "content": {
                            "fields": {
                                "fee_rate": "3000", # Example value (string per Rust code)
                                "tick_manager": {"fields": {"id": {"id": f"{object_id}_tick_manager"}}},
                                "position_manager": {"fields": {"id": {"id": f"{object_id}_position_manager"}}},
                                # Simulate type parameters for get_pool_coin_types_from_rpc
                                "type": f"0x123::pool::Pool<0x2::sui::SUI, 0xUSDC::usdc::USDC>" # Example
                            }
                        },
                        "type": f"0x123::pool::Pool<0x2::sui::SUI, 0xUSDC::usdc::USDC>" # Example
                    }
                }
            return None
        async def get_dynamic_fields(self, parent_id: str, cursor: Optional[str] = None, limit: Optional[int] = None) -> Optional[Dict[str, Any]]:
            logger.warning(f"MockSuiClient: get_dynamic_fields called for {parent_id}")
            # Simulate some dynamic fields
            return {"data": [{"objectId": f"{parent_id}_df_1"}, {"objectId": f"{parent_id}_df_2"}]}


logger = logging.getLogger(__name__)

# --- Constants ---
CETUS_POOL_CREATED_EVENT_TYPE = "0x1eabed72c53feb3805120a081dc15963c204dc8d091542592abaf7a35689b2fb::factory::CreatePoolEvent"
CETUS_SWAP_EVENT_TYPE = "0x1eabed72c53feb3805120a081dc15963c204dc8d091542592abaf7a35689b2fb::pool::SwapEvent"
CETUS_PACKAGE_ID = "0x3a5aa90ffa33d09100d7b6941ea1c0ffe6ab66e77062ddd26320c1b073aabb10"
_SUI_RPC_NODE_URL_FOR_DYNAMIC_FIELDS = "https://rpc.mainnet.sui.io/" # Placeholder


# --- Internal Dataclasses for Event Parsing ---
@dataclasses.dataclass
class CetusPoolCreatedInternal:
    pool_id: str
    token_type_a: str
    token_type_b: str

    @classmethod
    def from_sui_event_json(cls, event_json: Dict[str, Any]) -> Optional['CetusPoolCreatedInternal']:
        try:
            # Normalize coin types right away if needed, or assume they are canonical
            return cls(
                pool_id=event_json['pool_id'],
                token_type_a=normalize_coin_type(event_json['coin_type_a']),
                token_type_b=normalize_coin_type(event_json['coin_type_b'])
            )
        except KeyError as e:
            logger.error(f"Missing key in Cetus CreatePoolEvent JSON: {e}. Data: {event_json}")
            return None

@dataclasses.dataclass
class CetusSwapEventInternal:
    pool_id: str
    amount_in: int
    amount_out: int
    a_to_b: bool # True if swapping token_a for token_b

    @classmethod
    def from_event_json(cls, event_json: Dict[str, Any]) -> Optional['CetusSwapEventInternal']:
        try:
            return cls(
                pool_id=event_json['pool_id'],
                amount_in=int(event_json['amount_in']),
                amount_out=int(event_json['amount_out']),
                a_to_b=bool(event_json['a_to_b'])
            )
        except (KeyError, ValueError) as e:
            logger.error(f"Error parsing Cetus SwapEvent JSON: {e}. Data: {event_json}")
            return None


# --- Functions ---

def cetus_event_filter() -> Dict[str, str]:
    """Returns the event filter for Cetus pool creation events."""
    return {"MoveEventType": CETUS_POOL_CREATED_EVENT_TYPE}

async def get_coin_decimals_from_rpc(sui_client: SuiClient, coin_type: str) -> Optional[int]:
    """Helper to get coin decimals using pysui client."""
    try:
        metadata = await sui_client.get_coin_metadata(coin_type=coin_type)
        if metadata and "decimals" in metadata:
            return int(metadata["decimals"])
        logger.warning(f"Could not get decimals from RPC for {coin_type}. Metadata: {metadata}")
        return None
    except Exception as e:
        logger.error(f"Error fetching coin metadata via RPC for {coin_type}: {e}")
        return None

async def get_pool_coin_types_from_rpc(sui_client: SuiClient, pool_id_str: str) -> Optional[Tuple[str, str]]:
    """Helper to get pool's coin types from its object type via RPC."""
    try:
        pool_obj = await sui_client.get_object(object_id=pool_id_str, options={"showType": True})
        if pool_obj and pool_obj.get("data") and pool_obj["data"].get("type"):
            # Example type string: "0xPACKAGE::pool::Pool<TYPE_A, TYPE_B>"
            type_str = pool_obj["data"]["type"]
            # Basic parsing, assuming format like "...<T1, T2>"
            if '<' in type_str and '>' in type_str:
                params_str = type_str[type_str.find('<') + 1 : type_str.rfind('>')]
                type_params = [p.strip() for p in params_str.split(',')]
                if len(type_params) >= 2: # Cetus pools are typically 2 tokens
                    return (normalize_coin_type(type_params[0]), normalize_coin_type(type_params[1]))
            logger.error(f"Could not parse coin types from pool object type string: {type_str}")
            return None
        logger.warning(f"Could not get object or type for pool {pool_id_str}. Object: {pool_obj}")
        return None
    except Exception as e:
        logger.error(f"Error fetching pool object type for {pool_id_str}: {e}")
        return None


async def cetus_sui_event_to_pool(
    event_id_str: str, # Currently unused, but part of the signature from mod.rs
    event_json: Dict[str, Any],
    sui_client: SuiClient,
    http_client_for_blockberry: httpx.AsyncClient
) -> Optional['Pool']:
    """
    Converts a Cetus pool creation SuiEvent to a generic Pool object.
    """
    # Required here for concrete types
    from dex_indexer_py.types import Pool, Token, CetusPoolExtra, Protocol

    parsed_event = CetusPoolCreatedInternal.from_sui_event_json(event_json)
    if not parsed_event:
        return None

    # Fetch decimals for token_a
    decimals_a = await get_coin_decimals_from_rpc(sui_client, parsed_event.token_type_a)
    if decimals_a is None: # Fallback to Blockberry
        decimals_a = await blockberry.get_coin_decimals(parsed_event.token_type_a, http_client=http_client_for_blockberry)
    if decimals_a is None:
        logger.error(f"Failed to get decimals for token_a {parsed_event.token_type_a} for pool {parsed_event.pool_id}")
        return None # Or handle as error / default

    # Fetch decimals for token_b
    decimals_b = await get_coin_decimals_from_rpc(sui_client, parsed_event.token_type_b)
    if decimals_b is None: # Fallback to Blockberry
        decimals_b = await blockberry.get_coin_decimals(parsed_event.token_type_b, http_client=http_client_for_blockberry)
    if decimals_b is None:
        logger.error(f"Failed to get decimals for token_b {parsed_event.token_type_b} for pool {parsed_event.pool_id}")
        return None

    token_a = Token(token_type=parsed_event.token_type_a, decimals=decimals_a)
    token_b = Token(token_type=parsed_event.token_type_b, decimals=decimals_b)

    # Fetch pool object to get fee_rate
    fee_rate_val: Optional[int] = None
    try:
        # Assuming sui_client.get_object returns a dict-like structure
        # TODO: Confirm exact field path with pysui's get_object response structure
        # Example path: result.data.content.fields.fee_rate
        pool_obj_response = await sui_client.get_object(object_id=parsed_event.pool_id, options={"showContent": True})
        if pool_obj_response and pool_obj_response.get("data") and pool_obj_response["data"].get("content"):
            fields = pool_obj_response["data"]["content"].get("fields", {})
            if "fee_rate" in fields:
                fee_rate_val = int(fields["fee_rate"]) # Rust code has u64, typically string in JSON, convert to int
            else:
                logger.error(f"fee_rate not found in Cetus pool object {parsed_event.pool_id}. Fields: {fields}")
        else:
            logger.error(f"Could not fetch or parse Cetus pool object {parsed_event.pool_id}. Response: {pool_obj_response}")
    except Exception as e:
        logger.error(f"Error fetching/parsing fee_rate for Cetus pool {parsed_event.pool_id}: {e}")

    if fee_rate_val is None:
        logger.warning(f"Using default fee_rate (0) for Cetus pool {parsed_event.pool_id} as it couldn't be fetched.")
        fee_rate_val = 0 # Default or error

    pool_extra = CetusPoolExtra(fee_rate=fee_rate_val)
    
    # Pool tokens should be sorted by token_type for consistent representation
    tokens = sorted([token_a, token_b], key=lambda t: t.token_type)

    return Pool(
        protocol=Protocol.CETUS,
        pool_id=parsed_event.pool_id,
        tokens=tokens,
        extra=pool_extra
    )

async def _parse_swap(
    event_json: Dict[str, Any],
    sui_client: SuiClient,
    source_type_str: str # "SuiEvent" or "ShioEvent" for logging
) -> Optional['SwapEvent']:
    """Internal helper to parse swap event JSON (from Sui or Shio)."""
    # Required here for concrete types
    from dex_indexer_py.types import SwapEvent, Protocol

    parsed_swap = CetusSwapEventInternal.from_event_json(event_json)
    if not parsed_swap:
        logger.error(f"Failed to parse internal CetusSwapEvent from {source_type_str} JSON: {event_json}")
        return None

    coin_types = await get_pool_coin_types_from_rpc(sui_client, parsed_swap.pool_id)
    if not coin_types or len(coin_types) < 2:
        logger.error(f"Could not determine coin types for pool {parsed_swap.pool_id} from {source_type_str}.")
        return None
    
    token_type_a, token_type_b = coin_types[0], coin_types[1]

    if parsed_swap.a_to_b:
        coin_in_type = token_type_a
        coin_out_type = token_type_b
    else:
        coin_in_type = token_type_b
        coin_out_type = token_type_a
    
    return SwapEvent(
        protocol=Protocol.CETUS,
        pool_id=parsed_swap.pool_id,
        coins_in=[coin_in_type],
        coins_out=[coin_out_type],
        amounts_in=[parsed_swap.amount_in],
        amounts_out=[parsed_swap.amount_out]
    )

async def cetus_sui_event_to_swap_event(event_json: Dict[str, Any], sui_client: SuiClient) -> Optional['SwapEvent']:
    """Converts a Cetus swap SuiEvent to a generic SwapEvent."""
    return await _parse_swap(event_json, sui_client, "SuiEvent")

async def cetus_shio_event_to_swap_event(event_json: Dict[str, Any], sui_client: SuiClient) -> Optional['SwapEvent']:
    """Converts a Cetus swap ShioEvent to a generic SwapEvent."""
    # Assuming ShioEvent's parsed_json for Cetus swaps has the same structure as SuiEvent's parsed_json
    return await _parse_swap(event_json, sui_client, "ShioEvent")


def cetus_static_related_object_ids() -> List[str]:
    """Returns a list of static Cetus global object IDs relevant for indexing or monitoring."""
    # These are typically global objects like factory state, admin capabilities, etc.
    # Based on Rust code for Cetus:
    return [
        "0xc243890b081587dd9104f9610e87af9929184200e8886075b6076d95506d481a", # GLOBAL
        "0xdaa72d06823b383a99815bdda1b0887185a52f15f80655778784964791107835", # GLOBAL_CONFIG
        "0x530c96557904163905a38355998181849817153a698cce8006a6680570f75997", # LAUNCHPAD_GLOBAL_CONFIG
        # Add other relevant static/global IDs if known
    ]

async def cetus_pool_children_ids(pool: 'Pool', sui_client: SuiClient) -> List[str]:
    """
    Retrieves IDs of objects considered children or components of a Cetus pool.
    This is a simplified version.
    """
    from dex_indexer_py.types import Pool as PoolConcrete # For isinstance check

    if not isinstance(pool, PoolConcrete):
        logger.error(f"cetus_pool_children_ids: Expected Pool object, got {type(pool)}")
        return []
        
    child_ids: List[str] = []

    # 1. Fetch the main pool object to get manager IDs
    try:
        pool_obj_response = await sui_client.get_object(object_id=pool.pool_id, options={"showContent": True})
        if pool_obj_response and pool_obj_response.get("data") and pool_obj_response["data"].get("content"):
            fields = pool_obj_response["data"]["content"].get("fields", {})
            
            # TODO: Confirm exact field paths for tick_manager and position_manager IDs with pysui response
            tick_manager_id_obj = fields.get("tick_manager", {}).get("fields", {}).get("id", {}).get("id")
            position_manager_id_obj = fields.get("position_manager", {}).get("fields", {}).get("id", {}).get("id")

            manager_ids_to_query: List[str] = []
            if tick_manager_id_obj:
                manager_ids_to_query.append(tick_manager_id_obj)
            else:
                logger.warning(f"Could not find tick_manager_id for Cetus pool {pool.pool_id}")
            
            if position_manager_id_obj:
                manager_ids_to_query.append(position_manager_id_obj)
            else:
                logger.warning(f"Could not find position_manager_id for Cetus pool {pool.pool_id}")

            # 2. For each manager ID, get some dynamic fields (child objects)
            for manager_id in manager_ids_to_query:
                try:
                    # Fetching only a few dynamic fields as an example.
                    # In Rust, it iterates through all dynamic fields for ticks.
                    # TODO: Implement more comprehensive dynamic field fetching if needed (pagination).
                    dynamic_fields_response = await sui_client.get_dynamic_fields(parent_id=manager_id, limit=10) # Limit for simplicity
                    if dynamic_fields_response and dynamic_fields_response.get("data"):
                        for df_info in dynamic_fields_response["data"]:
                            if "objectId" in df_info:
                                child_ids.append(df_info["objectId"])
                except Exception as e_df:
                    logger.error(f"Error fetching dynamic fields for manager {manager_id} of pool {pool.pool_id}: {e_df}")
        else:
            logger.error(f"Could not fetch or parse main Cetus pool object {pool.pool_id} for children IDs.")
    except Exception as e_pool:
        logger.error(f"Error fetching main pool object {pool.pool_id} for children IDs: {e_pool}")

    # TODO: Implement tick score simulation part if required for advanced logic.
    # For now, this simplified version returns manager IDs (if found) and some of their dynamic field object IDs.
    # The original Rust code adds the manager IDs themselves to the list of children if they are objects.
    # Here, we are adding dynamic fields OF the managers.
    # If the managers themselves are child objects to be monitored, they should also be added.
    # For now, let's add the manager IDs that were successfully extracted.
    if tick_manager_id_obj: child_ids.append(tick_manager_id_obj)
    if position_manager_id_obj: child_ids.append(position_manager_id_obj)
    
    return list(set(child_ids)) # Return unique IDs


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Mock SuiClient for testing
    mock_sui_client = SuiClient() # Uses the placeholder mock defined above
    mock_http_client = httpx.AsyncClient() # For blockberry

    # Import concrete types for test usage
    from dex_indexer_py.types import Protocol, Token, CetusPoolExtra, Pool

    async def demo_cetus_parser():
        print("--- Testing Cetus Event Filter ---")
        event_filter = cetus_event_filter()
        print(f"Cetus Event Filter: {event_filter}")
        assert event_filter["MoveEventType"] == CETUS_POOL_CREATED_EVENT_TYPE

        print("\n--- Testing Cetus Pool Creation Event to Pool ---")
        # Example CreatePoolEvent JSON (structure based on typical Sui events)
        create_pool_event_json = {
            "pool_id": "0xTEST_CETUS_POOL_1",
            "coin_type_a": "0x2::sui::SUI",
            "coin_type_b": "0xUSDC::usdc::USDC" # Assume normalized for this test
        }
        # Mock the get_object response for this pool_id if cetus_sui_event_to_pool tries to fetch it
        # (Our current mock SuiClient has a generic pool response)
        
        pool_obj = await cetus_sui_event_to_pool(
            event_id_str="dummy_event_id_pool",
            event_json=create_pool_event_json,
            sui_client=mock_sui_client,
            http_client_for_blockberry=mock_http_client
        )
        if pool_obj:
            print(f"Parsed Pool: {pool_obj}")
            assert pool_obj.pool_id == "0xTEST_CETUS_POOL_1"
            assert pool_obj.protocol == Protocol.CETUS
            assert len(pool_obj.tokens) == 2
            assert pool_obj.tokens[0].token_type == "0x2::sui::SUI"
            assert pool_obj.tokens[0].decimals == 9 # From mock
            assert pool_obj.tokens[1].token_type == "0xUSDC::usdc::USDC"
            assert pool_obj.tokens[1].decimals == 6 # From mock
            assert isinstance(pool_obj.extra, CetusPoolExtra)
            assert pool_obj.extra.fee_rate == 3000 # From mock SuiClient.get_object
        else:
            print("Failed to parse Pool from CreatePoolEvent.")

        print("\n--- Testing Cetus Swap Event to SwapEvent ---")
        # Example SwapEvent JSON
        swap_event_json = {
            "pool_id": "0xTEST_CETUS_POOL_1", # Use the same pool ID
            "amount_in": "1000000000", # String for u64
            "amount_out": "650000",    # String for u64
            "a_to_b": True,
            # Other fields like vault_a_amount, vault_b_amount, fee_amount etc. might exist
            # but are not used by CetusSwapEventInternal currently.
        }
        # Mock get_pool_coin_types_from_rpc for this pool_id
        # (Our current mock SuiClient.get_object has a generic response that can provide this)
        
        swap_obj = await cetus_sui_event_to_swap_event(
            event_json=swap_event_json,
            sui_client=mock_sui_client
        )
        if swap_obj:
            print(f"Parsed SwapEvent: {swap_obj}")
            assert swap_obj.pool_id == "0xTEST_CETUS_POOL_1"
            assert swap_obj.protocol == Protocol.CETUS
            assert swap_obj.coins_in == ["0x2::sui::SUI"] # Based on a_to_b and mock pool type
            assert swap_obj.coins_out == ["0xUSDC::usdc::USDC"]
            assert swap_obj.amounts_in == [1000000000]
            assert swap_obj.amounts_out == [650000]
        else:
            print("Failed to parse SwapEvent from SuiEvent.")

        print("\n--- Testing Cetus Static Related Object IDs ---")
        static_ids = cetus_static_related_object_ids()
        print(f"Static Related IDs: {static_ids}")
        assert len(static_ids) >= 2 # Check a few known ones

        print("\n--- Testing Cetus Pool Children IDs (Simplified) ---")
        if pool_obj: # Requires a successfully parsed pool object
            children_ids = await cetus_pool_children_ids(pool_obj, mock_sui_client)
            print(f"Children IDs for pool {pool_obj.pool_id}: {children_ids}")
            # Expected: pool_id_tick_manager, pool_id_position_manager, and their dynamic fields
            expected_tick_manager_id = f"{pool_obj.pool_id}_tick_manager"
            expected_pos_manager_id = f"{pool_obj.pool_id}_position_manager"
            assert expected_tick_manager_id in children_ids
            assert expected_pos_manager_id in children_ids
            assert f"{expected_tick_manager_id}_df_1" in children_ids
            assert f"{expected_pos_manager_id}_df_2" in children_ids

        else:
            print("Skipping cetus_pool_children_ids test as pool_obj was not created.")


        print("\n--- Testing get_pool_coin_types_from_rpc ---")
        # This uses the mock get_object which returns a type string like
        # "0x123::pool::Pool<0x2::sui::SUI, 0xUSDC::usdc::USDC>"
        types_tuple = await get_pool_coin_types_from_rpc(mock_sui_client, "some_cetus_pool_id")
        if types_tuple:
            print(f"Coin types for 'some_cetus_pool_id': {types_tuple}")
            assert types_tuple == ("0x2::sui::SUI", "0xUSDC::usdc::USDC")
        else:
            print("Failed to get coin types via get_pool_coin_types_from_rpc.")
            
        await mock_http_client.aclose() # Close the httpx client used for blockberry

    asyncio.run(demo_cetus_parser())
    print("\nCetus parser demo finished.")

# Note: `pysui` and `httpx` would be requirements for this module to fully function.
