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
├── tools/                  # JAR utilities
│   ├── methods-extractor.jar
│   └── mop-extractor.jar
├── scripts/                # Python scripts
│   └── all_methods/        # .methods file generation
├── all_methods/            # Generated .methods files (557)
├── batch-XX/               # Batch execution directories
├── RESULTS/                # Consolidated results
├── docs/                   # Documentation
│   ├── 20251231_plano.md       # Execution plan
│   └── 20251231_pre_plano.md   # Validation experiments
└── venv/                   # Python virtual environment
```

## Experiment Configuration

| Parameter | Value |
|-----------|-------|
| APKs | 557 |
| Tools | 11 (ape, ares, droidbot, droidbot_bfs_greedy, droidbot_bfs_naive, droidbot_dfs_greedy, droidmate, fastbot, humanoid, monkey, qtesting) |
| Timeouts | 60, 120, 180, 300 seconds |
| Repetitions | 3 |
| Executions per APK | 132 |

## Batch Execution

APKs are divided into 38 batches of 15 APKs each for easier management and failure recovery.

### Setup a Batch

```bash
BATCH=01

mkdir -p batch-$BATCH
cd batch-$BATCH

for i in 01 02 03 04 05; do
    mkdir -p $i/{apks,instrumented,results,specs}
    cp -r ../specs/* $i/specs/
done
```

### Run a Batch

```bash
cd batch-XX
docker compose up -d
```

### Monitor Progress

```bash
docker logs rv-batchXX-01 2>&1 | grep "Status:" | tail -1
```

### Resume After Failure

Add to `docker-compose.yml`:

```yaml
environment:
  - RV_MEMORY_FILE=/opt/rvsec/rv-android/results/TIMESTAMP/execution_memory.json
  - RV_SKIP_INSTRUMENT=true
  - RV_SKIP_MONITORS=true
  - RV_SKIP_STATIC_ANALYSIS=true
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

### .methods files

CSV files with method reachability analysis:

| Column | Description |
|--------|-------------|
| class | Class name |
| method | Method name |
| parameters | Method parameters |
| signature | Full signature |
| is_activity | Whether class is an Activity |
| reachable | Reachable from entrypoints |
| reaches_mop | Reaches monitored methods |
| directly_reaches_mop | Directly calls monitored methods |
| androguard | Found in Androguard call graph |

## Scripts

### Generate .methods files

```bash
cd scripts
../venv/bin/python -m all_methods.batch_generator --all --sequential
```

### Monitor containers

```bash
python monitor.py batch-XX --prefix rv-batchXX --watch
```

## Related Work

- [Property Database](https://www.cs.cornell.edu/~legunsen/spec-eval/)
- [RVPrio](https://github.com/ncsu-swat/rvprio)

## References

This experiment extends the methodology from:

> "On the Effectiveness of Integrating Android Test-Case Generation with Runtime Verification for Detecting Cryptographic API Misuses"

## License

Research project - University of Brasilia (UnB)
