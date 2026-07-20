"""Capacity proof for the existing single-session External IM HTTP path."""

from __future__ import annotations

from dataclasses import dataclass
import math
import threading
import time
from typing import Any

from env.repos import identities as identity_repo
from env.services import messages as message_service
from tests.support.runtime import RuntimeWorkspaceTestCase
from tools.launcher import im_http_router, imessage_channel, web_management


CONTACT_COUNT = 100
ACTIVE_CONTACT_COUNT = 20
BURST_EVENT_COUNT = 50
IDLE_SWEEP_P95_LIMIT_SECONDS = 1.0
DISCOVERY_P95_LIMIT_SECONDS = 1.0
DISCOVERY_P99_LIMIT_SECONDS = 1.5
EVENT_FLOW_P99_LIMIT_SECONDS = 0.5
BURST_DRAIN_LIMIT_SECONDS = 5.0


@dataclass(frozen=True)
class _ProbeSession:
    key: str
    identity: dict[str, str]


class _RouterService:
    def __init__(self, router: im_http_router.ImHttpRouter) -> None:
        self._router = router

    def handle_api(
        self,
        method: str,
        path: str,
        body: bytes,
        headers: Any,
    ) -> tuple[int, dict[str, Any]]:
        return self._router.handle(method, path, body, headers)


