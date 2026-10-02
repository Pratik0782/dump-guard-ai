from collections import Counter
from typing import Any

from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
from sklearn.model_selection import GroupShuffleSplit


CATEGORICAL_FEATURES = (
    "district",
    "taluka",
    "village_name",
    "waste_type",
    "land_type",
    "weather",
)
NUMERIC_FEATURES = (
    "hour",
    "month",
    "is_weekend",
    "previous_incidents_30d",
    "complaints_30d",
    "distance_to_main_road_km",
    "nearby_road_density_km",
    "night_indicator",
)
SPATIAL_FEATURES = ("latitude", "longitude")
TARGET = "hotspot_risk"


def _features(row: dict[str, Any]) -> dict[str, Any]:
    features = {name: str(row[name]) for name in CATEGORICAL_FEATURES}
    features.update({name: float(row[name]) for name in NUMERIC_FEATURES})
    features.update({name: float(row[name]) for name in SPATIAL_FEATURES})
    return features


def _group(row: dict[str, Any]) -> str:
    return "|".join(str(row[name]) for name in ("district", "taluka", "village_name"))


def _new_classifier() -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=100,
        min_samples_leaf=5,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=1,
    )


def train_model(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) < 10:
        raise ValueError("At least 10 labeled dataset rows are required to train.")

    labels = [str(row[TARGET]) for row in rows]
    groups = [_group(row) for row in rows]
    train_indices, test_indices = next(
        GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42).split(
            rows, labels, groups
        )
    )

    validation_rows = [rows[index] for index in train_indices]
    held_out_rows = [rows[index] for index in test_indices]
    validation_labels = [labels[index] for index in train_indices]
    held_out_labels = [labels[index] for index in test_indices]

    validation_encoder = DictVectorizer()
    validation_features = validation_encoder.fit_transform(
        [_features(row) for row in validation_rows]
    )
    held_out_features = validation_encoder.transform(
        [_features(row) for row in held_out_rows]
    )
    validation_classifier = _new_classifier()
    validation_classifier.fit(validation_features, validation_labels)
    held_out_predictions = validation_classifier.predict(held_out_features)

    encoder = DictVectorizer()
    all_features = encoder.fit_transform([_features(row) for row in rows])
    classifier = _new_classifier()
    classifier.fit(all_features, labels)

    return {
        "encoder": encoder,
        "classifier": classifier,
        "metrics": {
            "records": len(rows),
            "localities": len(set(groups)),
            "held_out_localities": len({_group(row) for row in held_out_rows}),
            "accuracy": round(accuracy_score(held_out_labels, held_out_predictions), 3),
            "balanced_accuracy": round(
                balanced_accuracy_score(held_out_labels, held_out_predictions), 3
            ),
            "macro_f1": round(
                f1_score(
                    held_out_labels,
                    held_out_predictions,
                    average="macro",
                    zero_division=0,
                ),
                3,
            ),
            "validation": "20% held-out localities",
            "class_counts": dict(Counter(labels)),
        },
    }


def predict_many(
    model_bundle: dict[str, Any], rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    features = model_bundle["encoder"].transform([_features(row) for row in rows])
    classifier = model_bundle["classifier"]
    predictions = []
    for probabilities in classifier.predict_proba(features):
        class_probabilities = {
            str(label): round(float(probability), 3)
            for label, probability in zip(classifier.classes_, probabilities)
        }
        predictions.append(
            {
                "risk_level": str(classifier.classes_[probabilities.argmax()]),
                "confidence": round(float(probabilities.max()), 3),
                "probabilities": class_probabilities,
            }
        )
    return predictions


def predict(model_bundle: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    return predict_many(model_bundle, [row])[0]