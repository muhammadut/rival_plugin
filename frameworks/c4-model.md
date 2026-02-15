# C4 Model -- Architecture Decomposition Framework

**Purpose:** Analyze any software system at four zoom levels so you can identify exactly where a change lands, what it touches, and how far the blast radius extends.

---

## Core Concepts

### 1. The Four Levels Are Zoom Levels, Not Layers

The C4 model is a set of four hierarchical diagrams, each zooming into the previous one. They are not architectural layers (like presentation/business/data). Think of them as Google Maps zoom levels: you start with the continent, then the city, then the street, then the building.

- **Level 1 -- System Context:** Your system as a single box, showing who uses it and what external systems it talks to.
- **Level 2 -- Container:** Zoom into your system. Shows the runtime deployable units: web apps, APIs, databases, message queues, file systems.
- **Level 3 -- Component:** Zoom into one container. Shows the major structural building blocks inside it: services, controllers, repositories, modules.
- **Level 4 -- Code:** Zoom into one component. Shows classes, interfaces, functions. This is your actual source code structure.

### 2. Most Feature Work Lives at Level 3 (Component) and Level 4 (Code)

When a product manager says "add a discount code feature," you are almost always working at Component and Code levels. You rarely add a new Container (a whole new service or database) and you almost never change the System Context (adding a new external dependency). Knowing which level you are at prevents over-engineering (don't spin up a new microservice for a discount code) and under-engineering (don't stuff a new payment provider integration into an existing controller).

### 3. Blast Radius Scales with Level

A change at a higher C4 level has exponentially wider blast radius. Changing code inside a single component is low risk. Changing a component's public interface affects other components in that container. Adding or modifying a container affects deployment, infrastructure, and potentially other teams. Changing the system context means new external dependencies, contracts, and possibly compliance requirements.

### 4. Boundaries Between Levels Are Deployment and Communication Boundaries

The boundary between containers is a deployment boundary -- they run in separate processes or on separate infrastructure. The boundary between components is a code-organization boundary -- they live in the same deployable unit but are logically separate modules. This distinction matters because crossing a container boundary means network calls, serialization, latency, and failure modes that don't exist within a single container.

### 5. The Model Is Descriptive, Not Prescriptive

C4 does not tell you how to architect your system. It tells you how to *describe* your architecture at appropriate levels of detail. A monolith and a microservices system both have valid C4 diagrams. The value is in forcing you to be explicit about what exists at each level.

---

## Practical Application: Analyzing a Feature Request

When you receive a feature request, walk through these steps:

### Step 1: Identify the Affected Level

Ask: "Does this change introduce a new external system, a new deployable unit, a new module inside an existing unit, or just new code inside an existing module?"

| Question | If Yes, Level Affected |
|----------|----------------------|
| Do we need to integrate with a new third-party service or expose our system to new users? | Level 1 -- System Context |
| Do we need a new database, a new API service, a new queue, or a new frontend app? | Level 2 -- Container |
| Do we need a new module, service class, or major internal boundary inside an existing container? | Level 3 -- Component |
| Do we need new classes, functions, or modifications to existing ones within an existing component? | Level 4 -- Code |

### Step 2: Map the Current State

Before proposing changes, document what exists at the relevant level.

**Example -- Feature: "Add Stripe payment processing to our e-commerce app"**

Level 1 (System Context) -- current state:
```
[Customer] --> [E-Commerce System] --> [Inventory API (internal)]
                                   --> [Email Service (SendGrid)]
```

Level 1 -- proposed state:
```
[Customer] --> [E-Commerce System] --> [Inventory API (internal)]
                                   --> [Email Service (SendGrid)]
                                   --> [Payment Gateway (Stripe)]  <-- NEW
```

This is a Level 1 change. The blast radius is significant: new external dependency, API keys management, PCI compliance considerations, failure handling for an external service, webhook ingestion.

### Step 3: Assess Blast Radius

**Example -- Feature: "Add a coupon code field to checkout"**

Walk through the levels:
- Level 1: No new external systems. Not affected.
- Level 2: No new containers. Not affected.
- Level 3: Need a new `CouponService` component in the existing API container, and modification to the existing `CheckoutComponent`. Level 3 is affected.
- Level 4: New classes `Coupon`, `CouponValidator`, `CouponRepository`; modified `CheckoutController`, `CheckoutRequest` DTO. Level 4 is affected.

Blast radius: contained within a single container. No infrastructure changes. No new deployment units. Moderate risk -- touches checkout flow which is business-critical, but changes are internal.

### Step 4: Determine Review and Testing Scope

| Level Affected | Review Scope | Testing Scope | Deployment Considerations |
|---------------|-------------|--------------|--------------------------|
| Level 1 | Architecture review, security review, legal/compliance | Integration tests with external system, contract tests, chaos testing | New secrets, new network policies, new monitoring |
| Level 2 | Architecture review, DevOps review | Integration tests between containers, load tests, deployment pipeline changes | New CI/CD pipelines, new infrastructure provisioning |
| Level 3 | Team-level code review | Unit tests for new component, integration tests within container | None beyond normal deployment |
| Level 4 | Standard code review | Unit tests, maybe updated integration tests | None beyond normal deployment |

