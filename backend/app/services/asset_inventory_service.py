from datetime import datetime, timezone
from uuid import uuid4

from app.models.network_asset import NetworkAsset
from app.services.asset_store import asset_store


class AssetInventoryService:
    """
    SS4TS-NOC Asset Inventory Service

    H29.2.1:
    - Creates intelligent network assets
    - Updates persistent inventory store
    - Keeps in-memory cache
    - Synchronizes discovery results
    """

    def __init__(self):

        self.assets: dict[str, NetworkAsset] = {}


    def register(
        self,
        device: dict,
    ) -> NetworkAsset:

        now = datetime.now(
            timezone.utc
        ).isoformat()


        asset_id = (
            "MTK-"
            + uuid4().hex[:8].upper()
        )


        asset = NetworkAsset(

            asset_id=asset_id,


            ip_address=device.get(
                "ip_address"
            ),


            vendor=device.get(
                "vendor",
                "Unknown"
            ),


            model=device.get(
                "model"
            ),


            identity=device.get(
                "identity"
            ),


            platform=device.get(
                "platform"
            ),


            version=device.get(
                "version"
            ),


            architecture=device.get(
                "architecture"
            ),


            cpu=device.get(
                "cpu"
            ),


            cpu_count=device.get(
                "cpu_count"
            ),


            memory_usage=device.get(
                "memory_usage"
            ),


            uptime=device.get(
                "uptime"
            ),


            device_type=device.get(
                "device_type"
            ),


            confidence=device.get(
                "confidence",
                0
            ),


            status="ACTIVE",


            first_seen=now,


            last_seen=now,

        )


        #
        # In-memory cache
        #
        self.assets[
            asset.ip_address
        ] = asset



        #
        # Persistent SQLite Inventory
        #
        asset_store.save(
            asset.model_dump()
        )


        return asset



    def update(
        self,
        device: dict,
    ) -> NetworkAsset:

        return self.register(
            device
        )



    def get(
        self,
        ip_address: str,
    ) -> NetworkAsset | None:

        return self.assets.get(
            ip_address
        )



    def list_assets(
        self,
    ) -> list[NetworkAsset]:

        return list(
            self.assets.values()
        )



asset_inventory_service = (
    AssetInventoryService()
)
