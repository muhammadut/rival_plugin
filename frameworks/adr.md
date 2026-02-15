# Architecture Decision Records (ADR)

**Purpose:** Capture significant architecture decisions with their context and consequences so future engineers understand *why* the system is built the way it is.

---

## Core Concepts

### 1. Decisions Are First-Class Artifacts

Architecture decisions deserve the same version control treatment as code. An ADR is a short text file (typically Markdown) stored in the repository alongside the code it governs. When someone asks "why do we use Kafka instead of RabbitMQ?" six months from now, the ADR answers that question without needing to find the person who made the call. If the decision is not written down, it is not a decision -- it is folklore.

### 2. Context Over Conclusion

The most valuable part of an ADR is the Context section, not the Decision. Future engineers will face different constraints and need to evaluate whether the original reasoning still holds. A decision without context is an edict. A decision with context is a tool for future judgment. Always capture what forces, constraints, and trade-offs shaped the choice.

### 3. Immutability and Supersession

ADRs are append-only. You never edit the Decision or Context of an accepted ADR. If circumstances change, write a new ADR that supersedes the old one and update the old ADR's status to "Superseded by ADR-NNN." This preserves the historical record. The chain of supersessions tells the story of how the architecture evolved and why.

### 4. Lightweight by Design

An ADR is not a design document, RFC, or whitepaper. It captures *one* decision in 1-2 pages. If you need more than two pages, you are either bundling multiple decisions or writing a design doc. Keep them short so they actually get written and read. A team that writes no ADRs because the template is too heavy has the wrong template.

### 5. Status Lifecycle

An ADR moves through statuses: **Proposed** (under discussion), **Accepted** (approved and in effect), **Deprecated** (no longer relevant but was not wrong), **Superseded** (replaced by a newer decision). Some teams add **Rejected** for decisions that were considered but not adopted -- these are valuable because they prevent re-litigating settled debates.

---

## When Does a Decision Warrant an ADR?

Not every choice needs an ADR. Use this filter:

| Write an ADR When... | Skip an ADR When... |
|---|---|
| The decision is hard to reverse (choosing a database, message broker, auth provider) | The decision is trivially reversible (variable naming, CSS class choice) |
| Multiple reasonable alternatives exist and you chose one | There is only one obvious option |
| The decision affects multiple teams or services | The decision is local to one function or module |
| Someone will ask "why?" in 6 months | The reason is self-evident from the code |
| The team debated the choice for more than 15 minutes | Everyone immediately agreed |
| You are deviating from a convention or standard | You are following the established convention |

### Concrete Examples of ADR-Worthy Decisions

- Use PostgreSQL over MongoDB for the order service
- Adopt event sourcing for the payment domain
- Choose REST over gRPC for public-facing APIs
- Use a monorepo instead of per-service repos
- Implement CQRS for the reporting subsystem
- Migrate authentication from sessions to JWTs
- Adopt a specific error-handling strategy across services

---

## The ADR Template

```markdown
# ADR-{NNN}: {Short Decision Title}

## Status

{Proposed | Accepted | Deprecated | Superseded by ADR-NNN}

## Date

{YYYY-MM-DD}

## Context

{What is the issue that we are seeing that motivates this decision?
What forces are at play -- technical, business, team, timeline?
What constraints do we have? What have we tried or considered?}

## Decision

{What is the change that we are proposing and/or doing?
State it as an active, declarative sentence: "We will use X for Y."}

## Consequences

### Positive
- {Benefit 1}
- {Benefit 2}

### Negative
- {Trade-off 1}
- {Trade-off 2}

### Neutral
- {Side effect that is neither clearly good nor bad}

## Alternatives Considered

### {Alternative A}
- Pros: ...
- Cons: ...
- Why rejected: ...

### {Alternative B}
- Pros: ...
- Cons: ...
- Why rejected: ...
```

---

## Practical Application: Feature Request Walkthrough

