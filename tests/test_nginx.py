import requests
import sys
import time
import concurrent.futures

# Track test failures
failed = False

# ---------------------------------------------------------------------------
# Test 1: HTML server on port 8080 should return 200 with correct content
# ---------------------------------------------------------------------------
try:
    r = requests.get("http://nginx:8080")
    if r.status_code == 200:
        print("PASS: port 8080 returned status 200")
    else:
        print(f"FAIL: port 8080 returned status {r.status_code}, expected 200")
        failed = True

    # Verify response content contains expected HTML
    if "Hello from Rom" in r.text:
        print("PASS: port 8080 returned expected HTML content")
    else:
        print(f"FAIL: port 8080 unexpected content: {r.text[:100]}")
        failed = True
except Exception as e:
    print(f"FAIL: could not connect to port 8080: {e}")
    failed = True

# ---------------------------------------------------------------------------
# Test 2: Error server on port 8081 should return 403 with error message
# ---------------------------------------------------------------------------
try:
    r = requests.get("http://nginx:8081")
    if r.status_code == 403:
        print("PASS: port 8081 returned status 403")
    else:
        print(f"FAIL: port 8081 returned status {r.status_code}, expected 403")
        failed = True

    # Verify response content contains "Forbidden"
    if "Forbidden" in r.text:
        print("PASS: port 8081 returned 'Forbidden' message")
    else:
        print(f"FAIL: port 8081 unexpected content: {r.text[:100]}")
        failed = True
except Exception as e:
    print(f"FAIL: could not connect to port 8081: {e}")
    failed = True

# ---------------------------------------------------------------------------
# Test 3: HTTPS server on port 8443 should return 200 with correct content
# verify=False because we use a self-signed certificate
# ---------------------------------------------------------------------------
try:
    r = requests.get("https://nginx:8443", verify=False)
    if r.status_code == 200:
        print("PASS: port 8443 (HTTPS) returned status 200")
    else:
        print(f"FAIL: port 8443 (HTTPS) returned status {r.status_code}, expected 200")
        failed = True

    # Verify response content contains expected HTML
    if "Hello from Rom" in r.text:
        print("PASS: port 8443 (HTTPS) returned expected HTML content")
    else:
        print(f"FAIL: port 8443 (HTTPS) unexpected content: {r.text[:100]}")
        failed = True
except Exception as e:
    print(f"FAIL: could not connect to port 8443 (HTTPS): {e}")
    failed = True

# ---------------------------------------------------------------------------
# Test 4: Rate limiting on port 8080
# Config: rate=5r/s, burst=10, nodelay
# Expected: first ~11 requests succeed (1 + 10 burst), rest get 503
# We send 50 requests with 20 threads to overwhelm the rate limit
# ---------------------------------------------------------------------------
try:
    # Wait for rate limit slots to fully replenish from previous tests
    time.sleep(3)

    def make_request(_):
        return requests.get("http://nginx:8080").status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        status_codes = list(executor.map(make_request, range(50)))

    num_ok = status_codes.count(200)
    num_limited = status_codes.count(503)

    print(f"Rate limit results: {num_ok} OK (200), {num_limited} limited (503)")

    # Verify both allowed and rejected requests exist
    if num_limited > 0 and num_ok > 0:
        print(f"PASS: rate limiting works ({num_ok} allowed, {num_limited} limited)")
    else:
        print(f"FAIL: rate limiting not working (got {num_ok} OK, {num_limited} limited)")
        failed = True

    # Verify the threshold: with rate=5r/s and burst=10, at most ~15 should succeed
    # (11 immediate + a few that slip through during execution time)
    if num_ok <= 20:
        print(f"PASS: rate limit threshold correct (allowed {num_ok}, expected <= 20)")
    else:
        print(f"FAIL: too many requests allowed ({num_ok}), rate limit may not be working correctly")
        failed = True

except Exception as e:
    print(f"FAIL: rate limit test error: {e}")
    failed = True

# ---------------------------------------------------------------------------
# Exit with appropriate code
# ---------------------------------------------------------------------------
if failed:
    print("\nSOME TESTS FAILED")
    sys.exit(1)
else:
    print("\nALL TESTS PASSED")
    sys.exit(0)
