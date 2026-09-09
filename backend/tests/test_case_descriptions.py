from app.evidence.descriptions import DatasetReference, case_description
from app.evidence.schemas import EvidenceSource


def test_hai_description_explains_the_source_without_assuming_expertise():
    description = case_description([DatasetReference(EvidenceSource.HAI_ICS_BLIND)])

    assert "industrial-control testbed" in description
    assert "Each row is one snapshot" in description
    assert "not camera footage" in description
    assert "attack labels were removed" in description


def test_known_home_and_iot_sources_explain_devices_and_label_provenance():
    casas = case_description([DatasetReference(EvidenceSource.CASAS, "casas_milan@1.0")])
    fridge = case_description(
        [DatasetReference(EvidenceSource.TON_IOT_TELEMETRY, "ton_iot_fridge_telemetry@1.0")]
    )
    iot23 = case_description([DatasetReference(EvidenceSource.IOT23_ZEEK_BLIND)])

    assert "motion sensors, door/contact sensors, and temperature sensors" in casas
    assert "no cameras" in casas.lower()
    assert "networked refrigerator" in fridge
    assert "DDoS come from labels supplied by the dataset" in fridge
    assert "Philips Hue smart light, Amazon Echo, and Somfy smart door lock" in iot23
    assert "attack labels were removed" in iot23


def test_mixed_case_description_explains_correlation_and_avoids_duplicate_sources():
    description = case_description(
        [
            DatasetReference(EvidenceSource.HAI_ICS_BLIND),
            DatasetReference(EvidenceSource.CASAS),
            DatasetReference(EvidenceSource.CASAS_SMART_HOME),
        ]
    )

    assert description.count("CASAS smart-home sensors") == 1
    assert "HAI industrial-control telemetry" in description
    assert "lines the records up by time" in description
    assert "genuine shared device or network details" in description
    assert "not proof that an attack happened" in description


def test_empty_and_simulated_cases_are_explicit_about_what_is_real():
    assert "No evidence has been imported yet" in case_description([])
    simulated = case_description([DatasetReference(EvidenceSource.SIMULATION)])
    assert "made-up demonstration data" in simulated
    assert "not evidence of a real incident" in simulated