**Feature:** "The platform needs real-time notifications when an order status changes."

### Step 1: Identify the Decision

The feature requires a pub/sub mechanism. The architectural decision is: *Which messaging system do we adopt for real-time event delivery?*

### Step 2: Research Alternatives

| Option | Strengths | Weaknesses |
|---|---|---|
| Kafka | High throughput, durable, replay | Operational complexity, overkill for low volume |
| RabbitMQ | Mature, flexible routing, simpler ops | No built-in replay, lower throughput ceiling |
| Redis Pub/Sub | Already in stack, very fast | No persistence, messages lost if subscriber is down |
| SNS/SQS (AWS) | Managed, scales automatically | Vendor lock-in, latency variance |

### Step 3: Write the ADR

```markdown
# ADR-012: Use RabbitMQ for Order Event Delivery

## Status

Accepted

## Date

2026-02-14

## Context

The order management system needs to notify downstream services
(email, analytics, warehouse) when order status changes. Current
implementation uses synchronous HTTP calls, which causes cascading
failures when any downstream service is unavailable.

We process approximately 5,000 orders per day with a peak of 200
per minute. The team has operational experience with RabbitMQ from
the legacy notification system. We run on AWS but want to avoid
deep vendor coupling for messaging since a multi-cloud strategy is
under evaluation.

The notification consumer must be able to retry failed deliveries.
Message ordering within a single order is important; global ordering
is not.

## Decision

We will use RabbitMQ as the message broker for order status change
events. Each downstream consumer will have its own queue bound to
an order-events topic exchange. Messages will be persisted to disk
and acknowledged explicitly by consumers.

## Consequences

### Positive
- Decouples order service from downstream consumers
- Failed consumers do not block order processing
- Per-consumer queues allow independent scaling and retry policies
- Team already knows RabbitMQ -- no ramp-up time

### Negative
- Another piece of infrastructure to operate and monitor
- No built-in event replay; if a consumer needs historical events,
  we must build a separate mechanism
- Must manage queue depth alerts to catch stuck consumers early

### Neutral
- We will need a dead-letter queue strategy for poison messages
- Consumer idempotency is now a requirement since at-least-once
  delivery means duplicates are possible

## Alternatives Considered

### Apache Kafka
- Pros: Built-in replay via log retention, higher throughput ceiling
- Cons: Significant operational overhead (ZooKeeper/KRaft, partition
  management), no one on the team has production Kafka experience
- Why rejected: Our volume does not justify the complexity. Replay
  is a nice-to-have, not a requirement today.

### Redis Pub/Sub
- Pros: Already in our stack, sub-millisecond latency
- Cons: Fire-and-forget model -- messages are lost if a subscriber
  is offline. No persistence, no retry, no dead-letter support.
- Why rejected: We need delivery guarantees for order events.

### AWS SNS + SQS
- Pros: Fully managed, auto-scales, built-in DLQ
- Cons: Adds AWS coupling to a domain service, SNS fan-out adds
  latency variance, harder to run locally for development
- Why rejected: Multi-cloud evaluation makes vendor-neutral
  choice preferable at this time.
```

### Step 4: File It

Save as `docs/adr/012-use-rabbitmq-for-order-events.md` and link it from the ADR index.

---

## ADR Index File

Maintain an index at `docs/adr/README.md` so engineers can scan all decisions at a glance.

```markdown
# Architecture Decision Records

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| 001 | [Use PostgreSQL for persistence](001-use-postgresql.md) | Accepted | 2025-03-10 |
| 002 | [Adopt hexagonal architecture](002-hexagonal-architecture.md) | Accepted | 2025-03-15 |
| ... | ... | ... | ... |
| 011 | [Use Redis for session caching](011-redis-sessions.md) | Superseded by 015 | 2025-11-02 |
| 012 | [Use RabbitMQ for order events](012-rabbitmq-order-events.md) | Accepted | 2026-02-14 |
```

