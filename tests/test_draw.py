import secrets
import pytest
import fmcardgen.draw
import fmcardgen.config
from pathlib import Path
from PIL import Image, ImageStat, ImageChops

CONFIG = {
    "template": "template.png",
    "fields": [
        {
            "source": "title",
            "x": 200,
            "y": 200,
            "font": "RobotoCondensed/RobotoCondensed-Bold.ttf",
            "font_size": 200,
        }
    ],
}


def assert_images_equal(
    actual: Image.Image, expected: Image.Image, delta: float = 0.01
):
    assert (
        actual.width == expected.width and actual.height == expected.height
    ), "expected images to be the same dimensions"
    assert actual.mode == expected.mode, "expected images to be the same mode"

    diff = ImageChops.difference(actual, expected)
    stat = ImageStat.Stat(diff)
    num_channels = len(stat.mean)
    sum_channel_values = sum(stat.mean)
    max_all_channels = num_channels * 255.0
    diff_ratio = sum_channel_values / max_all_channels

    if diff_ratio > delta:
        token = secrets.token_urlsafe(8)
        save_location = Path(__file__).parent.parent.resolve()
        actual_path = save_location / f"{token}-actual.png"
        expected_path = save_location / f"{token}-expected.png"
        diff_path = save_location / f"{token}-diff.png"
        actual.save(str(actual_path))
        expected.save(str(expected_path))
        diff.save(str(diff_path))
        pytest.fail(
            f"images differ by {diff_ratio:.2f} (allowed={delta})\n"
            f"test images written to:\n"
            f"    actual: {actual_path}\n"
            f"    expected: {expected_path}\n"
            f"    diff: {diff_path}\n"
        )


@pytest.fixture(autouse=True)
def set_working_directory(monkeypatch):
    monkeypatch.chdir(Path(__file__).parent)


@pytest.fixture()
def config():
    return fmcardgen.config.CardGenConfig.parse_obj(CONFIG)


def test_draw(config):
    im = fmcardgen.draw.draw({"title": "Hello World"}, config)
    assert_images_equal(im, Image.open("test_draw_expected.png"))