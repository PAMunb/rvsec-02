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
- 80GB RAM (for 5 parallel containers)
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
│   └── ...
├── RESULTS/                # Consolidated results (ZIPs)
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
└── Container 05 → Batch 05 (15 APKs)

Container 01 finishes first:
├── Container 01 → Batch 06 (reassigned)
├── Container 02 → Batch 02 (still running)
├── Container 03 → Batch 03 (still running)
├── Container 04 → Batch 04 (still running)
└── Container 05 → Batch 05 (still running)
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
# All containers
for i in 01 02 03 04 05; do
    echo "=== rv-$i ==="
    docker logs rv-$i 2>&1 | grep "Status:" | tail -1
done
```

### 3. When a Container Finishes (100%)

```bash
BATCH=01
CONTAINER=01

# Stop container
docker stop rv-$CONTAINER

# Save container log
docker logs rv-$CONTAINER > containers/$CONTAINER/results/container.log 2>&1

# Find timestamp
TIMESTAMP=$(ls containers/$CONTAINER/results/ | grep -E "^[0-9]+$" | head -1)

# Create ZIP with results + log
cd containers/$CONTAINER/results
zip -r ../../../RESULTS/batch-$BATCH.zip $TIMESTAMP/ container.log
cd ../../..

# Clean up
rm -rf containers/$CONTAINER/results/*
rm -rf containers/$CONTAINER/instrumented/*

# Update docker-compose.yml to point to next batch
# Edit: ./batches/01 → ./batches/06

# Restart container
docker compose up -d rv$CONTAINER
```

## Resume After Failure

When a container crashes or hangs (e.g., zombie emulator processes), you can resume execution from where it stopped.

### 1. Diagnose

```bash
# Check if container is stuck (no recent logs)
docker logs rv-01 --since 5m 2>&1 | wc -l

# Check for zombie processes
docker exec rv-01 ps aux | grep -E "emulator.*defunct"

# Check resource usage
docker stats --no-stream rv-01
```

### 2. Stop the Container

```bash
docker stop rv-01
```

### 3. Find Timestamp

```bash
ls containers/01/results/
# Output: 20251230220756
```

### 4. Configure Resume

Add environment variables to `docker-compose.yml`:

```yaml
environment:
  - RV_MEMORY_FILE=/opt/rvsec/rv-android/results/TIMESTAMP/execution_memory.json
  - RV_SKIP_INSTRUMENT=true
  - RV_SKIP_MONITORS=true
  - RV_SKIP_STATIC_ANALYSIS=true
```

Replace `TIMESTAMP` with the actual value (e.g., `20251230220756`).

### 5. Restart Container

```bash
docker compose up -d rv01
```

### 6. Verify Resume

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
| container | Assigned container (01-05) |
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
