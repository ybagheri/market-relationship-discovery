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

A failed worker does not raise from inside the executor context. The coordinator collects the failure, lets the pool drain so every other job reaches a terminal state, and only then raises. Raising from inside the `with` block unwound into the executor's own shutdown, which stopped the remaining workers while they were still writing datasets: a failed run both reported an error and left half-written output on disk. The error names **every** failing profile with the count that completed, so a two-broker run that failed on both reports both. Results are sorted back into input profile order. Dataset IDs include time and random entropy to prevent filename collisions across workers.

A `DemoSafetyError` is re-raised as itself, not wrapped in `ParallelCollectionError`. A safety refusal means the terminal connected and the account was not provably demo, which is the platform working as intended rather than a transient connection error. The sequential collector and `doctor` both report it distinctly, and the parallel path keeps that distinction so a caller retrying connection failures does not retry a refusal that can never succeed.

## Retry policy

Only a connection failure is retried, and only up to `DATA__COLLECTION_ATTEMPTS`.

A `DataQualityError` is **not** retried. A failed quality check is a verdict about the data rather than a transient condition, so repeating the same request repeats the same verdict. It used to be retried, and each attempt re-ran the whole request, minting a fresh `dataset_id` — three partially-written datasets on disk in place of one reported error.

Retries are per **symbol** rather than per request. A whole-request retry re-runs the symbols that already succeeded, and every run mints a new ID, so a failure on the last symbol left the earlier datasets orphaned with no manifest referencing them. Each symbol is now written at most once per attempt.

## Validation boundary

The implementation was integration-tested on Windows with two configured demo terminals and two spawned workers. EURUSD tick collection completed for both profiles. Multi-terminal results still require substantially denser synchronized samples before research conclusions.
