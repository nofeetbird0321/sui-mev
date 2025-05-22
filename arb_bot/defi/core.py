# coding: utf-8
# Copyright (c) Mysten Labs, Inc.
# SPDX-License-Identifier: Apache-2.0

"""
Core DeFi interfaces and types for the Arb Bot, including Dex, Path, and TradeCtx.
"""

import abc
import dataclasses
import logging
from typing import Any, Dict, List, Optional, Tuple, Set, TYPE_CHECKING

# Assuming dex_indexer_py is in PYTHONPATH or a sibling directory correctly configured
try:
    from dex_indexer_py.types import Protocol
except ImportError:
    # Placeholder if dex_indexer_py.types is not found (e.g., during isolated testing)
    # In a real integrated environment, this import should work.
    class Protocol(abc.ABC): # Minimal ABC placeholder
        @abc.abstractmethod
        def to_str(self) -> str: ...
    
    class MockProtocol(Protocol): # Concrete mock for demo
        def __init__(self, name: str): self._name = name
        def to_str(self) -> str: return self._name

    Protocol.CETUS = MockProtocol("cetus") # type: ignore
    Protocol.TURBOS = MockProtocol("turbos") # type: ignore
    print("Warning: dex_indexer_py.types.Protocol not found. Using placeholder mock.")


# --- Placeholder Pysui Types (can be 'Any' for now) ---
if TYPE_CHECKING:
    from pysui.sui.sui_types.address import SuiAddress
    from pysui.sui.sui_types.grammar import Argument, ObjectArg # Pure, Result are also from grammar
    from pysui.sui.sui_txn.transaction_builder import ProgrammableTransactionBuilder
    from pysui.sui.sui_types.transaction_data import TransactionData
else:
    SuiAddress = Any
    Argument = Any # Represents pysui's Argument type (e.g., from ptb.input(...))
    ObjectArg = Any # Represents pysui's ObjectArg
    ProgrammableTransactionBuilder = Any
    TransactionData = Any


logger = logging.getLogger(__name__)

# --- Dataclasses ---

@dataclasses.dataclass
class FlashResult:
    """Result of a flashloan operation within a transaction."""
    coin_out: Any  # Typically an Argument representing the flashloaned coin
    receipt: Any   # Typically an Argument representing the flashloan receipt
    pool: Optional[Any] = None # Optional: Pool object or ID from which loan was taken


