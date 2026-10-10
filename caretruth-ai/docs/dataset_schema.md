# Dataset Schema & Field Mapping

CareTruth AI ingests `Hackathon_Dataset_India_Larg.csv` containing **10,000 healthcare facility records** across India with **41 columns**.

## Core Column Schema

| Column Name | Type | Description | Usage in System |
|---|---|---|---|
| `id` / `source_row` | int | 0-based dataset row index | Primary key & exact citation source |
| `name` | string | Facility name | Primary display name |
| `description` | string | Raw textual overview | Unstructured evidence extraction |
| `capability` | JSON array / string | Stated medical capabilities | Service matching & verification |
| `procedure` | JSON array / string | Procedures offered | Surgical capability checking |
| `equipment` | JSON array / string | Available equipment list | Equipment verification check |
| `specialties` | JSON array / string | Medical specialties | Category filtering |
| `facilityTypeId` | string | Facility type (e.g. Hospital, Clinic) | Capability-type mismatch validation |
| `latitude` | float | Geolocation latitude | Haversine distance calculation |
| `longitude` | float | Geolocation longitude | Haversine distance calculation |
| `address_zipOrPostcode` | string | PIN Code | Zip code matching & location display |
| `address_city` | string | City name | Regional analytics |
| `address_stateOrRegion` | string | State name | Regional coverage heatmaps |
| `numberDoctors` | float/int | Doctor headcount | Capacity verification |
| `capacity` | float/int | Bed capacity | High-volume operational checks |

## Derived Search & Verification Fields

- **`raw_text_blob`**: Unified concatenation of all text columns used for verbatim substring citation span matching.
- **`has_coords`**: Boolean flag indicating valid latitude & longitude coordinates.
- **`parsed_capabilities`**: Normalized lower-case list of capabilities for fast lookup.
- **`parsed_equipment`**: Normalized lower-case list of equipment for verification checks.
