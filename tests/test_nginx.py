
import requests
import sys
import concurrent.futures

#check if any test fails
failed = False

#Test 1: HTML server on port 8080 should return 200
try:
    r = requests.get("http://nginx:8080")
    if r.status_code == 200:
        print("PASS: port 8080 returned status 200")
    else:
        print(f"FAIL: port 8080 returned status {r.status_code},expected 200")
        failed = True
except Exception as e:
    print(f"FAIL: could not connect to port 8080: {e}")
    failed = True

#Test 2: Error server on port 8081 should return 403
try:
    r = requests.get("http://nginx:8081")
    if r.status_code == 403:
        print("PASS: port 8081 returned status 403")
    else:
        print(f"FAIL: port 8081 returned status {r.status_code},expected 403")
        failed = True
except Exception as e:
    print(f"FAIL: could not connect to port 8081: {e}")
    failed = True

#Test 3: Rate limiting on port 8080

try:
    def make_request(_):
        return requests.get("http://nginx:8080").status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        status_codes = list(executor.map(make_request, range(50)))

    num_ok = status_codes.count(200)
    num_limited = status_codes.count(503)

    if num_limited > 0 and num_ok > 0:
        print(f"PASS: rate limiting works ({num_ok} allowed,{num_limited} limited)")
    else:
        print(f"FAIL: rate limiting not working (got {num_ok} OK,{num_limited} limited)")
        failed = True
except Exception as e:
    print(f"FAIL: rate limit test error: {e}")
    failed = True

#Exit with code
if failed:
    print("SOME TESTS FAILED")
    sys.exit(1)
else:
    print("ALL TESTS PASSED")
    sys.exit(0)



