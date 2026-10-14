import numpy as np
import pandas as pd
import itertools

"""
This stage has the census data as input and samples households according to the
household weights given by INSEE. The resulting sample size can be controlled
through the 'sampling_rate' configuration option.
"""

def configure(context):
    if context.config("projection_year", None) is None:
        context.stage("data.census.filtered", alias = "source")
    else:
        context.stage("synthesis.population.projection.reweighted", alias = "source")

    context.config("random_seed")
    context.config("sampling_rate")
    context.stage("data.spatial.iris")

def execute(context):

    df_census = context.stage("source").sort_values(by = ["household_id", "person_id"]).copy()

    sampling_rate = context.config("sampling_rate")
    random = np.random.default_rng(context.config("random_seed"))

    # Perform stochastic rounding for the population (and scale weights)
    df_rounding = df_census[["household_id", "weight", "household_size"]].drop_duplicates("household_id")
    df_rounding["multiplicator"] = np.floor(df_rounding["weight"])
    df_rounding["multiplicator"] += random.random(len(df_rounding)) <= (df_rounding["weight"] - df_rounding["multiplicator"])
    df_rounding["multiplicator"] = df_rounding["multiplicator"].astype(int)

    # Multiply households (use same multiplicator for all household members)
    household_multiplicators = df_rounding["multiplicator"].values
    household_sizes = df_rounding["household_size"].values

    # create index to replicate all households members by their household weight
    # the order ([0, 1, 0, 1, 2, 2, ...]) is important here as they will be reassigned to new housholds later with that assumption
    expandor = np.split(np.arange(len(df_census)), np.cumsum(household_sizes))
    expandor = np.asarray([x for x in expandor if x.size > 0], dtype="object")
    expandor = np.repeat(expandor, household_multiplicators, axis=0)
    expandor = list(itertools.chain(*expandor))

    df_census = df_census.iloc[expandor]

    # Create new household and person IDs
    df_census["census_person_id"] = df_census["person_id"]
    df_census["census_household_id"] = df_census["household_id"]

    df_census["person_id"] = np.arange(len(df_census))

    household_sizes = np.repeat(household_sizes, household_multiplicators)
    household_count = np.sum(household_multiplicators)
    df_census.loc[:, "household_id"] = np.repeat(np.arange(household_count), household_sizes)

    # Select sample from 100% population
    selector = random.random(household_count) < sampling_rate
    selector = np.repeat(selector, household_sizes)
    df_census = df_census[selector]

    del df_census["weight"]

    df_iris = context.stage("data.spatial.iris")
    clean_iris = list(df_iris["iris_id"].cat.categories)
    clean_communes = list(df_iris["commune_id"].cat.categories)

    s_commune = df_census["commune_id"].astype(object).fillna("undefined")
    s_commune = s_commune.replace({"nan": "undefined", "NaN": "undefined", "None": "undefined", "<NA>": "undefined", "": "undefined"})

    s_iris = df_census["iris_id"].astype(object).fillna("undefined")
    s_iris = s_iris.replace({"nan": "undefined", "NaN": "undefined", "None": "undefined", "<NA>": "undefined", "": "undefined"})

    cat_commune = pd.CategoricalDtype(categories=clean_communes + ["undefined"], ordered=False)
    cat_iris = pd.CategoricalDtype(categories=clean_iris + ["undefined"], ordered=False)

    df_census["commune_id"] = s_commune.astype(cat_commune)
    df_census["iris_id"] = s_iris.astype(cat_iris)

    return df_census
