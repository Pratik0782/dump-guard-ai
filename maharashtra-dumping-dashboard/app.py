import csv
import io
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, send_from_directory

from risk_model import CATEGORICAL_FEATURES, NUMERIC_FEATURES, predict, predict_many, train_model


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "hotspots.csv"
SOURCE_NOTE = (
    "Synthetic incident and risk values. Locality names are representative, "
    "and coordinates are generated around district centres. These are not "
    "verified illegal-dumping incidents."
)

app = Flask(__name__)


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_rows():
    with DATA_PATH.open(encoding="utf-8-sig", newline="") as csv_file:
        rows = list(csv.DictReader(csv_file))

    for row in rows:
        for key in ("latitude", "longitude", "risk_score", "distance_to_main_road_km"):
            row[key] = _number(row.get(key))
        for key in (
            "incident_id",
            "hour",
            "month",
            "previous_incidents_30d",
            "complaints_30d",
        ):
            row[key] = int(_number(row.get(key)))
        try:
            row["date_sort"] = datetime.strptime(row["date"], "%d/%m/%Y").isoformat()
        except (KeyError, ValueError):
            row["date_sort"] = ""
    return rows


ROWS = _load_rows()
DISTRICTS = sorted({row["district"] for row in ROWS})
DISTRICT_TALUKAS = {
    "Kolhapur": [
        "Ajra",
        "Bhudargad",
        "Chandgad",
        "Gadhinglaj",
        "Gaganbawada",
        "Hatkanangale",
        "Kagal",
        "Karvir",
        "Panhala",
        "Radhanagari",
        "Shahuwadi",
        "Shirol",
    ],
    "Sangli": [
        "Atpadi",
        "Jat",
        "Kadegaon",
        "Kavathe Mahankal",
        "Khanapur",
        "Miraj",
        "Palus",
        "Shirala",
        "Tasgaon",
        "Walwa",
    ],
    "Satara": [
        "Jaoli",
        "Karad",
        "Khandala",
        "Khatav",
        "Koregaon",
        "Mahabaleshwar",
        "Man",
        "Patan",
        "Phaltan",
        "Satara",
        "Wai",
    ],
}
LOCALITIES = sorted(
    {
        (row["district"], row["taluka"], row["village_name"])
        for row in ROWS
    }
)


def _load_village_directory():
    with (BASE_DIR / "data" / "villages_mh.csv").open(
        encoding="utf-8-sig", newline=""
    ) as csv_file:
        return {
            (row["district"], row["taluka"], row["village_name"]): (
                float(row["latitude"]),
                float(row["longitude"]),
            )
            for row in csv.DictReader(csv_file)
        }


VILLAGE_COORDINATES = _load_village_directory()
PREDICTION_LOCALITIES = sorted(VILLAGE_COORDINATES)
INTEGER_PROFILE_FEATURES = {"hour", "month", "is_weekend", "night_indicator"}


def _prediction_profile(rows):
    defaults = {
        name: Counter(str(row[name]) for row in rows).most_common(1)[0][0]
        for name in CATEGORICAL_FEATURES
        if name not in {"district", "taluka", "village_name"}
    }
    for name in NUMERIC_FEATURES:
        if name in INTEGER_PROFILE_FEATURES:
            defaults[name] = int(
                Counter(int(row[name]) for row in rows).most_common(1)[0][0]
            )
            continue
        value = statistics.median(float(row[name]) for row in rows)
        if name in {"previous_incidents_30d", "complaints_30d"}:
            defaults[name] = int(round(value))
        else:
            defaults[name] = round(value, 2 if name == "distance_to_main_road_km" else 3)
    return {"sample_size": len(rows), "defaults": defaults}


@lru_cache(maxsize=1)
def _trained_model():
    return train_model(ROWS)


