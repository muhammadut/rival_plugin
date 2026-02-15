# Event Storming

**Purpose:** Discover domain behavior by mapping the flow of events, commands, and policies across a system -- producing a shared model that drives architecture and code structure.

---

## Core Concepts

### 1. Domain Events

A Domain Event is something that happened in the business domain that stakeholders care about, written in past tense. "Order Placed," "Payment Received," "Shipment Dispatched." Events are facts -- they are immutable records of what occurred. They are the primary building block of an Event Storming session. If you cannot express a feature as a sequence of events, you do not yet understand the feature.

### 2. Commands

A Command is the action that triggers an event. It represents an intent: "Place Order," "Process Payment," "Dispatch Shipment." Commands are always issued by an actor (a user, a scheduled job, an external system). A command can succeed (producing an event) or fail (producing an error event or rejection). The command-event pair is the fundamental cause-and-effect unit.

### 3. Aggregates

An Aggregate is the domain object that receives a command and decides whether to produce the event. It enforces business rules and invariants. "The Order aggregate receives the Place Order command, validates the cart is not empty, and emits Order Placed." Aggregates are consistency boundaries -- they guarantee that the rules within them are never violated, even under concurrent access.

### 4. Policies (Reactions)

A Policy is an automated reaction to an event: "When Order Placed, then Reserve Inventory." Policies connect events to subsequent commands, creating chains. They represent business rules that do not require human intervention. Policies are where most of the interesting cross-domain logic lives. They are often the source of the most complex bugs because they are implicit in stakeholders' minds.

### 5. Read Models (Views)

A Read Model is a projection of data optimized for a specific query or screen. "The Order History View is updated when Order Placed, Payment Received, or Shipment Dispatched occurs." Read models consume events and build queryable state. They decouple what the UI needs to display from how the domain processes commands.

---

## The Event Storming Color Code

| Element | Color (Sticky Note) | Grammar | Example |
|---|---|---|---|
| Domain Event | Orange | Past tense verb phrase | "Order Placed" |
| Command | Blue | Imperative verb phrase | "Place Order" |
| Aggregate | Yellow | Noun | "Order" |
| Policy | Lilac/Purple | "When... then..." | "When Payment Failed, then Notify Customer" |
| Read Model | Green | Noun phrase (the view) | "Order Summary Dashboard" |
| Actor | Small yellow | Role noun | "Customer," "Warehouse Manager" |
| External System | Pink | System name | "Stripe API," "Shipping Provider" |
| Hot Spot / Question | Red/Pink | Question or concern | "What happens if payment times out?" |

---

## Deriving Events from a Feature Request

**Feature:** "Customers can subscribe to a monthly product box. They are charged monthly. If payment fails, retry twice, then pause the subscription."

### Step 1: Identify Events (Orange Stickies)

Walk through the feature chronologically and ask "what happens?"

```
1. Subscription Created
2. Monthly Billing Cycle Triggered
3. Payment Attempted
4. Payment Succeeded
5. Payment Failed
6. Payment Retry Scheduled
7. Payment Retry Attempted
8. Subscription Paused
9. Shipment Requested
10. Subscription Resumed
11. Subscription Cancelled
```

### Step 2: Identify Commands (Blue Stickies)

For each event, ask "what action caused this?"

```
Event                          <-- Command                    <-- Actor
Subscription Created           <-- Create Subscription        <-- Customer
Monthly Billing Cycle Triggered <-- Trigger Billing Cycle     <-- Scheduler (cron)
Payment Attempted              <-- Attempt Payment            <-- Billing Policy
Payment Succeeded              <-- (outcome of Attempt)       <-- Payment Gateway
Payment Failed                 <-- (outcome of Attempt)       <-- Payment Gateway
Payment Retry Scheduled        <-- Schedule Retry             <-- Retry Policy
Payment Retry Attempted        <-- Attempt Payment            <-- Retry Scheduler
Subscription Paused            <-- Pause Subscription         <-- Retry Exhaustion Policy
Shipment Requested             <-- Request Shipment           <-- Fulfillment Policy
Subscription Resumed           <-- Resume Subscription        <-- Customer
Subscription Cancelled         <-- Cancel Subscription        <-- Customer
```

### Step 3: Identify Aggregates (Yellow Stickies)

Group commands and events around the nouns that enforce the rules.

```
[Subscription Aggregate]
  - Create Subscription --> Subscription Created
  - Pause Subscription --> Subscription Paused
  - Resume Subscription --> Subscription Resumed
  - Cancel Subscription --> Subscription Cancelled

[Billing Aggregate]
  - Trigger Billing Cycle --> Monthly Billing Cycle Triggered
  - Attempt Payment --> Payment Succeeded | Payment Failed
  - Schedule Retry --> Payment Retry Scheduled

[Shipment Aggregate]
  - Request Shipment --> Shipment Requested
```

