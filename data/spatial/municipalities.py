import numpy as np
import pandas as pd
import geopandas as gpd
import os

"""
Provides the municipality zoning system.
"""

def configure(context):
    context.stage("data.spatial.iris")

def execute(context):
    df_iris = context.stage("data.spatial.iris")
    df_iris["has_iris"] = ~df_iris["iris_id"].astype(str).str.endswith("0000")

    df_municipalities = context.stage("data.spatial.iris").dissolve(
        by = "commune_id").drop(columns = ["iris_id"]).reset_index()
    
    clean_communes = list(df_iris["commune_id"].cat.categories)
    df_municipalities["commune_id"] = df_municipalities["commune_id"].astype(
        pd.CategoricalDtype(categories=clean_communes, ordered=False)
    )
    return df_municipalities