@lru_cache(maxsize=1)
def _all_village_results():
    rows_by_district = defaultdict(list)
    rows_by_taluka = defaultdict(list)
    rows_by_locality = defaultdict(list)
    for row in ROWS:
        rows_by_district[row["district"]].append(row)
        rows_by_taluka[(row["district"], row["taluka"])].append(row)
        rows_by_locality[(row["district"], row["taluka"], row["village_name"])].append(row)

    model_inputs = []
    metadata = []
    for locality in PREDICTION_LOCALITIES:
        district, taluka, village = locality
        records = rows_by_locality.get(locality, [])
        if records:
            profile_level = "village"
            profile_rows = records
        elif rows_by_taluka.get((district, taluka)):
            profile_level = "taluka"
            profile_rows = rows_by_taluka[(district, taluka)]
        else:
            profile_level = "district"
            profile_rows = rows_by_district[district]

        profile = _prediction_profile(profile_rows)
        latitude, longitude = VILLAGE_COORDINATES[locality]
        model_inputs.append(
            {
                "district": district,
                "taluka": taluka,
                "village_name": village,
                "latitude": latitude,
                "longitude": longitude,
                **profile["defaults"],
            }
        )
        metadata.append(
            {
                "district": district,
                "taluka": taluka,
                "village_name": village,
                "latitude": latitude,
                "longitude": longitude,
                "incident_rows": len(records),
                "profile_level": profile_level,
                "profile_sample_size": profile["sample_size"],
            }
        )

    predictions = predict_many(_trained_model(), model_inputs)
    return [
        {
            **location,
            **prediction,
            "high_risk_score": round(prediction["probabilities"].get("High", 0) * 100, 1),
        }
        for location, prediction in zip(metadata, predictions)
    ]


def _filtered_rows(args):
    district = args.get("district", "").strip()
    risk = args.get("risk", "").strip()
    query = args.get("q", "").strip().casefold()

    return [
        row
        for row in ROWS
        if (not district or row["district"] == district)
        and (not risk or row["hotspot_risk"] == risk)
        and (
            not query
            or query in " ".join(str(value) for value in row.values()).casefold()
        )
    ]


@app.get("/css/<path:filename>")
def css_asset(filename):
    return send_from_directory(BASE_DIR / "public" / "css", filename)


@app.get("/js/<path:filename>")
def js_asset(filename):
    return send_from_directory(BASE_DIR / "public" / "js", filename)


@app.get("/")
def index():
    districts = sorted({row["district"] for row in ROWS})
    return render_template("index.html", districts=districts)


@app.get("/api/prediction-options")
def prediction_options():
    numeric_defaults = {
        name: statistics.median(float(row[name]) for row in ROWS)
        for name in NUMERIC_FEATURES
    }
    for name in ("hour", "month", "is_weekend", "night_indicator", "previous_incidents_30d", "complaints_30d"):
        numeric_defaults[name] = round(numeric_defaults[name])

    district_rows = defaultdict(list)
    taluka_rows = defaultdict(list)
    locality_rows = defaultdict(list)
    for row in ROWS:
        district_rows[row["district"]].append(row)
        taluka_rows[(row["district"], row["taluka"])].append(row)
        locality_rows[(row["district"], row["taluka"], row["village_name"])].append(row)

    return jsonify(
        {
            "districts": DISTRICTS,
            "talukas_by_district": {
                district: sorted(
                    set(DISTRICT_TALUKAS.get(district, ()))
                    | {taluka for place_district, taluka, _ in LOCALITIES if place_district == district}
                )
                for district in DISTRICTS
            },
            "localities": [
                {"district": district, "taluka": taluka, "village_name": village}
                for district, taluka, village in PREDICTION_LOCALITIES
            ],
            "profiles": {
                "districts": [
                    {"district": district, **_prediction_profile(rows)}
                    for district, rows in sorted(district_rows.items())
                ],
                "talukas": [
                    {"district": district, "taluka": taluka, **_prediction_profile(rows)}
                    for (district, taluka), rows in sorted(taluka_rows.items())
                ],
                "localities": [
                    {
                        "district": district,
                        "taluka": taluka,
                        "village_name": village,
                        **_prediction_profile(rows),
                    }
                    for (district, taluka, village), rows in sorted(locality_rows.items())
                ],
            },
            "categories": {
                name: sorted({str(row[name]) for row in ROWS})
                for name in CATEGORICAL_FEATURES
                if name not in {"district", "taluka", "village_name"}
            },
            "defaults": numeric_defaults,
            "ranges": {
                name: [
                    min(float(row[name]) for row in ROWS),
                    max(float(row[name]) for row in ROWS),
                ]
                for name in NUMERIC_FEATURES
            },
            "risk_levels": ["High", "Medium", "Low"],
        }
    )


