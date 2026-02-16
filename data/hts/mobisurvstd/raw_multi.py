import os
import polars as pl
import mobisurvstd

"""
This stage loads and merges multiple mobility surveys using MobiSurvStd and
produces a single standardized survey compatible with the eqasim pipeline.

Supports:
- multiple surveys
- department priority rules
- source tracking
"""

def configure(context):
    context.config("data_path")
    context.config("mobisurvstd_surveys")
    context.config("mobisurvstd_skip_spatial", True)

    context.config("output_path")

    surveys = context.config("mobisurvstd_surveys")
    for s in surveys:
        assert "survey_type" in s, \
            f"Survey {s['name']} must define survey_type"


def survey_path(context, survey_cfg):
    return os.path.join(context.config("data_path"), survey_cfg["path"])


def load_one_survey(context, survey_cfg):
    path = survey_path(context, survey_cfg)

    if not (os.path.isfile(path) or os.path.isdir(path)):
        raise RuntimeError(f"Survey path does not exist: {path}")

    std = mobisurvstd.standardize(
        source=path,
        output_directory=None,
        survey_type=survey_cfg.get("survey_type"),
        add_name_subdir=False,
        skip_spatial=context.config("mobisurvstd_skip_spatial"),
        no_validation=False
    )

    if std is None:
        raise RuntimeError(f"MobiSurvStd failed for survey {survey_cfg['name']}")

    # add source column
    hh = std.households.with_columns(
        source_survey=pl.lit(survey_cfg["name"])
    )
    pp = std.persons.with_columns(
        source_survey=pl.lit(survey_cfg["name"])
    )
    tt = std.trips.with_columns(
        source_survey=pl.lit(survey_cfg["name"])
    )

    return std, hh, pp, tt


def prefix_ids(hh, pp, tt):
    """Avoid cross-survey ID collisions"""

    hh = hh.with_columns(
        household_id=pl.col("source_survey") + "_" +
        pl.col("household_id").cast(pl.String)
    )

    pp = pp.with_columns(
        household_id=pl.col("source_survey") + "_" +
        pl.col("household_id").cast(pl.String),
        person_id=pl.col("source_survey") + "_" +
        pl.col("person_id").cast(pl.String)
    )

    tt = tt.with_columns(
        household_id=pl.col("source_survey") + "_" +
        pl.col("household_id").cast(pl.String),
        person_id=pl.col("source_survey") + "_" +
        pl.col("person_id").cast(pl.String),
        trip_id=pl.col("source_survey") + "_" +
        pl.col("trip_id").cast(pl.String)
    )

    return hh, pp, tt


def build_priority_map(surveys_cfg):
    """
    Build department -> survey_name priority map.
    First survey declaring a department wins.
    """
    priority = {}

    for cfg in surveys_cfg:
        for dep in cfg.get("priority_departments", []):
            dep = str(dep)
            if dep in priority:
                raise RuntimeError(
                    f"Department {dep} declared in multiple priority surveys "
                    f"({priority[dep]} and {cfg['name']})"
                )
            priority[dep] = cfg["name"]

    return priority


def filter_by_priority(households, persons, trips, priority_map):
    """
    Keep only households belonging to their priority survey when defined.
    """

    if not priority_map:
        return households, persons, trips

    priority_df = pl.DataFrame({
        "home_dep": list(priority_map.keys()),
        "priority_survey": list(priority_map.values())
    })

    households = households.join(
        priority_df,
        left_on="home_dep",
        right_on="home_dep",
        how="left"
    )

    households = households.filter(
        pl.col("priority_survey").is_null()
        | (pl.col("priority_survey") == pl.col("source_survey"))
    ).drop("priority_survey")

    # keep only linked persons/trips
    persons = persons.join(
        households.select("household_id"),
        on="household_id",
        how="semi"
    )

    trips = trips.join(
        households.select("household_id"),
        on="household_id",
        how="semi"
    )

    return households, persons, trips


