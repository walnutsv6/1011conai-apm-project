import base64
import importlib.util
import io
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

SCRIPT = Path(__file__).parents[1] / ".apm/skills/openai-compatible-imagegen/scripts/imagegen.py"
spec = importlib.util.spec_from_file_location("imagegen", SCRIPT)
imagegen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(imagegen)

PNG = b"\x89PNG\r\n\x1a\n" + b"fake-png-body"
SECRET = "sk-test-SECRET-value-1234"


class FakeResponse:
    def __init__(self, body, status=200, ctype="application/json"):
        self._body, self.status, self.headers = body, status, {"Content-Type": ctype}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for name in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "IMAGEGEN_MODEL", "IMAGEGEN_CONFIG", "LOCAL_KEY"):
        monkeypatch.delenv(name, raising=False)
    return tmp_path


@pytest.fixture
def calls(monkeypatch):
    recorded = []
    responses = []

    def fake_urlopen(req, timeout=None):
        recorded.append(req)
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(imagegen, "urlopen", fake_urlopen)
    return recorded, responses


def b64_response(count=1, **extra):
    data = [{"b64_json": base64.b64encode(PNG).decode(), "revised_prompt": f"rp{i}"} for i in range(count)]
    return FakeResponse(json.dumps(dict({"created": 1, "data": data, "usage": {"total_tokens": 9}}, **extra)).encode())


def test_dry_run_makes_no_request(env, calls, capsys):
    recorded, _ = calls
    rc = imagegen.main(["generate", "--prompt", "a slime", "--output", "out/slime.png"])
    assert rc == 0
    assert recorded == []
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "OPENAI_API_KEY (NOT SET)" in out
    assert not (env / "out").exists()


def test_missing_key_names_env_var(env, calls, capsys):
    rc = imagegen.main(["generate", "--prompt", "x", "--output", "a.png", "--execute", "--api-key-env", "LOCAL_KEY"])
    assert rc == 1
    assert "LOCAL_KEY is not set" in capsys.readouterr().err
    assert calls[0] == []


