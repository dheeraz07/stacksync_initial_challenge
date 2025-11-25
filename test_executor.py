import requests
import json
import time
import sys

BASE_URL = "http://localhost:8080/execute"


def run_test(name, script, expected_status=200, check_output=None):
    print(f"Testing: {name}...", end=" ")
    try:
        response = requests.post(BASE_URL, json={"script": script}, timeout=15)
        if response.status_code != expected_status:
            print(f"FAILED. Expected status {expected_status}, got {response.status_code}")
            print("Response:", response.text)
            return False

        if check_output:
            data = response.json()
            if not check_output(data):
                print("FAILED. Output verification failed.")
                print("Response:", json.dumps(data, indent=2))
                return False

        print("PASSED")
        return True
    except Exception as e:
        print(f"FAILED. Exception: {e}")
        return False


def main():
    print("Running tests against", BASE_URL)
    print("Ensure docker container is running: docker run --privileged -p 8080:8080 python-executor")
    print("-" * 50)

    # Test 1: Valid Script
    script_valid = """
    def main():
        import numpy as np
        return {"status": "success", "val": int(np.sum([1, 2, 3]))}
    """
    run_test(
        "Valid Script (numpy)",
        script_valid,
        200,
        lambda d: d["result"]["val"] == 6 and d["result"]["status"] == "success",
    )

    # Test 2: Infinite Loop (Timeout)
    script_loop = """
    def main():
        while True:
            pass
        return {}
    """
    run_test("Infinite Loop (Timeout)", script_loop, 408)  # Expect 408 Request Timeout

    # Test 3: File System Write Access (Security)
    script_fs = """
    def main():
        try:
            with open("/etc/passwd", "w") as f:
                f.write("hacked")
            return {"status": "hacked"}
        except Exception as e:
            return {"status": "blocked", "error": str(e)}
    """
    run_test(
        "File System Write (Security)",
        script_fs,
        200,
        lambda d: d["result"]["status"] == "blocked",
    )

    # Test 4: Invalid Syntax
    script_syntax = """
    def main(
        return {}
    """
    run_test("Invalid Syntax", script_syntax, 400)

    # Test 5: No main() function
    script_no_main = """
    print("I have no main")
    """
    run_test("No main() function", script_no_main, 400)


if __name__ == "__main__":
    main()
