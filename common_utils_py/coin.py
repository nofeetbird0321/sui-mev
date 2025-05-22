# coding: utf-8
# Copyright (c) Mysten Labs, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Coin related utility functions."""

import decimal

# The standard SUI coin type string
SUI_COIN_TYPE = "0x2::sui::SUI"

# A verbose representation of the SUI coin type string sometimes encountered
_VERBOSE_SUI_COIN_TYPE = "0x0000000000000000000000000000000000000000000000000000000000000002::sui::SUI"

def is_native_sui(coin_type_str: str) -> bool:
    """
    Checks if the given coin_type_str is the native SUI coin.
    """
    return normalize_coin_type(coin_type_str) == SUI_COIN_TYPE

def format_sui_with_symbol(value_mist: int, decimals: int = 9) -> str:
    """
    Formats a MIST value into a human-readable string with " SUI" appended.

    Args:
        value_mist: The amount in MIST (integer).
        decimals: The number of decimal places for SUI (defaults to 9).

    Returns:
        A string representing the value in SUI, e.g., "1.234567890 SUI".
    """
    if not isinstance(value_mist, int):
        raise TypeError("value_mist must be an integer.")
    if not isinstance(decimals, int) or decimals < 0:
        raise ValueError("decimals must be a non-negative integer.")

    # Create a Decimal from the integer MIST value
    mist_decimal = decimal.Decimal(value_mist)

    # Calculate the SUI value by dividing by 10^decimals
    # Using Decimal for precision
    sui_value = mist_decimal / (decimal.Decimal(10) ** decimals)

    # Format the string to ensure all decimal places are shown, even if trailing zeros
    # The 'f' format specifier is used for fixed-point notation.
    # The `.{decimals}f` part ensures it's formatted to the specified number of decimal places.
    formatted_sui = format(sui_value, f".{decimals}f")

    return f"{formatted_sui} SUI"

def normalize_coin_type(coin_type: str) -> str:
    """
    Normalizes a potentially verbose SUI coin type string to the canonical representation.
    """
    if coin_type == _VERBOSE_SUI_COIN_TYPE:
        return SUI_COIN_TYPE
    return coin_type

if __name__ == '__main__':
    # Example Usage
    print(f"Is '0x2::sui::SUI' native SUI? {is_native_sui('0x2::sui::SUI')}")
    print(f"Is '{_VERBOSE_SUI_COIN_TYPE}' native SUI? {is_native_sui(_VERBOSE_SUI_COIN_TYPE)}")
    print(f"Is '0x123::other::coin' native SUI? {is_native_sui('0x123::other::coin')}")

    print(f"Normalize '{_VERBOSE_SUI_COIN_TYPE}': {normalize_coin_type(_VERBOSE_SUI_COIN_TYPE)}")
    print(f"Normalize '0x2::sui::SUI': {normalize_coin_type('0x2::sui::SUI')}")
    print(f"Normalize '0xabc::test::FOO': {normalize_coin_type('0xabc::test::FOO')}")

    print(f"Format 1234567890 MIST: {format_sui_with_symbol(1234567890)}")
    print(f"Format 1000000000 MIST: {format_sui_with_symbol(1000000000)}")
    print(f"Format 500000000 MIST: {format_sui_with_symbol(500000000)}") # 0.5 SUI
    print(f"Format 1 MIST: {format_sui_with_symbol(1)}")
    print(f"Format 12345 MIST: {format_sui_with_symbol(12345)}")
    print(f"Format 0 MIST: {format_sui_with_symbol(0)}")
    print(f"Format 1234567890 MIST with 6 decimals: {format_sui_with_symbol(1234567890, 6)}") # Should be 1234.567890 SUI
    print(f"Format 123 MIST (value_mist) with 0 decimals: {format_sui_with_symbol(123, 0)}") # Should be 123 SUI
    print(f"Format 1 SUI in MIST (10^9) : {format_sui_with_symbol(10**9)}") # Should be 1.000000000 SUI
    print(f"Format 1.23 SUI in MIST : {format_sui_with_symbol(1230000000)}") # Should be 1.230000000 SUI

    # Example from description: 1234567890 MIST and decimals 9, it should return "1.234567890 SUI"
    # My code output for this is: 1.234567890 SUI - which is correct.

    # Test with a very large number
    large_mist_value = 12345678901234567890
    print(f"Format large MIST value: {format_sui_with_symbol(large_mist_value)}")

    # Test with a number that would result in leading zeros in the decimal part
    small_mist_value = 123
    print(f"Format small MIST value (123): {format_sui_with_symbol(small_mist_value)}") # Should be 0.000000123 SUI

    # Test with decimals=0
    print(f"Format 1234567890 MIST with 0 decimals: {format_sui_with_symbol(1234567890, 0)}") # Should be 1234567890 SUI

    # Test with a value that is exactly 1 SUI
    one_sui_in_mist = 10**9
    print(f"Format {one_sui_in_mist} MIST: {format_sui_with_symbol(one_sui_in_mist)}") # Should be 1.000000000 SUI

    # Test with a value less than 1 SUI but not zero
    half_sui_in_mist = 5 * (10**8)
    print(f"Format {half_sui_in_mist} MIST: {format_sui_with_symbol(half_sui_in_mist)}") # Should be 0.500000000 SUI

    try:
        format_sui_with_symbol(1.23) # type: ignore
    except TypeError as e:
        print(f"Error caught for float input: {e}")

    try:
        format_sui_with_symbol(123, decimals=-1) # type: ignore
    except ValueError as e:
        print(f"Error caught for negative decimals: {e}")
