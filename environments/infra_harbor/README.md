# Infra Harbor

A novel reinforcement learning environment for the [Prime Intellect Verifiers](https://github.com/PrimeIntellect-ai/verifiers) framework that trains and evaluates AI coding agents on **DevOps and infrastructure configuration** tasks.

Unlike SWE Harbor (which tests Python/Django application code changes), Infra Harbor tests a fundamentally different skill set: Docker Compose orchestration, nginx reverse proxy configuration, and CI/CD pipeline design.

---

## Table of Contents

- [How This RL Environment Works](#how-this-rl-environment-works)
- [Architecture](#architecture)
- [The Base Infrastructure Project](#the-base-infrastructure-project)
- [Tasks and Verifiers](#tasks-and-verifiers)
- [How We Built It](#how-we-built-it)
- [Quick Start: Local Verification](#quick-start-local-verification)
- [Running with the Verifiers Framework](#running-with-the-verifiers-framework)
- [Directory Structure](#directory-structure)

---

## How This RL Environment Works

Infra Harbor is designed as a **binary-reward RL environment** for training AI agents. Here is the core loop:

1. **Task presentation**: The environment selects a task (e.g., `fix-docker-compose`) and mounts its `instruction.md` into a Docker container at `/task/instruction.md`. The base infrastructure project lives at `/infra/` inside the container.

2. **Agent interaction**: A tool-use agent is placed inside the container with four tools -- `bash`, `read_file`, `write_file`, and `str_replace`. The agent reads the instruction, explores the codebase, and makes configuration changes.

3. **Verification**: After the agent finishes (or times out), the environment runs `test.sh`, which executes a pytest suite against the modified files. Tests perform **structural validation** -- parsing YAML, checking for specific keys/values, validating nginx syntax -- rather than running live services.

4. **Binary reward**: If all tests pass, the agent receives reward **1**. If any test fails, reward **0**. This clean signal is what makes the environment suitable for reinforcement learning (GRPO, PPO, etc.).

```
+------------------+     +-------------------+     +------------------+
|  Verifiers       |     |  Docker Container |     |  Reward Signal   |
|  Framework       |---->|                   |---->|                  |
|                  |     |  /task/            |     |  1 = all tests   |
|  - picks task    |     |    instruction.md  |     |      pass        |
|  - spins up      |     |  /infra/           |     |  0 = any test    |
|    sandbox       |     |    (base project)  |     |      fails       |
|  - injects agent |     |  /tests/           |     |                  |
|  - collects      |     |    test_solution.py|     |                  |
|    reward        |     |    test.sh         |     |                  |
+------------------+     +-------------------+     +------------------+
```

### Why Binary Rewards?

The Verifiers framework uses binary rewards (0 or 1) because they produce a clean learning signal for RL algorithms. Partial credit introduces noise and subjective judgment. With binary rewards, either the infrastructure configuration is correct and complete, or it isn't -- the same standard a production deployment would use.

### Why Structural Validation?

Infrastructure tasks can't be verified by running the actual services inside a test container (Docker-in-Docker is fragile and slow). Instead, we validate the **structure and content** of configuration files:

- **YAML parsing**: Load `docker-compose.yml` or `ci.yml` with PyYAML and assert on keys, values, and nesting
- **Text matching**: Check nginx configs for specific directives (`proxy_set_header`, `gzip on`, `limit_req_zone`)
- **Syntax validation**: Run `nginx -t` to validate nginx configuration syntax
- **File existence**: Verify that required files were created in the right locations

This approach is fast (sub-second verification), deterministic, and doesn't require any external services.

---

## Architecture

Infra Harbor extends the existing Harbor environment pattern from the Verifiers framework:

```
InfraHarborEnv (infra_harbor.py)
    |
    +-- extends HarborEnv (verifiers.envs.experimental.harbor_env)
            |
            +-- extends CliAgentEnv
                    |
                    +-- extends Environment (base class)
```

**What we inherit from HarborEnv:**
- Task loading from the `tasks/` directory (reads `task.toml`, `instruction.md`, tests)
- Docker sandbox lifecycle management (create, run, destroy)
- Test execution and binary reward computation
- Task instruction mounting at `/task/`

**What InfraHarborEnv adds:**
- A self-contained tool-use agent script (`agent.py`) that gets uploaded into the container
- OpenAI SDK configuration for the agent (via OpenRouter)
- Custom `post_sandbox_setup()` that installs dependencies and injects the agent
- Agent working directory set to `/infra/` (the infrastructure project root)

### The Agent

The agent script (embedded in `infra_harbor.py`) is a Python program that runs inside the container and:

1. Connects to an LLM via the OpenAI SDK (configured to use OpenRouter)
2. Receives a system prompt establishing it as a DevOps engineer
3. Has 4 tools: `bash`, `read_file`, `write_file`, `str_replace`
4. Reads `/task/instruction.md` and iteratively solves the task
5. Runs for up to 50 turns before stopping

The agent is the "policy" being trained/evaluated. Different LLMs can be swapped in via the `OPENAI_MODEL` environment variable.

---

## The Base Infrastructure Project

The Docker image contains a realistic multi-service infrastructure project at `/infra/`:

```
/infra/
  docker-compose.yml       # Multi-service orchestration (intentionally buggy)
  Dockerfile.web           # Flask web app image
  Dockerfile.worker        # Background worker image
  nginx/
    nginx.conf             # Main nginx config (intentionally buggy)
    conf.d/
      default.conf         # Site config (minimal, needs features)
  app/
    main.py                # Flask application
    worker.py              # Background worker
    requirements.txt       # Python dependencies
  scripts/
    entrypoint.sh          # Container entrypoint
    healthcheck.sh         # Health check script
  .github/
    workflows/             # Empty -- CI pipeline must be created
  .env.example             # Environment variable template
```

The project is deliberately set up with **realistic bugs and missing features** that the agent must identify and fix. The bugs are the kind that a DevOps engineer would encounter in real-world infrastructure reviews:

- Wrong port mappings
- Outdated image versions
- Missing healthchecks and dependency conditions
- Missing services (Redis)
- Incorrect upstream configurations
- Missing proxy headers, rate limiting, compression
- No CI/CD pipeline

---

## Tasks and Verifiers

### Task 1: `fix-docker-compose` (Medium -- 29 tests)

**What the agent must do:** Fix 7 issues in `docker-compose.yml`:

| Issue | Bug | Fix |
|-------|-----|-----|
| Port mapping | `8081:5000` | `8080:5000` |
| Postgres image | `postgres:13` | `postgres:16` |
| Postgres health | No healthcheck | Add `pg_isready` healthcheck |
| Web depends_on | Simple list form | Condition form with `service_healthy` |
| Redis service | Missing entirely | Add `redis:7-alpine` with healthcheck |
| REDIS_URL | Missing env var | Add to web and worker services |
| Data persistence | No volume | Add `postgres_data` named volume |

**How the verifier works:** Loads the YAML with PyYAML, then 7 test classes assert on specific keys and values:
- `ComposeFileTestCase` -- valid YAML, has version and services
- `WebServiceTestCase` -- correct port, REDIS_URL, condition-form depends_on
- `PostgresServiceTestCase` -- image version, healthcheck params, volume mount
- `RedisServiceTestCase` -- service exists, correct image, healthcheck, ports
- `WorkerServiceTestCase` -- REDIS_URL, depends on redis
- `VolumeTestCase` -- top-level volume declared, mounted on postgres
- `NginxPreservedTestCase` -- nginx service untouched

### Task 2: `fix-nginx-config` (Medium -- 24 tests)

**What the agent must do:** Fix 7 issues across `nginx.conf` and `conf.d/default.conf`:

| Issue | Current State | Required State |
|-------|--------------|----------------|
| Upstream port | `web:8000` | `web:5000` |
| Proxy headers | None | Host, X-Real-IP, X-Forwarded-For, X-Forwarded-Proto |
| Rate limiting | None | `limit_req_zone` + `limit_req` |
| /api/ location | Missing | Proxy to upstream with headers |
| /static/ location | Missing | Expires 30d, Cache-Control public |
| Gzip compression | None | `gzip on`, types, min_length |
| /health endpoint | Missing | `return 200 "ok"` |

**How the verifier works:** A mix of syntax validation and text matching:
- `NginxSyntaxTestCase` -- runs `nginx -t` to validate the config compiles
- `UpstreamTestCase` -- checks for correct `server web:5000` directive
- `ProxyHeadersTestCase` -- checks for all 4 `proxy_set_header` directives
- `RateLimitTestCase` -- checks for `limit_req_zone` and `limit_req`
- `StaticFilesTestCase` -- checks for `/static/` location with expires
- `GzipTestCase` -- checks for gzip directives
- `HealthCheckTestCase` -- checks for `/health` location
- `ApiLocationTestCase` -- checks for `/api/` location
- `PreservationTestCase` -- ensures required directives weren't removed

### Task 3: `add-ci-pipeline` (Hard -- 36 tests)

**What the agent must do:** Create `/infra/.github/workflows/ci.yml` from scratch with 3 jobs:

| Job | Purpose | Key Requirements |
|-----|---------|-----------------|
| `lint` | Code quality | Hadolint for Dockerfiles, yamllint for compose |
| `test` | Testing | Python 3.11 setup, install deps, run pytest |
| `build-and-push` | Deployment | Docker Buildx, GHCR login, build+push with caching |

The pipeline must trigger on push/PR to main, jobs must chain (`lint` -> `test` -> `build-and-push`), and the deploy job must only run on pushes to main.

**How the verifier works:** Parses the YAML and validates every structural aspect:
- `CiFileExistsTestCase` -- file exists and is valid YAML
- `TriggersTestCase` -- push and pull_request on main
- `LintJobTestCase` -- checkout, hadolint for both Dockerfiles, yamllint
- `TestJobTestCase` -- Python 3.11 setup, dependencies, pytest
- `BuildAndPushJobTestCase` -- conditional, GHCR login, Buildx, both image builds with correct tags
- `JobDependenciesTestCase` -- proper `needs` chain
- `CachingTestCase` -- GHA cache-from and cache-to on both builds

---

## How We Built It

### Design Philosophy

We started from the constraints of the Verifiers framework:

1. **Binary reward required** -- environments must return 0 or 1, not partial scores
2. **Harbor format** -- tasks use `task.toml` + `instruction.md` + `solution/solve.sh` + `tests/`
3. **Docker isolation** -- everything runs inside a container
4. **Structural validation** -- we can't run live Docker Compose stacks inside the test container, so we validate configuration files structurally

### Step 1: Choose the Domain

We chose DevOps/infrastructure configuration because:
- It's a fundamentally different skill domain from application code
- Config files (YAML, nginx conf) are parseable and structurally verifiable
- Real-world DevOps has clear "right answers" (correct ports, proper healthchecks)
- The tasks test both fixing bugs and creating new configurations

### Step 2: Build the Base Infrastructure

We created a realistic multi-service project that mirrors what a small engineering team might have:
- Flask web app + background worker (Python)
- PostgreSQL database
- Redis cache
- nginx reverse proxy
- Docker Compose orchestration
- GitHub Actions CI/CD (intentionally missing)

The key design choice was to introduce **realistic bugs** -- the kind you'd find in a code review:
- Wrong port number in the compose file
- Outdated Postgres version
- Missing healthchecks (services start before dependencies are ready)
- nginx upstream pointing to wrong port
- No proxy headers (breaks client IP detection)

### Step 3: Design the Tasks

Each task targets a specific DevOps skill area with escalating complexity:

- **fix-docker-compose** (medium): Teaches Docker Compose concepts -- services, healthchecks, dependency ordering, volumes, environment variables
- **fix-nginx-config** (medium): Teaches nginx concepts -- upstreams, proxy headers, rate limiting, gzip, static file caching
- **add-ci-pipeline** (hard): Requires creating a complete GitHub Actions workflow from scratch -- hardest because there's no existing file to modify

### Step 4: Write the Verifiers

Each test suite was designed to be:
- **Comprehensive**: 24-36 tests per task, covering every required change
- **Independent**: Each test checks one specific thing
- **Deterministic**: No flaky tests, no timing dependencies
- **Fast**: All tests run in < 1 second (structural validation, not live services)

### Step 5: Create Reference Solutions

Each task has a `solve.sh` that applies the correct fix. These serve two purposes:
- **Verification**: Run solve.sh + tests = reward 1 (proves the tests are satisfiable)
- **Training data**: Can be used as expert demonstrations for imitation learning

### Step 6: Build and Verify

The Docker image bundles everything needed:
```dockerfile
FROM python:3.11-slim
RUN apt-get install -y nginx curl      # For nginx -t validation
RUN pip install pyyaml pytest yamllint  # For YAML parsing and testing
COPY infra/ /infra/                    # The base infrastructure project
```

Verification matrix (all confirmed):

| Task | With Solution | Without Solution |
|------|:------------:|:----------------:|
| fix-docker-compose | 1 (29/29 pass) | 0 (24 fail) |
| fix-nginx-config | 1 (24/24 pass) | 0 (18 fail) |
| add-ci-pipeline | 1 (36/36 pass) | 0 (36 fail) |

---

## Quick Start: Local Verification

```bash
cd environments/infra_harbor

# Build the Docker image
docker build -t infra-harbor environment/

# Test a task WITH the reference solution (should print 1)
docker run --rm \
    -v $(pwd)/tasks/fix-docker-compose/solution:/solution \
    -v $(pwd)/tasks/fix-docker-compose/tests:/tests \
    infra-harbor \
    bash -c "mkdir -p /logs/verifier && bash /solution/solve.sh && bash /tests/test.sh && cat /logs/verifier/reward.txt"

# Test a task WITHOUT any solution (should print 0)
docker run --rm \
    -v $(pwd)/tasks/fix-docker-compose/tests:/tests \
    infra-harbor \
    bash -c "mkdir -p /logs/verifier && bash /tests/test.sh && cat /logs/verifier/reward.txt"
```

Replace `fix-docker-compose` with `fix-nginx-config` or `add-ci-pipeline` to test other tasks.

---

## Running with the Verifiers Framework

```python
from infra_harbor import load_environment

env = load_environment(
    tasks=["fix-docker-compose", "fix-nginx-config", "add-ci-pipeline"],
    docker_image="infra-harbor",
    timeout_seconds=900.0,
    max_turns=30,
)

# Use with any Verifiers-compatible training loop
# The environment returns binary rewards (0 or 1)
```

Environment variables:
- `OPENROUTER_API_KEY` -- API key for the agent's LLM (via OpenRouter)
- `OPENAI_MODEL` -- Which model the agent uses (default: `openai/gpt-4o`)

---

## Directory Structure

```
environments/infra_harbor/
  README.md                          # This file
  infra_harbor.py                    # Environment class (InfraHarborEnv)
  pyproject.toml                     # Package metadata and dependencies
  .env.example                       # API key template
  environment/
    Dockerfile                       # Test/verification Docker image
    infra/                           # Base infrastructure project
      docker-compose.yml             #   Multi-service orchestration
      Dockerfile.web                 #   Web app container
      Dockerfile.worker              #   Worker container
      nginx/                         #   Reverse proxy configs
        nginx.conf
        conf.d/default.conf
      app/                           #   Application code
        main.py
        worker.py
        requirements.txt
      scripts/                       #   Utility scripts
        entrypoint.sh
        healthcheck.sh
      .github/workflows/             #   Empty (agent creates CI pipeline)
      .env.example
  tasks/
    _template/                       # Template for creating new tasks
    fix-docker-compose/              # Task 1: Fix Docker Compose (medium)
      task.toml
      instruction.md
      solution/solve.sh
      tests/test_solution.py         #   29 tests
      tests/test.sh
    fix-nginx-config/                # Task 2: Fix nginx config (medium)
      task.toml
      instruction.md
      solution/solve.sh
      tests/test_solution.py         #   24 tests
      tests/test.sh
    add-ci-pipeline/                 # Task 3: Create CI/CD pipeline (hard)
      task.toml
      instruction.md
      solution/solve.sh
      tests/test_solution.py         #   36 tests
      tests/test.sh
```
