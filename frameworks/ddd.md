# Domain-Driven Design -- Modeling Framework

**Purpose:** Structure code around business concepts so that the software model mirrors how domain experts think, making the system easier to reason about, change, and extend.

---

## Core Concepts

### 1. Strategic Design: Bounded Contexts and Context Maps

A Bounded Context is a boundary within which a particular domain model is consistent and complete. The word "Order" means something different in the Sales context (a customer's purchase intent) than in the Shipping context (a package to deliver) or the Billing context (an invoice to collect). Trying to create one universal "Order" model that serves all three purposes leads to a bloated, contradictory mess.

A Context Map documents how bounded contexts relate to each other. The key relationship patterns are: Shared Kernel (two contexts share a subset of the model), Customer-Supplier (one context feeds data to another), Anti-Corruption Layer (a translation layer protects one context from another's model), and Separate Ways (contexts have no integration).

### 2. Tactical Design: The Building Blocks

Inside a bounded context, DDD provides specific patterns for structuring code:

- **Entity:** An object with a unique identity that persists across time. A `Customer` with ID `cust-123` is the same customer even if they change their name and address. Identity matters, not attribute equality.
- **Value Object:** An object defined entirely by its attributes, with no identity. A `Money(100, "USD")` is equal to any other `Money(100, "USD")`. Value objects are immutable. Use them aggressively -- they eliminate whole categories of bugs.
- **Aggregate:** A cluster of entities and value objects treated as a single unit for data changes. The aggregate root is the entry point. You never reach inside an aggregate to modify a child entity directly. Example: `Order` (root) contains `OrderLineItem` (child entity) and `ShippingAddress` (value object). You modify line items through the `Order`, not independently.
- **Domain Event:** Something that happened in the domain that other parts of the system care about. `OrderPlaced`, `PaymentReceived`, `InventoryReserved`. Named in past tense. Events are facts -- they are immutable records of what occurred.
- **Repository:** An abstraction that provides collection-like access to aggregates. You load and save whole aggregates, never individual child entities. `OrderRepository.findById(orderId)` returns a complete `Order` aggregate.

### 3. Aggregates Are Consistency Boundaries

This is the single most important tactical concept. An aggregate defines a transactional boundary: everything inside one aggregate is kept consistent within a single transaction. Cross-aggregate consistency is eventual, handled through domain events.

If two things must be atomically consistent, they belong in the same aggregate. If they can tolerate brief inconsistency, they belong in separate aggregates. Getting aggregate boundaries wrong is the most common DDD mistake and the most expensive to fix later.

### 4. Ubiquitous Language Is Not Optional

The terms used in code must match the terms used by domain experts. If the business says "policy" and the code says "rule," you have a translation tax on every conversation, every requirement, and every bug report. Rename the code. The codebase is the cheaper thing to change.

### 5. Domain Logic Lives in the Domain Layer, Not in Services or Controllers

Business rules belong on entities, value objects, and domain services -- not in application services, controllers, or "manager" classes. If your `OrderService` has methods like `calculateTotal()` and `validateShippingAddress()`, that logic should live on the `Order` aggregate and the `ShippingAddress` value object respectively. Application services orchestrate (load aggregate, call domain method, save aggregate, publish event) but contain no business logic themselves.

---

## Practical Application: Identifying Aggregate Boundaries

This is the hardest and most valuable skill in DDD. Here is a repeatable process.

### Step 1: List the Nouns from the Feature Request

**Feature:** "Customers can create wishlists, add products to them, share wishlists with other customers, and purchase all items in a wishlist at once."

Nouns: Customer, Wishlist, Product, WishlistItem, SharedAccess

### Step 2: Identify Invariants (Business Rules That Must Always Be True)

- A wishlist must have an owner (a customer).
- A wishlist item must reference a valid product.
- A wishlist cannot contain duplicate products.
- A shared wishlist grants read-only access unless the owner grants edit access.
- Purchasing a wishlist creates an order for each available item.

### Step 3: Group by Transactional Consistency Needs

Ask: "Which of these must be changed together atomically?"

- Wishlist + WishlistItems: Yes. Adding a duplicate must be checked atomically. These are one aggregate with `Wishlist` as the root.
- Wishlist + SharedAccess: SharedAccess references the Wishlist but doesn't need to be transactionally consistent with item changes. Separate aggregate (or a simple entity under Wishlist if the list is small).
- Customer + Wishlist: No. A customer can exist without wishlists. Separate aggregates. Wishlist holds a `customerId` reference.
- Product + WishlistItem: No. A product exists independently. WishlistItem holds a `productId` reference.
- Wishlist + Order: No. Purchasing creates a new Order aggregate. Connected by a domain event `WishlistPurchaseRequested`.

### Step 4: Define Aggregate Roots and Boundaries

```
Aggregate: Wishlist
  Root: Wishlist (id, ownerId, name, createdAt)
  Child Entities: WishlistItem (id, productId, addedAt, note)
  Value Objects: WishlistPermission (type: READ_ONLY | READ_WRITE)
  Child Entities: SharedAccess (id, sharedWithCustomerId, permission)

  Invariants enforced:
    - No duplicate productIds in items
    - Only owner can grant/revoke sharing
    - Maximum 50 items per wishlist

Aggregate: Customer (existing, not modified)
Aggregate: Product (existing, not modified)
Aggregate: Order (existing, triggered by domain event)
```

### Step 5: Define Domain Events

```
WishlistCreated { wishlistId, ownerId, name }
ItemAddedToWishlist { wishlistId, productId, itemId }
ItemRemovedFromWishlist { wishlistId, itemId }
WishlistShared { wishlistId, sharedWithCustomerId, permission }
WishlistPurchaseRequested { wishlistId, itemProductIds[], requestedBy }
```

### Step 6: Define the Repository

```
WishlistRepository
  findById(wishlistId): Wishlist          -- loads full aggregate
  findByOwnerId(customerId): List<Wishlist>  -- for listing (may be thin projections)
  save(wishlist): void                     -- persists full aggregate
```

---

## Bounded Context Identification

### When to Split a Bounded Context

Watch for these signals that you need separate bounded contexts:

| Signal | Example | Action |
|--------|---------|--------|
| Same word, different meaning | "Account" in auth (credentials) vs. billing (payment method) vs. CRM (company profile) | Three bounded contexts, each with its own `Account` model |
| Different rates of change | Product catalog changes weekly; order processing logic changes quarterly | Separate contexts so catalog changes don't risk order processing |
| Different teams own the code | Team A owns search, Team B owns checkout | Align bounded contexts with team boundaries |
| Different data consistency needs | Inventory needs strong consistency; product reviews are eventually consistent | Separate contexts with appropriate infrastructure |
| A model is getting bloated | `User` has 40 fields serving auth, profile, preferences, billing, support | Split into `AuthIdentity`, `UserProfile`, `BillingAccount`, etc. |

### Context Map Example

```
[Product Catalog Context]  ---Supplier--->  [Search Context]
         |
    Anti-Corruption Layer
         |
[Order Management Context]  ---Events--->  [Shipping Context]
         |                                        |
    Shared Kernel (Money value object)            |
         |                                        |
[Billing Context]  <---Events---  [Shipping Context]
```

---

## Output Format: What an Agent Should Produce

When applying DDD to analyze or design a feature, produce this structured output:

```markdown
## Domain Model Analysis

### Bounded Context
- Context name: [name]
- Responsibility: [one sentence]
- Upstream contexts: [what feeds data in]
- Downstream contexts: [what consumes data out]
- Integration pattern: [ACL / Shared Kernel / Events / REST]

### Aggregates

#### [AggregateName] Aggregate
- Root entity: [Name] (identity: [id field])
- Child entities: [list with identity fields]
- Value objects: [list with key attributes]
- Invariants:
  1. [Business rule that must always be true]
  2. [Another rule]
- Commands (things you can ask it to do):
  - [commandName](params) -- [what it does, what can go wrong]
- Domain events (things it announces):
  - [EventName] { [key fields] } -- [when it's raised]

### Repository Interfaces
- [RepositoryName]
  - [method signatures with brief descriptions]

### Domain Services (cross-aggregate logic)
- [ServiceName]: [what it coordinates and why it can't live on a single aggregate]
```

---

## Quick Reference Table

| DDD Concept | What It Is | Rule of Thumb | Common Mistake |
|------------|-----------|---------------|----------------|
| Bounded Context | A boundary where a model is consistent | If the same word means different things, you need separate contexts | Making one giant model for the whole company |
| Aggregate | Consistency/transaction boundary | If it must be atomically consistent, it's one aggregate | Aggregates that are too large (whole order history in one aggregate) |
| Aggregate Root | Single entry point to the aggregate | External code only references the root, never child entities | Letting services directly modify child entities |
| Entity | Object with identity | Use when you need to track something over time | Making everything an entity when a value object would do |
| Value Object | Immutable object defined by attributes | Use for measurements, descriptions, ranges, amounts | Using primitive types (string, int) instead of value objects |
| Domain Event | Past-tense fact about what happened | Use for cross-aggregate and cross-context communication | Events that carry too much data or represent commands |
| Repository | Collection-like access to aggregates | One repository per aggregate root, loads/saves whole aggregates | Repositories for child entities, or repositories that return partial aggregates |
| Domain Service | Logic that doesn't belong on one entity | Use when an operation spans multiple aggregates | Putting all logic in services instead of on entities (anemic domain model) |
| Anti-Corruption Layer | Translation between contexts | Use when integrating with external or legacy systems | Letting external models leak into your domain |
| Ubiquitous Language | Shared vocabulary in code and conversation | If the business calls it X, the code calls it X | Developer jargon in domain code ("dto", "payload", "handler" as domain names) |

### Aggregate Sizing Heuristic

**Too small:** You find yourself needing two-phase commits or complex sagas for simple operations. Two things that always change together are in separate aggregates.

**Too large:** You have lock contention. Simple updates require loading a huge object graph. Concurrent users frequently conflict. Your aggregate has more than ~3-5 child entities or more than ~1000 child records.

**Just right:** Each command modifies exactly one aggregate. Cross-aggregate operations use domain events with eventual consistency that the business actually tolerates.

### Mapping DDD to Code Structure

```
src/
  domain/                     # No framework dependencies
    order/                    # Bounded Context or Aggregate module
      Order.ts                # Aggregate Root (Entity)
      OrderLineItem.ts        # Child Entity
      Money.ts                # Value Object
      OrderStatus.ts          # Value Object (enum-like)
      OrderPlaced.ts          # Domain Event
      OrderRepository.ts      # Repository Interface (port)
      PricingService.ts       # Domain Service
  application/                # Orchestration, no business logic
    order/
      PlaceOrderCommand.ts    # Command DTO
      PlaceOrderHandler.ts    # Loads aggregate, calls method, saves, publishes events
  infrastructure/             # Framework and I/O
    persistence/
      PostgresOrderRepository.ts  # Repository Implementation (adapter)
    messaging/
      RabbitMQEventPublisher.ts
```

---

## Example Walkthrough: "Add subscription billing"

**Feature request:** "Customers can subscribe to a monthly plan. Plans have different tiers with different feature limits. Subscriptions auto-renew. Customers can upgrade/downgrade mid-cycle with prorated charges."

### Bounded Context Decision

This is a new bounded context: **Subscription Billing**. Reasons:
- "Customer" here means "subscriber with a payment method," different from "Customer" in the e-commerce context (a shopper with a cart).
- Different rate of change: billing rules change with pricing strategy, independent of product catalog changes.
- Different consistency needs: billing must be strongly consistent (never charge twice, never miss a charge).

### Aggregates

**Subscription Aggregate:**
```
Root: Subscription (subscriptionId, customerId, currentPlanId, status, currentPeriodStart, currentPeriodEnd)
Value Objects:
  BillingPeriod (start, end)
  SubscriptionStatus (ACTIVE | PAUSED | CANCELLED | PAST_DUE)

Invariants:
  - Cannot upgrade/downgrade a cancelled subscription
  - Billing period end must be after start
  - Status transitions: ACTIVE -> PAUSED, ACTIVE -> CANCELLED, PAUSED -> ACTIVE, ACTIVE -> PAST_DUE

Commands:
  - changePlan(newPlanId) -> raises PlanChanged event
  - cancel(reason) -> raises SubscriptionCancelled event
  - renew() -> raises SubscriptionRenewed event
  - markPastDue() -> raises SubscriptionPastDue event
```

**Plan Aggregate:**
```
Root: Plan (planId, name, tier, monthlyPriceInCents, features[])
Value Objects:
  PlanTier (FREE | BASIC | PRO | ENTERPRISE)
  FeatureLimit (featureName, limit)
  Money (amount, currency)

Invariants:
  - Price must be non-negative
  - Plan must have at least one feature
```

**Domain Service:**
```
ProrationCalculator:
  - calculateProration(currentPlan, newPlan, daysRemainingInPeriod) -> Money
  - Reason it's a service: it needs both Plan aggregates but doesn't belong on either one
```

**Domain Events:**
```
SubscriptionCreated { subscriptionId, customerId, planId, startsAt }
PlanChanged { subscriptionId, oldPlanId, newPlanId, proratedAmount }
SubscriptionRenewed { subscriptionId, planId, newPeriodEnd, chargeAmount }
SubscriptionCancelled { subscriptionId, reason, effectiveDate }
SubscriptionPastDue { subscriptionId, failedChargeAmount }
```

The `SubscriptionRenewed` event would be consumed by the **Payment Context** (separate bounded context) to actually charge the customer. The **Subscription Billing** context doesn't know how payments work -- it just announces that a charge is due.
