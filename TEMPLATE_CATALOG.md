# Visual Factory Template Catalog

## Library scope

Visual Factory Kit now contains **36 differentiated social-media template families**: twelve social-native category templates and twenty-four additional editorial, interface, data, system, community, proof, and campaign layouts. Each template is deterministic HTML/CSS, consumes the established brand and proof fields, supports optional non-sensitive `template_data`, and routes through the existing image QA and provenance workflow.

> **Interface-content guardrail:** Templates inspired by messages, reviews, inboxes, maps, or documents are illustrative abstractions. Use fictional or approved content only; do not imply access to private accounts, conversations, transactions, reviews, or location data.

## Extended catalog

| # | Format key | Family | Best use | Primary ratio |
| --- | --- | --- | --- | --- |
| 13 | `browser_tab_card_square` | Browser-tab card | Search-led education and product positioning | 1:1 |
| 14 | `crm_pipeline_landscape` | CRM pipeline | Lead progress, handoff, and response stories | 16:9 |
| 15 | `calendar_agenda_portrait` | Calendar agenda | Events, launches, and implementation schedules | 4:5 |
| 16 | `slack_update_square` | Team update | Community announcements and internal-win narratives | 1:1 |
| 17 | `highlighted_excerpt_portrait` | Highlighted excerpt | Insights, source-backed pull-outs, and founder notes | 4:5 |
| 18 | `redline_document_portrait` | Redline document | Before/after copy, revisions, and audit observations | 4:5 |
| 19 | `feedback_form_square` | Feedback form | Research takeaways, product feedback, and listening posts | 1:1 |
| 20 | `rating_review_square` | Rating review | Approved social proof and review highlights | 1:1 |
| 21 | `map_pin_portrait` | Map pin | Local presence, service areas, and location-led posts | 4:5 |
| 22 | `terminal_log_landscape` | Terminal log | Technical proof, build updates, and operations content | 16:9 |
| 23 | `browser_window_landscape` | Browser window | Website, workflow, and product-launch messages | 16:9 |
| 24 | `kanban_board_landscape` | Kanban board | Work-in-progress, planning, and operating-system content | 16:9 |
| 25 | `polaroid_quote_square` | Polaroid quote | Warm founder-led stories and approved customer moments | 1:1 |
| 26 | `newspaper_cover_portrait` | Newspaper cover | Big announcements, trend takes, and bold hooks | 4:5 |
| 27 | `pricing_menu_square` | Pricing menu | Offer framing, package comparisons, and value clarity | 1:1 |
| 28 | `data_bar_chart_square` | Data bar chart | Benchmark and proof posts with clean visual comparison | 1:1 |
| 29 | `funnel_map_landscape` | Funnel map | Demand generation, customer journey, and system models | 16:9 |
| 30 | `product_release_square` | Product release | Feature drops, new capabilities, and release notes | 1:1 |
| 31 | `case_study_chapter_portrait` | Case-study chapter | Outcome-led proof and transformation narratives | 4:5 |
| 32 | `before_after_portrait` | Before / after | Contrast-led transformations and point-of-view posts | 4:5 |
| 33 | `offer_stack_square` | Offer stack | Value stack, bundle composition, and campaign offers | 1:1 |
| 34 | `countdown_portrait` | Countdown | Deadlines, events, and time-sensitive launches | 4:5 |
| 35 | `do_dont_square` | Do / don't | Educational contrast, best practices, and myth correction | 1:1 |
| 36 | `carousel_cover_portrait` | Carousel cover | Swipeable teaching series and long-form social narratives | 4:5 |

## Initial social-native catalog

The initial twelve are documented in `TEMPLATE_LIBRARY_SPEC.md`: Notes sheet, message thread, public-post card, search/autocomplete, receipt audit, operating checklist, whiteboard model, metrics scorecard, launch calendar, testimonial quote, inbox alert, and workflow timeline.

## Rendering the full catalog

```bash
python visual_factory/render.py render --request examples/template-catalog-request.json --brand brand-packs/kaicalls
```

The example request creates one output per extended category. Copy the file and replace the generic display data with **approved, non-sensitive brand content**.
