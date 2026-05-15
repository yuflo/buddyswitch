# Track Registry

Tracks are collaboration lanes with explicit task relations.

Track fields:
- `id`
- `title`
- `status`
- `current_buddy`
- `next_buddy`
- `task_ids`
- `summary`
- `updated_at`

Task fields (runless):
- `id`, `buddy`, `title`, `status`, `track_id`
- `artifact_ids`, `artifact_slots`
- `summary`, `created_at`, `updated_at`

Artifact fields (runless provenance):
- `created_by`
- `source_refs`
