# coding: utf-8
# Copyright (c) Mysten Labs, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Sui Scan link generation functions."""

SCAN_URL = "https://suiscan.xyz/mainnet"

def tx(digest_str: str, tag: str = None) -> str:
    """Formats a transaction digest as a markdown link to Sui Scan."""
    link_text = tag if tag is not None else digest_str
    return f"[{link_text}]({SCAN_URL}/tx/{digest_str})"

def object(object_id_str: str, tag: str = None) -> str:
    """Formats an object ID as a markdown link to Sui Scan."""
    link_text = tag if tag is not None else object_id_str
    return f"[{link_text}]({SCAN_URL}/object/{object_id_str})"

def account(address_str: str, tag: str = None) -> str:
    """Formats an account address as a markdown link to Sui Scan."""
    link_text = tag if tag is not None else address_str
    return f"[{link_text}]({SCAN_URL}/account/{address_str})"

def coin(coin_type_str: str, tag: str = None) -> str:
    """Formats a coin type as a markdown link to Sui Scan."""
    link_text = tag if tag is not None else coin_type_str
    # Assuming the URL structure for coin is /coin/{coin_type_str}
    # Based on typical patterns, but crate code doesn't explicitly show coin URL structure
    return f"[{link_text}]({SCAN_URL}/coin/{coin_type_str})"

def checkpoint(digest_str: str, number: int, tag: str = None) -> str:
    """Formats a checkpoint digest and number as a markdown link to Sui Scan."""
    link_text = tag if tag is not None else str(number)
    return f"[{link_text}]({SCAN_URL}/checkpoint/{digest_str})"
