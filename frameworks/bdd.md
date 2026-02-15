# Behavior-Driven Development -- Scenario Specification Framework

**Purpose:** Translate feature requests into precise, testable scenarios using structured natural language so that developers, testers, and product owners share a single unambiguous definition of "done."

---

## Core Concepts

### 1. Given/When/Then Is a State Machine, Not Prose

Every scenario describes a state transition: the system starts in a known state (**Given**), something happens (**When**), and the system ends in a verifiable state (**Then**). This is not decorative -- it forces you to be explicit about preconditions, triggers, and outcomes. If you cannot fill in all three parts, the requirement is incomplete.

- **Given** sets up preconditions: data that exists, system state, user roles, configuration. These are facts about the world *before* the action.
- **When** is the single action under test. It should be exactly one trigger. If you have two actions, you have two scenarios.
- **Then** is the observable outcome. It must be verifiable -- something you can assert in code. "The system should be fast" is not a Then. "The response is returned within 200ms" is.

### 2. Scenarios Categorize Into Happy Path, Sad Path, and Edge Cases

Every feature has at least three kinds of scenarios. Missing any category means gaps in your specification and your test suite.

- **Happy path:** The user does the right thing and the system does the expected thing. This is the "golden scenario" described in the feature request. There is usually 1-3 of these.
- **Sad path:** The user does something wrong or the system encounters a known failure. Invalid input, unauthorized access, resource not found, external service down. There are usually 3-10 of these per feature.
- **Edge cases:** Boundary conditions, concurrency, timing, empty states, maximum limits. Zero items in cart, exactly-at-limit values, simultaneous updates, first-time vs. returning user. There are usually 2-5 of these per feature.

### 3. Gherkin Is the Syntax, BDD Is the Practice

