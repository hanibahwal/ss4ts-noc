from typing import Any


class AssetIntelligenceService:
    """
    SS4TS-NOC Asset Intelligence Engine

    H29.5:
    - Asset health scoring
    - Firmware risk detection
    - Memory risk analysis
    - Executive recommendations
    """


    def analyze(
        self,
        asset: dict[str, Any]
    ) -> dict[str, Any]:

        score = 100

        risks = []

        recommendations = []


        memory = asset.get(
            "memory_usage"
        )

        if memory is not None:

            if memory >= 80:

                score -= 30

                risks.append(
                    "High memory utilization"
                )

                recommendations.append(
                    "Investigate memory usage"
                )


            elif memory >= 60:

                score -= 10

                risks.append(
                    "Medium memory utilization"
                )


        version = asset.get(
            "version",
            ""
        )


        if version.startswith("6."):

            score -= 15

            risks.append(
                "Legacy RouterOS version"
            )

            recommendations.append(
                "Plan RouterOS upgrade"
            )


        if asset.get(
            "vendor"
        ) == "MikroTik":

            platform_score = (
                "RouterOS Device"
            )

        else:

            platform_score = (
                "Unknown Platform"
            )


        if score < 0:
            score = 0


        if score >= 85:

            health = "GOOD"

        elif score >= 60:

            health = "WARNING"

        else:

            health = "CRITICAL"



        return {

            "ip_address":
                asset.get("ip_address"),

            "identity":
                asset.get("identity"),

            "model":
                asset.get("model"),

            "health_score":
                score,

            "health_status":
                health,

            "platform":
                platform_score,

            "risks":
                risks,

            "recommendations":
                recommendations

        }



asset_intelligence_service = (
    AssetIntelligenceService()
)
