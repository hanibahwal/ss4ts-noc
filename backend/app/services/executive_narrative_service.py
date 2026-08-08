from typing import Any


class ExecutiveNarrativeService:
    """
    SS4TS-NOC Executive Narrative Engine

    H30:
    - Converts technical intelligence into executive decisions
    - Generates management summary
    - Identifies priorities
    """

    def generate(
        self,
        assets: list[dict[str, Any]]
    ) -> dict[str, Any]:

        total = len(assets)

        if total == 0:
            return {
                "overall_status": "UNKNOWN",
                "summary": "No assets available",
                "risks": [],
                "actions": []
            }


        legacy = 0
        warning = 0
        critical = 0

        for asset in assets:

            if "Legacy RouterOS version" in asset.get(
                "risks",
                []
            ):
                legacy += 1


            if asset.get(
                "health_status"
            ) == "WARNING":
                warning += 1


            if asset.get(
                "health_status"
            ) == "CRITICAL":
                critical += 1


        if critical > 0:

            status = "CRITICAL"

        elif warning > 0:

            status = "WARNING"

        else:

            status = "GOOD"



        actions = []


        if legacy:

            actions.append(
                f"Upgrade {legacy} legacy RouterOS devices"
            )


        if warning:

            actions.append(
                f"Review {warning} warning devices"
            )


        if not actions:

            actions.append(
                "Network assets operating normally"
            )


        summary = (
            f"{total} assets analyzed. "
            f"{legacy} legacy devices detected."
        )


        return {

            "overall_status": status,

            "summary": summary,

            "statistics": {

                "total_assets": total,

                "legacy_devices": legacy,

                "warning_devices": warning,

                "critical_devices": critical
            },

            "recommended_actions": actions
        }



executive_narrative_service = (
    ExecutiveNarrativeService()
)
