# A2 catalog — festival consumer manual test (for B2)

Publish to exchange `platform.events`, routing key `festival.started`:

```json
{
  "eventId": "manual-fest-1",
  "eventName": "festival.started",
  "occurredAt": "2026-07-28T00:00:00+00:00",
  "correlationId": "manual",
  "producer": "manual",
  "version": 1,
  "payload": {
    "festivalId": "fest-1",
    "entries": [{"gameId": "<PUBLISHED_GAME_ID>", "discountPercent": 20}],
    "startsAt": "2020-01-01T00:00:00+00:00",
    "endsAt": "2099-01-01T00:00:00+00:00"
  }
}
```

Then `GET /api/v1/catalog/games/{id}/effective-price` should show discountPercent 20.
Publish `festival.ended` with `{"festivalId":"fest-1"}` to clear.
