# S5 C2 Preflight Command

> Evidence ID: `S5C2P-20260804-02`
> Executable base: `e687fa264408de0bf70f7f7411194e78d044dad9`
> Runtime source: `8a0bbe8f7607cad0e574b6ce17a0aac4a68cab13d907b21eeb11999f15682a64`
> Purpose: historical READY evidence; not an executor command transcript

The hub ran this exact read-only command from the repository root:

```bash
BUDDYSWITCH_RUNTIME_DIR="$PWD/.buddyswitch-runtime" \
.buddyswitch-runtime/venv/bin/python - <<'PY'
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit

from buddyswitch.application.build import build_application
from buddyswitch.runtime_support.env_cleanup import CleanupContribution, CleanupIndexProjection

calls: list[str] = []

@dataclass(frozen=True)
class RouteRegistration:
    name: str
    factory: Callable[[], object]
    exact_paths: tuple[str, ...] = ()
    prefixes: tuple[str, ...] = ()

def overlaps(left: RouteRegistration, right: RouteRegistration) -> bool:
    if set(left.exact_paths) & set(right.exact_paths):
        return True
    if any(path.startswith(prefix) for path in left.exact_paths for prefix in right.prefixes):
        return True
    if any(path.startswith(prefix) for path in right.exact_paths for prefix in left.prefixes):
        return True
    return any(a.startswith(b) or b.startswith(a) for a in left.prefixes for b in right.prefixes)

def validate_routes(items: tuple[RouteRegistration, ...], reserved: tuple[RouteRegistration, ...] = ()) -> None:
    names: set[str] = set()
    accepted: list[RouteRegistration] = list(reserved)
    for item in items:
        assert item.name and item.name not in names
        assert item.exact_paths or item.prefixes
        names.add(item.name)
        assert len(item.exact_paths) == len(set(item.exact_paths))
        assert len(item.prefixes) == len(set(item.prefixes))
        for path in item.exact_paths:
            assert path.startswith('/api/') and '?' not in path and '#' not in path
        for prefix in item.prefixes:
            assert prefix.startswith('/api/') and prefix.endswith('/') and '?' not in prefix and '#' not in prefix
        assert not any(overlaps(item, other) for other in accepted)
        accepted.append(item)

def dispatch(items: tuple[RouteRegistration, ...], request: str) -> str | None:
    path = urlsplit(request).path
    for item in items:
        if path in item.exact_paths or any(path.startswith(prefix) for prefix in item.prefixes):
            item.factory()
            return item.name
    return None

routes = (
    RouteRegistration('track-read', lambda: calls.append('track') or object(), exact_paths=('/api/tracks',), prefixes=('/api/tracks/',)),
    RouteRegistration('communication-im', lambda: calls.append('im') or object(), prefixes=('/api/im/',)),
)
reserved = (RouteRegistration('host-instances', lambda: object(), exact_paths=('/api/instances',), prefixes=('/api/instances/',)),)
validate_routes(routes, reserved)
assert calls == []
assert dispatch(routes, '/api/tracks?state=open') == 'track-read'
assert dispatch(routes, '/api/tracks/track-alpha') == 'track-read'
assert dispatch(routes, '/api/im/messages?cursor=1') == 'communication-im'
assert dispatch(routes, '/api/tracks-extra') is None
assert dispatch(routes, '/api/imposter') is None
for invalid in (
    RouteRegistration('track-read', lambda: object(), exact_paths=('/api/other',)),
    RouteRegistration('duplicate-exact', lambda: object(), exact_paths=('/api/tracks',)),
    RouteRegistration('overlap-prefix', lambda: object(), prefixes=('/api/im/admin/',)),
    RouteRegistration('reserved-overlap', lambda: object(), prefixes=('/api/instances/admin/',)),
):
    try:
        validate_routes(routes + (invalid,), reserved)
    except AssertionError:
        pass
    else:
        raise AssertionError(f'route collision must fail: {invalid.name}')

application = build_application()
base_plan_fields = {'scope', 'role', 'delete_paths', 'warnings', 'counts_by_category', 'direct_delete_paths', 'external_delete_paths'}
plan_fields = set(base_plan_fields)
projection_fields: dict[str, str] = {}
for contribution in application.cleanup:
    projection = contribution.index_projection
    if projection is None:
        continue
    assert projection.object_ids_field != projection.records_field
    for field in (projection.object_ids_field, projection.records_field):
        assert field not in plan_fields
        plan_fields.add(field)
    projection_fields[projection.object_ids_field] = projection.records_field
assert projection_fields == {
    'artifact_object_ids': 'artifact_records',
    'comment_object_ids': 'comment_records',
    'message_object_ids': 'message_records',
}
probe = CleanupContribution(
    category='probe_objects',
    discover=lambda _root: (),
    index_projection=CleanupIndexProjection('probe_object_ids', 'probe_records'),
)
for field in (probe.index_projection.object_ids_field, probe.index_projection.records_field):
    assert field not in plan_fields
    plan_fields.add(field)
for invalid_projection in (
    CleanupIndexProjection('warnings', 'probe_records_2'),
    CleanupIndexProjection('probe_object_ids', 'probe_records_3'),
    CleanupIndexProjection('same', 'same'),
):
    try:
        candidate = set(plan_fields)
        assert invalid_projection.object_ids_field != invalid_projection.records_field
        for field in (invalid_projection.object_ids_field, invalid_projection.records_field):
            assert field not in candidate
            candidate.add(field)
    except AssertionError:
        pass
    else:
        raise AssertionError(f'projection collision must fail: {invalid_projection}')
print('S5C2P-20260804-02 PASS')
print('web positive=3 neighbor_negative=2 collisions=4 passive_factory=true')
print('cleanup current_contributions=' + ','.join(item.category for item in application.cleanup))
print('cleanup projection_fields=' + ','.join(sorted(projection_fields)))
print('cleanup novel_projection=probe_object_ids/probe_records collisions=3')
PY
```

Output:

```text
S5C2P-20260804-02 PASS
web positive=3 neighbor_negative=2 collisions=4 passive_factory=true
cleanup current_contributions=demand_aggregates,task_records,artifact_objects,artifact_attachments,track_objects,comment_objects,message_objects
cleanup projection_fields=artifact_object_ids,comment_object_ids,message_object_ids
cleanup novel_projection=probe_object_ids/probe_records collisions=3
```

The command created no file or long-lived resource. It tested a final-shaped
mechanism against the actual current application contribution set; production
implementation proof remains executor-owned.
