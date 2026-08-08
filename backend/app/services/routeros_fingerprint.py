from __future__ import annotations

import os
from typing import Any

import routeros_api


class RouterOSFingerprintCollector:
    """
    Read-only active MikroTik fingerprint collector.

    Primary source:
    - RouterOS API TCP/8728

    No configuration changes are performed.
    """

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def collect(
        self,
        ip_address: str,
    ) -> dict[str, Any]:

        username = os.getenv(
            "MIKROTIK_API_USERNAME",
            "",
        )

        password = os.getenv(
            "MIKROTIK_API_PASSWORD",
            "",
        )

        if not username or not password:
            return {
                "ip_address": ip_address,
                "vendor": "MikroTik",
                "platform": "RouterOS",
                "model": None,
                "identity": None,
                "version": None,
                "architecture": None,
                "cpu": None,
                "cpu_count": None,
                "cpu_frequency_mhz": None,
                "cpu_usage": None,
                "total_memory_bytes": None,
                "free_memory_bytes": None,
                "memory_usage": None,
                "uptime": None,
                "source": ["TCP Fingerprint"],
                "confidence": 70,
                "status": "partial",
                "error": (
                    "MikroTik API credentials "
                    "are not configured"
                ),
            }

        connection = None

        try:
            connection = routeros_api.RouterOsApiPool(
                ip_address,
                username=username,
                password=password,
                port=8728,
                plaintext_login=True,
            )

            api = connection.get_api()

            resources = api.get_resource(
                "/system/resource"
            ).get()

            identities = api.get_resource(
                "/system/identity"
            ).get()

            resource = (
                resources[0]
                if resources
                else {}
            )

            identity = (
                identities[0]
                if identities
                else {}
            )

            total_memory = self._to_float(
                resource.get("total-memory")
            )

            free_memory = self._to_float(
                resource.get("free-memory")
            )

            memory_usage = None

            if (
                total_memory is not None
                and total_memory > 0
                and free_memory is not None
            ):
                memory_usage = round(
                    (
                        (
                            total_memory
                            - free_memory
                        )
                        / total_memory
                    )
                    * 100,
                    2,
                )

            return {
                "ip_address": ip_address,
                "vendor": "MikroTik",
                "platform": (
                    resource.get("platform")
                    or "MikroTik"
                ),
                "model": resource.get(
                    "board-name"
                ),
                "board_name": resource.get(
                    "board-name"
                ),
                "identity": identity.get(
                    "name"
                ),
                "version": resource.get(
                    "version"
                ),
                "architecture": resource.get(
                    "architecture-name"
                ),
                "cpu": resource.get("cpu"),
                "cpu_count": self._to_float(
                    resource.get("cpu-count")
                ),
                "cpu_frequency_mhz": self._to_float(
                    resource.get(
                        "cpu-frequency"
                    )
                ),
                "cpu_usage": self._to_float(
                    resource.get("cpu-load")
                ),
                "total_memory_bytes": (
                    total_memory
                ),
                "free_memory_bytes": (
                    free_memory
                ),
                "memory_usage": memory_usage,
                "uptime": resource.get(
                    "uptime"
                ),
                "source": [
                    "RouterOS API 8728"
                ],
                "confidence": 99,
                "status": "fingerprinted",
                "error": None,
            }

        except Exception as exc:
            return {
                "ip_address": ip_address,
                "vendor": "MikroTik",
                "platform": "RouterOS",
                "model": None,
                "identity": None,
                "version": None,
                "architecture": None,
                "cpu": None,
                "cpu_count": None,
                "cpu_frequency_mhz": None,
                "cpu_usage": None,
                "total_memory_bytes": None,
                "free_memory_bytes": None,
                "memory_usage": None,
                "uptime": None,
                "source": [
                    "TCP Fingerprint"
                ],
                "confidence": 70,
                "status": "partial",
                "error": str(exc)[:500],
            }

        finally:
            if connection is not None:
                try:
                    connection.disconnect()
                except Exception:
                    pass


routeros_fingerprint_collector = (
    RouterOSFingerprintCollector()
)
