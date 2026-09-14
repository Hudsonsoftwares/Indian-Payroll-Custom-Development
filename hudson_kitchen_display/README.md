# Kitchen Display System (Custom KDS) for Odoo Community — v2

A from-scratch module recreating Odoo Enterprise's "Preparation Display"
workflow, plus the extra features requested on top of the v1 base:
undo/back, audio + visual late-order alerts, dark/high-contrast mode,
responsive layout, manager reporting, role-based access, and a manual
"Send to Kitchen" action.

## Install

1. Copy `hudson_kitchen_display` into your Odoo addons path.
2. Restart Odoo, **Apps > Update Apps List**, install
   "Kitchen Display System (Custom KDS)".
3. **Point of Sale > Orders > Preparation Display** to configure a display.
4. **Point of Sale > Orders > Kitchen Order History** (managers only) for the
   audit trail / average prep-time report.

## What's new in v2

### 1. Trigger point: order creation (confirmed, unchanged)
Orders are still sent to the kitchen the moment a `pos.order` record is
created (`models/pos_order.py: create()`). Left as-is per your call.
`action_manual_send_to_kitchen()` is available for anything created
afterward (see "Manual send" below).

### 2. Field-name differences — centralized in `utils.py`
All the version-sensitive lookups (`pos_categ_ids` vs `pos_categ_id`,
table numbering field, order-line note field, fulfillment-type
detection) now live in one file, `utils.py`, instead of being scattered
inline. If your Odoo version needs a different field name, that's the
only file to touch.

### 3. Manual "Send to Kitchen"
- **Robust version**: `pos.order.action_manual_send_to_kitchen()` — call
  it from a backend button, from a scheduled action, or via
  `/hudson_kitchen_display/manual_send/<order_id>`. Never duplicates a
  line that's already on a display, so it's safe to call repeatedly —
  useful for kiosk/self-order flows or items added after the initial
  send.
- **Experimental in-POS floating button**
  (`static/src/js/pos_send_button.js`, loaded into the
  `point_of_sale._assets_pos` bundle): a plain floating button on the
  live POS screen. Rather than patching Odoo's OWL components (which
  reshape often enough between versions to break silently), it calls
  `/hudson_kitchen_display/manual_send_last_order`, which resends the
  current cashier's most recent order (last 30 min). This is a
  heuristic — fine for a single-cashier terminal, less precise on a
  shared/multi-till login. If your Odoo version's POS bundle isn't
  named `point_of_sale._assets_pos` (older versions use
  `point_of_sale.assets`), update that key in `__manifest__.py`.

### 4. Preparation timers + visual/audio alerts
Each stage keeps its `alert_timer` (minutes). A card older than that
turns red (`kd-late` class) and the kitchen screen plays a short beep
(Web Audio API — no sound files needed) the first time a late order is
rendered, and again whenever a brand-new order arrives. A speaker icon
in the header toggles sound on/off (saved in the browser's
localStorage per screen).

### 5. Dark mode / high-contrast mode
The screen already runs dark by default. The **Contrast** button in the
header switches to a black/yellow high-contrast palette (bigger visual
separation for glare-heavy kitchen lighting), saved per browser.

### 6. Undo / back button
Every card now has an **Undo** button next to Advance, moving the order
back one stage — direct fix for the "no way to recover from a mis-tap"
complaint seen in third-party module reviews. Disabled automatically on
an order's first stage.

### 7. Responsive layout
CSS media queries reflow the sidebar to a horizontal bar and stack cards
full-width under ~900px (phone/small tablet), and enlarge cards/text
above 1600px (wall-mounted TV). Same HTML/JS, just CSS breakpoints.

### 8. Table number & notes
Already surfaced in v1 (table number or fulfillment type under the
order number; per-line notes in yellow) — unchanged, still there.

### 9. Manager backend view: history + average prep time
New model `pos.prep.order.stage.log` records every stage transition.
`pos.prep.order` now has `done_date` and a computed `prep_duration`
(minutes from creation to the last stage). **Point of Sale > Kitchen
Order History** gives you a list view plus pivot/graph (average prep
time by display × fulfillment type) for manager auditing.

### 10. Role-based access — "Kitchen Screen Access"
`res.users` gets a `kitchen_screen_access` boolean (Settings > Users >
a user's form, under the Access Rights tab — the exact tab's technical
name has changed across Odoo versions; if the checkbox doesn't show up,
open `views/res_users_views.xml` and adjust the `xpath` there to target
whichever notebook page exists in your version). Kitchen routes now
check `_has_kitchen_access()`: POS users/managers always get in; anyone
else needs this flag — useful for a kitchen-only login that shouldn't
also see backoffice/POS data.

### 11. Self-Order Kiosk / QR compatibility
No separate integration needed: as long as kiosk/self-order orders are
created through the standard `pos.order` model (true for Odoo's own
Self Order app and most third-party kiosk modules), they pass through
the same `create()` hook and reach the kitchen automatically.
`utils.get_fulfillment_type()` checks for a `takeaway` field (common on
self-order modules) so kiosk takeaway orders are tagged correctly —
adjust that helper if your kiosk module uses a different field name.

### 12. Near real-time updates (addressing the "manual refresh" complaint)
Stage changes now also emit a `bus.bus` ping on a per-display channel.
The kitchen screen opens a best-effort WebSocket subscription
(`/websocket`) and refreshes instantly on any ping, with an 8-second
poll kept running underneath as a safety net in case the WebSocket
path/protocol differs on your Odoo version or is blocked by a proxy.

### 13. `pos_hr` compatibility
Table/employee-session field access goes through `getattr`/`hasattr`
checks throughout, so a missing `pos_hr`-related field won't crash the
module — test with `pos_hr` installed on a staging DB before relying on
per-employee session data in the kitchen flow, since that module adds
its own layer on top of `pos.order`/`pos.session` that this addon
doesn't specifically target.

## Known trade-offs to test on your own instance

- The in-POS floating button is intentionally simple/heuristic (see
  above) rather than a deep OWL patch — safer against version drift,
  less precise on shared tills.
- WebSocket channel names (`pos_prep_display-<id>`,
  `pos_prep_order_status-<order_id>`) are custom to this module; nothing
  else needs to know about them.
- `res_users_views.xml`'s xpath target may need adjusting per version
  (noted above).
- As before: verify `pos_categ_ids`/`pos_categ_id`, table-number field,
  and order-line note field for your exact Odoo release via `utils.py`.

Test on a staging database before using on a live restaurant floor.
