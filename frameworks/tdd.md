# Test-Driven Development (TDD)

**Purpose:** Drive software design through short, repeatable test-write-refactor cycles that produce clean code with built-in regression safety.

---

## Core Concepts

### 1. The Red-Green-Refactor Cycle

Write a failing test first (Red), write the minimum code to make it pass (Green), then improve the code without changing behavior (Refactor). Each cycle should take 1-5 minutes. If you are spending longer, the step you are trying to take is too large -- break it down. The discipline is in resisting the urge to write production code before you have a failing test that demands it.

### 2. Test-First as a Design Tool

Writing the test before the implementation forces you to think about the API from the caller's perspective. If a function is hard to test, it is hard to use. Test-first surfaces coupling, unclear responsibilities, and missing abstractions *before* you commit to an implementation. The tests become executable documentation of intended behavior.

### 3. The Testing Pyramid

Unit tests form the base (fast, isolated, hundreds of them). Integration tests sit in the middle (verify component collaboration, slower, dozens). End-to-end tests are at the top (full system paths, slowest, a handful). A healthy codebase has roughly a 70/20/10 ratio. When the pyramid inverts, the test suite becomes slow and brittle.

### 4. What Makes a Good Unit Test

A good unit test is F.I.R.S.T: Fast (milliseconds), Isolated (no shared state, no filesystem/network), Repeatable (same result every run), Self-validating (pass/fail with no human judgment), and Timely (written before or alongside the code). Each test should verify one logical behavior, not one method. Name tests after the behavior they protect, not the method they call.

### 5. Triangulation and Transformation Priority Premise

When stuck on the simplest implementation, add another test case that forces generalization. This is triangulation. Move from specific (return a constant) to general (compute the result) through small, provable transformations. The Transformation Priority Premise ranks code changes from simplest (constant -> variable) to most complex (statement -> recursion) and suggests preferring simpler transformations to avoid large leaps.

---

## Practical Application: Feature Request Walkthrough

**Feature:** "Users can apply a percentage discount code to their cart total."

### Step 1: List Behaviors Before Coding

```
- Applying a valid 10% discount to a $100 cart yields $90
- Applying a 0% discount changes nothing
- Applying a 100% discount yields $0
- Discount codes are case-insensitive
- Expired discount codes are rejected
- Discount cannot reduce total below $0
- Discount applies to subtotal, not to tax
```

### Step 2: Start with the Simplest Case (Red)

```python
# test_discount.py
def test_apply_percentage_discount_to_cart():
    cart = Cart(subtotal=100.00)
    discount = PercentageDiscount(rate=10)

    result = cart.apply_discount(discount)

    assert result.subtotal == 90.00
```

Run it. It fails -- `Cart` does not exist yet. Good.

### Step 3: Make It Pass with Minimum Code (Green)

```python
# discount.py
class PercentageDiscount:
    def __init__(self, rate):
        self.rate = rate

class Cart:
    def __init__(self, subtotal):
        self.subtotal = subtotal

    def apply_discount(self, discount):
        self.subtotal = self.subtotal * (1 - discount.rate / 100)
        return self
```

Run it. It passes. Move on.

### Step 4: Add the Next Behavior (Red Again)

```python
def test_zero_percent_discount_changes_nothing():
    cart = Cart(subtotal=50.00)
    discount = PercentageDiscount(rate=0)

    result = cart.apply_discount(discount)

    assert result.subtotal == 50.00
```

This already passes with the current implementation. That is fine -- it confirms the generalization works. Move to a case that might not.

```python
def test_discount_cannot_reduce_total_below_zero():
    cart = Cart(subtotal=10.00)
    discount = PercentageDiscount(rate=150)

    result = cart.apply_discount(discount)

    assert result.subtotal == 0.00
```

This fails. The current code produces `-5.00`.

### Step 5: Fix It (Green)

```python
def apply_discount(self, discount):
    self.subtotal = max(0, self.subtotal * (1 - discount.rate / 100))
    return self
```

### Step 6: Refactor

The `apply_discount` method is doing math inline. Extract the calculation.

```python
class PercentageDiscount:
    def __init__(self, rate):
        self.rate = min(rate, 100)  # cap at 100%

    def apply_to(self, amount):
        return round(amount * (1 - self.rate / 100), 2)

class Cart:
    def __init__(self, subtotal):
        self.subtotal = subtotal

    def apply_discount(self, discount):
        self.subtotal = discount.apply_to(self.subtotal)
        return self
```

All tests still pass. The discount logic now lives with the discount. Continue the cycle for expired codes, case-insensitivity, etc.

---

## Unit Tests vs Integration Tests: Decision Guide

### When to Write a Unit Test

- Pure logic: calculations, transformations, validations
- Branching behavior: if/else paths, edge cases, error handling
- A single class or function in isolation
- You need fast feedback (sub-second)

