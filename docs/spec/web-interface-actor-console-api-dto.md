# Web Interface Actor Console API DTO Appendix

Status: Phase two/three DTO target.

## Route Inventory

Add these Web-interface API routes:

```text
GET /api/actors
GET /api/actors/{actor_id}/console
GET /api/tracks
GET /api/tracks/{track_id}
```

Reuse these existing route families:

```text
/api/web/im/*
/api/instances/*
/api/health
/api/roles
```

`/api/im/*` remains the lower external Central IM contract and is not exposed directly to Browser JavaScript through Web Management.

Do not add these first-cut routes:

```text
GET /api/actors/{actor_id}/tasks
GET /api/actors/{actor_id}/tracks
GET /api/tracks/{track_id}/comments
```

## GET /api/actors

Response:

```json
{
  "ok": true,
  "actors": [
    {
      "actor_id": "act-pm-demo",
      "role": "pm",
      "status": "active",
      "app_server_health": "healthy",
      "thread_id": "thread-main",
      "browser_port": 9222,
      "updated_at": "2026-06-26T10:00:00Z",
      "workspace_dir": "/tmp/buddyswitch/instances/act-pm-demo/workspace",
      "runtime": {
        "status": "active",
        "app_server_health": "healthy",
        "thread_id": "thread-main",
        "browser_port": 9222
      }
    }
  ]
}
```

Notes:

- The source is host-control instance list.
- This is a Web DTO, not a raw launcher JSON contract.

## GET /api/actors/{actor_id}/console

Response:

```json
{
  "ok": true,
  "console": {
    "actor": {
      "actor_id": "act-pm-demo",
      "role": "pm"
    },
    "runtime": {
      "status": "active",
      "app_server_health": "healthy",
      "thread_id": "thread-main",
      "thread_status": "idle",
      "browser_port": 9222,
      "updated_at": "2026-06-26T10:00:00Z",
      "workspace_dir": "/tmp/buddyswitch/instances/act-pm-demo/workspace"
    },
    "task": {
      "owner_actor": {
        "actor_id": "act-pm-demo",
        "role_id": "pm"
      },
      "current_anchor": null,
      "task_state": "none",
      "shelf": [],
      "warnings": []
    },
    "tracks": {
      "items": [],
      "source": "web-track-summary"
    },
    "im": {
      "target": {
        "kind": "actor",
        "actor_address": {
          "role_id": "pm",
          "actor_id": "act-pm-demo"
        }
      }
    }
  }
}
```

Notes:

- `task` may include additional fields returned by the existing task domain read model.
- `tracks.items` is a summary area for the console. It is not a separate actor-owned Track API.
- `im.target` is convenience metadata for the Browser composer.

## GET /api/tracks

Response:

```json
{
  "ok": true,
  "tracks": [
    {
      "id": "track-alpha",
      "title": "Actor console",
      "outcome": "Ship actor-centered Web management.",
      "owner_actor": {
        "role_id": "pm",
        "actor_id": "act-pm-demo"
      },
      "state": "active",
      "now": {
        "next": "Implement Web DTOs.",
        "blocker": null
      },
      "acceptance_criteria": [],
      "non_goals": [],
      "updated_at": "2026-06-26T10:00:00Z",
      "comment_summary": {
        "open_thread_count": 0,
        "comment_count": 0
      }
    }
  ]
}
```

Notes:

- Archived Tracks are excluded.
- This response is optimized for list scanning.

## GET /api/tracks/{track_id}

Response:

```json
{
  "ok": true,
  "track": {
    "id": "track-alpha",
    "title": "Actor console",
    "outcome": "Ship actor-centered Web management.",
    "owner_actor": {
      "role_id": "pm",
      "actor_id": "act-pm-demo"
    },
    "state": "active",
    "now": {
      "next": "Implement Web DTOs.",
      "blocker": null
    },
    "acceptance_criteria": [],
    "non_goals": [],
    "materials": [],
    "proofs": [],
    "updates": [],
    "comment_threads": [],
    "comment_summary": {
      "open_thread_count": 0,
      "resolved_thread_count": 0,
      "comment_count": 0
    },
    "updated_at": "2026-06-26T10:00:00Z"
  }
}
```

Notes:

- Comments are included in this detail DTO.
- The Browser does not need a separate comments route for the first cut.
- The lower domain helper, if added, speaks in Track semantics only: detail, summary, comments, threads.

## Error Shape

Use the existing Web API error envelope:

```json
{
  "ok": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "track not found: track-alpha"
  }
}
```

Expected codes:

- `INVALID_REQUEST` for malformed actor ids.
- `NOT_FOUND` for missing or archived Tracks.
- Existing command failure codes for launcher command failures.
