import re
from pathlib import Path


TITLE = r"<title[^>]*>macOS Fleet Matrix ephemeral runner lifecycle</title>"
DESCRIPTION = (
    r"<desc[^>]*>Animated lifecycle from queue through lease, boot, "
    r"build, teardown and recovery.</desc>"
)


def test_architecture_svg_is_self_contained_and_animated() -> None:
    svg = Path("docs/assets/fleet-lifecycle.svg").read_text(encoding="utf-8")
    assert svg.startswith("<svg")
    assert 'viewBox="0 0 1200 620"' in svg
    assert re.search(TITLE, svg)
    assert re.search(DESCRIPTION, svg)
    assert svg.count('<g transform="translate(') >= 6
    assert svg.count("<animate") >= 3
    assert "@media(prefers-reduced-motion:reduce)" in svg
    assert "<image" not in svg and "<iframe" not in svg
    assert 'href="http' not in svg and 'xlink:href="http' not in svg


def test_readme_embeds_repository_asset() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "docs/assets/fleet-lifecycle.svg" in readme
