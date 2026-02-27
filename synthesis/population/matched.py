from tqdm import tqdm
import itertools
import numpy as np
import pandas as pd
import numba
from pathlib import Path

import data.hts.egt.cleaned
import data.hts.entd.cleaned

"""
This stage attaches obervations from the household travel survey to the synthetic
population sample. This is done by statistical matching.

Hierarchical statistical matching with:
- intra-survey priority
- inter-survey fallback
- weight stabilization
- matching diagnostics logs
"""

INCOME_CLASS = {
    "egt": data.hts.egt.cleaned.calculate_income_class,
    "entd": data.hts.entd.cleaned.calculate_income_class,
}

DEFAULT_MATCHING_ATTRIBUTES = [
    "sex", "any_cars", "age_class", "socioprofessional_class",
    "departement_id"
]

def configure(context):
    context.config("processes")
    context.config("random_seed")
    context.config("matching_minimum_observations", 20)
    context.config("matching_minimum_observations_fallback", 5)
    context.config("matching_attributes", DEFAULT_MATCHING_ATTRIBUTES)
    context.config("matching_log_path")

    context.stage("synthesis.population.sampled")
    context.stage("synthesis.population.income.selected")
    context.stage("data.hts.selected", alias="hts")

@numba.jit(nopython=True) # Already parallelized parallel = True)
def sample_indices(uniform, cdf, selected_indices):
    out = np.empty(len(uniform), dtype=np.int64)
    for i, u in enumerate(uniform):
        out[i] = selected_indices[np.searchsorted(cdf, u)]
    return out

# ------------------------------------------------------------------
# MATCHING ENGINE
# ------------------------------------------------------------------

def statistical_matching(progress, df_source, source_identifier, weight,
                         df_target, target_identifier, columns,
                         random_seed=0, minimum_observations=0):

    random = np.random.RandomState(random_seed)

    # Reduce data frames
    df_source = df_source[[source_identifier, weight] + columns].copy()
    df_target = df_target[[target_identifier] + columns].copy()

    # Sort data frames
    df_source = df_source.sort_values(columns)
    df_target = df_target.sort_values(columns)

    unique_values = {
        c: list(sorted(set(df_source[c].unique()) | set(df_target[c].unique())))
        for c in columns
    }

    # Define search order
    source_filters = [
        [df_source[c].values == v for v in unique_values[c]]
        for c in columns
    ]
    target_filters = [
        [df_target[c].values == v for v in unique_values[c]]
        for c in columns
    ]

    # Perform matching
    weights = df_source[weight].values.astype(float)
    if weights.mean() > 0:
        weights /= weights.mean()

    assigned_indices = np.full(len(df_target), -1, dtype=int)
    assigned_levels = np.full(len(df_target), -1, dtype=int)
    unassigned = np.ones(len(df_target), dtype=bool)
    uniform = random.random_sample(len(df_target))

    column_indices = [np.arange(len(unique_values[c])) for c in columns]

    # hierarchical relaxation of attributes
    for level in range(len(columns), 0, -1):
        if not unassigned.any():
            break

        for combo in itertools.product(*column_indices[:level]):
            f_src = np.logical_and.reduce(
                [source_filters[i][k] for i, k in enumerate(combo)]
            )
            f_tgt = np.logical_and.reduce(
                [target_filters[i][k] for i, k in enumerate(combo)] + [unassigned]
            )

            if not f_tgt.any():
                continue

            idx = np.where(f_src)[0]
            if len(idx) < minimum_observations:
                continue

            w = weights[f_src]
            cdf = np.cumsum(w)
            cdf /= cdf[-1]

            picked = sample_indices(uniform[f_tgt], cdf, idx)
            assigned_indices[f_tgt] = picked
            assigned_levels[f_tgt] = level
            unassigned[f_tgt] = False

            progress.update(int(f_tgt.sum()))

    # global fallback
    if unassigned.any():
        cdf = np.cumsum(weights)
        cdf /= cdf[-1]
        assigned_indices[unassigned] = sample_indices(
            uniform[unassigned], cdf, np.arange(len(weights))
        )
        assigned_levels[unassigned] = 0
        progress.update(int(unassigned.sum()))

    df_target[source_identifier] = df_source[source_identifier].values[assigned_indices]
    return df_target[[target_identifier, source_identifier]], assigned_levels

