from unittest.mock import MagicMock, patch

from backend.services import radiology_service
from backend.services.radiology_service import RadiologyService


def test_two_instances_share_one_loaded_model():
    radiology_service._MODEL_CACHE.clear()
    fake = MagicMock()
    fake.to.return_value = fake
    fake.pathologies = ["Edema"]
    with patch("torchxrayvision.models.DenseNet", return_value=fake) as ctor:
        a, b = RadiologyService(), RadiologyService()
        assert a.load_model() and b.load_model()
    assert ctor.call_count == 1
    assert a.model is b.model and b.supported_labels == ["Edema"]
    radiology_service._MODEL_CACHE.clear()


def test_a_failed_load_is_not_cached():
    radiology_service._MODEL_CACHE.clear()
    with patch("torchxrayvision.models.DenseNet", side_effect=RuntimeError("weights missing")):
        try:
            RadiologyService().load_model()
        except Exception:
            pass
    assert radiology_service._MODEL_CACHE == {}