---

## Output Format: What an Agent Should Produce

When an agent determines that an architectural decision has been made (implicitly or explicitly), it should produce:

### 1. Decision Identification

A one-sentence statement of the decision.

```
Decision: Use RabbitMQ as the message broker for asynchronous
order status event delivery.
```

### 2. Complete ADR File

A Markdown file following the template above, saved to the project's ADR directory with the next sequential number.

### 3. Index Update

An updated line in the ADR index file.

### 4. Code Comments (where applicable)

If the decision affects specific code, add a pointer.

```python
# Architecture: See ADR-012 for why we use RabbitMQ here
# instead of synchronous HTTP calls to downstream services.
class OrderEventPublisher:
    def __init__(self, channel: BlockingChannel):
        self.channel = channel
```

---

## Quick Reference Table

| Concept | Guideline |
|---|---|
| File location | `docs/adr/NNN-short-title-with-dashes.md` |
| Numbering | Sequential integers, zero-padded to 3 digits: 001, 002, ... |
| Length | 1-2 pages maximum. Shorter is better. |
| Tone | Neutral, factual, third person. "We will..." not "I think..." |
| Context length | As long as needed to explain *why*. This is the most important section. |
| Decision length | 1-3 sentences. Be declarative. |
| Alternatives | Minimum 2 alternatives with pros, cons, and rejection reason |
| Reviewers | The team. ADRs are not unilateral -- they should be reviewed like code. |
| When to write | Before or immediately after the decision. Not three months later. |
| Supersession | New ADR references old. Old ADR status updated. Never delete old ADRs. |

---

## Common Mistakes

| Mistake | Why It Hurts | Fix |
|---|---|---|
| Writing ADRs after the fact from memory | Context is lost, rationalization replaces reasoning | Write during or immediately after the decision meeting |
| Bundling multiple decisions in one ADR | Hard to reference, supersede, or find later | One decision per ADR, even if they were discussed together |
| Skipping the Alternatives section | Future readers cannot tell if other options were considered | Always document at least two alternatives and why they lost |
| Using ADRs for every small choice | Noise drowns signal, team stops reading them | Apply the "will someone ask why?" filter |
| Never updating status | Readers follow outdated decisions | Review ADR statuses during quarterly architecture reviews |
| Writing a novel | No one reads it | If it is over 2 pages, split it or make it a design doc with an ADR summarizing the decision |

---

## Lifecycle Workflow

```
  +-----------+
  | Proposed  |  Author writes the ADR, opens a PR
  +-----+-----+
        |
        v
  +-----------+
  | Accepted  |  Team reviews and approves the PR
  +-----+-----+
        |
        |  (time passes, circumstances change)
        |
        v
  +-----+-----+       +-----+-----+
  | Deprecated |  OR   | Superseded |  A new ADR replaces this one
  +-----------+       | by ADR-NNN |
                      +-----------+
```

---

## Naming Conventions

Use lowercase, hyphen-separated names that start with the ADR number:

```
docs/adr/
  001-use-postgresql-for-persistence.md
  002-adopt-hexagonal-architecture.md
  003-use-jwt-for-api-authentication.md
  004-rejected-graphql-for-public-api.md     <-- rejected decisions are valuable too
  005-migrate-from-rest-to-grpc-internal.md
  README.md                                  <-- the index
```

---

## Integration with Development Workflow

1. **New ADR:** Author creates a branch, writes the ADR, opens a pull request.
2. **Review:** Team members review the ADR like code. Comments focus on missing context, unconsidered alternatives, or unstated consequences.
3. **Approval:** When consensus is reached, merge the PR. Status becomes Accepted.
4. **Implementation:** Reference the ADR number in commit messages and code comments.
5. **Revisit:** During architecture reviews (quarterly or per-milestone), scan the ADR index for decisions that may need re-evaluation.