@app.post("/api/predict")
def predict_risk():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Send prediction inputs as JSON."}), 400

    locality = tuple(
        str(payload.get(name, "")).strip()
        for name in ("district", "taluka", "village_name")
    )
    district, taluka, village = locality
    if district not in DISTRICTS:
        return jsonify({"error": "Choose Kolhapur, Sangli, or Satara."}), 400
    if not taluka or not village:
        return jsonify({"error": "Enter both a taluka and village name."}), 400
    if len(taluka) > 100 or len(village) > 100:
        return jsonify({"error": "Taluka and village names must be 100 characters or fewer."}), 400
    locality_known = locality in LOCALITIES
    taluka_has_training_rows = any(
        record["district"] == district and record["taluka"] == taluka
        for record in ROWS
    )

    row = dict(zip(("district", "taluka", "village_name"), locality))
    coordinates = VILLAGE_COORDINATES.get(locality)
    if coordinates is None:
        profile_rows = [
            record
            for record in ROWS
            if record["district"] == district
            and (not taluka_has_training_rows or record["taluka"] == taluka)
        ]
        coordinates = (
            statistics.mean(record["latitude"] for record in profile_rows),
            statistics.mean(record["longitude"] for record in profile_rows),
        )
    row["latitude"], row["longitude"] = coordinates

    categorical_options = {
        name: {str(record[name]) for record in ROWS}
        for name in CATEGORICAL_FEATURES
        if name not in {"district", "taluka", "village_name"}
    }
    for name, allowed_values in categorical_options.items():
        value = str(payload.get(name, "")).strip()
        if value not in allowed_values:
            return jsonify({"error": f"Choose a valid {name.replace('_', ' ')}."}), 400
        row[name] = value

    integer_features = {
        "hour",
        "month",
        "is_weekend",
        "night_indicator",
        "previous_incidents_30d",
        "complaints_30d",
    }
    for name in NUMERIC_FEATURES:
        try:
            value = float(payload[name])
        except (KeyError, TypeError, ValueError):
            return jsonify({"error": f"Enter a valid value for {name.replace('_', ' ')}."}), 400
        if not math.isfinite(value):
            return jsonify({"error": f"Enter a finite value for {name.replace('_', ' ')}."}), 400
        minimum = min(float(record[name]) for record in ROWS)
        maximum = max(float(record[name]) for record in ROWS)
        if value < minimum or value > maximum:
            return jsonify(
                {"error": f"{name.replace('_', ' ').capitalize()} must be between {minimum:g} and {maximum:g}."}
            ), 400
        if name in integer_features and not value.is_integer():
            return jsonify({"error": f"{name.replace('_', ' ').capitalize()} must be a whole number."}), 400
        row[name] = int(value) if name in integer_features else value

    model_bundle = _trained_model()
    return jsonify(
        {
            **predict(model_bundle, row),
            "model": {
                "name": "Random Forest classifier",
                **model_bundle["metrics"],
            },
            "locality_known": locality_known,
            "locality_note": (
                "This village appears in the incident sample. Its estimate uses synthetic labels and the approximate mapped centroid."
                if locality_known
                else (
                    "This village has no village-specific incident rows. Its approximate mapped centroid and the selected taluka's typical conditions are used for the estimate."
                    if taluka_has_training_rows
                    else "This village and taluka have no incident rows. Its approximate mapped centroid and the selected district's typical conditions are used for the estimate."
                )
            ),
            "disclaimer": "Prediction learned from synthetic sample labels; it is not a verified real-world risk assessment.",
        }
    )


