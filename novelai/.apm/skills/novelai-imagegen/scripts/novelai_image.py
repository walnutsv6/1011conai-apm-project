#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "novelai-sdk==0.14.1",
#   "pillow>=10,<13",
#   "socksio>=1.0,<2",
# ]
# ///
"""NovelAI image runner with stable JSON I/O and zero-Anlas-aware planning."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
MANIFEST_DIRNAME = "manifest"
ZERO_MAX_PIXELS = 1_048_576
ZERO_MAX_STEPS = 28
DEFAULT_MODEL = "nai-diffusion-5-full"
DEFAULT_SIZES = {
    "square": (1024, 1024),
    "landscape": (1216, 832),
    "portrait": (832, 1216),
}
SECRET_KEYS = ("api_key", "authorization", "cookie", "password", "token")


class RunnerError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.code, self.message, self.retryable = code, message, retryable
        self.details = details or {}


def redact(text: str) -> str:
    text = re.sub(r"pst-[A-Za-z0-9_-]+", "[REDACTED]", text)
    return re.sub(r"(?i)bearer\s+[A-Za-z0-9._~+/-]+=*", "Bearer [REDACTED]", text)


def scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]"
            if any(secret in key.lower() for secret in SECRET_KEYS)
            else scrub(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [scrub(item) for item in value]
    return redact(value) if isinstance(value, str) else value


def emit(value: dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def fail(error: RunnerError) -> int:
    item: dict[str, Any] = {
        "code": error.code,
        "message": redact(error.message),
        "retryable": error.retryable,
    }
    if error.details:
        item["details"] = scrub(error.details)
    emit({"ok": False, "error": item})
    return 2


def obj(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RunnerError("INVALID_REQUEST", f"{label} must be a JSON object.")
    return value


def integer(value: Any, label: str, low: int, high: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not low <= value <= high
    ):
        raise RunnerError(
            "INVALID_REQUEST", f"{label} must be an integer from {low} through {high}."
        )
    return value


def boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise RunnerError("INVALID_REQUEST", f"{label} must be a boolean.")
    return value


def load_request(args: argparse.Namespace) -> dict[str, Any]:
    try:
        if args.request_json_stdin:
            value = json.load(sys.stdin)
        else:
            value = json.loads(
                Path(args.request).expanduser().read_text(encoding="utf-8")
            )
    except FileNotFoundError as exc:
        raise RunnerError(
            "REQUEST_NOT_FOUND", f"Request file not found: {args.request}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise RunnerError("INVALID_JSON", f"Invalid request JSON: {exc.msg}.") from exc
    request = obj(value, "request")
    if request.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
        raise RunnerError(
            "UNSUPPORTED_SCHEMA", f"schema_version must be {SCHEMA_VERSION}."
        )
    return request


def root_path(request: dict[str, Any], cli_root: str | None) -> Path:
    return (
        Path(cli_root or request.get("project_root") or os.getcwd())
        .expanduser()
        .resolve()
    )


def inside(path: Path, root: Path, label: str) -> Path:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise RunnerError(
            "PATH_OUTSIDE_PROJECT",
            f"{label} must be inside {root}. Copy it there first.",
        ) from exc
    return path


def input_path(value: Any, root: Path, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise RunnerError("INVALID_REQUEST", f"{label} must be a non-empty path.")
    path = Path(value).expanduser()
    path = (path if path.is_absolute() else root / path).resolve()
    inside(path, root, label)
    if not path.is_file():
        raise RunnerError("INPUT_NOT_FOUND", f"{label} not found: {path}")
    return path


def output_dir(value: str | None, request: dict[str, Any], root: Path) -> Path:
    raw = (
        value
        or obj(request.get("output", {}), "output").get("directory")
        or "output/novelai-imagegen"
    )
    path = Path(raw).expanduser()
    path = (path if path.is_absolute() else root / path).resolve()
    inside(path, root, "output directory")
    character = obj(request.get("output", {}), "output").get("character")
    if character is not None:
        if not isinstance(character, str):
            raise RunnerError("INVALID_REQUEST", "output.character must be a string.")
        slug = re.sub(r"[^A-Za-z0-9._-]+", "-", character).strip("-.")[:80]
        if not slug:
            raise RunnerError("INVALID_REQUEST", "output.character is empty after normalization.")
        # Do not nest twice when the caller already points at the character folder.
        if path.name != slug:
            path = path / slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def parse_size(value: Any, orientation: Any) -> tuple[int, int]:
    if value is None:
        if orientation is not None and orientation not in DEFAULT_SIZES:
            raise RunnerError(
                "INVALID_REQUEST", "orientation must be square, landscape, or portrait."
            )
        return DEFAULT_SIZES.get(orientation or "square", DEFAULT_SIZES["square"])
    if isinstance(value, str):
        normalized = value.lower().strip()
        if normalized in DEFAULT_SIZES:
            return DEFAULT_SIZES[normalized]
        match = re.fullmatch(r"(\d{2,4})\s*[xX×]\s*(\d{2,4})", normalized)
        if not match:
            raise RunnerError("INVALID_REQUEST", f"Unsupported size: {value!r}.")
        width, height = int(match.group(1)), int(match.group(2))
    elif isinstance(value, dict):
        width, height = value.get("width"), value.get("height")
    elif isinstance(value, (list, tuple)) and len(value) == 2:
        width, height = value
    else:
        raise RunnerError(
            "INVALID_REQUEST", "size must be a preset, WIDTHxHEIGHT, pair, or object."
        )
    width = integer(width, "size.width", 64, 1600)
    height = integer(height, "size.height", 64, 1600)
    if width % 64 or height % 64:
        raise RunnerError(
            "INVALID_REQUEST", "size width and height must be multiples of 64."
        )
    return width, height


def zero_shape(is_opus: bool, size: tuple[int, int], steps: int, samples: int) -> bool:
    return (
        is_opus
        and size[0] * size[1] <= ZERO_MAX_PIXELS
        and steps <= ZERO_MAX_STEPS
        and samples == 1
    )


def policy(request: dict[str, Any]) -> dict[str, Any]:
    raw = obj(request.get("cost_policy", {}), "cost_policy")
    result = {
        "subscription_plan": raw.get("subscription_plan", "auto"),
        "prefer_zero_anlas": raw.get("prefer_zero_anlas", True),
        "require_zero_anlas": raw.get("require_zero_anlas", False),
        "confirm_above_anlas": raw.get("confirm_above_anlas", 100),
        "confirmed_paid": raw.get("confirmed_paid", False),
    }
    if result["subscription_plan"] not in {"auto", "opus", "non_opus"}:
        raise RunnerError(
            "INVALID_REQUEST", "subscription_plan must be auto, opus, or non_opus."
        )
    for key in ("prefer_zero_anlas", "require_zero_anlas", "confirmed_paid"):
        boolean(result[key], f"cost_policy.{key}")
    integer(
        result["confirm_above_anlas"], "cost_policy.confirm_above_anlas", 0, 1_000_000
    )
    return result


def normalized_generation(request: dict[str, Any]) -> dict[str, Any]:
    prompt = request.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise RunnerError("INVALID_REQUEST", "prompt must be a non-empty string.")
    result = deepcopy(request)
    result.update(
        schema_version=SCHEMA_VERSION,
        prompt=prompt.strip(),
        model=request.get("model", DEFAULT_MODEL),
        size=parse_size(request.get("size"), request.get("orientation")),
        steps=integer(request.get("steps", 28), "steps", 1, 50),
        scale=request.get("scale", 5.0),
        samples=integer(request.get("samples", 1), "samples", 1, 64),
        cost_policy=policy(request),
    )
    return result


def sdk() -> dict[str, Any]:
    try:
        import novelai
        from novelai import types
    except Exception as exc:
        raise RunnerError(
            "DEPENDENCY_ERROR",
            f"Unable to import novelai-sdk: {type(exc).__name__}: {exc}",
        ) from exc
    return {
        "NovelAI": novelai.NovelAI,
        "BackgroundRemovalParams": types.BackgroundRemovalParams,
        "CharacterReference": types.CharacterReference,
        "ColorizeParams": types.ColorizeParams,
        "ControlNet": types.ControlNet,
        "ControlNetImage": types.ControlNetImage,
        "DeclutterParams": types.DeclutterParams,
        "EmotionParams": types.EmotionParams,
        "GenerateImageParams": types.GenerateImageParams,
        "I2iParams": types.I2iParams,
        "InpaintParams": types.InpaintParams,
        "LineArtParams": types.LineArtParams,
        "SketchParams": types.SketchParams,
        "UpscaleParams": types.UpscaleParams,
    }


def sdk_version() -> str:
    try:
        return importlib.metadata.version("novelai-sdk")
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def subscription(client: Any) -> tuple[bool, str]:
    try:
        sub = client.user.get_subscription()
    except Exception as exc:
        raise RunnerError(
            "SUBSCRIPTION_CHECK_FAILED",
            f"Could not verify the NovelAI subscription: {type(exc).__name__}: {exc}",
            retryable=True,
        ) from exc
    perks = getattr(sub, "perks", None)
    unlimited = bool(getattr(perks, "unlimited_image_generation", False))
    return bool(
        getattr(sub, "active", False) and (getattr(sub, "is_opus", False) or unlimited)
    ), str(getattr(sub, "tier_name", "Unknown"))


def estimate_opus(request: dict[str, Any], module: dict[str, Any]) -> bool:
    selected = policy(request)["subscription_plan"]
    if selected != "auto":
        return selected == "opus"
    if not os.environ.get("NOVELAI_API_KEY"):
        raise RunnerError(
            "MISSING_API_KEY",
            "NOVELAI_API_KEY is required for automatic subscription detection.",
        )
    try:
        with module["NovelAI"]() as client:
            return subscription(client)[0]
    except RunnerError:
        raise
    except Exception as exc:
        raise RunnerError(
            "SDK_ERROR", f"NovelAI client failed: {type(exc).__name__}: {exc}"
        ) from exc


def generation_kwargs(data: dict[str, Any], root: Path, samples: int) -> dict[str, Any]:
    fields = (
        "negative_prompt",
        "quality",
        "uc_preset",
        "sampler",
        "noise_schedule",
        "seed",
        "cfg_rescale",
        "variety_boost",
        "straight_alpha",
        "tag_hint_transparent_background",
        "image_format",
    )
    kwargs = {
        "prompt": data["prompt"],
        "model": data["model"],
        "size": data["size"],
        "steps": data["steps"],
        "scale": data["scale"],
        "n_samples": samples,
        **{key: data[key] for key in fields if data.get(key) is not None},
    }
    module = sdk()
    if data.get("i2i") is not None:
        item = obj(data["i2i"], "i2i")
        extra = {"seed": item["seed"]} if "seed" in item else {}
        kwargs["i2i"] = module["I2iParams"](
            image=input_path(item.get("image"), root, "i2i.image"),
            strength=item.get("strength", 0.7),
            noise=item.get("noise", 0.0),
            **extra,
        )
    if data.get("inpaint") is not None:
        item = obj(data["inpaint"], "inpaint")
        extra = {"seed": item["seed"]} if "seed" in item else {}
        kwargs["inpaint"] = module["InpaintParams"](
            image=input_path(item.get("image"), root, "inpaint.image"),
            mask=input_path(item.get("mask"), root, "inpaint.mask"),
            strength=item.get("strength", 1.0),
            **extra,
        )
    refs = data.get("character_references")
    if refs is not None:
        if not isinstance(refs, list):
            raise RunnerError(
                "INVALID_REQUEST", "character_references must be an array."
            )
        kwargs["character_references"] = []
        for index, raw in enumerate(refs):
            item = obj(raw, f"character_references[{index}]")
            kwargs["character_references"].append(
                module["CharacterReference"](
                    image=input_path(
                        item.get("image"), root, f"character_references[{index}].image"
                    ),
                    type=item.get("type", "character&style"),
                    fidelity=item.get("fidelity", 1.0),
                    strength=item.get("strength", 1.0),
                )
            )
    if data.get("controlnet") is not None:
        control = obj(data["controlnet"], "controlnet")
        items = control.get("images")
        if not isinstance(items, list) or not items:
            raise RunnerError(
                "INVALID_REQUEST", "controlnet.images must be a non-empty array."
            )
        images = []
        for index, raw in enumerate(items):
            item = obj(raw, f"controlnet.images[{index}]")
            images.append(
                module["ControlNetImage"](
                    image=input_path(
                        item.get("image"), root, f"controlnet.images[{index}].image"
                    ),
                    info_extracted=item.get("info_extracted", 0.7),
                    strength=item.get("strength", 0.6),
                    controlnet_model=item.get("model", data["model"]),
                )
            )
        kwargs["controlnet"] = module["ControlNet"](
            images=images, strength=control.get("strength", 1.0)
        )
    return kwargs


def generation_plan(
    request: dict[str, Any], root: Path, is_opus: bool
) -> tuple[dict[str, Any], list[Any], list[int]]:
    data, module = normalized_generation(request), sdk()
    one = module["GenerateImageParams"](**generation_kwargs(data, root, 1))
    split = (
        data["samples"] > 1
        and data["cost_policy"]["prefer_zero_anlas"]
        and zero_shape(is_opus, data["size"], data["steps"], 1)
        and int(one.calculate_anlas(is_opus=is_opus)) == 0
    )
    batches = [1] * data["samples"] if split else []
    remaining = data["samples"]
    while not split and remaining:
        batches.append(min(8, remaining))
        remaining -= batches[-1]
    params_list, costs = [], []
    offset = 0
    for count in batches:
        kwargs = generation_kwargs(data, root, count)
        if data.get("seed") is not None:
            kwargs["seed"] = int(data["seed"]) + offset
        params = module["GenerateImageParams"](**kwargs)
        params_list.append(params)
        costs.append(int(params.calculate_anlas(is_opus=is_opus)))
        offset += count
    return data, params_list, costs


def enforce_cost(cost_policy: dict[str, Any], costs: list[int | None]) -> None:
    if any(cost is None for cost in costs):
        if cost_policy["require_zero_anlas"] or not cost_policy["confirmed_paid"]:
            raise RunnerError(
                "COST_UNKNOWN",
                "Anlas cost is unknown. Confirm the paid operation before retrying.",
            )
        return
    total = sum(int(cost) for cost in costs if cost is not None)
    if total == 0:
        return
    if cost_policy["require_zero_anlas"]:
        raise RunnerError(
            "ZERO_ANLAS_REQUIRED",
            f"Estimated cost is {total} Anlas; the operation was not executed.",
            details={"estimated_anlas": total},
        )
    if total > cost_policy["confirm_above_anlas"] and not cost_policy["confirmed_paid"]:
        raise RunnerError(
            "CONFIRMATION_REQUIRED",
            f"Estimated cost is {total} Anlas. Confirm before execution.",
            details={
                "estimated_anlas": total,
                "retry_with": {"cost_policy": {"confirmed_paid": True}},
            },
        )


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_name(request: dict[str, Any], fallback: str) -> str:
    raw = obj(request.get("output", {}), "output").get("basename", fallback)
    if not isinstance(raw, str):
        raise RunnerError("INVALID_REQUEST", "output.basename must be a string.")
    return (re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-.") or fallback)[:80]


def unique_path(directory: Path, stem: str, suffix: str) -> Path:
    candidate, index = directory / f"{stem}{suffix}", 2
    while candidate.exists():
        candidate, index = directory / f"{stem}-{index}{suffix}", index + 1
    return candidate


def input_metadata(request: dict[str, Any], root: Path) -> list[dict[str, str]]:
    found: list[tuple[str, Any]] = []
    for section, fields in (("i2i", ("image",)), ("inpaint", ("image", "mask"))):
        item = request.get(section)
        if isinstance(item, dict):
            found.extend(
                (f"{section}.{field}", item[field])
                for field in fields
                if item.get(field)
            )
    for index, item in enumerate(request.get("character_references") or []):
        if isinstance(item, dict) and item.get("image"):
            found.append((f"character_references[{index}].image", item["image"]))
    control = request.get("controlnet")
    if isinstance(control, dict):
        for index, item in enumerate(control.get("images") or []):
            if isinstance(item, dict) and item.get("image"):
                found.append((f"controlnet.images[{index}].image", item["image"]))
    if request.get("input"):
        found.append(("input", request["input"]))
    return [
        {
            "role": role,
            "filename": (path := input_path(value, root, role)).name,
            "sha256": hash_file(path),
        }
        for role, value in found
    ]


def save_images(
    images: list[Any],
    request: dict[str, Any],
    resolved: dict[str, Any],
    directory: Path,
    root: Path,
    cost: int | None,
    operation: str,
    seeds: list[int | None] | None = None,
    suffixes: list[str] | None = None,
) -> list[dict[str, Any]]:
    fmt = str(obj(request.get("output", {}), "output").get("format", "png")).lower()
    if fmt not in {"png", "webp"}:
        raise RunnerError("INVALID_REQUEST", "output.format must be png or webp.")
    base, inputs, results = (
        safe_name(request, operation.replace(":", "-")),
        input_metadata(request, root),
        [],
    )
    for index, image in enumerate(images):
        seed = seeds[index] if seeds and index < len(seeds) else None
        suffix = (
            suffixes[index]
            if suffixes and index < len(suffixes)
            else (f"seed{seed}" if seed is not None else f"{index + 1:02d}")
        )
        path = unique_path(directory, f"{base}-{suffix}", f".{fmt}")
        image.save(path)
        manifest_dir = directory / MANIFEST_DIRNAME
        manifest_dir.mkdir(parents=True, exist_ok=True)
        metadata = manifest_dir / f"{path.stem}.json"
        sha = hash_file(path)
        metadata.write_text(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "operation": operation,
                    "sdk_version": sdk_version(),
                    "request": scrub(request),
                    "resolved": scrub(resolved),
                    "seed": seed,
                    "estimated_anlas": cost,
                    "inputs": inputs,
                    "output": {
                        "filename": path.name,
                        "width": image.width,
                        "height": image.height,
                        "format": fmt,
                        "sha256": sha,
                    },
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        results.append(
            {
                "path": str(path),
                "metadata_path": str(metadata),
                "seed": seed,
                "width": image.width,
                "height": image.height,
                "sha256": sha,
            }
        )
    return results


def estimate_generation(
    request: dict[str, Any], root: Path, is_opus: bool
) -> dict[str, Any]:
    data, params, costs = generation_plan(request, root, is_opus)
    enforce_cost(data["cost_policy"], costs)
    total = sum(costs)
    return {
        "ok": True,
        "operation": request.get("operation", "generate"),
        "estimate_only": True,
        "resolved": scrub(data),
        "usage": {
            "estimated_anlas": total,
            "zero_anlas": total == 0,
            "request_count": len(params),
            "images": data["samples"],
        },
    }


def run_generation(
    request: dict[str, Any], root: Path, directory: Path, operation: str
) -> dict[str, Any]:
    if not os.environ.get("NOVELAI_API_KEY"):
        raise RunnerError("MISSING_API_KEY", "NOVELAI_API_KEY is not set.")
    module = sdk()
    try:
        with module["NovelAI"]() as client:
            is_opus, _tier = subscription(client)
            data, params_list, costs = generation_plan(request, root, is_opus)
            enforce_cost(data["cost_policy"], costs)
            images, seeds = [], []
            for params in params_list:
                generated = client.image.generate(params)
                images.extend(generated)
                seeds.extend(
                    int(params.seed) + index for index in range(len(generated))
                )
    except RunnerError:
        raise
    except Exception as exc:
        raise RunnerError(
            "SDK_ERROR", f"NovelAI {operation} failed: {type(exc).__name__}: {exc}"
        ) from exc
    total = sum(costs)
    saved = save_images(
        images, request, data, directory, root, total, operation, seeds=seeds
    )
    return {
        "ok": True,
        "operation": operation,
        "images": saved,
        "usage": {
            "estimated_anlas": total,
            "zero_anlas": total == 0,
            "request_count": len(params_list),
        },
        "warnings": ["Anlas values are best-effort estimates, not billing guarantees."],
    }


def build_tool(
    request: dict[str, Any], root: Path, module: dict[str, Any]
) -> tuple[str, Any, list[str]]:
    name = request.get("tool")
    image = input_path(request.get("input"), root, "input")
    if name == "line_art":
        return name, module["LineArtParams"](image=image), ["lineart"]
    if name == "sketch":
        return name, module["SketchParams"](image=image), ["sketch"]
    if name == "colorize":
        return (
            name,
            module["ColorizeParams"](
                image=image,
                prompt=request.get("prompt", ""),
                defry=request.get("defry", 0),
            ),
            ["colorized"],
        )
    if name == "emotion":
        return (
            name,
            module["EmotionParams"](
                image=image,
                emotion=request.get("emotion"),
                prompt=request.get("prompt", ""),
                defry=request.get("defry", 0),
            ),
            ["emotion"],
        )
    if name == "declutter":
        return (
            name,
            module["DeclutterParams"](
                image=image, keep_bubbles=request.get("keep_bubbles", False)
            ),
            ["decluttered"],
        )
    if name == "remove_background":
        return (
            name,
            module["BackgroundRemovalParams"](image=image),
            ["masked", "generated", "blend"],
        )
    if name == "upscale":
        return (
            name,
            module["UpscaleParams"](
                image=image, model=request.get("model", "nai-diffusion-5-curated")
            ),
            ["upscaled"],
        )
    raise RunnerError("INVALID_REQUEST", f"Unsupported Director Tool: {name!r}.")


def estimate_tool(
    request: dict[str, Any], root: Path, is_opus: bool
) -> tuple[str, Any, list[str], int | None]:
    module = sdk()
    name, params, suffixes = build_tool(request, root, module)
    cost = None if name == "upscale" else int(params.calculate_anlas(is_opus=is_opus))
    enforce_cost(policy(request), [cost])
    return name, params, suffixes, cost


def run_tool(request: dict[str, Any], root: Path, directory: Path) -> dict[str, Any]:
    if not os.environ.get("NOVELAI_API_KEY"):
        raise RunnerError("MISSING_API_KEY", "NOVELAI_API_KEY is not set.")
    module = sdk()
    try:
        with module["NovelAI"]() as client:
            is_opus, _tier = subscription(client)
            name, params, suffixes, cost = estimate_tool(request, root, is_opus)
            images = (
                client.tools.upscale(params)
                if name == "upscale"
                else client.tools.augment(params)
            )
    except RunnerError:
        raise
    except Exception as exc:
        raise RunnerError(
            "SDK_ERROR", f"NovelAI Director Tool failed: {type(exc).__name__}: {exc}"
        ) from exc
    saved = save_images(
        images,
        request,
        {"tool": name},
        directory,
        root,
        cost,
        f"tool:{name}",
        suffixes=suffixes,
    )
    return {
        "ok": True,
        "operation": f"tool:{name}",
        "images": saved,
        "usage": {
            "estimated_anlas": cost,
            "zero_anlas": cost == 0 if cost is not None else False,
            "request_count": 1,
        },
        "warnings": ["Anlas values are best-effort estimates, not billing guarantees."],
    }


def validate_environment(live: bool) -> dict[str, Any]:
    module = sdk()
    result: dict[str, Any] = {
        "ok": True,
        "operation": "validate",
        "python": sys.version.split()[0],
        "sdk_version": sdk_version(),
        "api_key_configured": bool(os.environ.get("NOVELAI_API_KEY")),
        "live": live,
    }
    if live:
        if not os.environ.get("NOVELAI_API_KEY"):
            raise RunnerError("MISSING_API_KEY", "NOVELAI_API_KEY is not set.")
        with module["NovelAI"]() as client:
            is_opus, tier = subscription(client)
        result["subscription"] = {"active_opus": is_opus, "tier": tier}
    return result


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--live", action="store_true")
    for name in ("estimate", "generate", "edit", "tool"):
        child = commands.add_parser(name)
        source = child.add_mutually_exclusive_group(required=True)
        source.add_argument("--request")
        source.add_argument("--request-json-stdin", action="store_true")
        child.add_argument("--project-root")
        if name != "estimate":
            child.add_argument("--out-dir")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "validate":
            emit(validate_environment(args.live))
            return 0
        request = load_request(args)
        root = root_path(request, args.project_root)
        if args.command == "estimate":
            is_opus = estimate_opus(request, sdk())
            if request.get("operation") == "tool" or request.get("tool"):
                name, _params, _suffixes, cost = estimate_tool(request, root, is_opus)
                emit(
                    {
                        "ok": True,
                        "operation": f"tool:{name}",
                        "estimate_only": True,
                        "usage": {
                            "estimated_anlas": cost,
                            "zero_anlas": cost == 0 if cost is not None else False,
                            "request_count": 1,
                        },
                    }
                )
            else:
                emit(estimate_generation(request, root, is_opus))
            return 0
        directory = output_dir(args.out_dir, request, root)
        emit(
            run_tool(request, root, directory)
            if args.command == "tool"
            else run_generation(request, root, directory, args.command)
        )
        return 0
    except RunnerError as exc:
        return fail(exc)
    except Exception as exc:  # noqa: BLE001 - convert unexpected failures to stable JSON
        validation = type(exc).__name__ == "ValidationError"
        code = "INVALID_REQUEST" if validation else "UNEXPECTED_ERROR"
        prefix = "Invalid request" if validation else "Unexpected failure"
        return fail(RunnerError(code, f"{prefix}: {type(exc).__name__}: {exc}"))


if __name__ == "__main__":
    raise SystemExit(main())
