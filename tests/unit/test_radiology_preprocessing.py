"""TorchXRayVision models expect pixels scaled to [-1024, 1024] and a center crop."""
import numpy as np
import pytest
from PIL import Image

pytest.importorskip("torch")
pytest.importorskip("torchxrayvision")

from backend.services.radiology_service import RadiologyService  # noqa: E402


def _service(name="densenet121-res224-all"):
    svc = RadiologyService()
    svc.model_name = name
    return svc


def _save(tmp_path, arr, mode="L"):
    p = tmp_path / "x.png"
    Image.fromarray(arr.astype("uint8"), mode).save(p)
    return p


def test_output_shape_matches_model_resolution(tmp_path):
    p = _save(tmp_path, np.full((300, 300), 128))
    assert tuple(_service().preprocess_image(p).shape) == (1, 1, 224, 224)
    assert tuple(_service("resnet50-res512-all").preprocess_image(p).shape) == (1, 1, 512, 512)


def test_black_and_white_map_to_xrv_range_extremes(tmp_path):
    black = _service().preprocess_image(_save(tmp_path, np.zeros((256, 256))))
    white = _service().preprocess_image(_save(tmp_path, np.full((256, 256), 255)))
    assert black.min().item() == pytest.approx(-1024, abs=1)
    assert white.max().item() == pytest.approx(1024, abs=1)


def test_mid_gray_is_near_zero(tmp_path):
    out = _service().preprocess_image(_save(tmp_path, np.full((256, 256), 128)))
    assert abs(out.mean().item()) < 20


def test_non_square_image_is_center_cropped_not_squashed(tmp_path):
    arr = np.zeros((200, 600))
    arr[:, :200] = 255  # bright left strip
    arr[:, -200:] = 255  # bright right strip, dark middle square
    out = _service().preprocess_image(_save(tmp_path, arr))
    assert out.mean().item() < -1000  # only the dark middle survives the crop


def test_rgb_input_is_collapsed_to_one_channel(tmp_path):
    rgb = np.stack([np.full((256, 256), v) for v in (255, 0, 0)], axis=-1)
    p = tmp_path / "rgb.png"
    Image.fromarray(rgb.astype("uint8"), "RGB").save(p)
    out = _service().preprocess_image(p)
    assert out.shape[1] == 1
