from tqdm import tqdm
import pandas as pd
import numpy as np
from itertools import product

"""
Transforms absolute OD flows from French census into a weighted destination
matrix given a certain origin commune for work and education.
"""

def configure(context):
    context.stage("data.od.cleaned")
    context.stage("data.spatial.codes")
    context.config("education_location_source", "bpe")

def fix_origins(df, commune_ids, purpose, category): 
    df_existing = df.groupby(['origin_id', category], observed=True)["weight"].sum()
    existing_ids = set(df_existing[df_existing > 0].index)

    all_categories = np.unique(df[category])
    missing_ids = set(product(commune_ids, all_categories)) - existing_ids

    print("Fixing %d origins for %s" % (len(missing_ids), purpose))

    if len(missing_ids) > 0:
        df_missing = pd.DataFrame(list(missing_ids), columns=["origin_id", category])
        
        df_missing["destination_id"] = df_missing["origin_id"]
        df_missing["weight"] = 1.0
        
        df_missing["origin_id"] = df_missing["origin_id"].astype(df["origin_id"].dtype)
        df_missing["destination_id"] = df_missing["destination_id"].astype(df["destination_id"].dtype)
        df_missing[category] = df_missing[category].astype(df[category].dtype)

        df = pd.concat([df, df_missing], ignore_index=True)
    
    return df.sort_values(["origin_id", "destination_id"])

def execute(context):
    df_codes = context.stage("data.spatial.codes")
    commune_ids = set(df_codes["commune_id"].unique())

    df_work, df_education = context.stage("data.od.cleaned")

    df_work = fix_origins(df_work, commune_ids, "work", "commute_mode")
    df_education = fix_origins(df_education, commune_ids, "education", "age_range")

    df_work = df_work[["origin_id", "destination_id", "weight"]].groupby(["origin_id", "destination_id"], observed=True).sum().reset_index()
   
    df_total = df_work[["origin_id", "weight"]].groupby("origin_id", observed=True).sum().reset_index().rename({ "weight" : "total" }, axis = 1)
    df_work = pd.merge(df_work, df_total, on = "origin_id")

    df_total = df_education[["origin_id", "age_range", "weight"]].groupby(["origin_id", "age_range"], observed=True).sum().reset_index().rename({ "weight" : "total" }, axis = 1)
    df_education = pd.merge(df_education, df_total, on = ["origin_id", "age_range"])
    
    if context.config("education_location_source") == 'bpe':
        df_education = df_education[["origin_id", "destination_id", "weight", "total"]].groupby(["origin_id", "destination_id"], observed=True).sum().reset_index()    
    
    df_work["weight"] /= df_work["total"]
    df_education["weight"] /= df_education["total"]

    del df_work["total"]
    del df_education["total"]
    
    df_work["weight"] = df_work["weight"].fillna(0.0)
    df_education["weight"] = df_education["weight"].fillna(0.0)
    
    return df_work, df_education