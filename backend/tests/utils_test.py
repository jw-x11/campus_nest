import json
from datetime import datetime, timedelta, timezone
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image
from sqlalchemy.exc import IntegrityError
from starlette.datastructures import Headers

import config.s3db_config as s3db_config
from caches.space import space_search_cache_key
from caches.view_history import _member, from_micros, to_micros
from crud.view_history import _page_from_rows, decode_cursor, encode_cursor
from schemas.spaces import SpaceSearchQuery
from utils.auth import hash_password, verify_password
from utils.exception_handler import integrity_error_handler
from utils.exceptions import AppError, NotFoundError, PermissionDeniedError
from utils.images import THUMBNAIL_LONG_EDGE, resize_long_edge
from utils.response import success_response
from utils.s3 import read_image


class TestPasswordHashing:
    def test_round_trip(self):
        hashed = hash_password("hunter2hunter2")
        assert hashed != "hunter2hunter2"
        assert verify_password("hunter2hunter2", hashed)
        assert not verify_password("wrong-password", hashed)

    def test_hashes_are_salted(self):
        assert hash_password("same-password") != hash_password("same-password")

    def test_only_first_72_bytes_count(self):
        hashed = hash_password("a" * 72 + "tail-one")
        assert verify_password("a" * 72 + "tail-two", hashed)


class TestReadImage:
    def _upload(self, body: bytes, content_type: str | None) -> UploadFile:
        headers = Headers({"content-type": content_type}) if content_type else Headers({})
        return UploadFile(file=BytesIO(body), filename="photo", headers=headers)

    async def test_accepts_allowed_type(self):
        body, content_type = await read_image(self._upload(b"data", "IMAGE/PNG"))
        assert (body, content_type) == (b"data", "image/png")

    @pytest.mark.parametrize("content_type", ["application/pdf", "text/plain", None])
    async def test_rejects_unsupported_type(self, content_type):
        with pytest.raises(HTTPException) as exc:
            await read_image(self._upload(b"data", content_type))
        assert exc.value.detail == "UNSUPPORTED_MEDIA_TYPE"

    async def test_rejects_empty_file(self):
        with pytest.raises(HTTPException) as exc:
            await read_image(self._upload(b"", "image/png"))
        assert exc.value.detail == "EMPTY_FILE"

    async def test_rejects_oversized_file(self):
        with pytest.raises(HTTPException) as exc:
            await read_image(self._upload(b"x" * (s3db_config.MAX_BYTES + 1), "image/jpeg"))
        assert exc.value.detail == "FILE_TOO_LARGE"


class TestResizeLongEdge:
    def _open(self, body: bytes) -> Image.Image:
        return Image.open(BytesIO(body))

    @pytest.mark.parametrize(
        "content_type, fmt", [("image/png", "PNG"), ("image/jpeg", "JPEG"),
                              ("image/webp", "WEBP"), ("image/gif", "GIF")]
    )
    def test_shrinks_to_long_edge_and_keeps_format(self, image_bytes, content_type, fmt):
        body, out_type = resize_long_edge(image_bytes(1600, 900, fmt), content_type)
        image = self._open(body)
        assert out_type == content_type
        assert image.format == fmt
        assert image.size == (THUMBNAIL_LONG_EDGE, 225)

    def test_portrait_uses_height_as_long_edge(self, image_bytes):
        body, _ = resize_long_edge(image_bytes(300, 1200), "image/png")
        assert self._open(body).size == (100, THUMBNAIL_LONG_EDGE)

    def test_small_image_is_not_upscaled(self, image_bytes):
        body, _ = resize_long_edge(image_bytes(120, 80), "image/png")
        assert self._open(body).size == (120, 80)

    def test_jpeg_output_drops_alpha(self, image_bytes):
        body, _ = resize_long_edge(image_bytes(800, 800, "PNG", mode="RGBA"), "image/jpeg")
        assert self._open(body).mode == "RGB"

    def test_rejects_non_image_bytes(self):
        with pytest.raises(HTTPException) as exc:
            resize_long_edge(b"definitely not an image", "image/png")
        assert exc.value.status_code == 400
        assert exc.value.detail == "INVALID_IMAGE"