def test_generate_saves_image_and_clean_sidecar(env, calls, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    recorded, responses = calls
    responses.append(b64_response(background="transparent"))
    rc = imagegen.main(["generate", "--prompt", "knight sprite", "--output", "assets/knight.png", "--execute",
                        "--background", "transparent", "--size", "1024x1024", "--quality", "low"])
    assert rc == 0
    req = recorded[0]
    assert req.full_url == "https://api.openai.com/v1/images/generations"
    assert req.get_header("Authorization") == "Bearer " + SECRET
    body = json.loads(req.data)
    assert body == {"model": "gpt-image-1", "prompt": "knight sprite", "n": 1, "size": "1024x1024",
                    "quality": "low", "background": "transparent"}
    assert "response_format" not in body
    assert (env / "assets/knight.png").read_bytes() == PNG
    meta_text = (env / "assets/knight.png.json").read_text(encoding="utf-8")
    assert SECRET not in meta_text
    meta = json.loads(meta_text)
    assert meta["revised_prompt"] == "rp0"
    assert meta["usage"] == {"total_tokens": 9}
    assert meta["response_background"] == "transparent"
    assert meta["detected_format"] == "png"


def test_base_url_and_model_from_env(env, calls, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:8080/v1/")
    monkeypatch.setenv("IMAGEGEN_MODEL", "local-sd")
    recorded, responses = calls
    responses.append(b64_response())
    assert imagegen.main(["generate", "--prompt", "x", "--output", "a.png", "--execute", "--no-auth"]) == 0
    assert recorded[0].full_url == "http://localhost:8080/v1/images/generations"
    assert recorded[0].get_header("Authorization") is None
    assert json.loads(recorded[0].data)["model"] == "local-sd"


def test_multiple_outputs_get_suffixes(env, calls, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    _, responses = calls
    responses.append(b64_response(3))
    assert imagegen.main(["generate", "--prompt", "x", "--n", "3", "--output", "s/coin.png", "--execute"]) == 0
    for i in (1, 2, 3):
        assert (env / f"s/coin-{i}.png").exists()
        assert (env / f"s/coin-{i}.png.json").exists()
    assert not (env / "s/coin.png").exists()


def test_n_limit_requires_allow_many(env, calls, capsys):
    assert imagegen.main(["generate", "--prompt", "x", "--n", "5", "--output", "a.png"]) == 1
    assert "--allow-many" in capsys.readouterr().err


def test_refuses_overwrite(env, calls, monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    (env / "a.png").write_bytes(b"old")
    assert imagegen.main(["generate", "--prompt", "x", "--output", "a.png", "--execute"]) == 1
    assert "overwrite" in capsys.readouterr().err
    assert calls[0] == []
    assert (env / "a.png").read_bytes() == b"old"


def test_url_response_downloaded_without_key(env, calls, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    recorded, responses = calls
    responses.append(FakeResponse(json.dumps({"data": [{"url": "https://cdn.example.com/x.png"}]}).encode()))
    responses.append(FakeResponse(PNG, ctype="image/png"))
    assert imagegen.main(["generate", "--prompt", "x", "--output", "a.png", "--execute",
                          "--model", "dall-e-3", "--response-format", "url"]) == 0
    assert recorded[1].full_url == "https://cdn.example.com/x.png"
    assert recorded[1].get_header("Authorization") is None
    assert (env / "a.png").read_bytes() == PNG


def test_edit_multipart_has_images_and_mask(env, calls, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    (env / "base.png").write_bytes(PNG)
    (env / "ref.png").write_bytes(PNG)
    (env / "mask.png").write_bytes(PNG)
    recorded, responses = calls
    responses.append(b64_response())
    rc = imagegen.main(["edit", "--prompt", "same knight, walking pose", "--image", "base.png", "--image", "ref.png",
                        "--mask", "mask.png", "--output", "walk.png", "--execute", "--extra-json", '{"input_fidelity": "high"}'])
    assert rc == 0
    req = recorded[0]
    assert req.full_url.endswith("/images/edits")
    assert req.get_header("Content-type").startswith("multipart/form-data; boundary=")
    body = req.data
    assert body.count(b'name="image[]"; filename=') == 2
    assert b'name="mask"; filename="mask.png"' in body
    assert b'name="input_fidelity"\r\n\r\nhigh' in body
    assert b'name="n"\r\n\r\n1' in body


def test_edit_rejects_external_inputs(env, calls, tmp_path_factory, capsys):
    outside = tmp_path_factory.mktemp("elsewhere") / "x.png"
    outside.write_bytes(PNG)
    assert imagegen.main(["edit", "--prompt", "x", "--image", str(outside), "--output", "o.png"]) == 1
    assert "outside the project" in capsys.readouterr().err


def test_http_error_masks_key(env, calls, monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    _, responses = calls
    err_body = io.BytesIO(json.dumps({"error": {"message": f"Incorrect API key provided: {SECRET}"}}).encode())
    responses.append(HTTPError("https://api.openai.com/v1/images/generations", 401, "Unauthorized", {}, err_body))
    assert imagegen.main(["generate", "--prompt", "x", "--output", "a.png", "--execute"]) == 1
    err = capsys.readouterr().err
    assert "HTTP 401" in err
    assert SECRET not in err
    assert "***" in err


def test_extra_json_rejects_credentials(env, calls, capsys):
    assert imagegen.main(["generate", "--prompt", "x", "--output", "a.png", "--extra-json", '{"api_key": "x"}']) == 1
    assert "credentials" in capsys.readouterr().err


def test_transparent_jpeg_rejected(env, calls, capsys):
    assert imagegen.main(["generate", "--prompt", "x", "--output", "a.jpg", "--background", "transparent"]) == 1
    assert "png or .webp" in capsys.readouterr().err


def test_base_url_with_credentials_rejected(env, calls, capsys):
    assert imagegen.main(["check", "--base-url", "https://user:pw@host/v1"]) == 1
    assert "credentials" in capsys.readouterr().err


def test_check_never_prints_key(env, calls, monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    assert imagegen.main(["check"]) == 0
    out = capsys.readouterr().out
    assert SECRET not in out
    assert "OPENAI_API_KEY (set)" in out


# ---------------------------------------------------------------- config file

def write_config(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


LOCAL_CONFIG = {
    "_comment": "no keys here",
    "base_url": "http://127.0.0.1:7860/v1",
    "model": "sdxl-turbo",
    "api_key_env": "LOCAL_KEY",
    "params": {"response_format": "b64_json", "size": "512x512"},
}


def test_config_file_in_cwd_sets_endpoint_model_key_env_and_params(env, calls, monkeypatch):
    monkeypatch.setenv("LOCAL_KEY", SECRET)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://should-not-win.example/v1")
    monkeypatch.setenv("IMAGEGEN_MODEL", "env-model")
    write_config(env / "imagegen.config.json", LOCAL_CONFIG)
    recorded, responses = calls
    responses.append(b64_response())
    assert imagegen.main(["generate", "--prompt", "x", "--output", "a.png", "--execute"]) == 0
    req = recorded[0]
    assert req.full_url == "http://127.0.0.1:7860/v1/images/generations"
    assert req.get_header("Authorization") == "Bearer " + SECRET
    assert json.loads(req.data) == {"model": "sdxl-turbo", "prompt": "x", "n": 1,
                                    "response_format": "b64_json", "size": "512x512"}
    meta = json.loads((env / "a.png.json").read_text(encoding="utf-8"))
    assert meta["config_file"].endswith("imagegen.config.json")
    assert meta["base_url_host"] == "127.0.0.1:7860"


def test_cli_overrides_config(env, calls, monkeypatch):
    write_config(env / "imagegen.config.json", dict(LOCAL_CONFIG, no_auth=True))
    recorded, responses = calls
    responses.append(b64_response())
    assert imagegen.main(["generate", "--prompt", "x", "--output", "a.png", "--execute", "--model", "other",
                          "--base-url", "http://10.0.0.5:9000/v1", "--size", "1024x1024"]) == 0
    req = recorded[0]
    assert req.full_url == "http://10.0.0.5:9000/v1/images/generations"
    assert req.get_header("Authorization") is None
    body = json.loads(req.data)
    assert body["model"] == "other" and body["size"] == "1024x1024"


def test_explicit_config_path_and_env_var(env, calls, capsys, monkeypatch):
    (env / "conf").mkdir()
    cfg = write_config(env / "conf" / "local.json", LOCAL_CONFIG)
    assert imagegen.main(["check", "--config", str(cfg)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["base_url"] == "http://127.0.0.1:7860/v1"
    assert out["model"] == "sdxl-turbo"
    assert out["sources"] == {"base_url": "config", "model": "config", "api_key_env": "config"}
    assert out["auth"] == "env LOCAL_KEY (NOT SET)"
    monkeypatch.setenv("IMAGEGEN_CONFIG", str(cfg))
    assert imagegen.main(["check"]) == 0
    assert json.loads(capsys.readouterr().out)["model"] == "sdxl-turbo"


def test_missing_explicit_config_is_an_error(env, calls, capsys):
    assert imagegen.main(["check", "--config", "nope.json"]) == 1
    assert "Config file not found" in capsys.readouterr().err


def test_no_config_reports_defaults(env, calls, capsys):
    assert imagegen.main(["check"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["config_file"].startswith("none")
    assert out["sources"]["base_url"] == "default"


@pytest.mark.parametrize("bad", [
    {"api_key": SECRET},
    {"base_url": "http://x/v1", "params": {"Authorization": "Bearer x"}},
    {"token": "abc"},
])
def test_config_with_credentials_rejected(env, calls, capsys, bad):
    write_config(env / "imagegen.config.json", bad)
    assert imagegen.main(["generate", "--prompt", "x", "--output", "a.png", "--execute", "--no-auth"]) == 1
    err = capsys.readouterr().err
    assert "Never store API keys" in err
    assert SECRET not in err
    assert calls[0] == []


@pytest.mark.parametrize("bad, message", [
    ({"base_ur": "http://x/v1"}, "Unknown field"),
    ({"model": 3}, "must be a str"),
    ({"api_key_env": "sk-abc def"}, "environment variable NAME"),
    ({"params": {"model": "x"}}, "must not set model"),
    ({"base_url": "ftp://x"}, "Invalid base URL"),
])
def test_config_validation(env, calls, capsys, bad, message):
    write_config(env / "imagegen.config.json", bad)
    assert imagegen.main(["check"]) == 1
    assert message in capsys.readouterr().err


def test_invalid_json_config(env, calls, capsys):
    (env / "imagegen.config.json").write_text("{ base_url: x }", encoding="utf-8")
    assert imagegen.main(["check"]) == 1
    assert "not valid JSON" in capsys.readouterr().err


def test_config_params_still_validated(env, calls, capsys):
    write_config(env / "imagegen.config.json", {"params": {"background": "transparent"}})
    assert imagegen.main(["generate", "--prompt", "x", "--output", "a.jpg"]) == 1
    assert "png or .webp" in capsys.readouterr().err
