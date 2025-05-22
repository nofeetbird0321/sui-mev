# coding: utf-8
# Copyright (c) Mysten Labs, Inc.
# SPDX-License-Identifier: Apache-2.0

"""
Python type definitions mirroring the Rust structs and enums in crates/dex-indexer/src/types.rs.
"""

import dataclasses
import enum
import json
from typing import Any, Dict, List, Optional, Set, Tuple, Type, TypeVar

# Assuming common_utils_py.coin.SUI_COIN_TYPE exists. For this file, we'll use a placeholder if not directly importable.
try:
    from common_utils_py.coin import SUI_COIN_TYPE, normalize_coin_type as normalize_coin_type_actual
except ImportError:
    SUI_COIN_TYPE = "0x2::sui::SUI" # Placeholder
    def normalize_coin_type_actual(coin_type: str) -> str: # Placeholder
        # In a real scenario, this would import from common_utils_py.coin
        if coin_type == "0x0000000000000000000000000000000000000000000000000000000000000002::sui::SUI":
            return SUI_COIN_TYPE
        return coin_type

T = TypeVar('T')

class Protocol(enum.Enum):
    CETUS = "cetus"
    TURBOS = "turbos"
    AFTERMATH = "aftermath"
    # Add other protocols as needed
    UNKNOWN = "unknown"

    def to_str(self) -> str:
        return self.value

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_str(cls, s: str) -> 'Protocol':
        s_lower = s.lower()
        for member in cls:
            if member.value == s_lower:
                return member
        # Fallback or raise error
        # For now, returning UNKNOWN for simplicity, matching Rust's FromStr<Protocol> behavior
        return cls.UNKNOWN


@dataclasses.dataclass(frozen=True) # Making Token hashable for sets, etc.
class Token:
    token_type: str
    decimals: int

    def __init__(self, token_type: str, decimals: int):
        # Object is frozen, so we must use __setattr__
        # For this subtask, assume token_type is already normalized as per instructions.
        # In a real scenario:
        # object.__setattr__(self, "token_type", normalize_coin_type_actual(token_type))
        object.__setattr__(self, "token_type", token_type)
        object.__setattr__(self, "decimals", decimals)

    def __lt__(self, other: 'Token') -> bool:
        # For sorting tokens within a pool, primarily by token_type
        if not isinstance(other, Token):
            return NotImplemented
        return self.token_type < other.token_type


@dataclasses.dataclass
class PoolExtra:
    """Base class for protocol-specific extra pool data."""
    type: str = dataclasses.field(init=False) # To aid deserialization

    def __post_init__(self):
        # Automatically set the type based on the class name for serialization
        self.type = self.__class__.__name__

    def to_dict(self) -> Dict[str, Any]:
        # Include the 'type' field
        d = dataclasses.asdict(self)
        d['type'] = self.type # Ensure type is correctly set from class name
        return d
    
    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        # Generic from_dict, specific subclasses might override if needed
        # This assumes 'type' field is present and matches class name for dispatch in Pool.from_line
        # For direct instantiation (e.g. CetusPoolExtra.from_dict), 'type' field in data is not strictly needed
        # but it's good practice to handle it.
        data.pop('type', None) # Remove 'type' if present, as it's not a field in all subclasses' __init__
        
        # Get constructor fields
        known_fields = {f.name for f in dataclasses.fields(cls)}
        # Filter data to only include known fields
        filtered_data = {k: v for k, v in data.items() if k in known_fields}
        
        return cls(**filtered_data)


@dataclasses.dataclass
class CetusPoolExtra(PoolExtra):
    fee_rate: int # e.g., in basis points or scaled value

@dataclasses.dataclass
class TurbosPoolExtra(PoolExtra):
    fee_rate: int # Placeholder, adjust to actual fields
    sqrt_price: str # Placeholder, typically a large integer string

@dataclasses.dataclass
class AftermathPoolExtra(PoolExtra):
    # Example fields, adjust to actual Aftermath pool structure
    lp_fee_pct: float
    swap_fee_pct: float
    # Aftermath pools can have more than 2 tokens and weights
    weights: List[int] = dataclasses.field(default_factory=list)


