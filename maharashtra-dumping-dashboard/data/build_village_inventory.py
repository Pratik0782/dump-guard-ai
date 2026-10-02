import argparse
import csv
import json
from pathlib import Path


DISTRICTS = {
    "kolhapur": "Kolhapur",
    "sangali": "Sangli",
    "satara": "Satara",
}
TALUKA_ALIASES = {
    "gagan-bawada": "Gaganbawada",
    "hatkalangale": "Hatkanangale",
    "jath": "Jat",
    "mahableshwar": "Mahabaleshwar",
}


def _ring_centroid(ring):
    if len(ring) < 4:
        points = ring[:-1] if ring and ring[0] == ring[-1] else ring
        return (
            sum(point[0] for point in points) / len(points),
            sum(point[1] for point in points) / len(points),
            0.0,
        )

    points = ring[:-1] if ring[0] == ring[-1] else ring
    area_twice = 0.0
    longitude_sum = 0.0
    latitude_sum = 0.0
    for index, (longitude, latitude) in enumerate(points):
        next_longitude, next_latitude = points[(index + 1) % len(points)]
        cross = longitude * next_latitude - next_longitude * latitude
        area_twice += cross
        longitude_sum += (longitude + next_longitude) * cross
        latitude_sum += (latitude + next_latitude) * cross
    if abs(area_twice) < 1e-12:
        return (
            sum(point[0] for point in points) / len(points),
            sum(point[1] for point in points) / len(points),
            0.0,
        )
    return longitude_sum / (3 * area_twice), latitude_sum / (3 * area_twice), abs(area_twice) / 2


def _feature_centroid(feature):
    geometry = feature["geometry"]
    polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    centroids = [_ring_centroid(polygon[0]) for polygon in polygons if polygon]
    total_area = sum(area for _, _, area in centroids)
    if total_area:
        longitude = sum(lon * area for lon, _, area in centroids) / total_area
        latitude = sum(lat * area for _, lat, area in centroids) / total_area
    else:
        longitude = sum(lon for lon, _, _ in centroids) / len(centroids)
        latitude = sum(lat for _, lat, _ in centroids) / len(centroids)
    return latitude, longitude


def build_inventory(geojson_path: Path, crosswalk_path: Path, output_path: Path) -> int:
    with geojson_path.open(encoding="utf-8") as source_file:
        features = json.load(source_file)["features"]

    properties_by_code = {}
    for feature in features:
        properties = feature.get("properties", {})
        district = DISTRICTS.get(properties.get("DISTRICT", "").casefold())
        if district and properties.get("TYPE", "").casefold() == "village":
            properties_by_code[properties.get("CEN_2001", "")] = {
                **properties,
                "centroid": _feature_centroid(feature),
            }

    records = {}
    with crosswalk_path.open(encoding="utf-8-sig", newline="") as source_file:
        for row in csv.DictReader(source_file):
            properties = properties_by_code.get(row.get("CEN_2001", ""))
            village_name = row.get("village_name_2011", "").strip()
            if not properties or not village_name:
                continue

            district = DISTRICTS[properties["DISTRICT"].casefold()]
            source_taluka = properties.get("SUB_DIST", "").strip()
            taluka = TALUKA_ALIASES.get(source_taluka.casefold(), source_taluka)
            latitude, longitude = properties["centroid"]
            key = (district, taluka, village_name)
            records.setdefault(
                key,
                {
                    "district": district,
                    "taluka": taluka,
                    "village_name": village_name,
                    "village_code_2011": row.get("village_code_2011", ""),
                    "latitude": round(latitude, 6),
                    "longitude": round(longitude, 6),
                },
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as output_file:
        fieldnames = (
            "district",
            "taluka",
            "village_name",
            "village_code_2011",
            "latitude",
            "longitude",
        )
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records[key] for key in sorted(records))
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the 3-district village selector data.")
    parser.add_argument("geojson", type=Path, help="DataMeet Maharashtra village GeoJSON")
    parser.add_argument("crosswalk", type=Path, help="DataMeet Maharashtra 2001/2011 code CSV")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("villages_mh.csv"),
    )
    args = parser.parse_args()
    count = build_inventory(args.geojson, args.crosswalk, args.output)
    print(f"Wrote {count} village entries to {args.output}")


if __name__ == "__main__":
    main()