### Step 4: Identify Policies (Purple Stickies)

Look for automated reactions -- "when X happens, then do Y."

```
Policy: "Charge on Cycle"
  When: Monthly Billing Cycle Triggered
  Then: Attempt Payment (against Billing aggregate)

Policy: "Retry Failed Payment"
  When: Payment Failed (and retry count < 2)
  Then: Schedule Retry

Policy: "Pause After Retries Exhausted"
  When: Payment Failed (and retry count >= 2)
  Then: Pause Subscription

Policy: "Fulfill on Payment"
  When: Payment Succeeded
  Then: Request Shipment
```

### Step 5: Identify Read Models (Green Stickies)

Ask "what does the user/admin need to see?"

```
Read Model: "My Subscription" (customer-facing)
  Built from: Subscription Created, Paused, Resumed, Cancelled
  Shows: Current status, next billing date, payment history

Read Model: "Failed Payments Dashboard" (admin-facing)
  Built from: Payment Failed, Retry Scheduled, Subscription Paused
  Shows: Failing subscriptions, retry status, paused accounts

Read Model: "Shipment Queue" (warehouse-facing)
  Built from: Shipment Requested
  Shows: Orders to pack and ship today
```

---

## Command-Event-Policy Chains

The chain is the core analytical tool. Trace the full reactive flow:

```
[Customer] ---> Create Subscription
                    |
                    v
              Subscription Created
                    |
                    v
              (Scheduler waits for billing date)
                    |
                    v
[Scheduler] ---> Trigger Billing Cycle
                    |
                    v
              Monthly Billing Cycle Triggered
                    |
                    v
              <<Policy: Charge on Cycle>>
                    |
                    v
              Attempt Payment ---> [Payment Gateway]
                   / \
                  /   \
                 v     v
      Payment       Payment
      Succeeded     Failed
         |             |
         v             v
   <<Fulfill>>    <<Retry Policy>>
         |             |
         v             v
   Request         retry < 2?
   Shipment        /       \
      |          yes        no
      v           |          |
  Shipment     Schedule    Pause
  Requested    Retry       Subscription
                  |            |
                  v            v
             (wait 24h)   Subscription
                  |        Paused
                  v
             Attempt Payment (retry)
                 / \
               ...  ...  (same branch)
```

This chain reveals:
- **Bounded contexts:** Subscription, Billing, and Fulfillment are separate domains
- **Async boundaries:** Payment retry requires a scheduled delay
- **Failure modes:** What if the shipment request fails after payment succeeds?
- **Hot spots:** The retry count logic must be atomic with the payment attempt

---

## From Event Storm to Code Structure

### Aggregates Become Modules or Services

```
src/
  subscription/
    commands.py      # CreateSubscription, PauseSubscription, ...
    events.py        # SubscriptionCreated, SubscriptionPaused, ...
    aggregate.py     # Subscription class with business rules
    repository.py    # Persistence for the Subscription aggregate
  billing/
    commands.py      # TriggerBillingCycle, AttemptPayment, ...
    events.py        # PaymentSucceeded, PaymentFailed, ...
    aggregate.py     # Billing class
    repository.py
  fulfillment/
    commands.py      # RequestShipment
    events.py        # ShipmentRequested
    aggregate.py     # Shipment class
    repository.py
  policies/
    charge_on_cycle.py        # Listens to BillingCycleTriggered
    retry_failed_payment.py   # Listens to PaymentFailed
    pause_after_retries.py    # Listens to PaymentFailed (retry exhausted)
    fulfill_on_payment.py     # Listens to PaymentSucceeded
```

### Events Become Data Structures

```python
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

@dataclass(frozen=True)
class PaymentFailed:
    subscription_id: UUID
    billing_cycle_id: UUID
    amount_cents: int
    currency: str
    failure_reason: str
    retry_count: int
    occurred_at: datetime
```

### Policies Become Event Handlers

```python
class RetryFailedPaymentPolicy:
    """When PaymentFailed and retry_count < 2, schedule a retry."""

    def __init__(self, billing_service, scheduler):
        self.billing = billing_service
        self.scheduler = scheduler

    def handle(self, event: PaymentFailed):
        if event.retry_count >= 2:
            return  # Let PauseAfterRetriesPolicy handle this

        self.scheduler.schedule(
            command=AttemptPayment(
                subscription_id=event.subscription_id,
                retry_count=event.retry_count + 1,
            ),
            delay=timedelta(hours=24),
        )
```

### Read Models Become Projections

