"""deploy/cos_upload.py：异地备份上传到腾讯云 COS。不连网络，用假连接检查请求。"""

import base64
import hashlib
import hmac
import importlib.util
from pathlib import Path
from urllib.parse import parse_qs

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "cos_upload.py"
spec = importlib.util.spec_from_file_location("cos_upload", SCRIPT)
cos = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cos)

CONFIG = {"COS_SECRET_ID": "AKIDtest", "COS_SECRET_KEY": "secret-test", "COS_REGION": "ap-guangzhou",
          "COS_BUCKET": "demo-1250000000"}


class FakeResponse:
    def __init__(self, status, body=b""):
        self.status, self._body = status, body

    def read(self):
        return self._body


class FakeConnection:
    def __init__(self, status=200, body=b""):
        self.status, self.body, self.requests, self.closed = status, body, [], False

    def request(self, method, path, body=None, headers=None):
        self.requests.append({"method": method, "path": path, "body": body, "headers": headers})

    def getresponse(self):
        return FakeResponse(self.status, self.body)

    def close(self):
        self.closed = True


@pytest.fixture
def backup(tmp_path):
    path = tmp_path / "study_planner-20261109-033000.db.gz"
    path.write_bytes(b"\x1f\x8b fake gzip")
    return path


def test_upload_sends_signed_put_with_md5(backup):
    conn = FakeConnection()
    key = cos.upload({**CONFIG, "COS_BACKUP_PREFIX": "backup/"}, str(backup), connection=conn)
    assert key == "backup/study_planner-20261109-033000.db.gz"
    sent = conn.requests[0]
    assert sent["method"] == "PUT" and sent["path"] == "/" + key and sent["body"] == backup.read_bytes()
    headers = sent["headers"]
    assert headers["Host"] == "demo-1250000000.cos.ap-guangzhou.myqcloud.com"
    assert headers["Content-MD5"] == base64.b64encode(hashlib.md5(backup.read_bytes()).digest()).decode()
    auth = {k: v[0] for k, v in parse_qs(headers["Authorization"], keep_blank_values=True).items()}
    assert auth["q-ak"] == "AKIDtest" and auth["q-sign-algorithm"] == "sha1"
    assert auth["q-header-list"] == "content-length;content-md5;content-type;host"
    assert "secret-test" not in headers["Authorization"], "签名里不能带明文 SecretKey"
    assert conn.closed


def test_signature_follows_documented_steps():
    headers = {"Host": "b.cos.ap-guangzhou.myqcloud.com", "Content-Length": "3"}
    auth = cos.sign("id", "key", "PUT", "/backup/a.gz", headers, now=1_000_060)
    key_time = "1000000;1000600"
    http_string = "put\n/backup/a.gz\n\ncontent-length=3&host=b.cos.ap-guangzhou.myqcloud.com\n"
    to_sign = f"sha1\n{key_time}\n{hashlib.sha1(http_string.encode()).hexdigest()}\n"
    sign_key = hmac.new(b"key", key_time.encode(), hashlib.sha1).hexdigest()
    expected = hmac.new(sign_key.encode(), to_sign.encode(), hashlib.sha1).hexdigest()
    assert auth.endswith(f"q-signature={expected}") and f"q-sign-time={key_time}" in auth


def test_error_status_raises_with_cos_message(backup):
    conn = FakeConnection(403, b"<Code>AccessDenied</Code>")
    with pytest.raises(RuntimeError, match="403.*AccessDenied"):
        cos.upload(CONFIG, str(backup), connection=conn)


def test_read_env_parses_file_and_env_overrides(tmp_path, monkeypatch):
    env = tmp_path / "backend.env"
    env.write_text("# 注释\nCOS_BUCKET=\"from-file\"\nCOS_REGION=ap-guangzhou\nJWT_SECRET_KEY=ignored\n", encoding="utf-8")
    monkeypatch.setenv("COS_REGION", "ap-shanghai")
    values = cos.read_env(str(env))
    assert values["COS_BUCKET"] == "from-file" and values["COS_REGION"] == "ap-shanghai"
    assert "JWT_SECRET_KEY" not in values, "只读 COS_* 这几项"


def test_missing_config_skips_without_failing(tmp_path, backup, monkeypatch, capsys):
    for key in cos.KEYS:
        monkeypatch.delenv(key, raising=False)
    assert cos.main(["--env", str(tmp_path / "none.env"), str(backup)]) == 0
    assert "跳过异地备份" in capsys.readouterr().out