@dataclasses.dataclass
class TradeCtx:
    """
    Context for building a programmable transaction block (PTB) for trades.
    Wraps pysui's ProgrammableTransactionBuilder.
    """
    # TODO: Replace placeholder with actual pysui.sui.sui_txn.transaction_builder.ProgrammableTransactionBuilder
    # For now, using a string placeholder to avoid direct dependency if pysui is not installed.
    # In a real scenario, this would be:
    # ptb: ProgrammableTransactionBuilder = dataclasses.field(default_factory=ProgrammableTransactionBuilder)
    ptb: Any = dataclasses.field(default_factory=lambda: "PLACEHOLDER_PTB_INSTANCE")
    command_count: int = 0

    def __post_init__(self):
        # If ptb is the placeholder string, log a warning or initialize a mock PTB if needed for tests
        if isinstance(self.ptb, str) and self.ptb == "PLACEHOLDER_PTB_INSTANCE":
            logger.debug("TradeCtx initialized with placeholder PTB. Real PTB needed for execution.")
            # Could assign a mock PTB here for testing if desired:
            # self.ptb = MockProgrammableTransactionBuilder() 

    def add_command(self, command: Any) -> None:
        """Placeholder for ptb.command(...) or similar."""
        logger.debug(f"TradeCtx (Placeholder): add_command called with: {command}")
        # In pysui, commands are added implicitly by ptb.move_call, ptb.transfer_objects etc.
        # This method might be more conceptual or for very specific low-level commands if any.
        # For now, let's assume it's a general incrementer for custom tracking if needed,
        # or that most PTB operations will directly use other methods.
        # If this is meant to directly map to ptb.add_command(some_command_object):
        # self.ptb.add_command(command) # Actual call
        self.command_count +=1 # Increment if a command was added.

    def transfer_arg(self, recipient_address: SuiAddress, coin_arg: Argument) -> None:
        """Placeholder for ptb.transfer_objects([coin_arg], recipient_address)."""
        logger.debug(f"TradeCtx (Placeholder): transfer_arg called. Recipient: {recipient_address}, Coin: {coin_arg}")
        # self.ptb.transfer_objects(objects_to_transfer=[coin_arg], recipient=self.ptb.input(recipient_address))
        self.command_count += 1

    def split_coin_equal_to_sender(self, coin_ref_arg: Argument, split_count: int, coin_type_tag: Any) -> List[Argument]:
        """Placeholder for ptb.split_coin_equal(coin=coin_ref_arg, split_count=split_count)."""
        logger.debug(f"TradeCtx (Placeholder): split_coin_equal_to_sender called. Coin: {coin_ref_arg}, Count: {split_count}")
        # result_args = self.ptb.split_coin_equal(coin=coin_ref_arg, split_count=self.ptb.input(split_count))
        # self.command_count refers to the index of the last command *before* this one.
        # If split_coin_equal returns N arguments, they are results of commands N, N+1, ..., N+split_count-1
        # This is complex to model without real PTB. For now, returning dummy args.
        dummy_results = [f"DUMMY_SPLIT_COIN_ARG_{i}" for i in range(split_count)]
        self.command_count += 1 # split_coin_equal is one command, but results in multiple arguments
        return dummy_results # type: ignore

    def split_coin_to_sender(self, coin_ref_arg: Argument, amount: int, coin_type_tag: Any) -> Argument:
        """Placeholder for ptb.split_coin(coin=coin_ref_arg, amounts=[amount])."""
        logger.debug(f"TradeCtx (Placeholder): split_coin_to_sender called. Coin: {coin_ref_arg}, Amount: {amount}")
        # result_arg = self.ptb.split_coin(coin=coin_ref_arg, amounts=[self.ptb.input(amount)])
        self.command_count += 1
        return f"DUMMY_SPLIT_AMOUNT_COIN_ARG" # type: ignore

    def make_move_vec(self, items: List[Argument], item_type_tag: Optional[Any] = None) -> Argument:
        """Placeholder for ptb.make_move_vector(items_to_vector=items, object_type=item_type_tag)."""
        logger.debug(f"TradeCtx (Placeholder): make_move_vec called with {len(items)} items. Type: {item_type_tag}")
        # vector_arg = self.ptb.make_move_vector(objects=items, object_type=item_type_tag if item_type_tag else None)
        self.command_count += 1 # This itself might not be a command, but an input builder.
                                # Let's assume it's used in a command that gets counted.
                                # Or, if it *is* a command (e.g. vector::construct):
        return f"DUMMY_MOVE_VEC_ARG" # type: ignore

    def pure(self, value: Any) -> Argument:
        """Placeholder for ptb.pure(value) or an Argument.Pure constructor."""
        logger.debug(f"TradeCtx (Placeholder): pure called with value: {value}")
        # return self.ptb.pure(value=value)
        # Or if directly creating Argument: from pysui.sui.sui_types.grammar import PureInput; return PureInput(value)
        return f"DUMMY_PURE_ARG({value})" # type: ignore

    def object_arg(self, object_data: Any, shared: bool = False) -> Argument:
        """
        Placeholder for creating an ObjectArg from object data.
        In pysui, this might involve ptb.input(ObjectArg(...)) or directly creating ObjectArg.
        """
        # Assuming object_data could be an ID string or a dict with id, version, digest.
        obj_id = object_data if isinstance(object_data, str) else object_data.get('id', 'UNKNOWN_ID')
        logger.debug(f"TradeCtx (Placeholder): object_arg called for obj_id: {obj_id}, shared: {shared}")
        # from pysui.sui.sui_types.grammar import ObjectArg, SharedObjectArg
        # if shared:
        #     return SharedObjectArg(object_id=obj_id, initial_shared_version=object_data.get('initialSharedVersion'), mutable=True)
        # else:
        #     return ObjectArg(object_id=obj_id, version=object_data.get('version'), digest=object_data.get('digest'))
        return f"DUMMY_OBJECT_ARG({obj_id})" # type: ignore

    def move_call_command(
        self, package_id_str: str, module_name: str, func_name: str, 
        type_args: List[Any], value_args: List[Argument]
    ) -> Optional[Argument]:
        """
        Placeholder for ptb.move_call(...).
        Returns a dummy Argument representing the result of the command (if any).
        """
        logger.debug(
            f"TradeCtx (Placeholder): move_call_command: "
            f"{package_id_str}::{module_name}::{func_name}, "
            f"Types: {type_args}, Args: {value_args}"
        )
        # result_arg_tuple = self.ptb.move_call(
        #     target=f"{package_id_str}::{module_name}::{func_name}",
        #     arguments=value_args,
        #     type_arguments=type_args
        # )
        # For this placeholder, assume a single result argument or None if it's complex.
        # The actual ptb.move_call returns a tuple of Arguments if the function has multiple return values.
        
        # Increment command_count for the move_call itself.
        current_cmd_idx = self.command_count
        self.command_count += 1
        
        # Simulate Argument.Result(command_index)
        # If the move call is expected to return something, return a dummy "Result" argument.
        # This depends on the function signature, which we don't know here.
        # Let's assume for this placeholder it might return one result.
        # In pysui, if a move call returns N values, it returns N Arguments.
        # If it returns 1 value, it's often Argument(Result(index_of_this_command)).
        # If it returns 0 values, it might return None or an empty tuple.
        # For simplicity, returning a single dummy result arg:
        return f"DUMMY_RESULT_ARG_FROM_CMD_{current_cmd_idx}" # type: ignore


    def last_command_idx(self) -> int:
        """Returns the index of the last command added (0-based)."""
        if self.command_count == 0:
            # As per Rust, which returns 0 if count is 0.
            # This might be interpreted as "no commands yet" or "index before first command".
            # If it means "index of the last valid command", then perhaps -1 or raise error.
            # Rust's u16 might wrap around, Python int doesn't.
            # Let's stick to Rust's behavior of returning 0 for count 0.
            return 0 
        return self.command_count - 1

    def finish_ptb(self) -> TransactionData:
        """Placeholder for completing and returning the PTB (or its data)."""
        logger.debug(f"TradeCtx (Placeholder): finish_ptb called. Final command count: {self.command_count}")
        # In pysui, this might be:
        # return self.ptb.transaction_data() # If you need TransactionData for signing
        # Or just self.ptb if the PTB object itself is what's needed next.
        return f"FINISHED_PTB_DATA_WITH_{self.command_count}_COMMANDS" # type: ignore


