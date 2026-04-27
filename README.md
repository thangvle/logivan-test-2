# Logivan Test 2

## Requirement

This is the description in the email:
Vulnerabilities for applying the LLM system to the real-world:

1. The Fuzzy Matching Trap: In logistics, text similarity is dangerous. "Quận 1" and "Quận 10" might look like a 90% text match, but they are geographically completely different.
2. Outdated API/Geography Edge Cases: Vietnam frequently updates its administrative boundaries (e.g., merging wards). Both Google Maps APIs and pre-trained LLMs often lag behind these changes, meaning Tier 3 could fail or hallucinate.
3. Static Architecture: If the LLM successfully resolves a messy address today, your current script will still pay tokens to resolve the exact same messy address tomorrow.

Requirement for AI system upgrade to resolves:

- How to build a self-healing feedback loop where successful LLM matches are cached back into Tier 1 (Programmatic Logic) to drive future token costs to zero.
- RAG over pre-trained memory: How to inject updated geographic context into the LLM when local APIs fail.
- Deterministic Validation: We do not use LLM "confidence scores" (as LLMs are people-pleasers and will fake high confidence). We want to hear how you would use post-LLM Python validation or API logprobs to route uncertain edge cases to a human review queue.

Notes: 
I would assume that this is the continuation of the last assignment where it requires to match the VAT invoices with deliveries. 

## Method
Since the Test Description does not clearly explain what tier mean and the context of tier is missing, this is how I define the tier of involving LLM into matching the deliveries with invoices

Clarifying the tier 
- Tier 1: Programmatic Logic
  - Using code/script to run the logic without LLM involve
  - 0 token usage
- Tier 2: Cached LLM Response
  - return previous LLM response for the same/similar user prompt/request
  - 0 - minimal token usage
- Tier 3: LLM inference
  - LLM inference from AI provider/on-prem hardware
  - Full token processing

## Approach

Defining the orchestration
- Input: `None`
- Output: `None`
- Logic: 
  - Going through Tier 1 -> Tier 3, then send the result for human review

Programmatic Logic Layer (Tier 1)
- Input: `raw_address: str`
- Output: `AddressResolved | None`
- Logic: Using address pattern recognize by LLM

LLM response cache Layer (Tier 2)
- Input: `raw_address: str`
- Output: `AddressResolved | None`
- Logic: using Vector search and Prefix Caching from LLM resquest

RAG service Layer (Tier 2)
- Input: `raw_address: str`
- Output: `AddressResolved | None`
- Logic: Vector search with reranking context of human review and updated  address information

LLM Service Layer (Tier 3)
- Input: `raw_address`
- Output: `(AddressResolved, logprob)`
- Logic: Prompt engineering + LLM call -> string tuple

Validator:
- Input: `AddressResolution`, `GroundTruth`
- Output: `ValidationResult` as boolean
- Logic: Check Coordinate, and save the result to the Human review Queue

Human Review Queue:
- Input: `ValidationResult`, `AddressResolution`, `GroundTruth`
- Output: `CorrectedResult`
- Logic: Let human compare the validation result with Address resolved by AI and correct the incorrect address.