Gherkin (the `Feature`/`Scenario`/`Given`/`When`/`Then` syntax) is a specific format for writing scenarios. BDD is the broader practice of deriving these scenarios collaboratively with stakeholders before writing code. You can practice BDD without Gherkin (just use structured bullet points), and you can write Gherkin without practicing BDD (but then you're just writing test scripts, not specifications).

### 4. Scenarios Are Specifications, Not Test Scripts

A scenario describes *what* the system does, not *how* it does it. "Given the user clicks the submit button with id='btn-submit'" is a test script coupled to UI implementation. "Given the user submits the registration form" is a specification that survives a UI redesign. Keep scenarios at the behavioral level -- they describe business outcomes, not interaction mechanics.

### 5. Derive Scenarios Systematically, Not by Brainstorming

Do not sit around and try to think of scenarios. Instead, use a structured derivation process: start with the happy path, then ask "what can go wrong at each Given/When/Then step?" for sad paths, then ask "what are the boundary conditions for each data element?" for edge cases. This produces more complete coverage than ad-hoc brainstorming.

---

## Practical Application: Deriving Scenarios from a Feature Request

### The Feature Request

> "Users can apply a promo code at checkout for a percentage discount. Promo codes have an expiration date and a maximum number of uses."

### Step 1: Write the Happy Path First

Identify the simplest successful flow. One actor, one action, one success outcome.

```gherkin
Feature: Promo Code Application at Checkout

  Scenario: Apply a valid promo code
    Given a promo code "SAVE20" exists with 20% discount
    And the promo code "SAVE20" expires on 2026-12-31
    And the promo code "SAVE20" has 50 remaining uses
    And the customer has a cart with a total of $100.00
    When the customer applies promo code "SAVE20"
    Then the cart total is reduced to $80.00
    And the promo code remaining uses decreases to 49
    And the applied discount is shown as "$20.00 off"
```

### Step 2: Derive Sad Paths by Breaking Each Precondition

For each **Given** line, ask: "What if this isn't true?"

```gherkin
  Scenario: Apply an expired promo code
    Given a promo code "OLDCODE" exists with 15% discount
    And the promo code "OLDCODE" expired on 2025-01-01
    And the customer has a cart with a total of $100.00
    When the customer applies promo code "OLDCODE"
    Then the promo code is rejected with message "This promo code has expired"
    And the cart total remains $100.00

  Scenario: Apply a fully redeemed promo code
    Given a promo code "MAXED" exists with 10% discount
    And the promo code "MAXED" has 0 remaining uses
    And the customer has a cart with a total of $100.00
    When the customer applies promo code "MAXED"
    Then the promo code is rejected with message "This promo code is no longer available"
    And the cart total remains $100.00

  Scenario: Apply a nonexistent promo code
    Given no promo code "FAKECODE" exists
    And the customer has a cart with a total of $100.00
    When the customer applies promo code "FAKECODE"
    Then the promo code is rejected with message "Invalid promo code"
    And the cart total remains $100.00
```

### Step 3: Derive Edge Cases from Boundary Conditions

For each data element, ask: "What happens at the boundaries?"

```gherkin
  Scenario: Apply a promo code with exactly 1 remaining use
    Given a promo code "LASTONE" exists with 25% discount
    And the promo code "LASTONE" has 1 remaining use
    And the customer has a cart with a total of $80.00
    When the customer applies promo code "LASTONE"
    Then the cart total is reduced to $60.00
    And the promo code remaining uses decreases to 0

  Scenario: Apply a promo code on the expiration date
    Given a promo code "TODAY" exists with 10% discount
    And the promo code "TODAY" expires on 2026-02-14
    And today's date is 2026-02-14
    And the customer has a cart with a total of $50.00
    When the customer applies promo code "TODAY"
    Then the cart total is reduced to $45.00

  Scenario: Apply a promo code to a cart with zero total
    Given a promo code "SAVE20" exists with 20% discount
    And the customer has a cart with a total of $0.00
    When the customer applies promo code "SAVE20"
    Then the cart total remains $0.00
    And the applied discount is shown as "$0.00 off"

  Scenario: Apply a promo code that results in fractional cents
    Given a promo code "SAVE15" exists with 15% discount
    And the customer has a cart with a total of $33.33
    When the customer applies promo code "SAVE15"
    Then the cart total is reduced to $28.33
    And the discount is rounded to the nearest cent

  Scenario: Apply a second promo code when one is already applied
    Given a promo code "FIRST10" exists with 10% discount
    And a promo code "SECOND20" exists with 20% discount
    And the customer has a cart with a total of $100.00
    And the customer has already applied promo code "FIRST10"
    When the customer applies promo code "SECOND20"
    Then the promo code "FIRST10" is removed
    And the promo code "SECOND20" is applied
    And the cart total is reduced to $80.00
```

### Step 4: Consider Concurrency and Race Conditions (if applicable)

```gherkin
  Scenario: Two customers apply the last use of a promo code simultaneously
    Given a promo code "RACE" exists with 10% discount
    And the promo code "RACE" has 1 remaining use
    When customer A applies promo code "RACE"
    And customer B applies promo code "RACE" at the same time
    Then exactly one customer receives the discount
    And the other customer sees "This promo code is no longer available"
```

---

## Scenario Derivation Checklist

Use this checklist to ensure complete coverage for any feature:

### Happy Paths
- [ ] Basic success flow with typical data
- [ ] Success flow with minimum valid data
- [ ] Success flow with maximum valid data (if different behavior)

### Sad Paths -- Input Validation
- [ ] Required field missing
- [ ] Invalid format (wrong type, bad pattern)
- [ ] Value out of allowed range
- [ ] Input too long / too short

### Sad Paths -- Business Rules
- [ ] Precondition not met (expired, disabled, not started yet)
- [ ] Resource exhausted (limit reached, out of stock)
- [ ] Insufficient permissions / unauthorized
- [ ] Resource not found (deleted, never existed)
- [ ] Conflict with existing state (duplicate, already applied)

### Sad Paths -- System Failures
- [ ] External service unavailable (if applicable)
- [ ] Timeout on dependent operation (if applicable)

### Edge Cases
- [ ] Empty collection (zero items, no results)
- [ ] Exactly-at-limit values (max count, boundary date)
- [ ] First-time vs. repeat action (first login, second purchase)
- [ ] Rounding and precision (currency, percentages)
- [ ] Concurrent access (two users, same resource)
- [ ] Idempotency (same action submitted twice)

---

## Gherkin Syntax Reference

### Basic Structure

```gherkin
Feature: [Feature name]
  As a [role]
  I want [capability]
  So that [business value]

  Background:
    Given [shared precondition for all scenarios in this file]

  Scenario: [Descriptive name of this specific case]
    Given [precondition]
    And [additional precondition]
    When [action]
    Then [expected outcome]
    And [additional expected outcome]
    But [negative expected outcome -- thing that should NOT happen]
```

### Advanced Syntax

**Scenario Outline** -- run the same scenario with different data:

```gherkin
  Scenario Outline: Apply promo codes with various discount percentages
    Given a promo code "<code>" exists with <discount>% discount
    And the customer has a cart with a total of $<cart_total>
    When the customer applies promo code "<code>"
    Then the cart total is reduced to $<expected_total>

    Examples:
      | code     | discount | cart_total | expected_total |
      | SAVE10   | 10       | 100.00     | 90.00          |
      | SAVE20   | 20       | 100.00     | 80.00          |
      | HALF     | 50       | 200.00     | 100.00         |
      | SAVE15   | 15       | 33.33      | 28.33          |
```

**Data Tables** -- pass structured data into a step:

```gherkin
  Scenario: Checkout with multiple items
    Given the customer has the following items in their cart:
      | product        | quantity | unit_price |
      | Widget A       | 2        | $10.00     |
      | Widget B       | 1        | $25.00     |
      | Premium Widget | 3        | $50.00     |
    When the customer proceeds to checkout
    Then the cart total is $195.00
```

**Tags** -- organize and filter scenarios:

```gherkin
  @smoke @checkout
  Scenario: Complete checkout with credit card
    ...

  @wip
  Scenario: Complete checkout with Apple Pay
    ...

  @slow @integration
  Scenario: Checkout triggers inventory reservation in warehouse system
    ...
```

---

## Output Format: What an Agent Should Produce

When deriving BDD scenarios from a feature request, produce this structured output:

```markdown
## BDD Scenarios for [Feature Name]

### Feature Description
As a [role], I want [capability], so that [business value].

### Scenario Summary
| Category   | Count | Scenarios |
|------------|-------|-----------|
| Happy path | N     | [list]    |
| Sad path   | N     | [list]    |
| Edge case  | N     | [list]    |
| Total      | N     |           |

### Scenarios

#### Happy Path

[Gherkin scenarios]

#### Sad Path

[Gherkin scenarios]

#### Edge Cases

[Gherkin scenarios]

### Open Questions
- [Any ambiguity in the feature request that needs product clarification]
- [Any business rule that was assumed but not stated]
```

---

## Quick Reference Table

| Element | Purpose | Rule | Example |
|---------|---------|------|---------|
| Feature | Groups related scenarios | One feature per file | `Feature: User Registration` |
| Scenario | One specific behavior | One When per scenario; name describes the case, not the feature | `Scenario: Register with an already-used email` |
| Given | Preconditions | State, not actions; use past tense or present state | `Given the user has an active subscription` |
| When | The trigger | Exactly one action; use present tense | `When the user cancels the subscription` |
| Then | Expected outcome | Observable and assertable; use present tense or future | `Then the subscription status is "cancelled"` |
| And | Additional step | Extends the previous keyword | `And a cancellation confirmation email is sent` |
| But | Negative assertion | Something that should NOT happen | `But the user is not charged for the next period` |
| Background | Shared Given steps | Applied to every scenario in the file; use sparingly | `Background: Given the user is logged in` |
| Scenario Outline | Parameterized scenario | Use when same flow, different data | See syntax reference above |
| Examples | Data for outline | Table of values to substitute | See syntax reference above |
| Tags | Categorization | Filter test runs, mark WIP, group by feature area | `@smoke`, `@payments`, `@wip` |

### Writing Good Scenario Names

| Bad Name | Why It's Bad | Good Name |
|----------|-------------|-----------|
| Test login | Doesn't describe the specific case | Login with valid credentials |
| Error handling | Vague, could be anything | Login with incorrect password shows error message |
| Happy path | Not descriptive at all | Successfully place an order with two items |
| Promo code test 1 | Numbered, not descriptive | Apply expired promo code is rejected |
| It should work | Not a scenario name | Transfer funds between own accounts updates both balances |

### Writing Good Steps

| Bad Step | Why It's Bad | Good Step |
|---------|-------------|-----------|
| `Given the database has data` | What data? Not specific | `Given a customer "Alice" exists with email "alice@test.com"` |
| `When the user clicks the button` | UI-coupled, not behavioral | `When the user submits the order` |
| `Then it works` | Not verifiable | `Then the order status is "confirmed"` |
| `Then the system should not crash` | Absence of failure is not a specification | `Then the error is logged and the user sees a retry option` |
| `When the user enters "test" into the field and clicks submit` | Two actions, should be separate | `Given the user has entered search term "test"` / `When the user submits the search` |

---

## Example Walkthrough: "User Password Reset"

**Feature request:** "Users can reset their password by entering their email. They receive a reset link that expires after 24 hours. The link can only be used once."

### Scenario Derivation

**Happy paths:**

```gherkin
Feature: Password Reset

  Scenario: Request a password reset with a registered email
    Given a user exists with email "user@example.com"
    When the user requests a password reset for "user@example.com"
    Then a password reset email is sent to "user@example.com"
    And the reset link expires in 24 hours

  Scenario: Reset password using a valid reset link
    Given a user exists with email "user@example.com"
    And a password reset was requested for "user@example.com" 2 hours ago
    When the user opens the reset link
    And the user sets a new password "NewSecure!Pass1"
    Then the password is changed successfully
    And the user can log in with "NewSecure!Pass1"
    And the user cannot log in with the old password
```

**Sad paths:**

```gherkin
  Scenario: Request password reset with an unregistered email
    Given no user exists with email "nobody@example.com"
    When the user requests a password reset for "nobody@example.com"
    Then the same success message is displayed as for a valid email
    But no email is actually sent
    # Security: don't reveal whether an email is registered

  Scenario: Use an expired reset link
    Given a user exists with email "user@example.com"
    And a password reset was requested for "user@example.com" 25 hours ago
    When the user opens the reset link
    Then the link is rejected with message "This reset link has expired"
    And the user is prompted to request a new reset

  Scenario: Use a reset link that has already been used
    Given a user exists with email "user@example.com"
    And a password reset link was used successfully 1 hour ago
    When the user opens the same reset link again
    Then the link is rejected with message "This reset link has already been used"

  Scenario: Set a new password that doesn't meet complexity requirements
    Given a user has opened a valid password reset link
    When the user sets a new password "weak"
    Then the password is rejected with message "Password must be at least 8 characters"
    And the reset link remains valid for another attempt
```

**Edge cases:**

```gherkin
  Scenario: Request multiple password resets in succession
    Given a user exists with email "user@example.com"
    And a password reset was requested for "user@example.com" 1 hour ago
    When the user requests another password reset for "user@example.com"
    Then a new reset email is sent
    And the previous reset link is invalidated

  Scenario: Use a reset link after the user's password was changed by other means
    Given a user exists with email "user@example.com"
    And a password reset was requested for "user@example.com"
    And the user subsequently changed their password through account settings
    When the user opens the reset link from the email
    Then the link is rejected with message "This reset link is no longer valid"

  Scenario: Reset link used exactly at the 24-hour boundary
    Given a user exists with email "user@example.com"
    And a password reset was requested exactly 24 hours ago
    When the user opens the reset link
    Then the link is accepted
    # Business decision: expire AFTER 24h, not AT 24h
```

**Open questions to raise with product:**
- Should we rate-limit password reset requests? (e.g., max 5 per hour per email)
- Should the old password be required to set a new one via the reset flow? (typically no)
- Should active sessions be terminated when password is reset? (usually yes for security)
- Should we notify the user on their old email if the password is changed? (security best practice)
