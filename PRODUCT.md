# Product

## Register

product

## Users

Lawyers and legal professionals using Juris as their AI research assistant. Primary workflow: ask legal questions against uploaded documents, review citations, track what the AI concluded and why. Secondary workflow (enterprise): audit AI decisions for compliance and accountability. Users work at a desk, under professional pressure, in high-stakes contexts. They expect precision, not personality.

## Product Purpose

Juris is an AI-powered legal research assistant that retrieves answers from a user's uploaded documents, cites its sources, and (as of M6) keeps an immutable audit trail of every AI decision so lawyers can prove later what the system concluded, under what evidence, and governed by what policy. It turns a capable RAG chatbot into an accountable legal record system.

## Brand Personality

Precise. Accountable. Composed.

No enthusiasm, no decoration, no friendly marketing voice. Juris is a professional tool in a serious domain. It earns trust by being exact and showing its work, not by being charming.

## Anti-references

- Generic SaaS dashboards (Notion, Linear clones) — not a productivity app
- Legaltech marketing sites with hero gradients and "supercharge your practice" copy
- ChatGPT / consumer AI aesthetic — rounded bubbly chat UI that reads as casual
- Finance/compliance dark themes that overuse amber warnings and red badges
- Glassmorphism or frosted-panel UI — decorative, not functional

## Design Principles

1. **Show the evidence.** Every answer cites its source. Every AI decision traces its inputs. Transparency is the product, not a feature.
2. **Precision over expression.** Data over decoration. The interface should feel like a well-designed professional instrument, not a consumer app.
3. **One level of nesting, never two.** The layout has panels, not panels inside cards inside panels. Complexity in the data does not justify complexity in the chrome.
4. **Trust degrades gracefully.** When data is unavailable (network, empty state, error), the interface is honest about it and never hides the gap.
5. **Additive, never disruptive.** New features (audit trail, voice, documents) appear as optional panels or contextual expansions, never replacing or overriding the primary conversation flow.

## Accessibility & Inclusion

WCAG 2.1 AA. Keyboard navigable panels and drawers. Sufficient contrast (4.5:1 body, 3:1 large text). Reduced-motion global rule already applied. Screen reader semantics on all interactive elements (aria-label on icon-only buttons).