# --- Abstract Base Classes (ABCs) ---

class Dex(abc.ABC):
    """Abstract Base Class for a DEX pool or trading venue."""

    @abc.abstractmethod
    def protocol(self) -> Protocol: ...

    @abc.abstractmethod
    def object_id(self) -> str: ...

    @abc.abstractmethod
    def coin_in_type(self) -> str: ...

    @abc.abstractmethod
    def coin_out_type(self) -> str: ...

    @abc.abstractmethod
    def liquidity(self) -> int:  # Placeholder for actual liquidity metric
        ...

    @abc.abstractmethod
    def flip(self) -> None:
        """Flips the direction of the Dex (coin_in <-> coin_out)."""
        ...

    @abc.abstractmethod
    def is_a_to_b(self) -> bool:
        """
        Indicates the current direction of the trade relative to canonical token order.
        E.g., if pool tokens are A and B (A < B lexically), is current trade A -> B?
        """
        ...
    
    def support_flashloan(self) -> bool:
        """Returns True if the DEX supports flashloans for its coin_out_type."""
        return False

    async def extend_flashloan_tx(self, ctx: TradeCtx, amount_in: int) -> FlashResult:
        """
        Extends the PTB in ctx with commands to perform a flashloan.
        Should return the flashloaned coin and receipt as Arguments.
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not implement extend_flashloan_tx")

    async def extend_repay_tx(self, ctx: TradeCtx, coin_in_arg: Argument, flash_res: FlashResult) -> Argument:
        """
        Extends the PTB in ctx with commands to repay the flashloan.
        Should return the 'leftover' coin Argument after repayment.
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not implement extend_repay_tx")

    @abc.abstractmethod
    async def extend_trade_tx(
        self, 
        ctx: TradeCtx, 
        sender_address: SuiAddress, 
        coin_in_arg: Argument, 
        amount_in_val: Optional[int] # Optional: some DEXes might not need explicit amount if using entire coin
    ) -> Argument: # Returns the coin_out Argument
        """
        Extends the PTB in ctx with commands to perform the trade.
        """
        ...

    def __hash__(self):
        return hash(self.object_id())

    def __eq__(self, other):
        if not isinstance(other, Dex):
            return NotImplemented
        return self.object_id() == other.object_id()

    def __repr__(self):
        # Ensure protocol() and types return strings for repr
        protocol_str = self.protocol().to_str() if self.protocol() else "UnknownProtocol"
        coin_in_short = self.coin_in_type().split('::')[-1] if self.coin_in_type() else "UnknownCoinIn"
        coin_out_short = self.coin_out_type().split('::')[-1] if self.coin_out_type() else "UnknownCoinOut"
        return f"{protocol_str}({self.object_id()}, {coin_in_short}->{coin_out_short})"


