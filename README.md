# DevOps Home Assignment - Nginx Docker Project

## Overview

This project demonstrates containerization, testing, and CI/CD automation using Docker. It consists of an Nginx web server running multiple server blocks inside a Docker container, a Python-based test container that validates the server's behavior, and a GitHub Actions CI pipeline that automates the entire build-and-test process.

## Project Structure

```
devops-HomeTask/
├── nginx/
│   ├── Dockerfile          # Ubuntu-based image with Nginx and OpenSSL
│   └── nginx.conf          # Nginx configuration with 3 server blocks
├── tests/
│   ├── Dockerfile          # Python slim image with test script
│   └── test_nginx.py       # Integration tests for all Nginx servers
├── docker-compose.yml      # Orchestrates both containers
├── .github/
│   └── workflows/
│       └── ci.yml          # GitHub Actions CI pipeline
└── README.md
```

## How to Build and Run

### Prerequisites

- Docker and Docker Compose installed
- Git installed

### Run Locally

```bash
# Clone the repository
git clone https://github.com/rom812/devops-HomeTask.git
cd devops-HomeTask

# Build and run everything
docker compose up --build

# Run with auto-exit when tests finish
docker compose up --build --abort-on-container-exit --exit-code-from tests

# Clean up
docker compose down
```

### Expected Output

```
tests-1  | PASS: port 8080 returned status 200
tests-1  | PASS: port 8081 returned status 403
tests-1  | PASS: rate limiting works (10 allowed, 40 limited)
tests-1  | ALL TESTS PASSED
```

## Architecture

### Nginx Container

The Nginx container is built on **Ubuntu 22.04** and runs three server blocks:

| Port | Protocol | Behavior |
|------|----------|----------|
| 8080 | HTTP | Serves a custom HTML page. Rate limited to 5 req/s. |
| 8081 | HTTP | Returns HTTP 403 Forbidden error. |
| 8443 | HTTPS | Serves a custom HTML page over HTTPS using a self-signed certificate. |

### Test Container

Built on **python:3.11-slim**, the test container runs three integration tests:

1. **HTTP Response Test** - Verifies port 8080 returns status 200
2. **Error Response Test** - Verifies port 8081 returns status 403
3. **Rate Limiting Test** - Sends 50 concurrent requests to port 8080 and verifies that some are accepted (200) and some are rejected (503)

The test script exits with code 0 on success and code 1 on failure.

### CI Pipeline

The GitHub Actions workflow triggers on every push and pull request to `main`. It:

1. Checks out the code
2. Builds both Docker images
3. Runs `docker compose up` with test validation
4. Uploads an artifact named `succeeded` if tests pass, or `fail` if tests fail

## Design Decisions and Trade-offs

### Ubuntu as the Nginx Base Image

The assignment requires Ubuntu as the base image. In production, a lighter base like `nginx:alpine` would reduce image size significantly (~20MB vs ~170MB). However, Ubuntu provides a familiar environment and easy access to tools like OpenSSL for certificate generation.

### Image Size Optimization

- **Nginx image**: The apt cache is removed after installation (`rm -rf /var/lib/apt/lists/*`) and packages are installed in a single `RUN` layer to avoid bloating the image with intermediate layers.
- **Test image**: Uses `python:3.11-slim` instead of the full Python image, reducing size from ~900MB to ~150MB.

### Self-Signed Certificate

The SSL certificate is generated during the Docker build using OpenSSL. This means the certificate is baked into the image -- no manual setup required. The trade-off is that the certificate is not trusted by browsers (they will show a warning), but encryption still works. In production, you would use a CA-signed certificate from a service like Let's Encrypt.

### Static File Serving vs `return` Directive

The port 8080 server block serves a static HTML file using `try_files` instead of the `return` directive. This is because Nginx's `return` directive is processed in the rewrite phase, which occurs before the preaccess phase where rate limiting (`limit_req`) runs. Using `return` would bypass rate limiting entirely. Serving a static file ensures the request goes through all processing phases, including rate limiting.

### `depends_on` Limitation

Docker Compose's `depends_on` only waits for the container to start, not for the service inside it to be ready. In practice, Nginx starts fast enough that the tests connect successfully. For more robust setups, a healthcheck or retry mechanism could be added.

## Rate Limiting Configuration

### How It Works

Rate limiting uses Nginx's `ngx_http_limit_req_module`, which implements the **leaky bucket algorithm**.

Two directives control it:

**1. Zone definition** (in `nginx.conf`, inside `http {}` block):

```nginx
limit_req_zone $binary_remote_addr zone=ratelimit:10m rate=5r/s;
```

- `$binary_remote_addr` - Tracks each client by their IP address (binary format saves memory).
- `zone=ratelimit:10m` - Creates a shared memory zone named "ratelimit" with 10MB of storage (~160,000 unique IPs).
- `rate=5r/s` - Sets the refill rate to 5 requests per second (1 request every 200ms).

**2. Zone application** (inside the `server {}` block):

```nginx
limit_req zone=ratelimit burst=10 nodelay;
```

- `zone=ratelimit` - References the zone defined above.
- `burst=10` - Allows up to 10 extra requests to be accepted during a traffic spike.
- `nodelay` - Burst requests are served immediately instead of being queued and drip-fed.

### Behavior

With `rate=5r/s` and `burst=10`:

- A client can make up to **11 requests instantly** (1 base + 10 burst slots).
- After the burst is used up, additional requests are rejected with **HTTP 503**.
- Burst slots refill at a rate of **5 per second** (one every 200ms).
- After 2 seconds of inactivity, all 10 burst slots are fully refilled.

### How to Change the Rate Limit Threshold

Edit `nginx/nginx.conf`:

**To change the rate** (e.g., to 10 requests per second):

```nginx
limit_req_zone $binary_remote_addr zone=ratelimit:10m rate=10r/s;
```

**To change the burst size** (e.g., allow 20 extra requests):

```nginx
limit_req zone=ratelimit burst=20 nodelay;
```

**To remove burst tolerance entirely** (strict rate only):

```nginx
limit_req zone=ratelimit;
```

After any change, rebuild the Docker image:

```bash
docker compose up --build
```

## Assumptions

- Docker and Docker Compose are available in the environment.
- Ports 8080, 8081, and 8443 are not in use by other services on the host machine.
- The self-signed certificate is acceptable for testing purposes (not production).
- The test container can resolve the hostname `nginx` via Docker Compose's internal DNS.
