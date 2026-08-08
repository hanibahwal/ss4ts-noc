from datetime import datetime, timezone
from typing import Any


class DeviceFingerprintEngine:
    """
    Professional Device Fingerprint Engine

    Converts discovered devices into intelligent assets.
    """

    def fingerprint(
        self,
        device: dict[str, Any],
    ) -> dict[str, Any]:

        ip = device.get("ip_address")

        vendor = device.get(
            "vendor",
            "Unknown",
        )

        ports = device.get(
            "open_ports",
            [],
        )

        confidence = 50

        capabilities = []

        device_family = "Unknown"

        role = "Unknown"


        # MikroTik detection
        if vendor.lower() == "mikrotik":

            device_family = "RouterOS"
            confidence += 30

            capabilities.extend(
                [
                    "Routing",
                    "Firewall",
                    "API",
                ]
            )


        # API availability
        if 8728 in ports or 8729 in ports:

            capabilities.append(
                "RouterOS API"
            )

            confidence += 10


        # Winbox detection
        if 8291 in ports:

            capabilities.append(
                "Winbox Management"
            )

            confidence += 5


        # Web management
        if 80 in ports or 443 in ports:

            capabilities.append(
                "Web Management"
            )


        # Role estimation

        if vendor.lower() == "mikrotik":

            if (
                8728 in ports
                and 8291 in ports
            ):
                role = "Network Router"


        confidence = min(
            confidence,
            99,
        )


        return {

            "ip_address": ip,

            "vendor": vendor,

            "family": device_family,

            "role": role,

            "confidence": confidence,

            "capabilities": sorted(
                set(capabilities)
            ),

            "fingerprinted_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),

        }


device_fingerprint_engine = DeviceFingerprintEngine()
