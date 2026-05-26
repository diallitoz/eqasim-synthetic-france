import pandas as pd
import numpy as np

"""
Cleans OD data to arrive at OD flows between municipalities for work
and education.
"""

def configure(context):
    context.stage("data.od.raw")
    context.stage("data.spatial.codes")

RENAME = { "COMMUNE" : "origin_id", "DCLT" : "destination_id", "IPONDI" : "weight", "DCETUF" : "destination_id" }

MAPPING_TRANS = {
    1: "no transport",
    2: "walk",
    3: "bike",
    4: "car",
    5: "car",
    6: "pt"
}

def get_age_range(age):
    if age <= 6: return "primary_school"
    if age == 11: return "middle_school"
    if age == 15: return "high_school"
    if age >= 18: return "higher_education"
    return ""

def execute(context):
    df_work, df_education = context.stage("data.od.raw")

    df_work = df_work.rename(RENAME, axis = 1)
    df_education = df_education.rename(RENAME, axis = 1)

    df_work.loc[~df_work["ARM"].str.contains("Z"), "origin_id"] = df_work["ARM"]
    df_education.loc[~df_education["ARM"].str.contains("Z"), "origin_id"] = df_education["ARM"]

    df_codes = context.stage("data.spatial.codes")

    df_work["origin_id"] = df_work["origin_id"].astype("category")
    df_work["destination_id"] = df_work["destination_id"].astype("category")

    excess_communes = (set(df_work["origin_id"].unique()) | set(df_work["destination_id"].unique())) - set(df_codes["commune_id"].unique())
    if len(excess_communes) > 0:
        raise RuntimeError("Found additional communes: %s" % excess_communes)

    df_education["origin_id"] = df_education["origin_id"].astype("category")
    df_education["destination_id"] = df_education["destination_id"].astype("category")

    excess_communes = (set(df_education["origin_id"].unique()) | set(df_education["destination_id"].unique())) - set(df_codes["commune_id"].unique())
    if len(excess_communes) > 0:
        raise RuntimeError("Found additional communes: %s" % excess_communes)

    df_work["commute_mode"] = df_work["TRANS"].map(MAPPING_TRANS).fillna("")
    assert not np.any(df_work["commute_mode"] == "")
    df_work["commute_mode"] = df_work["commute_mode"].astype("category")
    
    df_education["AGEREV10"] = df_education["AGEREV10"].astype(int)
    
    conds = [
        df_education["AGEREV10"] <= 6,
        df_education["AGEREV10"] == 11,
        df_education["AGEREV10"] == 15,
        df_education["AGEREV10"] >= 18
    ]
    choices = ["primary_school", "middle_school", "high_school", "higher_education"]
    df_education["age_range"] = np.select(conds, choices, default="")
    
    assert not np.any(df_education["age_range"] == "")
    df_education["age_range"] = df_education["age_range"].astype("category")

    print("Aggregating work ...")
    df_work = df_work.groupby(["origin_id", "destination_id", "commute_mode"], observed=True)["weight"].sum().reset_index()

    print("Aggregating education ...")
    df_education = df_education.groupby(["origin_id", "destination_id", "age_range"], observed=True)["weight"].sum().reset_index()

    df_work["weight"] = df_work["weight"].fillna(0.0)
    df_education["weight"] = df_education["weight"].fillna(0.0)

    return df_work, df_education