# Mapping for PoolExtra deserialization
POOL_EXTRA_TYPES: Dict[str, Type[PoolExtra]] = {
    "CetusPoolExtra": CetusPoolExtra,
    "TurbosPoolExtra": TurbosPoolExtra,
    "AftermathPoolExtra": AftermathPoolExtra,
    "PoolExtra": PoolExtra, # Fallback for base or unknown
}


P = TypeVar('P', bound='Pool')
@dataclasses.dataclass
class Pool:
    protocol: Protocol
    pool_id: str
    tokens: List[Token] # Should be sorted by token_type for consistent representation
    extra: PoolExtra

    def __post_init__(self):
        # Ensure tokens are sorted by token_type for consistent pair representation
        # and reliable token_index behavior if not already sorted.
        self.tokens.sort()


    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Pool):
            return NotImplemented
        return self.pool_id == other.pool_id

    def __hash__(self) -> int:
        return hash(self.pool_id)

    def token0_type(self) -> str:
        if len(self.tokens) < 1:
            raise IndexError("Pool has no tokens for token0_type")
        return self.tokens[0].token_type

    def token1_type(self) -> str:
        if len(self.tokens) < 2:
            raise IndexError("Pool has less than 2 tokens for token1_type")
        return self.tokens[1].token_type

    def token_count(self) -> int:
        return len(self.tokens)

    def token_index(self, token_type: str) -> Optional[int]:
        # Assumes self.tokens is sorted by token_type
        normalized_tt = normalize_coin_type_actual(token_type)
        for i, token in enumerate(self.tokens):
            if token.token_type == normalized_tt:
                return i
        return None

    def get_token(self, index: int) -> Optional[Token]:
        if 0 <= index < len(self.tokens):
            return self.tokens[index]
        return None

    def token01_pairs(self) -> List[Tuple[str, str]]:
        """Returns all unique, sorted pairs of token types in the pool."""
        pairs = []
        if len(self.tokens) < 2:
            return pairs
        # Assuming tokens are already sorted by token_type
        for i in range(len(self.tokens)):
            for j in range(i + 1, len(self.tokens)):
                # Pair is always (token_type_sorted_lexicographically_first, token_type_sorted_lexicographically_second)
                # Since self.tokens is sorted, tokens[i].token_type < tokens[j].token_type
                pairs.append((self.tokens[i].token_type, self.tokens[j].token_type))
        return pairs

    def to_line(self) -> str:
        # Ensure tokens are dicts, not Token objects, for JSON serialization
        tokens_json_list = [dataclasses.asdict(token) for token in self.tokens]
        tokens_json = json.dumps(tokens_json_list)
        
        # Use PoolExtra's to_dict method which includes the 'type' field
        extra_dict = self.extra.to_dict()
        extra_json = json.dumps(extra_dict)
        
        return f"{self.protocol.to_str()}|{self.pool_id}|{tokens_json}|{extra_json}"

    @classmethod
    def from_line(cls: Type[P], line: str) -> P:
        parts = line.strip().split('|', 3)
        if len(parts) != 4:
            raise ValueError(f"Invalid line format for Pool: {line}")

        protocol_str, pool_id_str, tokens_json_str, extra_json_str = parts

        protocol = Protocol.from_str(protocol_str)
        
        tokens_list_of_dicts = json.loads(tokens_json_str)
        tokens = [Token(token_type=td['token_type'], decimals=td['decimals']) for td in tokens_list_of_dicts]
        
        extra_dict = json.loads(extra_json_str)
        extra_type_str = extra_dict.get('type', "PoolExtra") # Default to base if type is missing
        
        extra_class = POOL_EXTRA_TYPES.get(extra_type_str, PoolExtra) # Fallback to base PoolExtra
        
        # Pass the whole dict to the specific PoolExtra subclass's from_dict or constructor
        pool_extra_instance = extra_class.from_dict(extra_dict)
        
        return cls(protocol=protocol, pool_id=pool_id_str, tokens=tokens, extra=pool_extra_instance)


