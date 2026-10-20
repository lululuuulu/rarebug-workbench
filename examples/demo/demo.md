# Experiment: race

Round: 1/3
Proposal digest: `6cc17995603ad6176150e539b0f941e89d73dd3f1e04d35f40951f82963ded4c`

## Static environment

- os: Synthetic Linux
- runtime: Python 3.11 simulator
- service_version: demo-1.0

## Timeline (UTC)

| Time | Source | Type |
|---|---|---|
| 2026-01-15T10:00:00+00:00 | SIM-ENV-001 | environment |
| 2026-01-15T10:03:00+00:00 | SIM-LOG-001 | log |
| 2026-01-15T10:04:00+00:00 | SIM-CHAT-001 | chat |
| 2026-01-15T10:05:00+00:00 | SIM-JIRA-001 | jira |

## Facts

| Claim | Provenance | Evidence |
|---|---|---|
| Concurrent requests were recorded | observed | E1 |
| Scheduler delay was recorded | observed | E2 |
| Recorded environment: {"os": "Synthetic Linux", "runtime": "Python 3.11 simulator", "service_version": "demo-1.0"} | configuration | E3 |

## Hypotheses (unverified)

- H-race: Request overlap and delay may expose a race; evidence E1, E2

## Exact evidence spans

| ID | Source | Span | Literal quote |
|---|---|---|---|
| E1 | SIM-LOG-001 | 0:17 | active_requests=9 |
| E2 | SIM-LOG-001 | 18:39 | scheduler_delay_ms=35 |
| E3 | SIM-ENV-001 | 0:92 | {"os": "Synthetic Linux", "runtime": "Python 3.11 simulator", "service_version": "demo-1.0"} |

## Strategy review

- S-race-1: score=2.0, cost/trial=1; controls={'cache_age_s': 0, 'clock_skew_s': 0, 'concurrency': 4, 'jitter_ms': 10}; 2 evidence references; 0 prior negative runs; bounded escalation preserves other controls

Selected: S-race-1
Expected observation: The simulator returns the case's matching failure signature
Stop: Stop after the trial budget or one matching failure signature
Budget: 20 trials; seed=7

## Decision and feedback

approve by scripted-demo-not-a-human: Explicit CLI demo opt-in

{'attempts': 20, 'hits': 0, 'outcome': 'not_reproduced', 'seed': 7, 'signature': None, 'simulator_digest': 'fc7e55c8afbd452b848444bc32faefaa149b664409b4d7d9bfb7507a4912a533'}
Cost units: 20

A matching synthetic signature supports this experiment, not a confirmed root cause.

## Reproducibility

Code: `7cae7e36196e099c5eae6901268397e2d87dae0bd945a883d245fdb50f36b847`
Simulator: `fc7e55c8afbd452b848444bc32faefaa149b664409b4d7d9bfb7507a4912a533`
Python: `3.14.0`

Event hashes detect accidental changes; they are not authenticated signatures.

---

# Experiment: race

Round: 2/3
Proposal digest: `3df181f12535ad5126c950537c93f653430aa9fe03c1bdba7a7fc22cf416075f`

## Static environment

- os: Synthetic Linux
- runtime: Python 3.11 simulator
- service_version: demo-1.0

## Timeline (UTC)

| Time | Source | Type |
|---|---|---|
| 2026-01-15T10:00:00+00:00 | SIM-ENV-001 | environment |
| 2026-01-15T10:03:00+00:00 | SIM-LOG-001 | log |
| 2026-01-15T10:04:00+00:00 | SIM-CHAT-001 | chat |
| 2026-01-15T10:05:00+00:00 | SIM-JIRA-001 | jira |
| 2026-01-15T10:05:01+00:00 | execution-feedback-1 | feedback |

## Facts

| Claim | Provenance | Evidence |
|---|---|---|
| Concurrent requests were recorded | observed | E1 |
| Scheduler delay was recorded | observed | E2 |
| Recorded environment: {"os": "Synthetic Linux", "runtime": "Python 3.11 simulator", "service_version": "demo-1.0"} | configuration | E3 |
| An execution outcome was recorded | observed | E4 |

## Hypotheses (unverified)

- H-race: Request overlap and delay may expose a race; evidence E1, E2

## Exact evidence spans

| ID | Source | Span | Literal quote |
|---|---|---|---|
| E1 | SIM-LOG-001 | 0:17 | active_requests=9 |
| E2 | SIM-LOG-001 | 18:39 | scheduler_delay_ms=35 |
| E3 | SIM-ENV-001 | 0:92 | {"os": "Synthetic Linux", "runtime": "Python 3.11 simulator", "service_version": "demo-1.0"} |
| E4 | execution-feedback-1 | 0:22 | outcome=not_reproduced |

## Strategy review

- S-race-2: score=0.5167, cost/trial=3; controls={'cache_age_s': 0, 'clock_skew_s': 0, 'concurrency': 12, 'jitter_ms': 40}; 2 evidence references; 1 prior negative runs; bounded escalation preserves other controls

Selected: S-race-2
Expected observation: The simulator returns the case's matching failure signature
Stop: Stop after the trial budget or one matching failure signature
Budget: 20 trials; seed=8

## Decision and feedback

approve by scripted-demo-not-a-human: Explicit CLI demo opt-in

{'attempts': 3, 'hits': 1, 'outcome': 'reproduced', 'seed': 8, 'signature': 'SIMULATED_RACE_FAILURE', 'simulator_digest': 'fc7e55c8afbd452b848444bc32faefaa149b664409b4d7d9bfb7507a4912a533'}
Cost units: 9

A matching synthetic signature supports this experiment, not a confirmed root cause.

## Reproducibility

Code: `7cae7e36196e099c5eae6901268397e2d87dae0bd945a883d245fdb50f36b847`
Simulator: `fc7e55c8afbd452b848444bc32faefaa149b664409b4d7d9bfb7507a4912a533`
Python: `3.14.0`

Event hashes detect accidental changes; they are not authenticated signatures.