@app.get("/api/dashboard")
def dashboard_data():
    rows = _filtered_rows(request.args)
    risk_counts = Counter(row["hotspot_risk"] for row in rows)
    district_counts = Counter(row["district"] for row in rows)
    waste_counts = Counter(row["waste_type"] for row in rows)
    month_counts = Counter(row["date"][-4:] + "-" + row["date"][3:5] for row in rows)
    hour_counts = Counter(row["hour"] for row in rows)

    grouped_locations = defaultdict(list)
    for row in rows:
        key = (row["district"], row["taluka"], row["village_name"])
        grouped_locations[key].append(row)

    locations = []
    for (district, taluka, village), incidents in grouped_locations.items():
        location_risk = Counter(item["hotspot_risk"] for item in incidents)
        locations.append(
            {
                "district": district,
                "taluka": taluka,
                "village_name": village,
                "incidents": len(incidents),
                "latitude": sum(item["latitude"] for item in incidents) / len(incidents),
                "longitude": sum(item["longitude"] for item in incidents) / len(incidents),
                "risk_score": round(
                    sum(item["risk_score"] for item in incidents) / len(incidents), 2
                ),
                "hotspot_risk": location_risk.most_common(1)[0][0],
            }
        )

    sorted_rows = sorted(rows, key=lambda row: row["risk_score"], reverse=True)
    return jsonify(
        {
            "total": len(rows),
            "average_risk": round(
                sum(row["risk_score"] for row in rows) / len(rows), 2
            )
            if rows
            else 0,
            "risk_counts": dict(risk_counts),
            "district_counts": dict(district_counts),
            "waste_counts": dict(waste_counts),
            "monthly_counts": dict(sorted(month_counts.items())),
            "hour_counts": dict(sorted(hour_counts.items())),
            "locations": sorted(
                locations,
                key=lambda location: location["risk_score"],
                reverse=True,
            )[:12],
            "map_points": locations,
            "source_note": SOURCE_NOTE,
        }
    )


@app.get("/api/records")
def records_data():
    rows = sorted(
        _filtered_rows(request.args),
        key=lambda row: row["date_sort"],
        reverse=True,
    )
    page = max(1, request.args.get("page", 1, type=int))
    page_size = 25
    start = (page - 1) * page_size
    records = [
        {key: value for key, value in row.items() if key != "date_sort"}
        for row in rows[start : start + page_size]
    ]
    return jsonify(
        {
            "records": records,
            "total": len(rows),
            "page": page,
            "page_size": page_size,
        }
    )


@app.get("/api/village-results")
def village_results_data():
    district = request.args.get("district", "").strip()
    risk = request.args.get("risk", "").strip()
    query = request.args.get("q", "").strip().casefold()
    villages = [
        row
        for row in _all_village_results()
        if (not district or row["district"] == district)
        and (not risk or row["risk_level"] == risk)
        and (
            not query
            or query
            in f"{row['district']} {row['taluka']} {row['village_name']}".casefold()
        )
    ]
    villages.sort(key=lambda row: (-row["high_risk_score"], row["district"], row["taluka"], row["village_name"]))
    page = max(1, request.args.get("page", 1, type=int))
    page_size = 50
    start = (page - 1) * page_size
    return jsonify(
        {
            "villages": villages[start : start + page_size],
            "total": len(villages),
            "page": page,
            "page_size": page_size,
            "risk_counts": dict(Counter(row["risk_level"] for row in villages)),
            "district_counts": dict(Counter(row["district"] for row in villages)),
            "with_incident_rows": sum(row["incident_rows"] > 0 for row in villages),
            "without_incident_rows": sum(row["incident_rows"] == 0 for row in villages),
            "source_note": "Modelled village results use synthetic training labels and approximate village centroids. Where available, typical conditions come from village records; otherwise taluka or district profiles are used.",
        }
    )


@app.get("/api/export")
def export_data():
    rows = _filtered_rows(request.args)
    output = io.StringIO(newline="")
    fieldnames = [key for key in ROWS[0] if key != "date_sort"] if ROWS else []
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=filtered-hotspots.csv"},
    )


if __name__ == "__main__":
    app.run(debug=True, port=5051)