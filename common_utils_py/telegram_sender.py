# coding: utf-8
# Copyright (c) Mysten Labs, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Telegram message sending utility."""

import asyncio
import logging
import os

# TODO: Make these configurable via a config file or proper environment loading
# For now, loaded from environment variables or defaulting to empty strings.
R2D2_TELEGRAM_BOT_TOKEN = os.getenv("R2D2_TELEGRAM_BOT_TOKEN", "")
TELEGRAM_BOT_TOKEN_ALERTS = os.getenv("TELEGRAM_BOT_TOKEN_ALERTS", "")

# TODO: Define actual chat and thread IDs
CHAT_GENERAL_PURPOSE = os.getenv("CHAT_GENERAL_PURPOSE", "") # Example
CHAT_MONEY_PRINTER = os.getenv("CHAT_MONEY_PRINTER", "")
CHAT_MONEY_PRINTER_THREAD_ERROR_REPORT = os.getenv("CHAT_MONEY_PRINTER_THREAD_ERROR_REPORT", "")
CHAT_SUI_BUILDS = os.getenv("CHAT_SUI_BUILDS", "")
CHAT_SUI_PERF_REGRESSION = os.getenv("CHAT_SUI_PERF_REGRESSION", "")
CHAT_SUI_RELEASE_MANAGEMENT = os.getenv("CHAT_SUI_RELEASE_MANAGEMENT", "")
CHAT_TESTING_AND_RELEASES = os.getenv("CHAT_TESTING_AND_RELEASES", "")

# Placeholder for the actual library, e.g., python-telegram-bot
# Add 'python-telegram-bot' to requirements.txt
try:
    from telegram import Bot
    from telegram.constants import ParseMode
    from telegram.error import TelegramError
    TELEGRAM_LIB_AVAILABLE = True
except ImportError:
    TELEGRAM_LIB_AVAILABLE = False
    # Mock objects for type hinting and basic structure if library is not available
    class Bot:
        def __init__(self, token: str):
            self.token = token
        async def send_message(self, chat_id: str, text: str, message_thread_id: str = None, parse_mode: str = None, disable_web_page_preview: bool = True, disable_notification: bool = False):
            logging.warning(f"Telegram library not found. Message not sent. Token: {self.token}, ChatID: {chat_id}, ThreadID: {message_thread_id}, Text: {text[:50]}...")
            await asyncio.sleep(0) # Simulate async call
            return True # Simulate success

    class TelegramError(Exception):
        pass

    class ParseMode:
        HTML = "HTML"
        MARKDOWN_V2 = "MarkdownV2"


logger = logging.getLogger(__name__)

class TelegramSender:
    """
    A class to send messages to Telegram.
    """
    def __init__(self, bot_token: str, chat_id: str, thread_id: str = None):
        """
        Initializes the TelegramSender.

        Args:
            bot_token: The Telegram bot token.
            chat_id: The Telegram chat ID.
            thread_id: The Telegram message thread ID (optional).
        """
        if not bot_token:
            logger.warning("TelegramSender initialized with an empty bot_token. Messages will not be sent.")
        if not chat_id:
            logger.warning("TelegramSender initialized with an empty chat_id. Messages will not be sent.")

        self.bot_token = bot_token
        self.chat_id = chat_id
        self.thread_id = thread_id
        if TELEGRAM_LIB_AVAILABLE and self.bot_token:
            self.bot = Bot(token=self.bot_token)
        else:
            self.bot = None # No bot instance if token is missing or library is unavailable
            if not TELEGRAM_LIB_AVAILABLE:
                logger.error("python-telegram-bot library is not installed. Please install it to send messages.")


    async def send_message(
        self,
        text: str,
        parse_mode: str = ParseMode.HTML, # Defaulting to HTML as it's safer
        disable_web_page_preview: bool = True,
        disable_notification: bool = False
    ) -> bool:
        """
        Sends a message to Telegram.

        Args:
            text: The message text.
            parse_mode: Message parsing mode (e.g., ParseMode.HTML, ParseMode.MARKDOWN_V2).
            disable_web_page_preview: Disables link previews if True.
            disable_notification: Sends the message silently if True.

        Returns:
            True if sending was successful, False otherwise.
        """
        if not self.bot_token or not self.chat_id:
            logger.error("Cannot send Telegram message: bot_token or chat_id is not configured.")
            return False
        
        if not self.bot:
            # This case handles if TELEGRAM_LIB_AVAILABLE was false or bot_token was empty during __init__
            logger.error("Telegram bot is not initialized. Cannot send message.")
            return False

        try:
            # Ensure text is within Telegram's message length limits (4096 chars)
            # Splitting logic can be added here if necessary, or truncate.
            max_length = 4096
            if len(text) > max_length:
                logger.warning(f"Message length {len(text)} exceeds {max_length} chars. Truncating.")
                text = text[:max_length - 3] + "..."

            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                message_thread_id=self.thread_id,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview,
                disable_notification=disable_notification,
            )
            logger.info(f"Message sent to Telegram chat {self.chat_id} (Thread: {self.thread_id})")
            return True
        except TelegramError as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
        except Exception as e:
            # Catch any other unexpected errors
            logger.error(f"An unexpected error occurred while sending Telegram message: {e}")
            return False

