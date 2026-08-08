from app.services.network_discovery_scanner import (
    NetworkDiscoveryScanner,
)


def test_scanner_creates_job():
    scanner = NetworkDiscoveryScanner()

    job = scanner.start(
        "127.0.0.1/32",
        "LOCALHOST",
    )

    assert job["job_id"].startswith(
        "DISC-"
    )
    assert (
        job["normalized_range"]
        == "127.0.0.1/32"
    )
    assert job["total_hosts"] == 1
    assert job["status"] in {
        "RUNNING",
        "COMPLETED",
    }


def test_scanner_rejects_large_network():
    scanner = NetworkDiscoveryScanner()

    try:
        scanner.start(
            "10.0.0.0/8"
        )
    except ValueError as exc:
        assert "too large" in str(exc)
    else:
        raise AssertionError(
            "Large discovery scope was accepted"
        )
