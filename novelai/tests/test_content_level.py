"""Tests for novelai-imagegen/scripts/content_level.py."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / ".apm/skills/novelai-imagegen/scripts/content_level.py"
spec = importlib.util.spec_from_file_location("content_level", MODULE_PATH)
cl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cl)

NEG_SAFE = "bad anatomy, uncensored, pussy, pubic hair, loli, child"


def cfg(level: int, fluids: bool | None = None, nude_contact: bool | None = None) -> dict:
    default = level >= 2
    return {
        "level": level,
        "level_id": cl.LEVELS[level]["id"],
        "options": {
            "fluids": default if fluids is None else fluids,
            "nude_contact": default if nude_contact is None else nude_contact,
        },
    }


def rules(prompt: str, negative: str, level: int, **kw) -> set[str]:
    return {v["rule"] for v in cl.check_prompt(prompt, negative, cfg(level, **kw))}


def test_tags_normalisation():
    assert cl.tags("{{Completely_Nude}}, 1.2::pubic hair::, [nipples]") == ["completely nude", "pubic hair", "nipples"]


# --- level 1 ---------------------------------------------------------------

def test_level1_allows_topless():
    assert rules("1girl, topless, nipples, white panties, rating:explicit", "uncensored", 1) == set()


@pytest.mark.parametrize("tag", ["completely nude", "bottomless", "no panties", "pulling down panties", "pink panties around thighs"])
def test_level1_rejects_groin_exposure(tag):
    assert "level1_groin" in rules(f"1girl, {tag}", NEG_SAFE, 1)


@pytest.mark.parametrize("level", [1, 2, 3])
def test_fluids_follow_option_at_every_level(level):
    prompt = "1girl, topless, nipples, pussy juice"
    assert "fluids" in rules(prompt, NEG_SAFE, level, fluids=False)
    assert "fluids" not in rules(prompt, NEG_SAFE, level, fluids=True)


@pytest.mark.parametrize("level,exposure", [(1, "topless, nipples"), (2, "completely nude"), (3, "completely nude")])
def test_nude_contact_follows_option_at_every_level(level, exposure):
    prompt = f"1girl, 1boy, {exposure}, hug, kiss"
    assert "nude_contact" in rules(prompt, NEG_SAFE, level, nude_contact=False)
    assert "nude_contact" not in rules(prompt, NEG_SAFE, level, nude_contact=True)


def test_nude_contact_ignores_solo_and_clothed_images():
    assert "nude_contact" not in rules("1girl, solo, completely nude, hugging own legs", NEG_SAFE, 2, nude_contact=False)
    assert "nude_contact" not in rules("1girl, 1boy, school uniform, hug", "", 2, nude_contact=False)


def test_level1_topless_requires_uncensored_negative():
    assert "required_negative" in rules("1girl, topless, nipples", "bad anatomy", 1)


# --- level 2 ---------------------------------------------------------------

def test_level2_allows_nude_without_genitals():
    assert rules("1girl, completely nude, nipples, rating:explicit", NEG_SAFE, 2) == set()


@pytest.mark.parametrize("tag", ["pubic hair", "uncensored", "pussy"])
def test_level2_rejects_genital_detail(tag):
    assert "level2_genital" in rules(f"1girl, nude, {tag}", NEG_SAFE, 2)


def test_level2_requires_genital_exclusions_in_negative():
    found = cl.check_prompt("1girl, nude, nipples", "uncensored", cfg(2))
    assert found[0]["rule"] == "required_negative"
    assert set(found[0]["tags"]) == {"pussy", "pubic hair"}


def test_level2_male_penis_uncensored_allowed():
    # Multi-character guideline: uncensored is allowed for an exposed penis.
    assert "level2_genital" not in rules("1boy, solo, male focus, completely nude, uncensored", "pussy, pubic hair", 2)


# --- level 3 ---------------------------------------------------------------

def test_level3_allows_genitals_for_single_female():
    prompt = "1girl, solo, completely nude, nipples, pubic hair, uncensored, rating:explicit"
    assert rules(prompt, "bad anatomy, spread pussy, loli, child, multiple girls", 3) == set()


def test_level3_multi_character_falls_back_to_no_genitals():
    assert "multi_character_genital" in rules("2girls, nude, pubic hair, uncensored", NEG_SAFE, 3)


def test_level3_still_bans_spreading_and_minor_tags():
    assert "always_banned" in rules("1girl, nude, spread pussy", "", 3)
    assert "minor_tags" in rules("1girl, nude, schoolgirl", "", 3)


@pytest.mark.parametrize("level", [1, 2, 3])
def test_sex_acts_banned_at_every_level(level):
    assert "always_banned" in rules("1girl, 1boy, sex", NEG_SAFE, level)


def test_minor_tags_only_matter_with_exposure():
    assert rules("1girl, child, school uniform, smile", "", 1) == set()


# --- config ----------------------------------------------------------------

def test_missing_config_defaults_to_level2(tmp_path):
    loaded = cl.load_config(tmp_path)
    if loaded["source"] == "default":
        assert loaded["level"] == 2
    else:  # falls back to the project config next to the skill
        assert loaded["path"].endswith("novelai-content-level.json")


OPTS = ["--fluids", "no", "--nude-contact", "yes"]


def test_set_and_load_roundtrip(tmp_path):
    assert cl.main(["set", "--project-root", str(tmp_path), "--level", "1", *OPTS]) == 0
    data = json.loads((tmp_path / cl.CONFIG_RELPATH).read_text(encoding="utf-8"))
    assert data["level"] == 1 and "project" not in data
    assert data["options"] == {"fluids": False, "nude_contact": True}
    assert cl.load_config(tmp_path)["level"] == 1


def test_set_requires_both_options(tmp_path):
    with pytest.raises(SystemExit):
        cl.main(["set", "--project-root", str(tmp_path), "--level", "2", "--fluids", "yes"])


def test_level3_requires_confirmation(tmp_path):
    assert cl.main(["set", "--project-root", str(tmp_path), "--level", "3", *OPTS]) == 2
    assert not (tmp_path / cl.CONFIG_RELPATH).exists()
    assert cl.main(["set", "--project-root", str(tmp_path), "--level", "3", *OPTS, "--confirm-eocs"]) == 0
    data = json.loads((tmp_path / cl.CONFIG_RELPATH).read_text(encoding="utf-8"))
    assert set(data["eocs_premises"]) == {"mosaic_before_release", "human_release_check"}


def test_enforce_raises_with_details(tmp_path):
    cl.main(["set", "--project-root", str(tmp_path), "--level", "1", *OPTS])
    with pytest.raises(cl.ContentLevelError) as exc:
        cl.enforce({"prompt": "1girl, completely nude", "negative_prompt": NEG_SAFE}, tmp_path)
    assert exc.value.code == "CONTENT_LEVEL_VIOLATION"
    assert exc.value.details["content_level"]["level"] == 1


def test_source_layout_is_not_a_deployment():
    # The package source (.apm/skills/...) must not be mistaken for an agent dir.
    assert cl._deployment() == (None, None)
    assert cl.CONFIG_RELPATH == Path(".claude") / cl.CONFIG_FILENAME


def test_config_found_in_agents_dir(tmp_path):
    (tmp_path / ".agents").mkdir()
    (tmp_path / ".agents" / cl.CONFIG_FILENAME).write_text(
        json.dumps({"level": 1, "options": {"fluids": False, "nude_contact": False}}), encoding="utf-8"
    )
    loaded = cl.load_config(tmp_path)
    assert loaded["level"] == 1 and loaded["path"].endswith(".agents/" + cl.CONFIG_FILENAME)