@dataclasses.dataclass
class PoolCache:
    token_pools: Dict[str, Set[Pool]] = dataclasses.field(default_factory=dict)
    token01_pools: Dict[Tuple[str, str], Set[Pool]] = dataclasses.field(default_factory=dict)
    pool_map: Dict[str, Pool] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class SwapEvent:
    protocol: Protocol
    pool_id: Optional[str] # Not all protocols might have pool_id directly in event
    coins_in: List[str]    # List of coin type strings
    coins_out: List[str]   # List of coin type strings
    amounts_in: List[int]
    amounts_out: List[int]

    def get_pool_id(self) -> Optional[str]:
        return self.pool_id

    def involved_coin_one_side(self) -> str:
        """
        Returns the coin type string that is involved on one side of the swap.
        Prioritizes SUI. If SUI is not involved, returns the first coin_in.
        """
        for coin_type in self.coins_in + self.coins_out:
            if normalize_coin_type_actual(coin_type) == SUI_COIN_TYPE:
                return SUI_COIN_TYPE
        if self.coins_in:
            return self.coins_in[0]
        if self.coins_out: # Should not happen if coins_in is empty for a valid swap
            return self.coins_out[0]
        return "" # Should not happen for a valid swap


# Burberry-related placeholders
class Event(enum.Enum):
    QUERY_EVENT_TRIGGER = "query_event_trigger"
    # Add other event types as needed

@dataclasses.dataclass
class NoAction:
    """Represents no action to be taken."""
    pass

@dataclasses.dataclass
class DummyExecutor:
    """
    Placeholder for a class that would implement an Executor Abstract Base Class (ABC) later.
    An executor would typically handle the execution of transactions or strategies.
    """
    name: str = "DummyExecutor"

    async def execute(self, action: Any) -> Any:
        print(f"{self.name}: Executing action: {action}")
        return None # Placeholder for actual execution result