```python
class FailedPaymentsDashboardProjection:
    """Builds the admin view of failing subscriptions."""

    def __init__(self, db):
        self.db = db

    def on_payment_failed(self, event: PaymentFailed):
        self.db.upsert("failed_payments", {
            "subscription_id": event.subscription_id,
            "last_failure": event.occurred_at,
            "failure_reason": event.failure_reason,
            "retry_count": event.retry_count,
            "status": "retrying" if event.retry_count < 2 else "exhausted",
        })

    def on_subscription_paused(self, event: SubscriptionPaused):
        self.db.update("failed_payments",
            where={"subscription_id": event.subscription_id},
            set={"status": "paused"},
        )

    def on_payment_succeeded(self, event: PaymentSucceeded):
        self.db.delete("failed_payments",
            where={"subscription_id": event.subscription_id},
        )
```

---

## Output Format: What an Agent Should Produce

When applying Event Storming to a feature request, produce these artifacts:

### 1. Event Catalog

```
Domain Events:
  - SubscriptionCreated(subscription_id, customer_id, plan_id, started_at)
  - PaymentFailed(subscription_id, amount, reason, retry_count, failed_at)
  - SubscriptionPaused(subscription_id, paused_at, reason)
  ...
```

### 2. Command-Event Mapping

```
Command -> Aggregate -> Event(s)
CreateSubscription -> Subscription -> SubscriptionCreated
AttemptPayment -> Billing -> PaymentSucceeded | PaymentFailed
PauseSubscription -> Subscription -> SubscriptionPaused
```

### 3. Policy Definitions

```
Policy: RetryFailedPayment
  Trigger: PaymentFailed (where retry_count < 2)
  Action: Schedule AttemptPayment with 24h delay

Policy: PauseAfterRetries
  Trigger: PaymentFailed (where retry_count >= 2)
  Action: Issue PauseSubscription command
```

### 4. Chain Diagram

ASCII or Mermaid diagram showing the full reactive flow from initial command through all policies to terminal events.

### 5. Bounded Context Map

Which aggregates belong together, where the context boundaries are, and how contexts communicate (events across boundaries, commands within boundaries).

### 6. Hot Spots List

Open questions and risk areas discovered during the storming.

```
Hot Spots:
- What if payment gateway is unreachable? (timeout vs failure distinction)
- Should paused subscriptions auto-resume on successful manual payment?
- How long do we retain failed payment records for compliance?
```

---

## Quick Reference Table

| Concept | Key Question | Output |
|---|---|---|
| Domain Event | "What happened?" | Past-tense fact: "Order Placed" |
| Command | "What triggered it?" | Imperative intent: "Place Order" |
| Aggregate | "Who decides?" | Noun + business rules: "Order" |
| Policy | "What happens automatically next?" | "When X, then Y" |
| Read Model | "What does the user need to see?" | Query-optimized view |
| Actor | "Who initiated the command?" | Human role or external system |
| Hot Spot | "What don't we know?" | Risk, question, or ambiguity |
| Bounded Context | "Where do the language and rules change?" | Service or module boundary |

---

## Common Mistakes

| Mistake | Why It Hurts | Fix |
|---|---|---|
| Writing events in present tense ("Order Places") | Confuses events with commands | Events are facts about the past: "Order Placed" |
| Skipping the policy discovery step | Misses cross-domain automation and complexity | Explicitly ask "what happens automatically?" after every event |
| Making aggregates too large | Everything is coupled, no clear boundaries | If an aggregate has > 7-8 events, look for a split |
| Confusing events with CRUD operations | "Order Updated" says nothing useful | Name events after business meaning: "Order Quantity Changed," "Shipping Address Corrected" |
| Ignoring failure events | Happy path bias hides real complexity | For every command, ask "what if this fails?" |
| Jumping to implementation too early | Missing events and policies that would reshape the design | Complete the full storm before writing code |

---

## Running an Event Storming Session (Quick Guide)

| Phase | Duration | Activity |
|---|---|---|
| **Chaotic Exploration** | 20-30 min | Everyone writes domain events on orange stickies simultaneously. No discussion, no ordering. |
| **Timeline Ordering** | 15-20 min | Arrange events left-to-right on a timeline. Identify gaps and duplicates. |
| **Commands and Actors** | 15-20 min | Add blue (command) and yellow actor stickies. Who triggers what? |
| **Aggregates** | 10-15 min | Cluster commands and events around yellow aggregate stickies. |
| **Policies** | 15-20 min | Add purple stickies for automated reactions. Trace chains. |
| **Read Models** | 10 min | Add green stickies for the views that users or admins need. |
| **Hot Spots** | 10 min | Mark unknowns and risks with red stickies. Do not solve them now. |
| **Bounded Contexts** | 10-15 min | Draw boundaries around aggregates that belong together. Name the contexts. |
