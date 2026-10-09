"""PUBLIC_STANDARD: unavailable runtimes retain discoverable contracts."""
from geoworld_open.client.models import CapabilityDescription


def test_unavailable_capability_roundtrips_its_actionable_reason():
    description = CapabilityDescription(name='scientific-operator', version='1.0', category='science',
        availability='unavailable', availability_reason='Scientific modeling is unavailable on this backend.',
        input_schema={}, output_schema={})
    assert CapabilityDescription.model_validate_json(description.model_dump_json()) == description
    assert description.availability == 'unavailable'
