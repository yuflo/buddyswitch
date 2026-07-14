from __future__ import annotations

from io import BytesIO

from tests.support.fake_cdp import (
    read_client_text_frame,
    websocket_accept_value,
    write_server_text_frame,
)


def test_websocket_accept_matches_rfc_example() -> None:
    assert websocket_accept_value("dGhlIHNhbXBsZSBub25jZQ==") == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="


def test_reads_masked_client_text_frame() -> None:
    payload = b"hello"
    mask = b"mask"
    masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))

    assert read_client_text_frame(BytesIO(bytes([0x81, 0x80 | len(payload)]) + mask + masked)) == "hello"


def test_writes_unmasked_server_text_frame() -> None:
    stream = BytesIO()

    write_server_text_frame(stream, "hello")

    assert stream.getvalue() == b"\x81\x05hello"