def apply_priority(hh, pp, tt, priority_map):
    if not priority_map:
        return hh, pp, tt

    p_df = pl.DataFrame({
        "home_dep": list(priority_map.keys()),
        "priority_survey": list(priority_map.values())
    })

    hh = hh.join(p_df, on="home_dep", how="left")

    hh = hh.filter(
        pl.col("priority_survey").is_null() |
        (pl.col("priority_survey") == pl.col("source_survey"))
    ).drop("priority_survey")

    pp = pp.join(hh.select("household_id"), on="household_id", how="semi")
    tt = tt.join(hh.select("household_id"), on="household_id", how="semi")

    return hh, pp, tt


def ensure_unique_ids(households, persons, trips):
    """
    Prefix IDs with survey name to avoid collisions across surveys.
    """

    households = households.with_columns(
        household_id=pl.col("source_survey") + "_" + pl.col("household_id").cast(pl.String)
    )

    persons = persons.with_columns(
        household_id=pl.col("source_survey") + "_" + pl.col("household_id").cast(pl.String),
        person_id=pl.col("source_survey") + "_" + pl.col("person_id").cast(pl.String)
    )

    trips = trips.with_columns(
        household_id=pl.col("source_survey") + "_" + pl.col("household_id").cast(pl.String),
        person_id=pl.col("source_survey") + "_" + pl.col("person_id").cast(pl.String),
        trip_id=pl.col("source_survey") + "_" + pl.col("trip_id").cast(pl.String)
    )

    return households, persons, trips

def force_string_ids(df, cols):
    for c in cols:
        if c in df.columns:
            df = df.with_columns(pl.col(c).cast(pl.String))
    return df

def execute(context):
    surveys_cfg = context.config("mobisurvstd_surveys")

    if not isinstance(surveys_cfg, list) or not surveys_cfg:
        raise RuntimeError("mobisurvstd_surveys must be a non-empty list")

    all_households = []
    all_persons = []
    all_trips = []
    survey_objects = []

    print(f"Loading {len(surveys_cfg)} mobility surveys...")

    for cfg in surveys_cfg:
        print(f"  -> {cfg['name']}")
        std, hh, pp, tt = load_one_survey(context, cfg)

        hh, pp, tt = prefix_ids(hh, pp, tt)

        survey_objects.append(std)
        all_households.append(hh)
        all_persons.append(pp)
        all_trips.append(tt)

    print("Concatenating surveys (schema-relaxed)...")

    households = pl.concat(all_households, how="vertical_relaxed")
    persons = pl.concat(all_persons, how="vertical_relaxed")
    trips = pl.concat(all_trips, how="vertical_relaxed")

    # harmonize id types
    households = force_string_ids(households, ["household_id", "home_dep"])
    persons = force_string_ids(persons, ["person_id", "household_id"])
    trips = force_string_ids(trips, ["trip_id", "person_id", "household_id"])

    print("Applying department priority rules...")
    priority_map = build_priority_map(surveys_cfg)
    households, persons, trips = apply_priority(
        households, persons, trips, priority_map
    )

    #if priority_map:
    #   print(f"Applying priority filter on {len(priority_map)} departments")
    #    households, persons, trips = filter_by_priority(
    #        households, persons, trips, priority_map
    #    )

    print("Final merged survey sizes:")
    print(f"  households: {len(households):,}")
    print(f"  persons:    {len(persons):,}")
    print(f"  trips:      {len(trips):,}")

    base = survey_objects[0]
    base.households = households
    base.persons = persons
    base.trips = trips

    return base


def validate(context):
    surveys_cfg = context.config("mobisurvstd_surveys")

    for cfg in surveys_cfg:
        path = survey_path(context, cfg)
        assert os.path.isfile(path) or os.path.isdir(path), \
            f"Cannot read survey from `{path}`"
