from __future__ import annotations

import os

from dataclasses import dataclass

import urllib.request
import urllib.parse


@dataclass
class TelegramNotificationResult:

    success: bool

    status_code: int | None

    message: str



class NotificationResponseApprovalTelegramAdapter:
    """
    SS4TS Telegram Executive Notification Adapter

    H23.4.5.5.12.22.13.7.8.2

    Responsibilities:

    - Send approval escalation notifications
    - Notify NOC
    - Notify Management
    """



    def __init__(self):

        #
        # Load Telegram Bot Token
        # Support Docker Secret File
        #

        self.bot_token = ""

        token_file = os.getenv(
            "TELEGRAM_BOT_TOKEN_FILE",
            "",
        )


        if token_file:

            try:

                with open(
                    token_file,
                    "r",
                    encoding="utf-8",
                ) as file:

                    self.bot_token = (
                        file.read()
                        .strip()
                    )


            except Exception:

                self.bot_token = ""



        #
        # Fallback Environment Variable
        #

        if not self.bot_token:

            self.bot_token = os.getenv(
                "TELEGRAM_BOT_TOKEN",
                "",
            )



        self.noc_chat_id = os.getenv(
            "TELEGRAM_NOC_CHAT_ID",
            "",
        )


        self.management_chat_id = os.getenv(
            "TELEGRAM_MANAGEMENT_CHAT_ID",
            "",
        )



    def send_event(
        self,
        event,
    ) -> TelegramNotificationResult:


        if event.target == "MANAGEMENT":

            chat_id = (
                self.management_chat_id
            )


        elif event.target == "NOC":

            chat_id = (
                self.noc_chat_id
            )


        else:

            return TelegramNotificationResult(

                success=False,

                status_code=None,

                message="No notification target",

            )



        return self._send_message(

            chat_id,

            event.message,

        )



    def _send_message(
        self,
        chat_id: str,
        message: str,
    ) -> TelegramNotificationResult:


        if not self.bot_token:

            return TelegramNotificationResult(

                success=False,

                status_code=None,

                message="Telegram bot token missing",

            )



        if not chat_id:

            return TelegramNotificationResult(

                success=False,

                status_code=None,

                message="Telegram chat id missing",

            )



        url = (

            "https://api.telegram.org/"

            f"bot{self.bot_token}/sendMessage"

        )



        payload = urllib.parse.urlencode(

            {

                "chat_id": chat_id,

                "text": message,

            }

        ).encode()



        try:

            request = urllib.request.Request(

                url,

                data=payload,

                method="POST",

            )


            with urllib.request.urlopen(

                request,

                timeout=10,

            ) as response:


                return TelegramNotificationResult(

                    success=True,

                    status_code=response.status,

                    message="Telegram message sent",

                )



        except Exception as exc:


            return TelegramNotificationResult(

                success=False,

                status_code=None,

                message=f"Telegram error: {exc}",

            )



def create_telegram_adapter():

    return (

        NotificationResponseApprovalTelegramAdapter()

    )
