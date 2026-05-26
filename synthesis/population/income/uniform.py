import numpy as np
import pandas as pd
from synthesis.population.income.utils import income_uniform_sample

"""
This stage assigns a household income to each household of the synthesized
population. For that it looks up the municipality of each household in the
income database to obtain the municipality's income distribution (in centiles).
Then, for each household, a centile is selected randomly from the respective
income distribution and a random income within the selected stratum is chosen.
"""

def configure(context):
    context.stage("data.income.municipality")
    context.stage("synthesis.population.sampled")
    context.stage("synthesis.population.spatial.home.zones")
    context.config("random_seed")

def execute(context):
    random = np.random.default_rng(context.config("random_seed"))

    df_income = context.stage("data.income.municipality")
    df_income = df_income[(df_income["attribute"] == "all") & (df_income["value"] == "all")]
    
    centile_cols = ["q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8", "q9"]
    df_income_clean = df_income[["commune_id"] + centile_cols].copy()
    df_income_clean[centile_cols] = df_income_clean[centile_cols] / 12.0

    df_households = context.stage("synthesis.population.sampled")[[
        "household_id", "consumption_units"
    ]].drop_duplicates("household_id")

    df_homes = context.stage("synthesis.population.spatial.home.zones")[[
        "household_id", "commune_id"
    ]]

    df_households = pd.merge(df_households, df_homes, on="household_id")

    income_dict = df_income_clean.set_index("commune_id")[centile_cols].to_dict(orient="index")

    print("Imputing income vectorially...")
    
    def sample_group(group):
        commune_id = group.name
        n_samples = len(group)
        
        if commune_id in income_dict:
            centiles = list(income_dict[commune_id].values())
        else:
            centiles = [0.0] * 9 
            
        incomes = income_uniform_sample(random, centiles, n_samples)
        return pd.Series(incomes, index=group.index)

    household_incomes = df_households.groupby("commune_id", observed=True).apply(sample_group).reset_index(level=0, drop=True)
    
    df_households["household_income"] = household_incomes * df_households["consumption_units"]

    df_households = df_households[["household_id", "household_income", "consumption_units"]]
    assert len(df_households) == len(df_households["household_id"].unique())
    
    return df_households