@dataclasses.dataclass(frozen=True) # Making Path immutable and hashable
class Path:
    """Represents a sequence of Dex trades."""
    path: List[Dex] = dataclasses.field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.path

    def is_disjoint(self, other: 'Path') -> bool:
        """Checks if this path shares no common pool object_ids with another path."""
        if self.is_empty() or other.is_empty():
            return True # Empty paths are disjoint from anything
        
        self_ids = {dex.object_id() for dex in self.path}
        other_ids = {dex.object_id() for dex in other.path}
        return self_ids.isdisjoint(other_ids)

    def coin_in_type(self) -> Optional[str]:
        """Returns the input coin type of the first Dex in the path."""
        if not self.path:
            return None
        return self.path[0].coin_in_type()

    def coin_out_type(self) -> Optional[str]:
        """Returns the output coin type of the last Dex in the path."""
        if not self.path:
            return None
        return self.path[-1].coin_out_type()

    def contains_pool(self, pool_id_str: Optional[str]) -> bool:
        """Checks if a pool with the given ID is in this path."""
        if not pool_id_str or self.is_empty():
            return False
        return any(dex.object_id() == pool_id_str for dex in self.path)
    
    def __len__(self) -> int:
        return len(self.path)

    def __repr__(self) -> str:
        if self.is_empty():
            return "Path([])"
        path_str = " -> ".join([
            dex.coin_in_type().split("::")[-1] + f"({dex.protocol().to_str()[:2]}:{dex.object_id()[-4:]})" 
            for dex in self.path
        ])
        # Add the final output coin type
        path_str += f" -> {self.coin_out_type().split('::')[-1] if self.coin_out_type() else '?'}"
        return f"Path({path_str})"


