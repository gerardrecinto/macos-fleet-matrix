TITLE = "macOS Fleet Matrix ephemeral runner lifecycle"
DESCRIPTION = "Animated lifecycle from queue through lease, boot, build, teardown and recovery."


def test_architecture_svg_is_self_contained_and_animated() -> None:
    with open("docs/assets/fleet-lifecycle.svg", encoding="utf-8") as handle:
        svg = handle.read()

    assert svg.startswith("<svg")
    assert 'viewBox="0 0 1200 620"' in svg
    assert TITLE in svg
    assert DESCRIPTION in svg
    assert svg.count('<g transform="translate(') >= 6
    assert svg.count("<animate") >= 3
    assert "@media(prefers-reduced-motion:reduce)" in svg
    assert "<image" not in svg and "<iframe" not in svg
    assert 'href="http' not in svg and 'xlink:href="http' not in svg


def test_readme_embeds_repository_asset() -> None:
    with open("README.md", encoding="utf-8") as handle:
        readme = handle.read()

    assert "docs/assets/fleet-lifecycle.svg" in readme
