Track payload examples for `python3 scripts/env/client.py track <operation> --payload <json>`.

Create:

```json
{
  "track_id": "track-example",
  "title": "Example Track",
  "status": "active",
  "current_buddy": "pm",
  "next_buddy": "dev",
  "summary": "Why this track exists."
}
```

Advance:

```json
{
  "track_id": "track-example",
  "current_buddy": "dev",
  "next_buddy": "test",
  "summary": "Why the next buddy should continue."
}
```
