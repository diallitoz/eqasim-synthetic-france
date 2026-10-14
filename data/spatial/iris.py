import pandas as pd
import geopandas as gpd
import os
import py7zr
import glob

"""
Loads the IRIS zoning system.
"""

def configure(context):
    context.config("data_path")
    context.stage("data.spatial.codes")
    context.stage("data.spatial.iris_raw")
    context.config("output_path")

def execute(context):
    output_path = context.config("output_path")
    df_codes = context.stage("data.spatial.codes")
    df_iris = context.stage("data.spatial.iris_raw")

    # Merge with requested codes and verify integrity
    df_iris = pd.merge(df_iris, df_codes, on = ["iris_id", "commune_id"])

    df_iris["iris_id"] = df_iris["iris_id"].astype("category")
    df_iris["commune_id"] = df_iris["commune_id"].astype("category")

    requested_iris = set(df_codes["iris_id"].unique())
    merged_iris = set(df_iris["iris_id"].unique())

    if requested_iris != merged_iris:
        raise RuntimeError("Some IRIS are missing: %s" % (requested_iris - merged_iris,))

    clean_iris = sorted(set(df_iris["iris_id"].dropna().unique()) - {"undefined"})
    clean_communes = sorted(set(df_iris["commune_id"].dropna().unique()) - {"undefined"})

    df_iris["iris_id"] = df_iris["iris_id"].astype(pd.CategoricalDtype(categories=clean_iris, ordered=False))
    df_iris["commune_id"] = df_iris["commune_id"].astype(pd.CategoricalDtype(categories=clean_communes, ordered=False))
    
    # Export
    df_iris.to_file(os.path.join(output_path, "df_iris.gpkg"), driver="GPKG")
    df_iris.to_file(os.path.join(output_path, "df_iris.geojson"), driver="GeoJSON")
    df_iris.to_parquet(os.path.join(output_path, "df_iris.parquet"))
    df_iris.to_file(os.path.join(output_path, "df_iris.shp"))
    return df_iris