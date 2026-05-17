## `track.create` payload

```json
{
  "track_id": "track-onboarding",
  "title": "Onboarding polish",
  "outcome": "Reduce first-use friction and improve activation clarity.",
  "appetite": "2 days",
  "now": {
    "next": "Review hero copy and first-run checklist.",
    "blocker": null
  }
}
```

## `track.update_now` payload

```json
{
  "track_id": "track-onboarding",
  "state": "blocked",
  "health": "risk",
  "now": {
    "next": "Align copy decision with PM and Design.",
    "blocker": "Final one-line positioning is not settled."
  }
}
```

## `track.add_update` payload

```json
{
  "track_id": "track-onboarding",
  "kind": "decision",
  "summary": "Adopt shorter hero copy and keep one primary CTA."
}
```

## `track.archive` payload

```json
{
  "track_id": "track-onboarding"
}
```