class TestS3UrlHelpers:
    @pytest.mark.parametrize(
        "url, expected",
        [
            ("/media/spaces/1/abc.jpg", "/media/spaces/1/abc-thumb.jpg"),
            ("http://host/a.b/photo.png", "http://host/a.b/photo-thumb.png"),
            ("/media/no-extension", "/media/no-extension-thumb"),
        ],
    )
    def test_to_thumbnail_url(self, url, expected):
        assert s3db_config.to_thumbnail_url(url) == expected

    def test_public_url_joins_without_double_slash(self, monkeypatch):
        monkeypatch.setattr(s3db_config, "S3_PUBLIC_URL", "/media/")
        assert s3db_config.public_url("/avatars/1.png") == "/media/avatars/1.png"

    @pytest.mark.parametrize(
        "url, expected",
        [
            ("/media/avatars/u/1.png", "avatars/u/1.png"),
            ("http://localhost/media/avatars/u/1.png", "avatars/u/1.png"),
            ("http://s3:8333/campus-nest/spaces/1/a.jpg", "spaces/1/a.jpg"),
            ("https://elsewhere.com/other/a.jpg", None),
            ("", None),
        ],
    )
    def test_key_from_url(self, monkeypatch, url, expected):
        monkeypatch.setattr(s3db_config, "S3_PUBLIC_URL", "/media")
        monkeypatch.setattr(s3db_config, "S3_BUCKET", "campus-nest")
        assert s3db_config.key_from_url(url) == expected


class TestSearchCacheKey:
    def _key(self, **params) -> str:
        return space_search_cache_key(SpaceSearchQuery.model_validate(params))

    def test_text_filters_are_case_insensitive(self):
        assert self._key(kw="Garage", city="BERKELEY") == self._key(kw="garage", city="berkeley")

    def test_missing_sort_matches_newest_first(self):
        assert self._key() == self._key(sort="post_date") == self._key(sort="post_date", order="desc")
        assert self._key() != self._key(sort="post_date", order="asc")

    def test_default_sort_order_per_field(self):
        assert self._key(sort="price") == self._key(sort="price", order="asc")

    def test_paging_shares_one_key(self):
        assert self._key(pg=1, **{"pg-size": 5}) == self._key(pg=3, **{"pg-size": 50})

    @pytest.mark.parametrize(
        "params",
        [{"kw": "x"}, {"city": "Oakland"}, {"pc": "94"}, {"from": "2026-01-01"}, {"to": "2026-01-01"},
         {"price-type": "single"}, {"min": 5}, {"max": 5}, {"sort": "price"}],
    )
    def test_each_filter_changes_key(self, params):
        assert self._key(**params) != self._key()


class TestHistoryCursor:
    def test_round_trip(self):
        viewed_at = datetime(2026, 5, 4, 3, 2, 1, 123456, tzinfo=timezone.utc)
        assert decode_cursor(encode_cursor(42, viewed_at)) == (to_micros(viewed_at), 42)

    def test_cursor_is_url_safe_without_padding(self):
        cursor = encode_cursor(1, datetime.now(timezone.utc))
        assert "=" not in cursor and "+" not in cursor and "/" not in cursor

    # "not-a-cursor", "1:2:3" and "abc:def" once base64-encoded.
    @pytest.mark.parametrize("cursor", ["!!!", "bm90LWEtY3Vyc29y", "MToyOjM", "YWJjOmRlZg"])
    def test_malformed_cursor_raises_value_error(self, cursor):
        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor(cursor)

    def test_micros_round_trip_is_exact(self):
        value = datetime(2030, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc)
        assert from_micros(to_micros(value)) == value

    def test_member_is_zero_padded_for_lexical_order(self):
        assert _member(7) == "0000000007"
        assert sorted([_member(10), _member(9)]) == [_member(9), _member(10)]

    def test_page_from_rows_is_strictly_after_cursor(self):
        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        rows = [(5, t0), (4, t0), (3, t0 - timedelta(seconds=1)), (2, t0 - timedelta(seconds=2))]
        page, has_more = _page_from_rows(rows, (to_micros(t0), 5), limit=2)
        assert [space_id for space_id, _ in page] == [4, 3]
        assert has_more is True
        page, has_more = _page_from_rows(rows, (to_micros(t0), 4), limit=2)
        assert [space_id for space_id, _ in page] == [3, 2]
        assert has_more is False


class TestResponsesAndErrors:
    def test_success_response_envelope(self):
        resp = success_response(message="ok", data={"when": datetime(2026, 1, 1, tzinfo=timezone.utc)})
        assert resp.status_code == 200
        assert json.loads(resp.body) == {
            "code": 200, "message": "ok", "data": {"when": "2026-01-01T00:00:00+00:00"},
        }

    def test_app_error_defaults(self):
        assert NotFoundError().status_code == 404
        assert NotFoundError().message == "Resource not found"
        assert PermissionDeniedError("nope").message == "nope"
        assert str(AppError()) == "Internal Server Error"

    @pytest.mark.parametrize(
        "orig, message",
        [
            ("Duplicate entry 'x'", "Username already exists"),
            ("violates FOREIGN KEY constraint", "Associated data does not exist"),
            ("check constraint failed", "Data constraint conflict, please check the input"),
        ],
    )
    async def test_integrity_error_handler(self, orig, message):
        request = SimpleNamespace(url="http://test/api/x")
        resp = await integrity_error_handler(request, IntegrityError("stmt", {}, Exception(orig)))
        body = json.loads(resp.body)
        assert resp.status_code == 400
        assert body["message"] == message
        assert body["data"]["error_type"] == "IntegrityError"
