# Social-Native Template Library

## Purpose

This expansion adds **social-native visual metaphors** to the existing campaign-card system. Each family presents the same approved message, proof, and brand identity through a recognisable interface or editorial format. These templates are intended for static feed posts, carousel slides, story covers, and paid-social variants; they are not mock screenshots of live customer accounts.

> **Privacy guardrail:** Message threads, inboxes, receipts, reviews, and activity feeds must use fictional or approved data. The factory must never be used to imply access to a real person’s private account, device, messages, or transaction history.

## Template taxonomy

| Family | Best use | Core module | Primary export | Priority |
| --- | --- | --- | --- | --- |
| Apple Notes-style insight | Founder insight, observation, concise advice | Headline, highlighted takeaway, note lines | 4:5 portrait | Implement now |
| iMessage/SMS-style conversation | Objection handling, before/after, customer education | Two-sided message bubbles, timestamp, takeaway | 1:1 square | Implement now |
| X/Tweet-style post card | Opinion, contrarian hook, distribution-friendly thought leadership | Author row, post text, proof/reply metrics | 1:1 square | Implement now |
| Search/autocomplete | Search-led pain point, category education, intent capture | Query, suggestions, result highlight | 4:5 portrait | Implement now |
| Thermal receipt audit | Cost-of-inaction, audit, pricing transparency | Itemized rows, total, audited callout | 4:5 portrait | Implement now |
| Notion-style operating checklist | Process proof, workflows, implementation plans | Breadcrumb, checklist, progress cue | 4:5 portrait | Implement now |
| Whiteboard/napkin diagram | Simple explanation, system model, founder POV | Nodes, hand-drawn arrows, central idea | 16:9 landscape | Implement now |
| Metrics scorecard | Benchmark, KPI win, case-study proof | Three metric tiles, primary result | 1:1 square | Implement now |
| Launch calendar | Event, webinar, product milestone, deadline | Date block, event card, CTA | 4:5 portrait | Implement now |
| Testimonial pull quote | Social proof, customer voice, review highlight | Quote, attribution, rating/proof line | 1:1 square | Implement now |
| Inbox alert | Urgency, lead-response story, alert-based use case | Inbox rows, unread state, highlight | 4:5 portrait | Implement now |
| Workflow timeline | Product walkthrough, launch sequence, carousel teaching slide | Step rail, milestones, outcome | 16:9 landscape | Implement now |

## Implementation contract

Every new format remains in the existing deterministic workflow. The request’s established `message`, `proof`, and `output` blocks remain required. An optional top-level `template_data` object supplies family-specific copy; templates use useful demonstration defaults when those optional fields are absent. Existing requests therefore remain valid without migration.

| Shared field | Role in new families |
| --- | --- |
| `message.headline` | Main social hook or display title |
| `message.subhead` / `supporting_copy` | Supporting explanation, secondary note, or post body |
| `message.proof_label` / `proof[0].claim` | Highlight, proof point, total, score, or credibility cue |
| `message.cta` | Discreet action prompt where the category supports one |
| `template_data` | Category-specific, non-sensitive UI content such as `messages`, `tasks`, `suggestions`, `receipt_items`, `metrics`, `events`, or `nodes` |

## Design rules

The library intentionally varies texture, hierarchy, colour temperature, and density rather than merely changing the aspect ratio of the current dark campaign card. Every family must retain a small brand signature, strong text contrast, mobile legibility, and a clear primary insight. Templates should use **abstracted product-inspired UI**, not trademark-dependent or pixel-for-pixel imitations of a platform interface. The brand’s own tokens should inform the accent colour wherever practical, while neutral paper, ink, system, and whiteboard treatments may provide useful contrast for a feed.

## Rollout

The first release implements all twelve families above and exposes one 1:1, 4:5, or 16:9 format per family. The next release can add per-family aspect-ratio variants after real performance data identifies which categories earn saves, shares, clicks, and completions for each brand.
