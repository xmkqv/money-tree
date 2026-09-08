---
name: stagepass
vendors:
  payments: stripe
  mail: postmark
---

- an organizer adds an event and publishes its shows
- a buyer holds seats, pays once, and receives one ticket per seat
- a gate scans a ticket and admits it one time
- an organizer refunds an order or cancels a show, and the affected tickets stop admitting

```sql:types
type money_minor = int8 check(value ≥ 0)
type ticket_code = text check(len(value) = 32)
```

```sh:surface
stagepass event add FILE
stagepass show publish SHOW
stagepass show cancel SHOW --reason TEXT
stagepass seat hold SHOW SEAT… --session KEY
stagepass order buy HOLD… --email EMAIL --payment TOKEN
stagepass order refund ORDER --reason TEXT
stagepass ticket scan CODE --gate GATE
```

```ts:private
cron:release_holds[1m]()
    set hold[state=active, expires_at ≤ now()] state = expired

cron:send_reminders[1h]()
    show[state=published, starts_at ∈ now()+1day ± 30min].each(show →
        order[show_id=show.id, state=paid].each(order → vendor[mail].send(order.email, reminder(show)))
    )
```

- a show price is in the currency of its event
- a published show keeps its [venue][venue] and seat plan
- a ticket code is secret and admits one time

# catalog

```sql:types
enum show_state { draft, published, cancelled, complete }

event(
    id pk
    key nn uq text check(len(key) > 0)
    title nn text
    currency nn text check(value is ISO-4217)
)
show(
    id pk
    event_id nn → event.id
    venue_id nn → $venue.venue.id
    starts_at nn datetime
    state nn show_state default draft
    price nn money_minor
)
```

```ts:surface
publishShow(showId)
    inv:show.state ≠ draft → error
    inv:$venue.seatPlan(show.venue_id) is incomplete → error
    set show[id=showId] state = published

cancelShow(showId, reason)
    inv:show.state ≠ published → error
    set show[id=showId] state = cancelled
    order[show_id=showId, state=paid].each(order →
        refundOrder(order.id, reason)
        vendor[mail].send(order.email, cancellation(show, reason))
    )
```

# sales

```sql:types
enum hold_state { active, expired, converted }
enum order_state { pending, paid, refunded }

hold(
    id pk
    show_id nn → show.id
    seat_id nn → $venue.seat.id
    session_key nn text
    state nn hold_state default active
    expires_at nn datetime
    uq(show_id, seat_id) where state = active
)
order(
    id pk
    show_id nn → show.id
    email nn text
    state nn order_state default pending
    total nn money_minor
    payment_key uq text
    refund_reason text
    created_at nn datetime default now()
)
ticket(
    id pk
    order_id nn → order.id
    seat_id nn → $venue.seat.id
    code nn uq ticket_code
    voided_at datetime
    uq(order_id, seat_id)
)
```

```ts:surface
holdSeats(showId, seatIds, sessionKey) → Hold[]
    inv:show.state ≠ published → error
    inv:any seat ∉ $venue.seatIds(show.venue_id) → error
    inv:any seat has an active hold or a ticket for the show → error
    create one active hold per seat with expires_at = now() + 10min

buyOrder(holdIds, email, paymentToken) → Order
    inv:holds span more than one show or session → error
    inv:any hold.state ≠ active → error
    total = sum(show.price) over holds
    payment_key = vendor[payments].charge(paymentToken, total, event.currency)
    create paid order with one ticket per hold
    set hold[id ∈ holdIds] state = converted

refundOrder(orderId, reason)
    inv:order.state ≠ paid → error
    vendor[payments].refund(order.payment_key)
    set ticket[order_id=orderId] voided_at = now()
    set order[id=orderId] state = refunded, refund_reason = reason
```

# entry

```sql:types
entry(
    id pk
    ticket_id nn uq → ticket.id
    gate nn text
    scanned_at nn datetime default now()
)
```

```ts:surface
scanTicket(code, gate) → admitted | duplicate | rejected
    ticket = ticket[code=code]
    return rejected if ticket is absent, voided, or its show is cancelled
    return duplicate with the first entry if entry[ticket_id=ticket.id] exists
    create entry
    return admitted
```

# refs

[venue]: ../venue/spec.md