class DexSearcher(abc.ABC):
    """Abstract Base Class for searching DEXes and paths."""

    @abc.abstractmethod
    async def find_dexes(self, coin_in_type: str, coin_out_type: Optional[str] = None) -> List[Dex]:
        """
        Finds all known DEXes that can trade coin_in_type for coin_out_type.
        If coin_out_type is None, finds all DEXes with coin_in_type as one of their tokens.
        """
        ...

    @abc.abstractmethod
    async def find_test_path(self, object_ids: List[str]) -> Optional[Path]:
        """
        Constructs a Path from a list of object IDs, typically for testing.
        This implies the DexSearcher has a way to fetch/reconstruct Dex instances from IDs.
        """
        ...


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger_core_demo = logging.getLogger(__name__ + ".Demo")
    logger_core_demo.setLevel(logging.DEBUG)

    logger_core_demo.info("--- Arb Bot DeFi Core Types Demonstration ---")

    # --- Test TradeCtx ---
    logger_core_demo.info("\n--- Testing TradeCtx ---")
    ctx = TradeCtx()
    logger_core_demo.info(f"Initial TradeCtx PTB: {ctx.ptb}, Command Count: {ctx.command_count}")
    
    ctx.move_call_command("0x1", "module", "func", [], [])
    ctx.transfer_arg("0xRECIPIENT", "DUMMY_COIN_ARG_0")
    split_coins = ctx.split_coin_equal_to_sender("DUMMY_COIN_ARG_1", 2, "0x2::sui::SUI")
    logger_core_demo.info(f"Split coins result (dummy): {split_coins}")
    
    logger_core_demo.info(f"TradeCtx after some commands: Command Count = {ctx.command_count}, Last Idx = {ctx.last_command_idx()}")
    finished_ptb_data = ctx.finish_ptb()
    logger_core_demo.info(f"Finished PTB data (dummy): {finished_ptb_data}")
    assert ctx.command_count == 3 # move_call, transfer, split_equal

    # --- Dummy Dex Implementation for Path testing ---
    @dataclasses.dataclass
    class DummyDex(Dex):
        _protocol: Protocol
        _object_id: str
        _coin_in_type: str
        _coin_out_type: str
        _liquidity: int = 1000
        _is_a_to_b: bool = True # Placeholder

        def protocol(self) -> Protocol: return self._protocol
        def object_id(self) -> str: return self._object_id
        def coin_in_type(self) -> str: return self._coin_in_type
        def coin_out_type(self) -> str: return self._coin_out_type
        def liquidity(self) -> int: return self._liquidity
        def is_a_to_b(self) -> bool: return self._is_a_to_b # Not used by Path directly

        def flip(self) -> None:
            self._coin_in_type, self._coin_out_type = self._coin_out_type, self._coin_in_type
            self._is_a_to_b = not self._is_a_to_b # Example flip logic

        async def extend_trade_tx(self, ctx: TradeCtx, sender_address: Any, coin_in_arg: Any, amount_in_val: Optional[int]) -> Any:
            logger_core_demo.debug(f"DummyDex {self.object_id()}: extend_trade_tx called.")
            # Simulate adding a trade command and returning a new coin argument
            ctx.move_call_command(self.object_id(), "pool", "swap", 
                                  [self.coin_in_type(), self.coin_out_type()], 
                                  [coin_in_arg])
            return f"DUMMY_COIN_OUT_FROM_{self.object_id()[-4:]}"


    SUI = "0x2::sui::SUI"
    USDC = "0xUSDC::usdc::USDC"
    ETH = "0xETH::eth::ETH"

    dex1 = DummyDex(Protocol.CETUS, "pool1_cetus_sui_usdc", SUI, USDC) # type: ignore
    dex2 = DummyDex(Protocol.TURBOS, "pool2_turbos_usdc_eth", USDC, ETH) # type: ignore
    dex3 = DummyDex(Protocol.CETUS, "pool3_cetus_eth_sui", ETH, SUI) # type: ignore
    
    # Another pool for disjoint test
    dex_other_1 = DummyDex(Protocol.CETUS, "pool_other_1", SUI, "0xFOO::foo::FOO") # type: ignore


    # --- Test Path ---
    logger_core_demo.info("\n--- Testing Path ---")
    path_empty = Path()
    logger_core_demo.info(f"Empty Path: {path_empty}, is_empty: {path_empty.is_empty()}, len: {len(path_empty)}")
    assert path_empty.is_empty()
    assert len(path_empty) == 0
    assert path_empty.coin_in_type() is None
    assert path_empty.coin_out_type() is None

    path1 = Path(path=[dex1, dex2, dex3])
    logger_core_demo.info(f"Path 1: {path1}, len: {len(path1)}")
    assert not path1.is_empty()
    assert len(path1) == 3
    assert path1.coin_in_type() == SUI
    assert path1.coin_out_type() == SUI # Path is SUI -> USDC -> ETH -> SUI
    
    logger_core_demo.info(f"Path 1 contains 'pool2_turbos_usdc_eth': {path1.contains_pool('pool2_turbos_usdc_eth')}")
    assert path1.contains_pool('pool2_turbos_usdc_eth')
    logger_core_demo.info(f"Path 1 contains 'non_existent_pool': {path1.contains_pool('non_existent_pool')}")
    assert not path1.contains_pool('non_existent_pool')

    # Test is_disjoint
    path2_overlapping = Path(path=[dex_other_1, dex1]) # Shares dex1 (pool1_cetus_sui_usdc)
    path3_disjoint = Path(path=[dex_other_1])
    
    logger_core_demo.info(f"Path 1 disjoint Path 2 (overlapping): {path1.is_disjoint(path2_overlapping)}")
    assert not path1.is_disjoint(path2_overlapping)
    
    logger_core_demo.info(f"Path 1 disjoint Path 3 (disjoint): {path1.is_disjoint(path3_disjoint)}")
    assert path1.is_disjoint(path3_disjoint)
    
    logger_core_demo.info(f"Empty Path disjoint Path 1: {path_empty.is_disjoint(path1)}")
    assert path_empty.is_disjoint(path1)

    logger_core_demo.info("\nAll arb_bot.defi.core demo tests executed.")
