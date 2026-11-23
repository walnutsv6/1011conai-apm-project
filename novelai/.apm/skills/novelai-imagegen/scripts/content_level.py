#!/usr/bin/env python3
"""Project content level (性的描写の表現レベル) for NovelAI requests.

Standard library only. Imported by ``novelai_image.py`` and usable as a CLI:

    python3 content_level.py show  [--project-root DIR]
    python3 content_level.py set   --level 1|2|3 --fluids yes|no --nude-contact yes|no [options]
    python3 content_level.py check [--project-root DIR] PATH [PATH ...]

The decision is stored per project in ``<agent dir>/novelai-content-level.json``,
where ``<agent dir>`` is the folder the skills are deployed under (``.claude``
for Claude Code, ``.agents`` for Codex, ...).
It is written by the ``novelai-content-level`` skill after asking the user.

Levels (cumulative):

1. ``topless`` -- breasts may be exposed; the groin may not (no panty removal).
2. ``cero``    -- the groin may be exposed; no genital detail or pubic hair.
               This is the default when no decision has been recorded.
3. ``eocs``    -- genitals and pubic hair may be depicted for a single
               female character (EOCS-based, mosaic before release).

Options asked at every level:

- ``fluids``       -- 愛液・白い液体の表現.
- ``nude_contact`` -- hugging / skinship with an exposed (level 1: topless,
                      levels 2-3: also nude) female character, excluding any
                      contact with the groin.

Adulthood (every character is 18+ and looks adult) is a precondition of all
sexual content at every level, not an option.

The check is a tag-level safety net, not a guarantee and not a review of the
image. Rules that cannot be expressed as tags (age impression, consent,
background, image sets) still come from the guideline documents.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

CONFIG_FILENAME = "novelai-content-level.json"
# Agent folders searched for the config, after the one this script is deployed in.
AGENT_DIRS = (".claude", ".agents")


def _deployment() -> tuple[Path | None, str | None]:
    """(project root, agent dir name) when deployed as <root>/<agent dir>/skills/<skill>/scripts/."""
    here = Path(__file__).resolve()
    # ``.apm`` is the package source layout, not a deployment.
    if len(here.parents) > 4 and here.parents[2].name == "skills" and here.parents[3].name != ".apm":
        return here.parents[4], here.parents[3].name
    return None, None


def _agent_dirs() -> list[str]:
    _root, deployed = _deployment()
    names = [deployed] if deployed else []
    return names + [name for name in AGENT_DIRS if name not in names]


# Relative path written by ``set`` (the deployed agent dir, else .claude).
CONFIG_RELPATH = Path(_agent_dirs()[0]) / CONFIG_FILENAME
CONFIG_SCHEMA_VERSION = 1
DEFAULT_LEVEL = 2
# Options asked in the hearing at every level. When a recorded config lacks a
# key, levels 2-3 default to True (the guideline body) and level 1 to False.
OPTION_KEYS = ("fluids", "nude_contact")
# Level 3 premises confirmed in the hearing. Adulthood is not listed here: it
# is a precondition at every level. An actual EOCS review is not required.
EOCS_PREMISES = ("mosaic_before_release", "human_release_check")

LEVELS: dict[int, dict[str, str]] = {
    1: {
        "id": "topless",
        "label": "レベル1: 乳房の露出まで（股間の露出・パンティーの脱衣は不可）",
        "rating": "自主規制レーティング 15歳未満禁止 相当（愛液・白い液体を含む画像は18歳未満禁止）",
    },
    2: {
        "id": "cero",
        "label": "レベル2: 股間の露出まで（性器・陰毛の描写は不可／現行・CERO基準）",
        "rating": "自主規制レーティング 18歳未満禁止",
    },
    3: {
        "id": "eocs",
        "label": "レベル3: 股間の露出および性器・陰毛の描写可（EOCS基準）",
        "rating": "EOCS 18歳未満禁止（性器描写はモザイク修正が前提）",
    },
}
LEVEL_IDS = {value["id"]: key for key, value in LEVELS.items()}


# --------------------------------------------------------------------------- #
# Tag normalisation
# --------------------------------------------------------------------------- #

_WEIGHT_PREFIX = re.compile(r"^-?\d+(?:\.\d+)?::")


def tags(prompt: str | None) -> list[str]:
    """Split a NovelAI prompt into normalised lowercase tags.

    Strips emphasis brackets ``{}`` ``[]`` ``()``, numeric weights
    (``1.2::tag::``) and turns underscores into spaces.
    """
    if not prompt:
        return []
    result = []
    for raw in re.split(r"[,\n|]", prompt):
        tag = raw.strip().lower().replace("_", " ")
        tag = _WEIGHT_PREFIX.sub("", tag)
        tag = tag.replace("::", "")
        tag = tag.strip("{}[]() \t")
        tag = re.sub(r"\s+", " ", tag)
        if tag:
            result.append(tag)
    return result


def _matches(tag_list: list[str], patterns: list[str]) -> list[str]:
    compiled = [re.compile(pattern) for pattern in patterns]
    return [tag for tag in tag_list if any(p.fullmatch(tag) for p in compiled)]


# --------------------------------------------------------------------------- #
# Tag rules
# --------------------------------------------------------------------------- #

# Breast exposure (allowed from level 1).
BREAST_EXPOSURE = [r"topless", r"nipples?", r"(areola|areolae)", r"bare breasts", r"breasts out"]

# Groin exposure / panty removal (allowed from level 2).
GROIN_EXPOSURE = [
    r"(completely |full )?nude",
    r"naked",
    r"bottomless",
    r"no panties",
    r"pulling down (own )?panties",
    r"panty pull",
    r"panties (down|removed|aside)",
    r"(.+ )?panties around (one )?(thighs?|knees?|legs?|ankles?|one leg)",
    r"(.+ )?panties (pulled|pulling) down",
    r"undressing panties",
    r"bare (crotch|groin)",
    r"exposed (crotch|groin)",
]

# Genital detail / pubic hair (allowed only at level 3, single female subject).
GENITAL_DETAIL = [
    r"uncensored",
    r"pussy",
    r"vagina",
    r"vulva",
    r"clitoris",
    r"labia",
    r"(female )?pubic hair",
    r"pubic stubble",
    r"cleft of venus",
]

# Fluids (愛液・白い液体). Allowed at any level only with options.fluids.
FLUIDS = [
    r"pussy juice( trail| drip| puddle)?",
    r"(love|vaginal) (juice|fluid)",
    r"cum( on [a-z ]+)?",
    r"semen",
    r"white liquid( on [a-z ]+)?",
    r"sticky white liquid",
    r"bukkake",
]

# Never allowed at any level (sexual acts, self-stimulation, coercion, excretion).
ALWAYS_BANNED = [
    r"sex",
    r"(vaginal|anal|oral)( sex)?",
    r"(after|implied|clothed) sex",
    r"penetration",
    r"(group sex|threesome|gangbang|orgy)",
    r"(fellatio|blowjob|irrumatio|deepthroat|paizuri|titjob|handjob|footjob|cunnilingus|anilingus)",
    r"(female |male )?masturbation",
    r"fingering",
    r"(spread|spreading) (own )?pussy",
    r"(pussy|vaginal|object) insertion",
    r"(dildo|vibrator|sex toy)",
    r"cum (in|inside) (pussy|ass|mouth)",
    r"creampie",
    r"ejaculation",
    r"(rape|molestation|non-consensual|sexual assault)",
    r"(peeing|pee|urination|scat|defecation)",
]

# Minor-associated tags: rejected whenever the prompt contains any exposure,
# fluid or genital tag (sexual content must depict adults who look adult).
MINOR_TAGS = [
    r"loli",
    r"shota",
    r"child",
    r"toddler",
    r"aged down",
    r"(elementary|middle|high) school student",
    r"kindergartener",
]
# Additionally rejected at level 3 (EOCS: no high-school / grade association).
EOCS_EXTRA_MINOR = [r"schoolgirl", r"school ?girl", r"jk", r"(first|second|third)[- ]year student"]

# Physical contact between characters (gated by options.nude_contact when a
# character is exposed). Groin contact is never allowed and is not an option.
CONTACT = [
    r"hug(ging)?( from behind)?",
    r"(mutual |one-arm )?embrac(e|ing)",
    r"(french |surprise )?kiss(ing)?",
    r"cheek kiss|kissing cheek|kissing forehead|forehead kiss",
    r"cuddl(e|ing)",
    r"(arm|arms) around (another's )?(waist|shoulders?|neck)",
    r"head ?pat|patting head|headpat",
    r"holding hands|hand holding|interlocked fingers",
    r"(breast|ass|butt) grab",
    r"grabbing (another's )?(breasts?|ass|butt)",
    r"(breast|chest) (fondle|fondling)|fondling breasts?",
    r"grop(e|ing)",
    r"caress(ing)?",
    r"touching (another's )?(breasts?|stomach|belly|thighs?|ass|butt|face|cheek|hair)",
    r"hand on another's [a-z ]+",
    r"lap pillow|sitting on (another's )?lap|sitting on person",
    r"(princess |piggyback )?carry(ing)?",
    r"body contact|skin contact|skinship",
    r"straddling",
    r"face sitting|sitting on face",
    r"breast press|breasts? against [a-z ]+",
]

# Subject-count tags that make the image multi-character (level 3 genital
# allowance applies only to a single female character).
MULTI_CHARACTER = [
    r"[2-9]\+?(girls|boys)",
    r"(1|one) ?boy",
    r"multiple (girls|boys|others)",
    r"(yuri|yaoi|hetero|couple|duo|trio|group)",
    r"[2-9]\+? ?others?",
]


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #


class ContentLevelError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code, self.message, self.details = code, message, details or {}


def _candidate_roots(root: Path | None) -> list[Path]:
    roots: list[Path] = []
    if root is not None:
        roots.append(Path(root).expanduser().resolve())
    deployed_root, _name = _deployment()
    if deployed_root is not None and deployed_root not in roots:
        roots.append(deployed_root)
    return roots


def config_path(root: Path | None = None) -> Path:
    for candidate in _candidate_roots(root):
        for name in _agent_dirs():
            path = candidate / name / CONFIG_FILENAME
            if path.is_file():
                return path
    roots = _candidate_roots(root)
    return (roots[0] if roots else Path.cwd()) / CONFIG_RELPATH


def _validate(data: Any, path: Path) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ContentLevelError("INVALID_CONTENT_LEVEL", f"{path} must be a JSON object.")
    level = data.get("level")
    if isinstance(level, str):
        level = LEVEL_IDS.get(level, level)
    if isinstance(level, bool) or level not in LEVELS:
        raise ContentLevelError(
            "INVALID_CONTENT_LEVEL", f"{path}: level must be 1, 2 or 3 (got {data.get('level')!r})."
        )
    options = data.get("options", {})
    if not isinstance(options, dict):
        raise ContentLevelError("INVALID_CONTENT_LEVEL", f"{path}: options must be an object.")
    resolved_options = {}
    for key in OPTION_KEYS:
        value = options.get(key, level >= 2)
        if not isinstance(value, bool):
            raise ContentLevelError("INVALID_CONTENT_LEVEL", f"{path}: options.{key} must be a boolean.")
        resolved_options[key] = value
    if level == 3:
        premises = data.get("eocs_premises", {})
        missing = [
            key
            for key in EOCS_PREMISES
            if not (isinstance(premises, dict) and premises.get(key) is True)
        ]
        if missing:
            raise ContentLevelError(
                "INVALID_CONTENT_LEVEL",
                f"{path}: level 3 requires confirmed eocs_premises ({', '.join(missing)}). "
                "Run the novelai-content-level skill again.",
            )
    result = dict(data)
    result.update(level=level, level_id=LEVELS[level]["id"], options={**options, **resolved_options})
    return result


def load_config(root: Path | None = None) -> dict[str, Any]:
    """Return the project's content level. Missing file -> default level 2."""
    path = config_path(root)
    if not path.is_file():
        return {
            "level": DEFAULT_LEVEL,
            "level_id": LEVELS[DEFAULT_LEVEL]["id"],
            "options": {key: True for key in OPTION_KEYS},
            "source": "default",
            "path": str(path),
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContentLevelError("INVALID_CONTENT_LEVEL", f"{path}: invalid JSON ({exc.msg}).") from exc
    result = _validate(data, path)
    result.update(source="config", path=str(path))
    return result


def summary(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "level": config["level"],
        "level_id": config["level_id"],
        "fluids": config["options"]["fluids"],
        "nude_contact": config["options"]["nude_contact"],
        "source": config.get("source", "config"),
        "project": config.get("project"),
    }


# --------------------------------------------------------------------------- #
# Checking
# --------------------------------------------------------------------------- #


def check_prompt(prompt: str | None, negative: str | None, config: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a list of violations for one positive/negative prompt pair."""
    level = config["level"]
    fluids_ok = config["options"]["fluids"]
    contact_ok = config["options"]["nude_contact"]
    positive = tags(prompt)
    neg = tags(negative)
    violations: list[dict[str, Any]] = []

    def add(rule: str, found: list[str], message: str) -> None:
        if found:
            violations.append({"rule": rule, "tags": sorted(set(found)), "message": message})

    breast = _matches(positive, BREAST_EXPOSURE)
    groin = _matches(positive, GROIN_EXPOSURE)
    genital = _matches(positive, GENITAL_DETAIL)
    fluid = _matches(positive, FLUIDS)
    multi = _matches(positive, MULTI_CHARACTER)
    sexual = bool(breast or groin or genital or fluid)

    add("always_banned", _matches(positive, ALWAYS_BANNED), "性行為・自慰を想起させる動作・強要・排泄はどのレベルでも含めない。")
    if sexual:
        minor = MINOR_TAGS + (EOCS_EXTRA_MINOR if level == 3 else [])
        add("minor_tags", _matches(positive, minor), "露出表現を含むプロンプトに未成年を連想させるタグは入れない。")

    if level < 2:
        add("level1_groin", groin, "レベル1では股間の露出・パンティーの脱衣は不可。")
    if not fluids_ok:
        add("fluids", fluid, "このプロジェクトでは愛液・白い液体の表現は許可されていない（オプション fluids）。")
    if not contact_ok and multi and (breast or groin):
        add(
            "nude_contact",
            _matches(positive, CONTACT),
            "このプロジェクトでは露出した女性キャラクターへの抱擁・スキンシップは許可されていない（オプション nude_contact）。",
        )

    genital_allowed = level >= 3 and not multi
    if not genital_allowed:
        if level >= 3 and multi:
            message = "複数キャラクターの画像には性器・陰毛の描写（レベル3の許容）を適用しない。"
            rule = "multi_character_genital"
        else:
            message = f"レベル{level}では性器・陰毛の描写（positive の uncensored を含む）は不可。"
            rule = f"level{level}_genital"
        # A male character's exposed penis is governed by the multi-character
        # guideline (uncensored allowed there); only flag uncensored when no boy.
        has_boy = bool(_matches(positive, [r"(1|one) ?boy", r"[2-9]\+?boys", r"multiple boys", r"(solo )?male focus"]))
        found = [t for t in genital if not (t == "uncensored" and has_boy)]
        add(rule, found, message)

        exposed = breast or groin
        if exposed and not genital_allowed:
            missing = []
            if "uncensored" not in neg and not has_boy:
                missing.append("uncensored")
            if groin:
                if not _matches(neg, [r"pussy", r"vagina", r"vulva", r"genitals?"]):
                    missing.append("pussy")
                if not _matches(neg, [r"(female )?pubic hair"]):
                    missing.append("pubic hair")
            if missing:
                violations.append(
                    {
                        "rule": "required_negative",
                        "tags": missing,
                        "message": "露出表現を含むプロンプトの negative_prompt には uncensored と性器・陰毛の除外指定を入れる。",
                    }
                )
    return violations


def request_prompts(request: dict[str, Any]) -> list[tuple[str, str | None, str | None]]:
    """(label, positive, negative) pairs found in a runner request."""
    pairs: list[tuple[str, str | None, str | None]] = []
    if isinstance(request.get("prompt"), str):
        pairs.append(("prompt", request["prompt"], request.get("negative_prompt")))
    for key in ("characters", "character_prompts"):
        items = request.get(key)
        if isinstance(items, list):
            for index, item in enumerate(items):
                if isinstance(item, dict) and isinstance(item.get("prompt"), str):
                    neg = item.get("negative_prompt") or item.get("uc") or request.get("negative_prompt")
                    pairs.append((f"{key}[{index}]", item["prompt"], neg))
    return pairs


def check_request(request: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    # Character prompts share the base prompt's subject-count tags.
    base = request.get("prompt") if isinstance(request.get("prompt"), str) else ""
    result = []
    for label, positive, negative in request_prompts(request):
        text = positive if label == "prompt" else f"{base}, {positive}"
        for violation in check_prompt(text, negative, config):
            result.append({"field": label, **violation})
    return result


def enforce(request: dict[str, Any], root: Path | None) -> dict[str, Any]:
    """Raise ContentLevelError on violation; return the level summary otherwise."""
    config = load_config(root)
    violations = check_request(request, config)
    if violations:
        raise ContentLevelError(
            "CONTENT_LEVEL_VIOLATION",
            f"Request exceeds the project content level {config['level']} ({config['level_id']}). "
            "Change the prompt, or re-run the novelai-content-level skill if the project's level should change.",
            {"content_level": summary(config), "violations": violations},
        )
    return summary(config)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _iter_requests(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        path = Path(raw).expanduser()
        if path.is_dir():
            files.extend(sorted(p for p in path.rglob("*.json") if "manifest" not in p.parts))
        else:
            files.append(path)
    return files


def _cmd_show(args: argparse.Namespace) -> int:
    config = load_config(Path(args.project_root) if args.project_root else Path.cwd())
    print(json.dumps({"ok": True, **config, "label": LEVELS[config["level"]]["label"]}, ensure_ascii=False, indent=2))
    return 0


def _cmd_set(args: argparse.Namespace) -> int:
    root = Path(args.project_root or Path.cwd()).expanduser().resolve()
    level = LEVEL_IDS.get(args.level) or int(args.level)
    data: dict[str, Any] = {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "level": level,
        "level_id": LEVELS[level]["id"],
        "label": LEVELS[level]["label"],
        "options": {"fluids": args.fluids == "yes", "nude_contact": args.nude_contact == "yes"},
        "decided_at": args.date or date.today().isoformat(),
        "decided_by": "user (novelai-content-level hearing)",
    }
    if args.project:
        data["project"] = args.project
    if args.notes:
        data["notes"] = args.notes
    if level == 3:
        data["eocs_premises"] = {key: args.confirm_eocs for key in EOCS_PREMISES}
    path = root / CONFIG_RELPATH
    _validate(data, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "path": str(path), **data}, ensure_ascii=False, indent=2))
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    config = load_config(Path(args.project_root) if args.project_root else Path.cwd())
    failures = []
    checked = 0
    for path in _iter_requests(args.paths):
        try:
            request = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            failures.append({"path": str(path), "error": str(exc)})
            continue
        if not isinstance(request, dict) or not request_prompts(request):
            continue
        checked += 1
        violations = check_request(request, config)
        if violations:
            failures.append({"path": str(path), "violations": violations})
    print(
        json.dumps(
            {"ok": not failures, "content_level": summary(config), "checked": checked, "failures": failures},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not failures else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    show = commands.add_parser("show", help="print the project's content level")
    show.add_argument("--project-root")

    setp = commands.add_parser("set", help="record the level decided in the hearing")
    setp.add_argument("--project-root")
    setp.add_argument("--level", required=True, choices=["1", "2", "3", *LEVEL_IDS])
    setp.add_argument("--project", help="optional label; not asked in the hearing")
    setp.add_argument("--fluids", required=True, choices=["yes", "no"], help="愛液・白い液体の表現")
    setp.add_argument(
        "--nude-contact", required=True, choices=["yes", "no"],
        help="露出した女性キャラクターへの抱擁・スキンシップ（股間への接触は除く）",
    )
    setp.add_argument(
        "--confirm-eocs", action="store_true",
        help="level 3: user confirmed mosaic before release and human release check",
    )
    setp.add_argument("--notes")
    setp.add_argument("--date")

    check = commands.add_parser("check", help="lint request JSON files or folders against the level")
    check.add_argument("--project-root")
    check.add_argument("paths", nargs="+")

    args = parser.parse_args(argv)
    try:
        return {"show": _cmd_show, "set": _cmd_set, "check": _cmd_check}[args.command](args)
    except ContentLevelError as exc:
        print(json.dumps({"ok": False, "error": {"code": exc.code, "message": exc.message}}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
