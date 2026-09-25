# Parallel Collection

## Why processes are required

The official MetaTrader 5 Python module owns a process-global terminal connection. Initializing different terminals safely therefore requires separate worker processes rather than shared adapter state.

## Execution model

`ParallelCollectionCoordinator` creates one `ProcessPoolExecutor` job per configured broker profile. Every job receives a complete typed MT5 profile, symbol mapping, collection request, and raw-data directory. Each worker constructs its own `MT5Adapter`, verifies `DEMO`, performs read-only collection, writes independent Parquet files and manifests, shuts down, and returns its batch.

Enable parallel collection with:

```bash
python -m market_relationship_discovery collect --parallel --max-workers 2 --broker-profile BROKER_A --broker-profile BROKER_B --symbol EURUSD --data-type tick --limit 500
```

`DATA__COLLECTION_MAX_WORKERS` provides the default and is bounded between one and eight. Duplicate broker profiles are rejected.

## Failure and ordering

A failed worker raises a profile-specific `ParallelCollectionError`; other results must not be mistaken for a complete run. Results are sorted back into input profile order. Dataset IDs include time and random entropy to prevent filename collisions across workers.

## Validation boundary

The implementation was integration-tested on Windows with one configured demo terminal and one spawned worker. Simultaneous two-terminal collection was not executed because a second demo terminal is not configured. The architecture supports it, but real multi-terminal concurrency requires an environment-level validation with at least two authorized demo terminals.