if __name__ == '__main__':
    print("--- Testing Protocol Enum ---")
    proto_cetus = Protocol.CETUS
    print(f"Enum member: {proto_cetus}, string: {proto_cetus.to_str()}, __str__: {str(proto_cetus)}")
    assert proto_cetus.to_str() == "cetus"
    proto_from_str = Protocol.from_str("TURBOS")
    assert proto_from_str == Protocol.TURBOS
    proto_unknown = Protocol.from_str("nonexistent")
    assert proto_unknown == Protocol.UNKNOWN
    print("Protocol Enum tests passed.")

    print("\n--- Testing Token ---")
    # Assuming normalize_coin_type_actual is available or mocked for testing
    # For this subtask, direct instantiation as per problem statement:
    token_sui = Token(token_type="0x2::sui::SUI", decimals=9)
    token_usdc = Token(token_type="0xTEST::usdc::USDC", decimals=6)
    print(f"Token SUI: {token_sui}")
    print(f"Token USDC: {token_usdc}")
    assert token_sui.token_type == "0x2::sui::SUI"
    # Test sorting (relies on __lt__)
    tokens_list = [token_usdc, token_sui]
    tokens_list.sort()
    assert tokens_list == [token_sui, token_usdc] # 0x2... < 0xT...
    print("Token tests passed.")

    print("\n--- Testing PoolExtra ---")
    cetus_extra = CetusPoolExtra(fee_rate=30)
    turbos_extra = TurbosPoolExtra(fee_rate=5, sqrt_price="12345678901234567890")
    aftermath_extra = AftermathPoolExtra(lp_fee_pct=0.001, swap_fee_pct=0.003, weights=[50,50])
    print(f"Cetus Extra: {cetus_extra}, type: {cetus_extra.type}, dict: {cetus_extra.to_dict()}")
    assert cetus_extra.type == "CetusPoolExtra"
    assert cetus_extra.to_dict()['fee_rate'] == 30
    assert cetus_extra.to_dict()['type'] == "CetusPoolExtra"

    # Test from_dict for PoolExtra subclasses
    cetus_extra_from_dict_data = {"type": "CetusPoolExtra", "fee_rate": 25}
    cetus_extra_loaded = CetusPoolExtra.from_dict(cetus_extra_from_dict_data.copy()) # copy because from_dict might pop
    assert cetus_extra_loaded.fee_rate == 25
    print(f"Cetus Extra from_dict: {cetus_extra_loaded}")
    
    # Test base PoolExtra from_dict (if it were used directly, though less common)
    base_extra_data = {"type": "PoolExtra"} # No other fields for base
    base_extra_loaded = PoolExtra.from_dict(base_extra_data.copy())
    assert base_extra_loaded.type == "PoolExtra" # type is set in __post_init__
    print(f"Base PoolExtra from_dict: {base_extra_loaded}")

    print("PoolExtra tests passed.")

    print("\n--- Testing Pool ---")
    pool1_tokens = [token_sui, token_usdc] # Already sorted by __init__ if Token implements <
    pool1 = Pool(protocol=Protocol.CETUS, pool_id="0xpool_id_cetus1", tokens=pool1_tokens, extra=cetus_extra)
    print(f"Pool 1: {pool1}")
    assert pool1.token0_type() == "0x2::sui::SUI"
    assert pool1.token1_type() == "0xTEST::usdc::USDC"
    assert pool1.token_count() == 2
    assert pool1.token_index("0x2::sui::SUI") == 0
    assert pool1.token_index("0xTEST::usdc::USDC") == 1
    assert pool1.token_index("0xNonExistent::coin::COIN") is None
    assert pool1.get_token(0) == token_sui
    
    # Test __eq__ and __hash__
    pool1_copy = Pool(protocol=Protocol.CETUS, pool_id="0xpool_id_cetus1", tokens=pool1_tokens, extra=cetus_extra)
    pool2 = Pool(protocol=Protocol.TURBOS, pool_id="0xpool_id_turbos1", tokens=pool1_tokens, extra=turbos_extra)
    assert pool1 == pool1_copy
    assert hash(pool1) == hash(pool1_copy)
    assert pool1 != pool2
    assert hash(pool1) != hash(pool2) # Highly likely, not guaranteed for different objects

    # Test token01_pairs
    print(f"Pool 1 token pairs: {pool1.token01_pairs()}")
    assert pool1.token01_pairs() == [("0x2::sui::SUI", "0xTEST::usdc::USDC")]
    
    # Test 3-token pool pairs
    token_eth = Token(token_type="0xETH::eth::ETH", decimals=8)
    pool3_tokens = sorted([token_sui, token_usdc, token_eth])
    pool3 = Pool(protocol=Protocol.AFTERMATH, pool_id="0xpool_id_am1", tokens=pool3_tokens, extra=aftermath_extra)
    expected_pairs_pool3 = [
        ("0x2::sui::SUI", "0xETH::eth::ETH"),
        ("0x2::sui::SUI", "0xTEST::usdc::USDC"),
        ("0xETH::eth::ETH", "0xTEST::usdc::USDC"),
    ]
    print(f"Pool 3 token pairs: {pool3.token01_pairs()}")
    assert pool3.token01_pairs() == expected_pairs_pool3


    print("Pool basic tests passed.")

    print("\n--- Testing Pool Serialization/Deserialization ---")
    line_pool1 = pool1.to_line()
    print(f"Serialized Pool 1: {line_pool1}")
    
    # Example expected line: cetus|0xpool_id_cetus1|[{"token_type": "0x2::sui::SUI", "decimals": 9}, {"token_type": "0xTEST::usdc::USDC", "decimals": 6}]|{"type": "CetusPoolExtra", "fee_rate": 30}
    # Check parts of the string
    assert line_pool1.startswith("cetus|0xpool_id_cetus1|")
    assert '"CetusPoolExtra"' in line_pool1
    assert '"fee_rate": 30' in line_pool1
    assert '"token_type": "0x2::sui::SUI"' in line_pool1

    rehydrated_pool1 = Pool.from_line(line_pool1)
    print(f"Rehydrated Pool 1: {rehydrated_pool1}")
    assert rehydrated_pool1 == pool1
    assert rehydrated_pool1.protocol == Protocol.CETUS
    assert rehydrated_pool1.pool_id == "0xpool_id_cetus1"
    assert len(rehydrated_pool1.tokens) == 2
    assert rehydrated_pool1.tokens[0].token_type == "0x2::sui::SUI"
    assert isinstance(rehydrated_pool1.extra, CetusPoolExtra)
    assert rehydrated_pool1.extra.fee_rate == 30 # type: ignore

    # Test with AftermathPoolExtra which has more complex fields
    line_pool3 = pool3.to_line()
    print(f"Serialized Pool 3 (Aftermath): {line_pool3}")
    rehydrated_pool3 = Pool.from_line(line_pool3)
    print(f"Rehydrated Pool 3: {rehydrated_pool3}")
    assert rehydrated_pool3.pool_id == pool3.pool_id
    assert isinstance(rehydrated_pool3.extra, AftermathPoolExtra)
    assert rehydrated_pool3.extra.lp_fee_pct == 0.001 # type: ignore
    assert rehydrated_pool3.extra.weights == [50,50] # type: ignore
    assert len(rehydrated_pool3.tokens) == 3
    
    print("Pool Serialization/Deserialization tests passed.")


    print("\n--- Testing PoolCache ---")
    cache = PoolCache()
    cache.pool_map[pool1.pool_id] = pool1
    cache.token_pools.setdefault(token_sui.token_type, set()).add(pool1)
    cache.token_pools.setdefault(token_usdc.token_type, set()).add(pool1)
    for pair in pool1.token01_pairs():
        cache.token01_pools.setdefault(pair, set()).add(pool1)

    print(f"Cache pool_map: {cache.pool_map}")
    print(f"Cache token_pools for SUI: {cache.token_pools.get(token_sui.token_type)}")
    print(f"Cache token01_pools for (SUI,USDC): {cache.token01_pools.get((token_sui.token_type, token_usdc.token_type))}")
    assert pool1 in cache.token_pools[token_sui.token_type]
    print("PoolCache tests passed.")

    print("\n--- Testing SwapEvent ---")
    swap1 = SwapEvent(
        protocol=Protocol.TURBOS,
        pool_id="0xpool_id_turbos1",
        coins_in=["0x2::sui::SUI"],
        amounts_in=[1000000000],
        coins_out=["0xTEST::usdc::USDC"],
        amounts_out=[650000]
    )
    print(f"SwapEvent 1: {swap1}")
    assert swap1.get_pool_id() == "0xpool_id_turbos1"
    assert swap1.involved_coin_one_side() == "0x2::sui::SUI"

    swap2 = SwapEvent(
        protocol=Protocol.CETUS,
        pool_id="0xpool_id_cetus2",
        coins_in=["0xTEST::usdc::USDC"],
        amounts_in=[500000],
        coins_out=["0xETH::eth::ETH"],
        amounts_out=[25000000] # Example amount
    )
    print(f"SwapEvent 2 (no SUI): {swap2}")
    assert swap2.involved_coin_one_side() == "0xTEST::usdc::USDC"
    print("SwapEvent tests passed.")

    print("\n--- Testing Burberry Placeholders ---")
    burberry_event = Event.QUERY_EVENT_TRIGGER
    print(f"Burberry Event: {burberry_event}")
    no_action_instance = NoAction()
    print(f"NoAction instance: {no_action_instance}")
    dummy_executor_instance = DummyExecutor(name="MyTestExecutor")
    print(f"DummyExecutor instance: {dummy_executor_instance}")
    # await dummy_executor_instance.execute(no_action_instance) # Example call if in async context
    print("Burberry Placeholders tests passed.")

    print("\nAll dex_indexer_py.types tests executed.")