def _nearest_rank(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


class ExternalEventCapacityTests(RuntimeWorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        router = im_http_router.ImHttpRouter(actor_lister=lambda _role_id: [])
        self._server = web_management.create_server("127.0.0.1", 0, _RouterService(router))
        self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._server_thread.start()
        host, port = self._server.server_address
        self.api = imessage_channel.BuddySwitchImApi(f"http://{host}:{port}")
        self._expected_session_key_by_event: dict[str, str] = {}
        self._message_id_by_event: dict[str, str] = {}
        self._available_at_by_event: dict[str, float] = {}
        actor_id = self._runtime_actor_id(role="market", label="capacity-probe")
        identity_repo.save_actor_identity_profile(
            {
                "identity": {"id": actor_id, "type": "actor"},
                "role_id": "market",
            }
        )
        self.actor_identity = {"id": actor_id, "type": "actor"}

    def tearDown(self) -> None:
        try:
            self._server.shutdown()
            self._server_thread.join(timeout=2)
            self._server.server_close()
            self.assertFalse(
                self._server_thread.is_alive(),
                "capacity probe HTTP server did not stop",
            )
        finally:
            super().tearDown()

    def _create_sessions(self) -> list[_ProbeSession]:
        sessions: list[_ProbeSession] = []
        for index in range(CONTACT_COUNT):
            created = self.api.create_external_session(display_name=f"capacity contact {index:03d}")
            self.assertTrue(created.get("ok"), msg=created)
            key = created.get("external_session_key")
            identity = created.get("identity")
            self.assertIsInstance(key, str, msg=created)
            self.assertIsInstance(identity, dict, msg=created)
            assert isinstance(key, str)
            assert isinstance(identity, dict)
            sessions.append(_ProbeSession(key=key, identity=dict(identity)))
        return sessions

    def _create_event(self, session: _ProbeSession, *, label: str) -> str:
        result = message_service.send_im_message(
            sender_identity=self.actor_identity,
            target_identity=session.identity,
            content=label,
        )
        self.assertTrue(result.get("ok"), msg=result)
        event_id = str(result.get("event_id") or "")
        message = result.get("message")
        message_id = str(message.get("id") or "") if isinstance(message, dict) else ""
        self.assertTrue(event_id, msg=result)
        self.assertTrue(message_id, msg=result)
        self._expected_session_key_by_event[event_id] = session.key
        self._message_id_by_event[event_id] = message_id
        self._available_at_by_event[event_id] = time.perf_counter()
        return event_id

    def _scan_once(
        self,
        sessions: list[_ProbeSession],
    ) -> tuple[float, list[str], list[float], list[float]]:
        sweep_started = time.perf_counter()
        found: list[str] = []
        discovery_latencies: list[float] = []
        event_flow_durations: list[float] = []
        for session in sessions:
            event_flow_started = time.perf_counter()
            response = self.api.read_events(external_session_key=session.key, limit=1, wait_ms=0)
            self.assertTrue(response.get("ok"), msg=response)
            events = response.get("events")
            self.assertIsInstance(events, list, msg=response)
            assert isinstance(events, list)
            self.assertLessEqual(len(events), 1, msg=response)
            if not events:
                continue
            event = events[0]
            self.assertIsInstance(event, dict, msg=event)
            assert isinstance(event, dict)
            event_id = str(event.get("event_id") or "")
            message_id = str(event.get("message_id") or "")
            self.assertEqual(self._expected_session_key_by_event.get(event_id), session.key)
            self.assertEqual(self._message_id_by_event.get(event_id), message_id)
            fetched = self.api.get_message(external_session_key=session.key, message_id=message_id)
            self.assertTrue(fetched.get("ok"), msg=fetched)
            fetched_message = fetched.get("message")
            self.assertIsInstance(fetched_message, dict, msg=fetched)
            assert isinstance(fetched_message, dict)
            self.assertEqual(fetched_message.get("id"), message_id)
            ack = self.api.ack_event(external_session_key=session.key, event_id=event_id)
            self.assertTrue(ack.get("ok"), msg=ack)
            completed_at = time.perf_counter()
            found.append(event_id)
            discovery_latencies.append(completed_at - self._available_at_by_event[event_id])
            event_flow_durations.append(completed_at - event_flow_started)
        return time.perf_counter() - sweep_started, found, discovery_latencies, event_flow_durations

    def test_existing_single_session_http_path_meets_imessage_capacity_budget(self) -> None:
        sessions = self._create_sessions()

        _warm_duration, warm_events, _warm_discovery, _warm_flow = self._scan_once(sessions)
        self.assertEqual(warm_events, [])
        idle_sweep_durations = [self._scan_once(sessions)[0] for _ in range(5)]

        active_stride = CONTACT_COUNT // ACTIVE_CONTACT_COUNT
        active_sessions = [sessions[index * active_stride] for index in range(ACTIVE_CONTACT_COUNT)]
        active_event_ids = {
            self._create_event(session, label=f"active {index:02d}")
            for index, session in enumerate(active_sessions)
        }
        _active_sweep, active_found, active_discovery, event_flow_durations = self._scan_once(sessions)
        self.assertEqual(set(active_found), active_event_ids)
        self.assertEqual(len(active_found), ACTIVE_CONTACT_COUNT)
        _post_ack_sweep, post_ack_events, _post_discovery, _post_flow = self._scan_once(sessions)
        self.assertEqual(post_ack_events, [])

        burst_event_ids = {
            self._create_event(
                active_sessions[index % ACTIVE_CONTACT_COUNT],
                label=f"burst {index:02d}",
            )
            for index in range(BURST_EVENT_COUNT)
        }
        burst_started = time.perf_counter()
        burst_found: list[str] = []
        for _sweep in range(10):
            _duration, found, _discovery, flow = self._scan_once(sessions)
            burst_found.extend(found)
            event_flow_durations.extend(flow)
            if set(burst_found) == burst_event_ids:
                break
        burst_drain_seconds = time.perf_counter() - burst_started
        self.assertEqual(set(burst_found), burst_event_ids)
        self.assertEqual(len(burst_found), BURST_EVENT_COUNT)
        _final_sweep, final_events, _final_discovery, _final_flow = self._scan_once(sessions)
        self.assertEqual(final_events, [])

        idle_sweep_p95 = _nearest_rank(idle_sweep_durations, 0.95)
        discovery_p95 = _nearest_rank(active_discovery, 0.95)
        discovery_p99 = _nearest_rank(active_discovery, 0.99)
        event_flow_p99 = _nearest_rank(event_flow_durations, 0.99)
        print(
            "IM capacity probe: "
            f"idle_sweep_p95_ms={idle_sweep_p95 * 1000:.1f} "
            f"discovery_p95_ms={discovery_p95 * 1000:.1f} "
            f"discovery_p99_ms={discovery_p99 * 1000:.1f} "
            f"event_flow_p99_ms={event_flow_p99 * 1000:.1f} "
            f"burst_drain_ms={burst_drain_seconds * 1000:.1f}"
        )

        self.assertLessEqual(idle_sweep_p95, IDLE_SWEEP_P95_LIMIT_SECONDS)
        self.assertLessEqual(discovery_p95, DISCOVERY_P95_LIMIT_SECONDS)
        self.assertLessEqual(discovery_p99, DISCOVERY_P99_LIMIT_SECONDS)
        self.assertLessEqual(event_flow_p99, EVENT_FLOW_P99_LIMIT_SECONDS)
        self.assertLessEqual(burst_drain_seconds, BURST_DRAIN_LIMIT_SECONDS)
