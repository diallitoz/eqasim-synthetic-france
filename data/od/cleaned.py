# -*- coding: utf-8 -*-
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

def execute(context):
    
    
    # Load data
    df_work, df_education = context.stage("data.od.raw")

    # Renaming
    df_work = df_work.rename(RENAME, axis = 1)
    df_education = df_education.rename(RENAME, axis = 1)

    # Fix arrondissements
    df_work.loc[~df_work["ARM"].str.contains("Z"), "origin_id"] = df_work["ARM"]
    df_education.loc[~df_education["ARM"].str.contains("Z"), "origin_id"] = df_education["ARM"]

    # Verify spatial data for work
    df_codes = context.stage("data.spatial.codes")

    df_work["origin_id"] = df_work["origin_id"].astype("category")
    df_work["destination_id"] = df_work["destination_id"].astype("category")

    excess_communes = (set(df_work["origin_id"].unique()) | set(df_work["destination_id"].unique())) - set(df_codes["commune_id"].unique())
    if len(excess_communes) > 0:
        raise RuntimeError("Found additional communes: %s" % excess_communes)

    # Verify spatial data for education
    df_codes = context.stage("data.spatial.codes")

    df_education["origin_id"] = df_education["origin_id"].astype("category")
    df_education["destination_id"] = df_education["destination_id"].astype("category")

    excess_communes = (set(df_education["origin_id"].unique()) | set(df_education["destination_id"].unique())) - set(df_codes["commune_id"].unique())
    if len(excess_communes) > 0:
        raise RuntimeError("Found additional communes: %s" % excess_communes)

    # Clean commute mode for work
    df_work["commute_mode"] = ""
    df_work.loc[df_work["TRANS"] == 1, "commute_mode"] = "no transport"
    df_work.loc[df_work["TRANS"] == 2, "commute_mode"] = "walk"
    df_work.loc[df_work["TRANS"] == 3, "commute_mode"] = "bike"
    df_work.loc[df_work["TRANS"] == 4, "commute_mode"] = "car"
    df_work.loc[df_work["TRANS"] == 5, "commute_mode"] = "car"
    df_work.loc[df_work["TRANS"] == 6, "commute_mode"] = "pt"
    assert not np.any(df_work["commute_mode"] == "")
    df_work["commute_mode"] = df_work["commute_mode"].astype("category")
    
    

    # Clean age range for education
    df_education["AGEREV10"] = df_education["AGEREV10"].astype(int)
    df_education["age_range"] = ""
    df_education.loc[df_education["AGEREV10"] <= 6, "age_range"] = "primary_school"
    df_education.loc[df_education["AGEREV10"] == 11, "age_range"] = "middle_school"
    df_education.loc[df_education["AGEREV10"] == 15, "age_range"] = "high_school"
    df_education.loc[df_education["AGEREV10"] >= 18, "age_range"] = "higher_education"
    assert not np.any(df_education["age_range"] == "")
    df_education["age_range"] = df_education["age_range"].astype("category")

    origins_work = df_work["origin_id"].cat.categories
    modes = df_work["commute_mode"].cat.categories

    origins_educ = df_education["origin_id"].cat.categories
    ages = df_education["age_range"].cat.categories

    comm_work_bef = set(df_work["origin_id"].unique())
    comm_educ_bef = set(df_education["origin_id"].unique())

    # Aggregate the flows
    print("Aggregating work ...")
    #df_work = df_work.groupby(["origin_id", "destination_id", "commute_mode"],observed=False)["weight"].sum().reset_index()

    df_work = (
    df_work
    .groupby(
        ["origin_id", "destination_id", "commute_mode"],
        observed=True,
        sort=False
    )["weight"]
    .sum()
    .reset_index()
    )

    print("Aggregating education ...")
    #df_education = df_education.groupby(["origin_id", "destination_id","age_range"],observed=False)["weight"].sum().reset_index()

    df_education = (
    df_education
    .groupby(
        ["origin_id", "destination_id", "age_range"],
        observed=True,
        sort=False
    )["weight"]
    .sum()
    .reset_index()
    )


    df_work["weight"] = df_work["weight"].fillna(0.0)
    df_education["weight"] = df_education["weight"].fillna(0.0)


    """
    orig_work_after = set(df_work["origin_id"].unique())
    orig_educ_after = set(df_education["origin_id"].unique())

    desti_work_after = set(df_work["destination_id"].unique())
    desti_educ_after = set(df_education["destination_id"].unique())

    missing_orig_communes_work = comm_work_bef - orig_work_after
    missing_orig_communes_educ = comm_educ_bef - orig_educ_after

    missing_desti_communes_work = comm_work_bef - desti_work_after
    missing_desti_communes_educ = comm_educ_bef - desti_educ_after

    missing_destinations_work = sorted(missing_desti_communes_work)

    missing_destinations_educ = sorted(missing_desti_communes_educ)

    print("Work: missing commumes destination imputation ...", len(missing_destinations_work))

    # work
    missing_index_w = pd.MultiIndex.from_product(
    [origins, missing_destinations_work, modes],
    names=["origin_id", "destination_id", "commute_mode"]
    )

    df_missing_w = (
        pd.DataFrame(index=missing_index_w)
        .reset_index()
    )

    df_missing_w["weight"] = 0.0

    df_work = pd.concat(
    [df_work, df_missing_w],
    ignore_index=True
    )

    df_work = (
    df_work
    .groupby(
        ["origin_id", "destination_id", "commute_mode"],
        observed=True,
        sort=False
    )["weight"]
    .sum()
    .reset_index()
    )

    print("Education: missing commumes destination imputation ...", len(missing_destinations_educ))

    # education
    missing_index_e = pd.MultiIndex.from_product(
    [origins, missing_destinations_educ, ages],
    names=["origin_id", "destination_id", "age_range"]
    )

    df_missing_e = (
        pd.DataFrame(index=missing_index_e)
        .reset_index()
    )

    df_missing_e["weight"] = 0.0

    df_education = pd.concat(
    [df_education, df_missing_e],
    ignore_index=True
    )

    df_education = (
    df_education
    .groupby(
        ["origin_id", "destination_id", "age_range"],
        observed=True,
        sort=False
    )["weight"]
    .sum()
    .reset_index()
    )

    #stop

    if len(missing_orig_communes_work) > 0:
        #print("Work: communes perdues apres agregation: %s" % (sorted(missing_communes_work),))
        raise RuntimeError("Work: communes origine perdues apres agregation: %s" % (sorted(missing_orig_communes_work),))

    if len(missing_orig_communes_educ) > 0:
        #print("Education: communes perdues apres agregation: %s" % (sorted(missing_communes_educ),))
        raise RuntimeError("Education: communes origine perdues apres agregation %s" % (sorted(missing_orig_communes_educ),))
    
    if len(missing_desti_communes_work) > 0:
        #print("Work: communes perdues apres agregation: %s" % (sorted(missing_communes_work),))
        raise RuntimeError("Work: communes destination perdues apres agregation: %s" % (sorted(missing_desti_communes_work),))

    if len(missing_desti_communes_educ) > 0:
        #print("Education: communes perdues apres agregation: %s" % (sorted(missing_communes_educ),))
        raise RuntimeError("Education: communes destination perdues apres agregation %s" % (sorted(missing_desti_communes_educ),)) 
    """
    # -------------------------
    # 2️e Agrégation observée (rapide)
    # -------------------------
    df_work = df_work.groupby(["origin_id", "destination_id", "commute_mode"], observed=True)["weight"].sum().reset_index()
    df_education = df_education.groupby(["origin_id", "destination_id", "age_range"], observed=True)["weight"].sum().reset_index()

    df_work["weight"] = df_work["weight"].fillna(0.0)
    df_education["weight"] = df_education["weight"].fillna(0.0)

    # -------------------------
    # 3️e Identifier communes manquantes (destination)
    # -------------------------
    missing_dest_work = sorted(set(comm_work_bef) - set(df_work["destination_id"].unique()))
    missing_dest_educ = sorted(set(comm_educ_bef) - set(df_education["destination_id"].unique()))

    
    

    # -------------------------
    # 4️e Ajouter les lignes manquantes avec poids 0
    # -------------------------
    def add_missing_dest(df, origins, missing_destinations, categories, weight_col):
        """Ajoute uniquement les destinations manquantes, pour toutes les origines et catégories (modes ou ages)"""
        if not missing_destinations:
            return df

        # Construction minimale du dataframe à ajouter
        rows = []
        for dest in missing_destinations:
            for cat in categories:
                for orig in origins:
                    rows.append((orig, dest, cat, 0.0))

        cols = [df.columns[0], df.columns[1], df.columns[2], weight_col]
        df_missing = pd.DataFrame(rows, columns=cols)

        # Concat sans refaire de groupby global
        df_combined = pd.concat([df, df_missing], ignore_index=True)
        return df_combined

    print("Work: missing commumes destination imputation ...", len(missing_dest_work))
    # work
    df_work = add_missing_dest(df_work, origins_work, missing_dest_work, modes, "weight")

    print("Education: missing commumes destination imputation ...", len(missing_dest_educ))
    # education
    df_education = add_missing_dest(df_education, origins_educ, missing_dest_educ, ages, "weight")

    # -------------------------
    # 5️e Vérification des communes origin et destination
    # -------------------------
    def check_missing(df, origins_expected, destinations_expected, stage):
        missing_orig = set(origins_expected) - set(df["origin_id"].unique())
        missing_dest = set(destinations_expected) - set(df["destination_id"].unique())
        if missing_orig:
            raise RuntimeError(f"{stage}: communes origine manquantes apres imputation: {sorted(missing_orig)}")
        if missing_dest:
            raise RuntimeError(f"{stage}: communes destination manquantes apres imputation: {sorted(missing_dest)}")

    check_missing(df_work, comm_work_bef, comm_work_bef, "Work")
    check_missing(df_education, comm_educ_bef, comm_educ_bef, "Education")

    return df_work, df_education