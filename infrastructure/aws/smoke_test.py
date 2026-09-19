"""End-to-end check of a deployed KaamSetu API. Standard library only.

    python infrastructure/aws/smoke_test.py https://<api-id>.execute-api.<region>.amazonaws.com

The demo key is read from KAAMSETU_DEMO_KEY_FILE (default ~/.config/kaamsetu/demo-api-key) and is
never printed. Each run creates one clearly labelled customer in the demo business; its id is
printed so it can be removed.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

KEY_FILE = Path(os.environ.get("KAAMSETU_DEMO_KEY_FILE", "~/.config/kaamsetu/demo-api-key"))


class Client:
    def __init__(self, base_url: str, key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.key = key

    def call(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        key: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        headers = {"Content-Type": "application/json"}
        if key:
            headers["X-Demo-Key"] = key
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            self.base_url + path, data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read() or b"{}")


def main(base_url: str) -> int:
    key = KEY_FILE.expanduser().read_text().strip()
    client = Client(base_url, key)
    failures: list[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        print(f"{'PASS' if condition else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
        if not condition:
            failures.append(name)

    status, body = client.call("GET", "/api/v1/health")
    check("health is open and reports ok", status == 200 and body["data"]["status"] == "ok")

    status, missing = client.call("GET", "/api/v1/customers/cus_probe")
    check("no key is rejected (401)", status == 401 and missing["error"]["code"] == "UNAUTHORIZED")

    status, wrong = client.call("GET", "/api/v1/customers/cus_probe", key="wrong-key")
    check(
        "a wrong key is rejected identically",
        status == 401 and wrong["error"] == missing["error"],
    )

    status, body = client.call(
        "POST", "/api/v1/customers", key=key, body={"name": "Smoke", "business_id": "bus_other"}
    )
    check("a body naming a business is refused (422)", status == 422, f"got {status}")

    status, created = client.call(
        "POST",
        "/api/v1/customers",
        key=key,
        body={"name": "Deployment Smoke Test", "phone": "90000 99999"},
    )
    customer_id = created.get("data", {}).get("customer_id", "")
    check("customer is created (201)", status == 201 and customer_id.startswith("cus_"))
    check("phone was normalized", created.get("data", {}).get("phone") == "+919000099999")

    status, fetched = client.call("GET", f"/api/v1/customers/{customer_id}", key=key)
    check(
        "customer reads back identically",
        status == 200 and fetched.get("data") == created["data"],
    )

    status, absent = client.call("GET", "/api/v1/customers/cus_doesnotexist", key=key)
    check("unknown customer is 404", status == 404 and absent["error"]["code"] == "NOT_FOUND")

    print(f"\nCreated customer: {customer_id or '(none)'}")
    print("FAILED: " + ", ".join(failures) if failures else "All checks passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
