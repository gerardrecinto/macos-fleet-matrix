from pathlib import Path
import re


def test_architecture_svg_is_self_contained_and_animated() -> None:
    svg = Path("docs/assets/fleet-lifecycle.svg").read_text(encoding="utf-8")
    assert svg.startswith("<svg")
    assert 'viewBox="0 0 1200 620"' in svg
    assert "<title>macOS Fleet Matrix ephemeral runner lifecycle</title>" in svg
    assert "<desc>Animated lifecycle from queue through lease, boot, build, teardown and recovery.</desc>" in svg
    assert svg.count("<g transform=\"translate(") >= 6
    assert svg.count("<animate") >= 3
    assert "@media(prefers-reduced-motion:reduce)" in svg
    assert not re.search(r"https?://", svg)


def test_readme_embeds_repository_asset() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "docs/assets/fleet-lifecycle.svg" in readme