# ------------------------------------------------------------------
# PARALLEL WRAPPER
# ------------------------------------------------------------------

def _worker(context, args):
    df_target, seed = args
    return statistical_matching(
        context.progress,
        context.data("df_source"),
        context.data("source_identifier"),
        context.data("weight"),
        df_target,
        context.data("target_identifier"),
        context.data("columns"),
        seed,
        context.data("minimum_observations"),
    )

def parallel_match(context, df_source, source_id, weight,
                   df_target, target_id, columns, min_obs):

    rnd = np.random.RandomState(context.config("random_seed"))
    chunks = np.array_split(df_target, context.config("processes"))

    with context.progress(total=len(df_target), label="Matching"):
        with context.parallel({
            "df_source": df_source,
            "source_identifier": source_id,
            "weight": weight,
            "target_identifier": target_id,
            "columns": columns,
            "minimum_observations": min_obs
        }) as pool:
            seeds = rnd.randint(1_000_000, size=len(chunks))
            res = pool.map(_worker, zip(chunks, seeds))

    return pd.concat([r[0] for r in res]), np.hstack([r[1] for r in res])

# ------------------------------------------------------------------
# HIERARCHICAL MATCHING
# ------------------------------------------------------------------

def hierarchical_matching(context, df_source, df_target, columns):

    main_min = context.config("matching_minimum_observations")
    fb_min = context.config("matching_minimum_observations_fallback")

    if "source_survey" not in df_source.columns:
        return parallel_match(context, df_source, "hts_id",
                              "person_weight", df_target,
                              "person_id", columns, main_min)

    assignments = []
    levels_all = []

    for survey, src_sub in df_source.groupby("source_survey"):
        tgt_sub = df_target[df_target["departement_id"].isin(src_sub["departement_id"].unique())]
        if len(tgt_sub) == 0:
            continue

        try:
            a, l = parallel_match(context, src_sub, "hts_id",
                                  "person_weight", tgt_sub,
                                  "person_id", columns, main_min)
        except Exception:
            a, l = parallel_match(context, df_source, "hts_id",
                                  "person_weight", tgt_sub,
                                  "person_id", columns, fb_min)

        assignments.append(a)
        levels_all.append(l)

    return pd.concat(assignments), np.hstack(levels_all)


def execute(context):

    df_hh, df_pp, df_tt = context.stage("hts")
    df_source = pd.merge(df_pp, df_hh)
    df_source = df_source.rename(columns={"person_id": "hts_id"})

    df_target = context.stage("synthesis.population.sampled")

    columns = context.config("matching_attributes")

    AGE_BOUNDARIES = [14, 29, 44, 59, 74, 1000]
    if "age_class" in columns:
        df_target["age_class"] = np.digitize(df_target["age"], AGE_BOUNDARIES, True)
        df_source["age_class"] = np.digitize(df_source["age"], AGE_BOUNDARIES, True)

    if "any_cars" in columns:
        df_target["any_cars"] = df_target["number_of_vehicles"] > 0
        df_source["any_cars"] = df_source["number_of_vehicles"] > 0

    df_assignment, levels = hierarchical_matching(
        context, df_source, df_target, columns
    )

    # ------------------------------------------------------------------
    # LOGGING
    # ------------------------------------------------------------------

    log_path = Path(context.config("matching_log_path"))
    log_path.mkdir(parents=True, exist_ok=True)

    levels_df = pd.DataFrame({
    "person_id": df_assignment["person_id"].values,
    "matching_level": levels
    })

    log = df_target.merge(levels_df, on="person_id", how="left")

    log["matching_level"].value_counts().sort_index().to_csv(
        log_path / "levels.csv"
    )

    log[["person_id", "matching_level"]].to_csv(
    log_path / "individual.csv",
    index=False
    )

    if "departement_id" in log:
        log.groupby(["departement_id","matching_level"]).size().unstack(fill_value=0)\
            .to_csv(log_path / "by_dep.csv")

    # ------------------------------------------------------------------

    df_target = df_target.merge(df_assignment, on="person_id")
    return df_target[["person_id", "hts_id"]]
