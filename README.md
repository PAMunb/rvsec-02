# RV-Android Experiment 02

This experiment evaluates the performance of Android testing tools using the RV-Android platform with JavaMOP runtime verification.
## Experimental Configuration

- **Architecture**: Docker Compose with 5 parallel execution groups
- **Applications**: 10 Android APKs distributed across groups
- **Testing Tools**: 7 tools evaluated (ape, ares, droidbot_bfs_greedy, droidbot_dfs_greedy, fastbot, humanoid, qtesting)
- **JavaMOP Specifications**: Two separate executions
  - JCA (cryptography-specific properties)
  - Generic properties (e.g., Iterator usage patterns)
- **Resources**: 8 CPUs, 16GB RAM per container
- **Timeout**: 3 hours per execution

## Directory Structure

Each group (01-05) contains:
- `apks/`: Original Android applications
- `instrumented/`: Instrumented APKs with JavaMOP monitors
- `results/`: Experimental results and coverage data

## Execution

Start the experiment:
```bash
docker-compose up
```

Monitor execution progress:
```bash
python status.py
```

View specific execution details:
```bash
python status.py --exec 01
```


## Applications Under Test

- Group 01: com.blogspot.e_kanivets.moneytracker_38.apk, com.gianlu.dnshero_40.apk
- Group 02: com.pindroid_69.apk, com.github.axet.hourlyreminder_476.apk  
- Group 03: com.thibaudperso.sonycamera_24.apk, com.rafapps.simplenotes_7.apk
- Group 04: li.klass.fhem_141.apk, org.pulpdust.lesserpad_42.apk
- Group 05: org.secuso.privacyfriendlydicer_8.apk, org.secuso.privacyfriendlyludo_5.apk