# Traceveil dataset catalog

This is the single starting point for reusable Traceveil datasets. Runtime case
storage remains under `data/evidence` and is intentionally not part of this
catalog.

## `sample/` — quick imports

| File | Import-page source | Profile | Notes |
| --- | --- | --- | --- |
| `sample/simulated-evidence.csv` | Simulation | `simulated@1.0` | Three synthetic smoke-test rows |
| `sample/hai-ics-blind-sample.csv` | HAI ICS · Blind | `hai_ics_blind@1.0` | 300 real HAI 23.05 telemetry rows; labels removed; each row contains dozens of independently analysed metrics |
| `sample/iot23-zeek-blind-sample.csv` | IoT-23 · Blind | `iot23_zeek_blind@1.0` | 1,000 real flows from four physical/scenario devices; labels removed |
| `sample/ton-iot-fridge-sample.csv` | TON_IoT Telemetry | `ton_iot_fridge_telemetry@1.0` | 1,000 rows balanced across the seven published classes |
| `sample/casas-milan-sample.csv` | CASAS | `casas_milan@1.0` | 1,000 contiguous smart-home sensor events |

The IoT-23, TON_IoT, and CASAS samples contain 1,000 rows. HAI is intentionally
smaller because one wide telemetry row produces many metric baselines and
comparisons. The samples preserve real device identities and do not create a
false shared device merely to force a correlation.

`sample/contract-fixtures/` contains tiny schema-contract inputs used by the
automated backend tests. They are useful for validation checks but are not
representative evaluation datasets.

## `full/` — not installed

The complete source archives, extracted originals, and import-ready full CSVs
were removed from this workspace to reclaim disk space. The `full/` directory
is intentionally absent. The preparation scripts remain under `backend/scripts/`
if full datasets are downloaded again later. For normal UI work, use the curated
files in `sample/`.

## Web-download copies

The simulation example plus the label-free HAI and IoT-23 research samples are
also copied to `frontend/public/examples/`. Those copies are required for the
download links in the running frontend; this directory is the human-facing
catalog.

Use `CHECKSUMS.sha256` to confirm that a local file has not changed.
See `DEVICE_INVENTORY.md` for the physical devices represented by each dataset.