---

## Output Format: What an Agent Should Produce

When analyzing architecture using C4, produce this structured output:

```markdown
## C4 Impact Analysis

### Current System Context (Level 1)
- Users: [list actors]
- External systems: [list integrations]
- Change at this level: [Yes/No] -- [why]

### Affected Containers (Level 2)
- Container: [name] -- [technology] -- [responsibility]
- New containers needed: [Yes/No] -- [what and why]

### Affected Components (Level 3)
- Component: [name] -- [what changes]
- New components: [name] -- [responsibility]
- Component interfaces affected: [list public APIs/contracts that change]

### Code Changes (Level 4)
- New: [classes/modules to create]
- Modified: [classes/modules to change]
- Deleted: [classes/modules to remove]

### Blast Radius Summary
- Highest level affected: [1/2/3/4]
- Risk: [Low/Medium/High]
- Reason: [one sentence]
- Cross-team coordination needed: [Yes/No]
- Infrastructure changes needed: [Yes/No]
```

---

## Quick Reference Table

| Level | Name | Contains | Boundary Type | Example Elements | Blast Radius if Changed |
|-------|------|----------|--------------|-----------------|------------------------|
| 1 | System Context | Your system + external actors and systems | Organization / trust boundary | Users, third-party APIs, other internal systems | Very High -- new contracts, compliance, security |
| 2 | Container | Deployable units within your system | Deployment / process boundary | Web app, REST API, database, message broker, S3 bucket | High -- infrastructure, CI/CD, cross-team |
| 3 | Component | Logical modules within a container | Code organization boundary | Services, controllers, repositories, domain modules | Medium -- internal to one deployable unit |
| 4 | Code | Classes, functions, data structures | None (implementation detail) | Classes, interfaces, functions, DTOs | Low -- localized, standard code review |

### Common Mistakes

| Mistake | Why It's Wrong | Fix |
|---------|---------------|-----|
| Calling a class a "container" | Containers are deployment units, not code constructs | A Spring Boot app is a container; a `@Service` class is a component |
| Skipping Level 3 | Jumping from "we have an API" to code misses the internal structure | Always identify the major components inside each affected container |
| Treating C4 as architecture prescription | C4 is a visualization tool, not an architecture style | Use it to describe, then use other frameworks (DDD, etc.) to decide |
| Creating Level 4 diagrams for everything | Code-level diagrams go stale instantly | Only use Level 4 for complex algorithms or tricky patterns that need explanation |
| Conflating "component" with framework-specific terms | A React component is not a C4 component | C4 components are coarse-grained: a whole feature module, not a UI widget |

### Decision Shortcuts

- **"Just add a field to an existing form"** --> Level 4 only. Low blast radius.
- **"Integrate with Twilio for SMS"** --> Level 1. New external system. High blast radius.
- **"Split the monolith's auth into a separate service"** --> Level 2. New container. High blast radius.
- **"Add caching to the product search"** --> Level 3 if adding Redis (new container = Level 2), Level 3 if in-memory cache (new component inside existing container).
- **"Refactor the order processing module"** --> Level 3 if changing component interfaces, Level 4 if internal-only refactor.

### Mapping C4 to Common Tech Stacks

| C4 Level | Monolith (Rails/Django/Spring) | Microservices | Serverless |
|----------|-------------------------------|---------------|------------|
| Container | The app + its database | Each service + its data store | Each Lambda group + DynamoDB table |
| Component | Modules, engines, Django apps, Spring `@Service` groups | Modules within a single service | Individual Lambda functions |
| Code | Classes, functions | Classes, functions | Handler code within a Lambda |

---

## Example Walkthrough: "Add real-time order tracking"

**Feature request:** "Customers should see live updates when their order status changes."

**Level 1 analysis:** Do we need a new external system? If we use a third-party tracking service (like AfterShip), yes. If we build it ourselves, no. Decision: build ourselves. Level 1 not affected.

**Level 2 analysis:** Do we need a new container? Yes -- we need a WebSocket server for real-time push (or use Server-Sent Events). We also need a message broker if we don't have one, to propagate order status changes. New containers: WebSocket service, possibly Redis Pub/Sub.

**Level 3 analysis:** Inside the existing API container, we need a new `OrderStatusEventPublisher` component. Inside the new WebSocket container, we need `ConnectionManager`, `OrderStatusSubscription`, `EventConsumer` components.

**Level 4 analysis:** Specific classes and functions within each new component.

**Blast radius:** Level 2 -- High. New infrastructure (WebSocket server, Redis), new deployment pipeline, new monitoring, potential load concerns with persistent connections. Requires DevOps coordination, load testing, and capacity planning.
