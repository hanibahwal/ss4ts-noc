from __future__ import annotations

import shutil
import socket
import subprocess
import threading
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.services.network_discovery_engine import (
    NetworkDiscoveryEngine,
)

from app.services.routeros_fingerprint import (
    routeros_fingerprint_collector,
)

from app.services.asset_inventory_service import (
    asset_inventory_service,
)


class NetworkDiscoveryScanner:
    """
    SS4TS-NOC concurrent discovery runtime.

    Phase H29.1:
    - CIDR-aware
    - concurrent probing
    - ICMP detection
    - TCP fingerprinting
    - RouterOS API fingerprinting
    - cancellation
    - incremental progress

    Discovery is read-only.
    """

    DEFAULT_WORKERS = 64

    PROBE_PORTS = (
        8291,   # Winbox
        8728,   # RouterOS API
        8729,   # RouterOS API SSL
        22,
        443,
        80,
    )


    def __init__(self) -> None:

        self.engine = NetworkDiscoveryEngine()

        self._jobs: dict[str, dict[str, Any]] = {}

        self._lock = threading.RLock()

        self._ping_binary = shutil.which(
            "ping"
        )

        self._fingerprint_semaphore = (
            threading.BoundedSemaphore(8)
        )


    @staticmethod
    def _now() -> str:
        return datetime.now(
            timezone.utc
        ).isoformat()


    def start(
        self,
        network_range: str,
        name: str | None = None,
    ) -> dict[str, Any]:

        info = self.engine.describe(
            network_range
        )

        job_id = (
            f"DISC-{uuid4().hex[:16].upper()}"
        )

        job = {

            "job_id": job_id,

            "name":
                name
                or f"Discovery {info['cidr']}",

            "requested_range":
                network_range,

            "normalized_range":
                info["cidr"],

            "network":
                info["network"],

            "netmask":
                info["netmask"],

            "broadcast":
                info["broadcast"],

            "total_addresses":
                info["total_addresses"],

            "total_hosts":
                info["usable_hosts"],

            "first_host":
                info["first_host"],

            "last_host":
                info["last_host"],

            "status":
                "RUNNING",

            "scanned":0,

            "found":0,

            "mikrotik":0,

            "ubiquiti":0,

            "other":0,

            "progress":0.0,

            "created_at":
                self._now(),

            "started_at":
                self._now(),

            "completed_at":
                None,

            "cancel_requested":
                False,

            "results":[],

            "error":
                None,
        }


        with self._lock:
            self._jobs[job_id] = job


        threading.Thread(
            target=self._run,
            args=(job_id,),
            daemon=True,
        ).start()


        return self.get(job_id)



    def get(
        self,
        job_id:str,
    ) -> dict[str,Any]:

        with self._lock:

            job=self._jobs.get(
                job_id
            )

            if job is None:
                raise KeyError(job_id)

            return {
                k:v
                for k,v in job.items()
                if k!="results"
            }



    def results(
        self,
        job_id:str,
    ):

        with self._lock:

            return list(
                self._jobs[job_id]["results"]
            )



    def _icmp_probe(
        self,
        ip:str,
    ) -> bool:

        if not self._ping_binary:
            return False


        try:

            result=subprocess.run(
                [
                    self._ping_binary,
                    "-n",
                    "-c",
                    "1",
                    "-W",
                    "1",
                    ip,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=1.5,
            )

            return result.returncode==0


        except Exception:

            return False



    @staticmethod
    def _tcp_open(
        ip:str,
        port:int,
        timeout:float=0.20,
    ) -> bool:

        try:

            with socket.create_connection(
                (ip,port),
                timeout=timeout,
            ):
                return True

        except OSError:

            return False



    def _probe(
        self,
        ip:str,
    ) -> dict[str,Any]:

        icmp_alive = self._icmp_probe(
            ip
        )


        open_ports=[]


        for port in self.PROBE_PORTS:

            if self._tcp_open(
                ip,
                port,
            ):
                open_ports.append(port)



        discovered = (
            icmp_alive
            or bool(open_ports)
        )


        vendor=None
        device_type=None
        confidence=0

        fingerprint=None



        if (
            8291 in open_ports
            or 8728 in open_ports
            or 8729 in open_ports
        ):

            vendor="MikroTik"

            device_type=(
                "RouterOS Device"
            )

            confidence=90



        #
        # H29.1 RouterOS Fingerprint
        #

        if (
            vendor=="MikroTik"
            and 8728 in open_ports
        ):

            try:

                with self._fingerprint_semaphore:

                    fingerprint = (
                        routeros_fingerprint_collector.collect(
                            ip
                        )
                    )


                if fingerprint.get(
                    "status"
                )=="fingerprinted":

                    confidence = int(
                        fingerprint.get(
                            "confidence",
                            confidence,
                        )
                    )

                    asset_inventory_service.register(
                        {
                            "ip_address": ip,
                            **fingerprint,
                            "device_type": "RouterOS Device",
                            "confidence": confidence,
                        }
                    )


            except Exception as exc:

                fingerprint = {
                    "status":
                        "failed",

                    "error":
                        str(exc),
                }



        if discovered and vendor is None:

            vendor="Unknown"

            device_type=(
                "Network Device"
            )

            confidence=25



        methods=[]


        if icmp_alive:
            methods.append(
                "ICMP"
            )


        if open_ports:
            methods.append(
                "TCP"
            )


        if fingerprint:

            methods.extend(
                fingerprint.get(
                    "source",
                    []
                )
            )


        return {


            "ip_address":
                ip,


            "discovered":
                discovered,


            "vendor":
                vendor,


            "model":
                (
                    fingerprint.get(
                        "model"
                    )
                    if fingerprint
                    else None
                ),


            "identity":
                (
                    fingerprint.get(
                        "identity"
                    )
                    if fingerprint
                    else None
                ),


            "platform":
                (
                    fingerprint.get(
                        "platform"
                    )
                    if fingerprint
                    else None
                ),


            "version":
                (
                    fingerprint.get(
                        "version"
                    )
                    if fingerprint
                    else None
                ),


            "architecture":
                (
                    fingerprint.get(
                        "architecture"
                    )
                    if fingerprint
                    else None
                ),


            "cpu":
                (
                    fingerprint.get(
                        "cpu"
                    )
                    if fingerprint
                    else None
                ),


            "cpu_count":
                (
                    fingerprint.get(
                        "cpu_count"
                    )
                    if fingerprint
                    else None
                ),


            "memory_usage":
                (
                    fingerprint.get(
                        "memory_usage"
                    )
                    if fingerprint
                    else None
                ),


            "uptime":
                (
                    fingerprint.get(
                        "uptime"
                    )
                    if fingerprint
                    else None
                ),


            "device_type":
                device_type,


            "confidence":
                confidence,


            "open_ports":
                open_ports,


            "discovery_methods":
                methods,


            "fingerprint_status":
                (
                    fingerprint.get(
                        "status"
                    )
                    if fingerprint
                    else "not_attempted"
                ),


            "fingerprint_source":
                (
                    fingerprint.get(
                        "source"
                    )
                    if fingerprint
                    else []
                ),


            "first_seen":
                (
                    self._now()
                    if discovered
                    else None
                ),
        }



    def _record(
        self,
        job_id: str,
        result: dict[str, Any],
    ) -> None:

        with self._lock:
            job = self._jobs[job_id]

            job["scanned"] += 1

            if result.get("discovered"):

                job["results"].append(result)
                job["found"] += 1

                vendor = result.get("vendor")

                if vendor == "MikroTik":
                    job["mikrotik"] += 1
                elif vendor == "Ubiquiti":
                    job["ubiquiti"] += 1
                else:
                    job["other"] += 1

            total = max(int(job["total_hosts"]), 1)

            job["progress"] = round(
                (job["scanned"] / total) * 100,
                1,
            )


    def _run(
        self,
        job_id: str,
    ) -> None:

        try:

            with self._lock:
                cidr = self._jobs[job_id]["normalized_range"]

            hosts = [
                str(host)
                for host in self.engine.iter_hosts(cidr)
            ]

            with ThreadPoolExecutor(
                max_workers=self.DEFAULT_WORKERS,
                thread_name_prefix="ss4ts-disc",
            ) as executor:

                futures = {
                    executor.submit(
                        self._probe,
                        ip,
                    ): ip
                    for ip in hosts
                }

                for future in as_completed(futures):

                    if self._jobs[job_id]["cancel_requested"]:
                        for pending in futures:
                            pending.cancel()
                        break

                    try:
                        result = future.result()

                    except Exception as exc:

                        result = {
                            "ip_address": futures[future],
                            "discovered": False,
                            "error": str(exc),
                        }

                    self._record(
                        job_id,
                        result,
                    )

            with self._lock:

                job = self._jobs[job_id]

                if job["cancel_requested"]:
                    job["status"] = "CANCELLED"
                else:
                    job["status"] = "COMPLETED"
                    job["progress"] = 100.0

                job["completed_at"] = self._now()

        except Exception as exc:

            with self._lock:
                job = self._jobs[job_id]
                job["status"] = "FAILED"
                job["error"] = str(exc)
                job["completed_at"] = self._now()



network_discovery_scanner = (
    NetworkDiscoveryScanner()
)
