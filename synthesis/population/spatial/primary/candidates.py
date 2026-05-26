import pandas as pd
import numpy as np

def configure(context):
    context.stage("data.od.weighted")
    context.stage("synthesis.locations.education")
    context.stage("synthesis.locations.work")
    context.stage("synthesis.population.spatial.home.zones")
    context.stage("synthesis.population.enriched")
    context.stage("synthesis.population.trips")

    context.config("output_path")
    context.config("random_seed")
    context.config("education_location_source", "bpe")

EDUCATION_MAPPING = {
    "primary_school": ["C1"],
    "middle_school": ["C2"],
    "high_school": ["C3"],
    "higher_education": ["C4", "C5", "C6"]}

def process(context, purpose, random, df_persons, df_od, df_locations, step_name):
    print(f"Vectorized Processing for {step_name}")

    df_persons_active = df_persons[df_persons["has_%s_trip" % purpose]]
    if len(df_persons_active) == 0:
        return pd.DataFrame(columns=["origin_id", "destination_id", "location_id"])

    df_demand = df_persons_active.groupby("commune_id", observed=True).size().reset_index(name="count")
    df_demand = df_demand[df_demand["count"] > 0]

    print(f"[{step_name}] Preparing OD dictionary...")
    od_dict = {}
    for origin_id, group in df_od.groupby("origin_id", observed=True):
        weights = group["weight"].values.astype(np.float64)
        s = np.sum(weights)
        if s > 0:
            od_dict[origin_id] = {
                "dests": group["destination_id"].values,
                "probs": weights / s
            }

    print(f"[{step_name}] Sampling destination municipalities...")
    flow_origins = []
    flow_dests = []
    
    missing_od_origins = set()

    for row in df_demand.itertuples(index=False):
        orig = row.commune_id
        cnt = row.count

        if orig in od_dict:
            dests = random.choice(od_dict[orig]["dests"], size=cnt, p=od_dict[orig]["probs"])
        else:
            missing_od_origins.add(orig)
            dests = np.full(cnt, orig)

        flow_origins.extend(np.full(cnt, orig))
        flow_dests.extend(dests)

    if missing_od_origins:
        print(f"[{step_name}] WARNING: {len(missing_od_origins)} municipalities have active student residents but NO outbound internal OD flows recorded.")
        print(f"[{step_name}] INSEE codes concerned: {sorted(list(missing_od_origins))}")

    df_flow = pd.DataFrame({
        "origin_id": flow_origins,
        "destination_id": flow_dests
    })

    print(f"[{step_name}] Preparing locations dictionary...")
    loc_dict = {}
    for dest_id, group in df_locations.groupby("commune_id", observed=True):
        if "weight" in group.columns:
            weights = group["weight"].values.astype(np.float64)
            s = np.sum(weights)
            probs = weights / s if s > 0 else np.ones(len(group)) / len(group)
        else:
            probs = np.ones(len(group)) / len(group)

        loc_dict[dest_id] = {
            "loc_ids": group["location_id"].values,
            "probs": probs
        }
    print(f"[{step_name}] Sampling exact locations...")
    
    df_flow = df_flow.sort_values("destination_id").reset_index(drop=True)
    final_locs = np.empty(len(df_flow), dtype=object)

    missing_loc_destinations = set()

    for dest_id, indices in df_flow.groupby("destination_id", observed=True).groups.items():
        cnt = len(indices)
        if dest_id in loc_dict:
            data = loc_dict[dest_id]
            sampled_locs = random.choice(data["loc_ids"], size=cnt, p=data["probs"])
        else:
            missing_loc_destinations.add(dest_id)
            sampled_locs = np.full(cnt, "UNKNOWN_LOCATION")
            
        final_locs[indices] = sampled_locs

    if missing_loc_destinations:
        print(f"[{step_name}] WARNING: {len(missing_loc_destinations)} municipalities were chosen as destinations but have NO corresponding buildings businesses schools.")
        print(f"[{step_name}] INSEE codes concerned: {sorted(list(missing_loc_destinations))}")

    df_flow["location_id"] = final_locs

    return df_flow[["origin_id", "destination_id", "location_id"]]


def execute(context):
    # Prepare population data
    df_persons = context.stage("synthesis.population.enriched")[["person_id", "household_id", "age_range"]].copy()
    df_trips = context.stage("synthesis.population.trips")

    df_persons["has_work_trip"] = df_persons["person_id"].isin(df_trips[
        (df_trips["following_purpose"] == "work") | (df_trips["preceding_purpose"] == "work")
    ]["person_id"])
    
    df_persons["has_education_trip"] = df_persons["person_id"].isin(df_trips[
        (df_trips["following_purpose"] == "education") | (df_trips["preceding_purpose"] == "education")
    ]["person_id"])

    df_homes = context.stage("synthesis.population.spatial.home.zones")
    df_persons = pd.merge(df_persons, df_homes, on = "household_id")

    # Prepare spatial data
    df_work_od, df_education_od = context.stage("data.od.weighted")

    # Sampling
    random = np.random.default_rng(context.config("random_seed"))

    df_locations = context.stage("synthesis.locations.work")
    df_locations["weight"] = df_locations["employees"]
    
    df_work = process(context, "work", random, df_persons, df_work_od, df_locations, "work")

    df_locations = context.stage("synthesis.locations.education")
    if context.config("education_location_source") == 'bpe':
        df_education = process(context, "education", random, df_persons, df_education_od, df_locations, "education")
    else:
        df_education = []
        for prefix, education_type in EDUCATION_MAPPING.items():
            df_education.append(
                process(context, "education", random,
                    df_persons[df_persons["age_range"]==prefix],
                    df_education_od[df_education_od["age_range"]==prefix],
                    df_locations[df_locations["education_type"].isin(education_type)],
                    f"education_{prefix}")
            )
        df_education = pd.concat(df_education)

    return dict(
        work_candidates = df_work,
        education_candidates = df_education,
        persons = df_persons[df_persons["has_work_trip"] | df_persons["has_education_trip"]][[
            "person_id", "household_id", "age_range", "commune_id", "has_work_trip", "has_education_trip"
        ]]
    )