if __name__ == '__main__':
    # Example Usage (requires environment variables to be set for actual sending)
    # Ensure R2D2_TELEGRAM_BOT_TOKEN and CHAT_GENERAL_PURPOSE are set in your environment
    # e.g. export R2D2_TELEGRAM_BOT_TOKEN="your_token"
    #      export CHAT_GENERAL_PURPOSE="your_chat_id"

    logging.basicConfig(level=logging.INFO)

    async def main():
        if not R2D2_TELEGRAM_BOT_TOKEN or not CHAT_GENERAL_PURPOSE:
            logger.warning("Skipping TelegramSender example: R2D2_TELEGRAM_BOT_TOKEN or CHAT_GENERAL_PURPOSE not set.")
            logger.warning("To run this example, set the environment variables:")
            logger.warning("  export R2D2_TELEGRAM_BOT_TOKEN=\"your_bot_token\"")
            logger.warning("  export CHAT_GENERAL_PURPOSE=\"your_chat_id\"")
            logger.warning("  (Optionally) export CHAT_MONEY_PRINTER_THREAD_ERROR_REPORT=\"your_thread_id\"")
            return

        # Example 1: Sending to a chat without a specific thread
        sender_chat_only = TelegramSender(
            bot_token=R2D2_TELEGRAM_BOT_TOKEN,
            chat_id=CHAT_GENERAL_PURPOSE
        )
        success_chat = await sender_chat_only.send_message("Hello from common_utils_py! (Chat only)")
        print(f"Chat-only message sent: {success_chat}")

        # Example 2: Sending to a specific thread within a chat
        # Ensure CHAT_MONEY_PRINTER_THREAD_ERROR_REPORT is also set for this to work
        if CHAT_MONEY_PRINTER_THREAD_ERROR_REPORT:
            sender_with_thread = TelegramSender(
                bot_token=R2D2_TELEGRAM_BOT_TOKEN, # or specific token like TELEGRAM_BOT_TOKEN_ALERTS
                chat_id=CHAT_MONEY_PRINTER, # Assuming this is the group chat for the thread
                thread_id=CHAT_MONEY_PRINTER_THREAD_ERROR_REPORT
            )
            success_thread = await sender_with_thread.send_message(
                "<b>Hello from common_utils_py!</b> (Thread message with HTML formatting)",
                parse_mode=ParseMode.HTML
            )
            print(f"Thread message sent: {success_thread}")
        else:
            logger.warning("Skipping threaded message example: CHAT_MONEY_PRINTER_THREAD_ERROR_REPORT not set.")

        # Example 3: Message with link preview disabled (default)
        success_link_disabled = await sender_chat_only.send_message("Test with link: https://mystenlabs.com (preview disabled)")
        print(f"Link preview disabled message sent: {success_link_disabled}")

        # Example 4: Message with link preview enabled
        success_link_enabled = await sender_chat_only.send_message(
            "Test with link: https://mystenlabs.com (preview enabled)",
            disable_web_page_preview=False
        )
        print(f"Link preview enabled message sent: {success_link_enabled}")

        # Example 5: Silent notification
        success_silent = await sender_chat_only.send_message("Silent message.", disable_notification=True)
        print(f"Silent message sent: {success_silent}")
        
        # Example 6: Message too long
        long_text = "A" * 5000
        success_long = await sender_chat_only.send_message(long_text)
        print(f"Long message sent (should be truncated): {success_long}")


    if TELEGRAM_LIB_AVAILABLE:
        asyncio.run(main())
    else:
        logger.error("Cannot run TelegramSender example: python-telegram-bot is not installed.")
        print("Please install it using: pip install python-telegram-bot")

# Note: To actually use this, 'python-telegram-bot' library needs to be installed.
# Add 'python-telegram-bot' to your project's requirements.txt or install with pip.
