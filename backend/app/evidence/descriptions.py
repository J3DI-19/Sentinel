from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.evidence.schemas import EvidenceSource


MANAGED_DESCRIPTION_PREFIX = "Dataset overview:"


@dataclass(frozen=True)
class DatasetReference:
    source: EvidenceSource
    profile: str | None = None


@dataclass(frozen=True)
class DatasetExplanation:
    name: str
    row_kind: str
    description: str


_EXPLANATIONS = {
    EvidenceSource.HAI_ICS_BLIND: DatasetExplanation(
        name="HAI industrial-control telemetry",
        row_kind="a snapshot of readings and control states across the testbed",
        description=(
            "This is real industrial-control testbed data from boiler, turbine, water-treatment, "
            "pump, tank, sensor, actuator, and PLC systems. Each row is one snapshot containing many "
            "measurements; it is not camera footage. The original attack labels were removed, so "
            "Traceveil flags unusual changes in the measurements without being told which rows are attacks."
        ),
    ),
    EvidenceSource.IOT23_ZEEK_BLIND: DatasetExplanation(
        name="IoT-23 network traffic",
        row_kind="one network connection or flow",
        description=(
            "This is network-connection data from IoT-23 scenarios involving a Raspberry Pi, Philips "
            "Hue smart light, Amazon Echo, and Somfy smart door lock. Each row describes a network "
            "connection, not a photo or video. The original attack labels were removed, so Traceveil "
            "looks for unusual communication patterns without being told which flows are malicious."
        ),
    ),
    EvidenceSource.CASAS: DatasetExplanation(
        name="CASAS smart-home sensors",
        row_kind="one motion, door, or temperature sensor event",
        description=(
            "This is smart-apartment data from motion sensors, door/contact sensors, and temperature "
            "sensors. Each row says which sensor changed and when. There are no cameras or recordings; "
            "Traceveil uses the sequence and timing of these small sensor events to find unusual activity."
        ),
    ),
    EvidenceSource.CASAS_SMART_HOME: DatasetExplanation(
        name="CASAS smart-home sensors",
        row_kind="one motion, door, or temperature sensor event",
        description=(
            "This is smart-home data from motion sensors, door/contact sensors, and temperature sensors. "
            "Each row says which sensor changed and when. There are no cameras or recordings; Traceveil "
            "uses the sequence and timing of these small sensor events to find unusual activity."
        ),
    ),
    EvidenceSource.TON_IOT_FRIDGE_TELEMETRY: DatasetExplanation(
        name="TON_IoT refrigerator telemetry",
        row_kind="one refrigerator temperature and operating-state reading",
        description=(
            "This is data from a networked refrigerator reporting its temperature and high/low operating "
            "condition. Each row is one device reading, not camera data. Normal and attack names such as "
            "DDoS come from labels supplied by the dataset; Traceveil clearly separates those supplied "
            "labels from patterns it discovers itself."
        ),
    ),
    EvidenceSource.TON_IOT_TELEMETRY: DatasetExplanation(
        name="TON_IoT device telemetry",
        row_kind="one smart-device measurement or state update",
        description=(
            "This is smart-device telemetry, such as temperature or operating-state readings from a "
            "networked refrigerator. Each row is one device measurement, not camera data. Normal and "
            "attack names such as DDoS come from labels supplied by the dataset; Traceveil clearly "
            "separates those supplied labels from patterns it discovers itself."
        ),
    ),
    EvidenceSource.TON_IOT_NETWORK: DatasetExplanation(
        name="TON_IoT network traffic",
        row_kind="one network flow between a source and destination",
        description=(
            "This is network-traffic data showing which computers or IoT devices communicated, when, "
            "and through which ports and protocols. Each row is one network flow, not the content of a "
            "camera or microphone. Any normal or attack name in the file is a label supplied by the "
            "dataset and is shown separately from Traceveil's own findings."
        ),
    ),
    EvidenceSource.CICIOT2023_NETWORK: DatasetExplanation(
        name="CICIoT2023 network traffic",
        row_kind="one summary of IoT network activity",
        description=(
            "This is summarized network-traffic data from IoT device scenarios. Each row contains counts "
            "and measurements about network activity rather than a photo, video, or message. Any attack "
            "name in the file is a label supplied by the dataset and is shown separately from Traceveil's "
            "own findings."
        ),
    ),
    EvidenceSource.SIMULATION: DatasetExplanation(
        name="simulated demonstration events",
        row_kind="one made-up device event",
        description=(
            "This is made-up demonstration data used to show how Traceveil handles device events, "
            "timestamps, findings, and alerts. Each row represents a simulated device action or reading. "
            "It is useful for testing the workflow, but it is not evidence of a real incident."
        ),
    ),
    EvidenceSource.SIMULATED: DatasetExplanation(
        name="simulated demonstration events",
        row_kind="one made-up device event",
        description=(
            "This is made-up demonstration data used to show how Traceveil handles device events, "
            "timestamps, findings, and alerts. Each row represents a simulated device action or reading. "
            "It is useful for testing the workflow, but it is not evidence of a real incident."
        ),
    ),
    EvidenceSource.GENERIC: DatasetExplanation(
        name="generic uploaded records",
        row_kind="one record from the uploaded file",
        description=(
            "This is a general-purpose upload that does not match one of Traceveil's named datasets. "
            "Each row is treated as an event using the timestamps, device names, and other fields present "
            "in the file. Check the Evidence view to see exactly what the original columns mean."
        ),
    ),
}


def is_managed_case_description(value: str | None) -> bool:
    return not (value or "").strip() or (value or "").startswith(MANAGED_DESCRIPTION_PREFIX)


def _explanation(reference: DatasetReference) -> DatasetExplanation:
    profile = (reference.profile or "").lower()
    if reference.source == EvidenceSource.TON_IOT_TELEMETRY and "fridge" in profile:
        return _EXPLANATIONS[EvidenceSource.TON_IOT_FRIDGE_TELEMETRY]
    return _EXPLANATIONS[reference.source]


def case_description(references: Iterable[DatasetReference]) -> str:
    unique: dict[tuple[str, str], DatasetReference] = {}
    for reference in references:
        explanation = _explanation(reference)
        unique[(explanation.name, explanation.row_kind)] = reference

    ordered = [_explanation(unique[key]) for key in sorted(unique)]
    if not ordered:
        return (
            f"{MANAGED_DESCRIPTION_PREFIX} No evidence has been imported yet. Leave this description "
            "as-is and Traceveil will replace it with a simple explanation after the first dataset is imported."
        )
    if len(ordered) == 1:
        return f"{MANAGED_DESCRIPTION_PREFIX} {ordered[0].description}"

    contents = "; ".join(f"{item.name} ({item.row_kind})" for item in ordered)
    return (
        f"{MANAGED_DESCRIPTION_PREFIX} This case combines {contents}. Traceveil lines the records up "
        "by time and compares genuine shared device or network details to show possible connections "
        "between datasets. A finding means a rule noticed something worth reviewing; it is not proof "
        "that an attack happened."
    )
