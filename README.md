# RVSec-02: Runtime Verification Experiments with Generic Specs

Runtime verification experiments on Android applications using 27 generic specifications from the Property Database.

## Overview

This project executes runtime verification experiments on 557 Android APKs from F-Droid, using JavaMOP specifications to detect API misuse patterns at runtime. The experiments are orchestrated using Docker Compose with parallel container execution.

## Specifications

27 specifications selected from the [Property Database](https://www.cs.cornell.edu/~legunsen/spec-eval/), categorized by severity using [RVPrio](https://github.com/ncsu-swat/rvprio):

- **ERROR (17)**: Bugs that cause exceptions or incorrect behavior
- **WARNING (8)**: Potential code issues
- **SUGGESTION (2)**: Code improvements

Specifications are located in `./specs/`.

## Requirements

- Docker and Docker Compose
- KVM support (`/dev/kvm`)
- 112GB RAM (for 7 parallel containers)
- 500GB+ disk space
- Python 3.8+ with venv

### Python Dependencies

```bash
source ./venv/bin/activate
pip install -r requirements.txt
```

## Project Structure

```
rvsec-02/
├── specs/                  # 27 JavaMOP specifications (.mop)
├── batches/                # APKs organized by batch (01-37)
│   ├── 01/                 # 15 APKs
│   ├── 02/                 # 15 APKs
│   ├── ...
│   ├── 36/                 # 16 APKs
│   └── 37/                 # 16 APKs
├── containers/             # Execution data per container
│   ├── 01/
│   │   ├── instrumented/   # Instrumented APKs
│   │   ├── results/        # Results + logs
│   │   └── specs/          # Specs copy
│   ├── 02/ ... 07/
├── results/                # Consolidated results
│   ├── batch-01/           # Batch results directory
│   │   ├── YYYYMMDDHHMMSS/ # Timestamp folder with execution results
│   │   ├── execution.log   # Container log
│   │   └── instrument_errors.json  # Instrumentation errors (if any)
│   ├── batch-01.zip        # Zipped batch results
│   └── ...
├── scripts/                # Python scripts
│   └── all_methods/        # .methods file generation
├── all_methods/            # Generated .methods files (557)
├── APKs.csv                # APK metadata
├── BATCHES.csv             # Batch execution tracking
├── docker-compose.yml
├── .env
└── docs/
    ├── 20251231_plano.md       # Execution plan
    └── 20251231_pre_plano.md   # Validation experiments
```

## Experiment Configuration

| Parameter | Value |
|-----------|-------|
| APKs | 557 |
| Batches | 37 (35×15 + 2×16 APKs) |
| Tools | 11 (ape, ares, droidbot, droidbot_bfs_greedy, droidbot_bfs_naive, droidbot_dfs_greedy, droidmate, fastbot, humanoid, monkey, qtesting) |
| Timeouts | 60, 120, 180, 300 seconds |
| Repetitions | 3 |
| Executions per APK | 132 |

## Execution Approach: Dynamic Batch Allocation

Each container processes batches independently. When a container finishes its batch, it is reconfigured for the next available batch without affecting other containers.

```
Initial:
├── Container 01 → Batch 01 (15 APKs)
├── Container 02 → Batch 02 (15 APKs)
├── Container 03 → Batch 03 (15 APKs)
├── Container 04 → Batch 04 (15 APKs)
├── Container 05 → Batch 05 (15 APKs)
├── Container 06 → Batch 06 (15 APKs)
└── Container 07 → Batch 07 (15 APKs)

Container 01 finishes first:
├── Container 01 → Batch 08 (reassigned)
├── Container 02 → Batch 02 (still running)
├── Container 03 → Batch 03 (still running)
├── Container 04 → Batch 04 (still running)
├── Container 05 → Batch 05 (still running)
├── Container 06 → Batch 06 (still running)
└── Container 07 → Batch 07 (still running)
```

### Advantages

- **No idle time**: Finished container gets next batch immediately
- **Load balancing**: Faster containers process more batches
- **Isolation**: Restart only 1 container, others continue
- **Recovery**: If stuck, only 15 APKs affected
- **Tracking**: BATCHES.csv controls allocation

## Quick Start

### 1. Start Execution

```bash
docker compose up -d
docker compose ps
```

### 2. Monitor Progress

```bash
# Using monitor script (recommended)
python monitor.py containers --prefix rv

# Or using watchdog for continuous monitoring with auto-resume
nohup python watchdog.py containers --prefix rv --interval 10 &
```

### 3. When a Container Finishes (100%)

```bash
BATCH=01
CONTAINER=01

# Stop container
docker stop rv-$CONTAINER

# Find timestamp
TIMESTAMP=$(ls containers/$CONTAINER/results/ | grep -E "^[0-9]+$" | head -1)

# Create results directory
mkdir -p results/batch-$BATCH

# Copy results
cp -r containers/$CONTAINER/results/$TIMESTAMP results/batch-$BATCH/
docker logs rv-$CONTAINER > results/batch-$BATCH/execution.log 2>&1
cp containers/$CONTAINER/instrumented/instrument_errors.json results/batch-$BATCH/ 2>/dev/null

# Create ZIP
cd results && zip -r batch-$BATCH.zip batch-$BATCH/ && cd ..

# Clean up
rm -rf containers/$CONTAINER/results/*
rm -rf containers/$CONTAINER/instrumented/*

# Update docker-compose.yml: change batch number in volumes
# Also remove resume config if present (RV_MEMORY_FILE, RV_SKIP_*)

# Update BATCHES.csv

# Restart container
docker compose up -d rv$CONTAINER
```

## Watchdog (Auto-Resume)

The watchdog monitors containers and automatically resumes stuck ones.

```bash
# Start in background
nohup python watchdog.py containers --prefix rv --interval 10 &

# Check logs
tail -f watchdog.log

# Stop
pkill -f "watchdog.py"
```

## Manual Resume After Failure

When a container crashes or hangs (use only if watchdog is not running).

### 1. Diagnose

```bash
# Check if stuck (0 = stuck)
docker logs rv-01 --since 5m 2>&1 | wc -l

# Check for zombie processes
docker exec rv-01 ps aux | grep -E "emulator.*defunct"
```

### 2. Configure Resume

```bash
CONTAINER=01
TIMESTAMP=$(ls containers/$CONTAINER/results/ | grep -E "^[0-9]+$" | head -1)

docker stop rv-$CONTAINER
```

Add to `docker-compose.yml` in the container's environment section:

```yaml
- RV_MEMORY_FILE=/opt/rvsec/rv-android/results/TIMESTAMP/execution_memory.json
- RV_SKIP_INSTRUMENT=true
- RV_SKIP_MONITORS=true
- RV_SKIP_STATIC_ANALYSIS=true
```

### 3. Recreate Container and Verify

**IMPORTANT**: Always recreate the container from scratch (stop + rm + up), not just restart. Using only `docker compose up -d` may not work correctly (emulator won't start, low CPU/RAM).

```bash
docker stop rv-$CONTAINER && docker rm rv-$CONTAINER && docker compose up -d rv$CONTAINER
docker logs rv-$CONTAINER 2>&1 | grep "Skipping" | head -5
```

### 4. Verify Resume

```bash
# Check logs for "Skipping" messages
docker logs rv-01 2>&1 | grep -i "skip"

# Verify progress continues from previous state
docker logs rv-01 2>&1 | grep "Status:" | tail -1
```

## Docker Images

- `phtcosta/rvandroid:0.0.1` - RV4Android container
- `phtcosta/humanoid:1.0` - UI automation service

## Environment Variables

| Variable | Description |
|----------|-------------|
| `RV_REPETITIONS` | Number of repetitions |
| `RV_TIMEOUTS` | Space-separated timeout values (seconds) |
| `RV_TOOLS` | Space-separated tool names |
| `RV_JCA_SPEC` | `true` for JCA specs, `false` for generic specs |
| `RV_MEMORY_FILE` | Path to execution_memory.json for resume |
| `RV_SKIP_INSTRUMENT` | Skip APK instrumentation |
| `RV_SKIP_MONITORS` | Skip monitor generation |
| `RV_SKIP_STATIC_ANALYSIS` | Skip static analysis |

## CSV Files

### APKs.csv

| Column | Description |
|--------|-------------|
| apk | APK filename |
| batch | Batch number (01-37) |
| instrumented | Whether APK was successfully instrumented |
| methods_count | Number of methods in .methods file |
| methods_empty | Whether .methods file is empty |
| manifest_package | Package from AndroidManifest.xml |
| detected_package | Package detected by heuristic |

### BATCHES.csv

| Column | Description |
|--------|-------------|
| batch | Batch number (01-37) |
| apks_total | Total APKs in batch |
| apks_instrumented | Instrumented APKs in batch |
| container | Assigned container (01-07) |
| status | pending, running, completed |
| start | Start timestamp |
| end | End timestamp |

## Output Files

### execution_memory.json

Tracks execution progress:

```json
{
  "app.apk": {
    "1": {
      "60": {
        "ape": {
          "executed": true,
          "start": 1735327492.817862,
          "finish": 1735338302.994924
        }
      }
    }
  }
}
```

### Result ZIP Structure

```
batch-01.zip
├── 20251230220756/           # Timestamp folder
│   ├── execution_memory.json
│   ├── app1.apk/
│   │   ├── rvsec.csv
│   │   ├── rvsec-cov.csv
│   │   └── logs/
│   └── ...
└── container.log             # Docker container log
```

## Scripts

### Generate .methods files

```bash
cd scripts
../venv/bin/python -m all_methods.batch_generator --all --sequential
```

## Related Work

- [Property Database](https://www.cs.cornell.edu/~legunsen/spec-eval/)
- [RVPrio](https://github.com/ncsu-swat/rvprio)

## References

This experiment extends the methodology from:

> "On the Effectiveness of Integrating Android Test-Case Generation with Runtime Verification for Detecting Cryptographic API Misuses"

## License

Research project - University of Brasilia (UnB)
