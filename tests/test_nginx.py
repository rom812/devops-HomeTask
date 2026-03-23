import requests
import sys
import time
import ssl
import socket
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
# Test 4: Verify the SSL certificate properties
# We connect directly with Python's ssl module to inspect the certificate.
# This proves the cert exists, is issued for "localhost", and is self-signed
# (issuer == subject, meaning no external CA signed it).
# ---------------------------------------------------------------------------
try:
    # Connect with CERT_REQUIRED so getpeercert() returns the full parsed dict.
    # We load no trusted CAs, so we must set check_hostname=False.
    # Instead we manually verify the cert fields ourselves.
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    # First connection: get the raw DER cert to verify it exists
    with socket.create_connection(("nginx", 8443)) as sock:
        with ctx.wrap_socket(sock, server_hostname="nginx") as ssock:
            der_cert = ssock.getpeercert(binary_form=True)

    if not der_cert:
        print("FAIL: no SSL certificate received")
        failed = True
    else:
        print("PASS: SSL certificate is present")

        # Parse the DER certificate to extract subject and issuer fields
        # We use the cryptography library if available, otherwise openssl via subprocess
        import subprocess
        import tempfile
        import os

        # Write the PEM cert to a temp file and parse with openssl
        pem_cert = ssl.DER_cert_to_PEM_cert(der_cert)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
            f.write(pem_cert)
            temp_path = f.name

        try:
            # Extract subject CN
            subject_out = subprocess.run(
                ["openssl", "x509", "-in", temp_path, "-noout", "-subject"],
                capture_output=True, text=True
            ).stdout.strip()

            # Extract issuer CN
            issuer_out = subprocess.run(
                ["openssl", "x509", "-in", temp_path, "-noout", "-issuer"],
                capture_output=True, text=True
            ).stdout.strip()

            # Check CN = localhost
            if "CN = localhost" in subject_out or "CN=localhost" in subject_out:
                print("PASS: certificate CN is 'localhost'")
            else:
                print(f"FAIL: certificate subject unexpected: {subject_out}")
                failed = True

            # Self-signed = issuer matches subject
            # Both should contain CN=localhost
            if "CN = localhost" in issuer_out or "CN=localhost" in issuer_out:
                print("PASS: certificate is self-signed (issuer CN matches subject CN)")
            else:
                print(f"FAIL: certificate is not self-signed, issuer: {issuer_out}")
                failed = True
        finally:
            os.unlink(temp_path)

except Exception as e:
    print(f"FAIL: SSL certificate test error: {e}")
    failed = True

# ---------------------------------------------------------------------------
# Test 5: Rate limiting on port 8080
# Config: rate=5r/s, burst=10, nodelay
# Expected: first ~11 requests succeed (1 + 10 burst), rest get 503
# We send 50 requests concurrently with 20 threads to overwhelm the rate limit
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
# Test 6: Verify the rate is specifically 5 requests per second
# After exhausting burst slots above, we wait 1 second. In that time,
# exactly 5 new slots should refill (rate=5r/s = 1 slot every 200ms).
# Then we fire another burst and check that ~5 succeed.
# This proves the RATE is 5/s, not just that rate limiting exists.
# ---------------------------------------------------------------------------
try:
    # Wait 1 second for slots to refill at 5r/s
    time.sleep(1)

    # Send another burst of 20 requests concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        status_codes_2 = list(executor.map(make_request, range(20)))

    num_ok_2 = status_codes_2.count(200)
    num_limited_2 = status_codes_2.count(503)

    print(f"Rate verification results: {num_ok_2} OK (200), {num_limited_2} limited (503)")

    # After 1 second at 5r/s, ~5 slots should have refilled.
    # Allow a small margin (3-5) for timing variance in containers:
    #   - Lower bound (3): sleep may be slightly short, fewer slots refill
    #   - Upper bound (5): sleep may be slightly long + request execution time
    #     allows a couple extra slots to refill
    if 3 <= num_ok_2 <= 5:
        print(f"PASS: rate is ~5r/s (allowed {num_ok_2} after 1s, expected 1-5)")
    else:
        print(f"FAIL: rate is not 5r/s (allowed {num_ok_2} after 1s, expected 1-5)")
        failed = True

except Exception as e:
    print(f"FAIL: rate verification test error: {e}")
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