```python
# UNIT: Tests the discount calculation in isolation
def test_percentage_discount_rounds_to_two_decimals():
    discount = PercentageDiscount(rate=33)
    assert discount.apply_to(100.00) == 67.00
    assert discount.apply_to(99.99) == 66.99
```

### When to Write an Integration Test

- Two or more components must collaborate correctly
- Database queries return expected results
- HTTP endpoints serialize/deserialize correctly
- Message queues deliver and consume events
- You need confidence that the wiring works

```python
# INTEGRATION: Tests the HTTP layer + discount service + database together
def test_apply_discount_code_via_api(client, db_session):
    db_session.add(DiscountCode(code="SAVE10", rate=10, expires_at=future()))
    db_session.commit()

    response = client.post("/cart/discount", json={"code": "SAVE10"})

    assert response.status_code == 200
    assert response.json()["subtotal"] == 90.00
```

### Common Mistakes

| Mistake | Why It Hurts | Fix |
|---|---|---|
| Mocking everything in integration tests | You are testing mocks, not wiring | Use real dependencies or test containers |
| Hitting the database in unit tests | Slow, flaky, tests implementation | Mock the repository interface |
| One giant assertion per test | Failure messages are useless | One logical behavior per test |
| Testing private methods | Couples tests to implementation | Test through the public API |
| No test for the sad path | Bugs hide in error handling | Write tests for invalid input, timeouts, nulls |

---

## Output Format: What an Agent Should Produce

When applying TDD to implement a feature, produce the following artifacts in order:

### 1. Behavior List

A plain-text checklist of discrete behaviors extracted from the requirement.

```
Behaviors for "Percentage Discount":
- [ ] Valid discount reduces subtotal by percentage
- [ ] Zero-rate discount leaves subtotal unchanged
- [ ] Rate capped at 100% (no negative totals)
- [ ] Expired codes rejected with clear error
- [ ] Codes are case-insensitive
- [ ] Discount applies to subtotal only, not tax
```

### 2. Test File (written first)

The complete test file with all test cases, including:
- Descriptive test names using `test_<behavior_description>` pattern
- Arrange-Act-Assert structure in every test
- Edge cases and error cases alongside happy paths

### 3. Implementation File (written second)

The production code that makes all tests pass. Should be the simplest code that satisfies the tests -- no speculative generality.

### 4. Refactoring Notes

Brief comments on what was restructured after green and why.

```
Refactoring notes:
- Extracted discount calculation from Cart into PercentageDiscount.apply_to()
  Reason: Discount math is the discount's responsibility, not the cart's.
- Introduced Money value object for subtotal
  Reason: Floating-point rounding was causing cent-level errors.
```

---

## Quick Reference Table

| Concept | Rule of Thumb |
|---|---|
| Cycle length | 1-5 minutes per Red-Green-Refactor loop |
| Test naming | `test_<unit>_<behavior>_<condition>` e.g., `test_discount_rejects_expired_code` |
| Arrange-Act-Assert | Three sections per test, separated by blank lines |
| One assertion rule | One *logical* assertion per test (multiple `assert` lines are fine if they verify one behavior) |
| Test isolation | No test should depend on another test's state or execution order |
| Mocking boundary | Mock at architectural boundaries (DB, HTTP, filesystem), not between your own classes |
| Test speed | Unit < 10ms, Integration < 1s, E2E < 30s |
| When to skip TDD | Throwaway spikes, UI layout tweaks, generated code. Resume TDD once design is clear. |
| Refactor trigger | All tests green + you see duplication, unclear naming, or a method doing two things |
| Flaky test policy | Fix or delete immediately. A flaky test trains the team to ignore failures. |

---

## Test Doubles Cheat Sheet

| Double | Purpose | Example |
|---|---|---|
| **Stub** | Returns canned answers | `payment_gateway.charge = Mock(return_value=Success())` |
| **Mock** | Verifies interactions | `mock_emailer.send.assert_called_once_with(to="user@x.com")` |
| **Fake** | Working lightweight implementation | In-memory repository instead of PostgreSQL |
| **Spy** | Records calls for later inspection | `spy.calls` returns `[("charge", 100), ("refund", 50)]` |
| **Dummy** | Fills a parameter slot, never used | `NullLogger()` passed to satisfy a constructor |

---

## Anti-Patterns to Avoid

| Anti-Pattern | Symptom | Remedy |
|---|---|---|
| **Ice cream cone** | More E2E tests than unit tests | Delete redundant E2E tests, push logic down to units |
| **Liar test** | Test passes but does not verify anything meaningful | Review assertions -- every test must be able to fail |
| **Slow suite** | Full suite takes > 5 minutes | Profile, move slow tests to a separate CI stage |
| **Test-after** | Writing tests after code as an afterthought | You miss design feedback; discipline to write test first |
| **Shotgun surgery** | Changing one feature breaks 40 tests | Tests are coupled to implementation; test behavior not structure |
| **DRY tests** | Heavy test abstractions that obscure what is being tested | Prefer readability over reuse in test code; some duplication is fine |
