# Dataset device inventory

This catalog distinguishes a physical device from a dataset row. A HAI row is
one whole-testbed snapshot, a CASAS row is one individual sensor event, a
TON_IoT row is refrigerator telemetry, and an IoT-23 row is one network flow.

| Dataset | Devices represented | What Traceveil uses as `device_id` | Camera data? |
| --- | --- | --- | --- |
| HAI 23.05 | P1 boiler and heat-transfer process; P2 turbine/rotor process; P3 water-treatment pumps and reservoirs; P4 hardware-in-the-loop process. Control hardware includes Emerson Ovation and GE Mark VIe DCSs, Siemens S7-300/S7-1500 PLCs, ET200 remote I/O, and dSPACE SCALEXIO. | `hai-testbed-01` for the combined testbed. The `P1_`…`P4_` columns are individual sensor, actuator, and controller points—not separate cameras. | No. This is industrial process/control telemetry. |
| IoT-23 | Malicious scenarios were captured from a malware-running Raspberry Pi. The three benign captures use a Philips Hue smart LED lamp, Amazon Echo smart assistant, and Somfy smart door lock. | A stable scenario/device identifier added during preparation; source and destination IPs remain separate network entities. | No camera is identified in the official IoT-23 device set. |
| CASAS Milan | 28 `Mxxx` passive-infrared motion sensors, three `Dxxx` door/contact sensors, and two `Txxx` temperature sensors in a smart apartment. | The native sensor ID (`M001`…`M028`, `D001`…`D003`, or `T001`…`T002`). | No. The activity is inferred from ambient sensors, not video. |
| TON_IoT refrigerator | One networked refrigerator reporting temperature and a high/low condition. | The TON_IoT refrigerator adapter identifies it as a `smart_refrigerator`. | No. This local subset is refrigerator telemetry. |

## Interpreting connections

Only merge records as the same device when their stable `device_id` genuinely
matches. IP addresses are retained as network entities because they can change,
be shared, or describe a remote peer. HAI's signal prefixes identify testbed
processes, while CASAS sensor IDs identify individual physical sensors. This
prevents unrelated devices from being correlated simply because two datasets
have similar timestamps.

Sources: [HAI official repository](https://github.com/icsdataset/hai),
[IoT-23 official dataset page](https://www.stratosphereips.org/datasets-iot23),
and the locally installed CASAS Milan and TON_IoT source files.
