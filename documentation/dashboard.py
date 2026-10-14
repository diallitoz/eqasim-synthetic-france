import shutil

from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

def plot_dashboard_eqasim(pop_data, modal_shares, km_modal_shares, dist_stats_by_mode, fig_title, output_path):
    """Génère le tableau de bord avec les 4 graphiques."""
    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(18, 14))
    fig.suptitle(fig_title, fontsize=20, fontweight='bold')

    # 1. Population (filtrage pour affichage)
    ax1 = axes[0, 0]
    plot_pop = {k: v for k, v in pop_data.items() if k != "Nombre de ménages"}
    sns.barplot(x=list(plot_pop.keys()), y=list(plot_pop.values()), ax=ax1, palette='Blues_r')
    ax1.set_title('Indicateurs de Population', fontsize=14)
    ax1.set_ylabel('Nombre de personnes')
    for container in ax1.containers:
        ax1.bar_label(container, fmt='%d', padding=3)

    # 2. Parts Modales
    ax2 = axes[0, 1]
    modal_shares_sorted = modal_shares.sort_values(ascending=False)
    sns.barplot(x=modal_shares_sorted.values, y=modal_shares_sorted.index, ax=ax2, palette='viridis')
    ax2.set_title('Parts Modales des Déplacements (%)', fontsize=14)
    ax2.set_xlabel('Part (%)')
    for container in ax2.containers:
        ax2.bar_label(container, fmt='%.1f%%', padding=3)

    # 3. Parts Modales Kilométriques
    ax3 = axes[1, 0]
    ax3.pie(km_modal_shares, labels=km_modal_shares.index, 
            autopct='%1.1f%%', startangle=140, 
            colors=sns.color_palette('viridis', len(km_modal_shares)))
    centre_circle = plt.Circle((0,0),0.70,fc='white')
    ax3.add_artist(centre_circle)
    ax3.set_title('Parts Modales Kilométriques', fontsize=14)

    # 4. Distances par Mode
    ax4 = axes[1, 1]
    dist_stats_by_mode.sort_values('Mean (km)', ascending=False).plot(kind='bar', ax=ax4, color=['#2b8cbe', '#a6bddb'])
    ax4.set_title('Distance de trajet par mode (km)', fontsize=14)
    ax4.set_ylabel('Kilomètres')
    ax4.set_xlabel('Mode de transport')
    ax4.tick_params(axis='x', rotation=45)
    for container in ax4.containers:
        ax4.bar_label(container, fmt='%.1f', padding=3)

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    #plt.show()
    plt.savefig(output_path + '/tableau_bord_mobilite.png', dpi=300, bbox_inches='tight', 
            facecolor='white', edgecolor='none')
    plt.savefig(output_path + '/tableau_bord_mobilite.pdf', dpi=300, bbox_inches='tight', 
            facecolor='white', edgecolor='none')
# ==========================================
# 1. INDICATORS COMPUTATION (EQASIM & SURVEY)
# ==========================================
def prepare_trips_data_hts(df_trips):
    """Prepare trip data (unit conversions and filtering)."""
    trips = df_trips.copy()

    # Convert distance from meters to kilometers
    trips["distance_km"] = trips["euclidean_distance"] / 1000

    # Convert duration from seconds to minutes
    trips["duration_min"] = trips["trip_duration"] / 60

    # Filter: keep only valid trips (< 100 km) and remove missing values
    trips_filtered = trips[
        (trips["distance_km"] < 100) & (trips["distance_km"].notna())
    ].copy()

    return trips_filtered


def get_population_indicators_hts(df_households, df_persons):
    """Calculate population indicators using survey weights."""
    return {
        "Number of households": df_households["household_weight"].sum(),
        "Total population": df_persons["person_weight"].sum(),
        "Population 5+": df_persons.loc[
            df_persons["age"] >= 5, "person_weight"
        ].sum(),
        "Population 18+": df_persons.loc[
            df_persons["age"] >= 18, "person_weight"
        ].sum(),
    }


def get_mobility_indicators_hts(df_households, df_persons, df_trips):
    """Calculate main weighted global mobility indicators."""
    # Weighted population 5+
    pop_5_plus_w = df_persons.loc[
        df_persons["age"] >= 5, "person_weight"
    ].sum()

    # Motorization rate: Sum(vehicles * household weight) / Sum(household weights)
    total_vehicles_w = (
        df_households["number_of_vehicles"] * df_households["household_weight"]
    ).sum()
    total_households_w = df_households["household_weight"].sum()
    motorization_rate = (
        total_vehicles_w / total_households_w if total_households_w > 0 else 0
    )

    # Total weighted trips
    total_trips_w = df_trips["trip_weight"].sum()

    # Total weighted distance and duration
    total_dist_w = (df_trips["distance_km"] * df_trips["trip_weight"]).sum()
    total_time_w = (df_trips["duration_min"] * df_trips["trip_weight"]).sum()

    return {
        "Average motorization rate": round(motorization_rate, 2),
        "Total trips": int(total_trips_w),
        "Trips per resident (5+)": round(total_trips_w / pop_5_plus_w, 2),
        "Mean daily distance / resident (5+) (km)": round(
            total_dist_w / pop_5_plus_w, 1
        ),
        "Mean daily duration / resident (5+) (min)": round(
            total_time_w / pop_5_plus_w, 1
        ),
    }


def get_modal_shares_hts(df_trips):
    """Calculate trip volume modal shares (%)."""
    mode_weights = df_trips.groupby("mode")["trip_weight"].sum()
    shares = (mode_weights / mode_weights.sum()) * 100
    return shares.sort_values(ascending=False).round(1)


def get_km_modal_shares_hts(df_trips):
    """Calculate kilometric modal shares (%)."""
    trips_copy = df_trips.copy()
    trips_copy["weighted_dist"] = (
        trips_copy["distance_km"] * trips_copy["trip_weight"]
    )
    km_mode_weights = trips_copy.groupby("mode")["weighted_dist"].sum()
    km_shares = (km_mode_weights / km_mode_weights.sum()) * 100
    return km_shares.sort_values(ascending=False).round(1)


def weighted_median_hts(df, val_col, weight_col):
    """Utility function to calculate weighted median of a column."""
    df_sorted = df.dropna(subset=[val_col, weight_col]).sort_values(val_col)
    if df_sorted.empty:
        return np.nan
    cumsum = df_sorted[weight_col].cumsum()
    cutoff = df_sorted[weight_col].sum() / 2.0
    return df_sorted[cumsum >= cutoff][val_col].iloc[0]


def get_distance_stats_by_mode_hts(df_trips):
    """Calculate weighted mean and median distance by transport mode."""
    stats = []

    for mode, group in df_trips.groupby("mode"):
        w_mean = np.average(group["distance_km"], weights=group["trip_weight"])
        w_med = weighted_median_hts(group, "distance_km", "trip_weight")

        stats.append(
            {
                "mode": mode,
                "Mean (km)": round(w_mean, 1),
                "Median (km)": round(w_med, 1),
            }
        )

    return pd.DataFrame(stats).set_index("mode")


# ==========================================
# 2. EQASIM (Eqasim) FUNCTIONS
# ==========================================


def load_data_eqasim(households_path, persons_path, trips_path):
    """Load data from parquet and geoparquet files."""
    households = pd.read_parquet(households_path)
    persons = pd.read_parquet(persons_path)
    trips = gpd.read_parquet(trips_path)
    return households, persons, trips


def prepare_trips_data_eqasim(trips):
    """Calculate distances, durations, and filter relevant trips."""
    # Compute distance in kilometers (assumes metric CRS, e.g., EPSG:2154)
    trips["distance_km"] = trips.geometry.length / 1000

    # Compute travel time in minutes
    trips["duration_min"] = (
        trips["arrival_time"] - trips["departure_time"]
    ) / 60

    # Filter: trips under 100 km
    trips_filtered = trips[trips["distance_km"] < 100].copy()

    # Fallback if 'mode' column is missing
    if "mode" not in trips_filtered.columns:
        trips_filtered["mode"] = "Unknown"

    return trips_filtered


def get_population_indicators_eqasim(households, persons):
    """Calculate and return population indicators."""
    return {
        "Number of households": households["household_id"].nunique(),
        "Total population": len(persons),
        "Population 5+": len(persons[persons["age"] >= 5]),
        "Population 18+": len(persons[persons["age"] >= 18]),
    }


def get_mobility_indicators_eqasim(households, persons, trips_filtered):
    """Calculate and return main mobility indicators."""
    pop_5_plus = len(persons[persons["age"] >= 5])
    total_trips = len(trips_filtered)

    return {
        "Average motorization rate": round(
            households["number_of_vehicles"].mean(), 2
        ),
        "Total trips": total_trips,
        "Trips per resident (5+)": round(total_trips / pop_5_plus, 2)
        if pop_5_plus
        else 0,
        "Mean daily distance / resident (5+) (km)": round(
            trips_filtered["distance_km"].sum() / pop_5_plus, 1
        )
        if pop_5_plus
        else 0,
        "Mean daily duration / resident (5+) (min)": round(
            trips_filtered["duration_min"].sum() / pop_5_plus, 1
        )
        if pop_5_plus
        else 0,
    }


def get_modal_shares_eqasim(trips_filtered):
    """Calculate trip volume modal shares (%)."""
    return (trips_filtered["mode"].value_counts(normalize=True) * 100).round(1)


def get_km_modal_shares_eqasim(trips_filtered):
    """Calculate kilometric modal shares (%)."""
    total_km = trips_filtered["distance_km"].sum()
    shares = (
        trips_filtered.groupby("mode")["distance_km"].sum() / total_km
    ) * 100
    return shares.sort_values(ascending=False).round(1)


def get_distance_stats_by_mode_eqasim(trips_filtered):
    """Calculate mean and median distance by transport mode."""
    stats = (
        trips_filtered.groupby("mode")["distance_km"]
        .agg(["mean", "median"])
        .round(1)
    )
    return stats.rename(columns={"mean": "Mean (km)", "median": "Median (km)"})

def get_population_indicators_eqasim(households, persons):
    """Calculate and return population indicators for Eqasim."""
    return {
        "Number of households": households["household_id"].nunique(),
        "Total population": len(persons),
        "Population 5+": len(persons[persons["age"] >= 5]),
        "Population 18+": len(persons[persons["age"] >= 18]),
    }


def get_mobility_indicators_eqasim(households, persons, trips_filtered):
    """Calculate and return main mobility indicators for Eqasim."""
    pop_5_plus = len(persons[persons["age"] >= 5])
    total_trips = len(trips_filtered)

    return {
        "Average motorization rate": round(
            households["number_of_vehicles"].mean(), 2
        ),
        "Total trips": total_trips,
        "Trips per resident (5+)": round(total_trips / pop_5_plus, 2)
        if pop_5_plus
        else 0,
        "Mean daily distance / resident (5+) (km)": round(
            trips_filtered["distance_km"].sum() / pop_5_plus, 1
        )
        if pop_5_plus
        else 0,
        "Mean daily duration / resident (5+) (min)": round(
            trips_filtered["duration_min"].sum() / pop_5_plus, 1
        )
        if pop_5_plus
        else 0,
    }


def get_modal_shares_eqasim(trips_filtered):
    """Calculate trip modal shares (%)."""
    return (trips_filtered["mode"].value_counts(normalize=True) * 100).round(1)


def get_km_modal_shares_eqasim(trips_filtered):
    """Calculate kilometric modal shares (%)."""
    total_km = trips_filtered["distance_km"].sum()
    shares = (
        trips_filtered.groupby("mode")["distance_km"].sum() / total_km
    ) * 100
    return shares.sort_values(ascending=False).round(1)


def get_distance_stats_by_mode_eqasim(trips_filtered):
    """Calculate mean and median distance by transport mode."""
    stats = (
        trips_filtered.groupby("mode")["distance_km"]
        .agg(["mean", "median"])
        .round(1)
    )
    return stats.rename(columns={"mean": "Mean (km)", "median": "Median (km)"})


def get_population_indicators_hts(df_households, df_persons):
    """Calculate weighted population indicators for Survey (HTS)."""
    return {
        "Number of households": df_households["household_weight"].sum(),
        "Total population": df_persons["person_weight"].sum(),
        "Population 5+": df_persons.loc[
            df_persons["age"] >= 5, "person_weight"
        ].sum(),
        "Population 18+": df_persons.loc[
            df_persons["age"] >= 18, "person_weight"
        ].sum(),
    }


def get_mobility_indicators_hts(df_households, df_persons, df_trips):
    """Calculate main weighted mobility indicators for Survey (HTS)."""
    pop_5_plus_w = df_persons.loc[
        df_persons["age"] >= 5, "person_weight"
    ].sum()

    total_vehicles_w = (
        df_households["number_of_vehicles"] * df_households["household_weight"]
    ).sum()
    total_households_w = df_households["household_weight"].sum()
    motorization_rate = (
        total_vehicles_w / total_households_w if total_households_w > 0 else 0
    )

    total_trips_w = df_trips["trip_weight"].sum()
    total_dist_w = (df_trips["distance_km"] * df_trips["trip_weight"]).sum()
    total_time_w = (df_trips["duration_min"] * df_trips["trip_weight"]).sum()

    return {
        "Average motorization rate": round(motorization_rate, 2),
        "Total trips": int(total_trips_w),
        "Trips per resident (5+)": round(total_trips_w / pop_5_plus_w, 2),
        "Mean daily distance / resident (5+) (km)": round(
            total_dist_w / pop_5_plus_w, 1
        ),
        "Mean daily duration / resident (5+) (min)": round(
            total_time_w / pop_5_plus_w, 1
        ),
    }


def get_modal_shares_hts(df_trips):
    """Calculate weighted trip modal shares (%)."""
    mode_weights = df_trips.groupby("mode")["trip_weight"].sum()
    shares = (mode_weights / mode_weights.sum()) * 100
    return shares.sort_values(ascending=False).round(1)


def get_km_modal_shares_hts(df_trips):
    """Calculate weighted kilometric modal shares (%)."""
    df_trips_copy = df_trips.copy()
    df_trips_copy["weighted_dist"] = (
        df_trips_copy["distance_km"] * df_trips_copy["trip_weight"]
    )
    km_mode_weights = df_trips_copy.groupby("mode")["weighted_dist"].sum()
    km_shares = (km_mode_weights / km_mode_weights.sum()) * 100
    return km_shares.sort_values(ascending=False).round(1)


def weighted_median_hts(df, val_col, weight_col):
    """Utility function to calculate weighted median."""
    df_sorted = df.dropna(subset=[val_col, weight_col]).sort_values(val_col)
    if df_sorted.empty:
        return np.nan
    cumsum = df_sorted[weight_col].cumsum()
    cutoff = df_sorted[weight_col].sum() / 2.0
    return df_sorted[cumsum >= cutoff][val_col].iloc[0]


def get_distance_stats_by_mode_hts(df_trips):
    """Calculate weighted mean and median distance by transport mode."""
    stats = []

    for mode, group in df_trips.groupby("mode"):
        w_mean = np.average(group["distance_km"], weights=group["trip_weight"])
        w_med = weighted_median_hts(group, "distance_km", "trip_weight")

        stats.append(
            {
                "mode": mode,
                "Mean (km)": round(w_mean, 1),
                "Median (km)": round(w_med, 1),
            }
        )

    return pd.DataFrame(stats).set_index("mode")


# ==========================================
# 2. DASHBOARD PREPARATION & PLOTTING
# ==========================================


def prepare_dashboard_inputs(
    pop_eqasim,
    pop_hts,
    mod_eqasim,
    mod_hts,
    km_eqasim,
    km_hts,
    dist_eqasim,
    dist_hts,
    eqasim_sample_rate=1.0,
):
    """Format Eqasim and HTS indicators into DataFrames for plotting.

    Parameters
    ----------
    eqasim_sample_rate : float, optional
        Sampling rate used in the Eqasim Eqasim (e.g., 0.31 for 31%).
    """
    scale_factor = 1.0 / eqasim_sample_rate
    pop_df = pd.DataFrame(
        {
            "Survey": pop_hts,
            "Eqasim": {k: v * scale_factor for k, v in pop_eqasim.items()},
        }
    )

    modal_shares_df = (
        pd.concat([mod_hts.rename("Survey"), mod_eqasim.rename("Eqasim")], axis=1)
        .fillna(0)
        .sort_values(by="Survey", ascending=False)
    )

    km_modal_shares_df = (
        pd.concat([km_hts.rename("Survey"), km_eqasim.rename("Eqasim")], axis=1)
        .fillna(0)
        .sort_values(by="Survey", ascending=False)
    )

    dist_hts_renamed = dist_hts.rename(
        columns={
            "Mean (km)": "Survey - Mean",
            "Median (km)": "Survey - Median",
        }
    )
    dist_eqasim_renamed = dist_eqasim.rename(
        columns={
            "Mean (km)": "Eqasim - Mean",
            "Median (km)": "Eqasim - Median",
        }
    )

    dist_stats_df = (
        pd.concat([dist_hts_renamed, dist_eqasim_renamed], axis=1)
        .fillna(0)
        .reindex(
            columns=[
                "Survey - Mean",
                "Survey - Median",
                "Eqasim - Mean",
                "Eqasim - Median",
            ]
        )
    )

    return pop_df, modal_shares_df, km_modal_shares_df, dist_stats_df


def plot_dashboard_hts_eqasim(
    pop_df,
    modal_shares_df,
    km_modal_shares_df,
    dist_stats_df,
    fig_title="Comparative Mobility Dashboard — Survey vs Eqasim",
    outpath=None,
):
    """Generate a 4-subplot dashboard comparing HTS survey and Eqasim."""
    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(18, 14))
    fig.suptitle(fig_title, fontsize=18, fontweight="bold")

    colors_duo = ["#2b8cbe", "#e6550d"]

    # --- 1. POPULATION INDICATORS ---
    ax1 = axes[0, 0]
    pop_plot = pop_df.drop(index=["Number of households"], errors="ignore")
    pop_plot.plot(kind="bar", ax=ax1, color=colors_duo, width=0.7)
    ax1.set_title("Population Indicators", fontsize=13, fontweight="bold")
    ax1.set_ylabel("Number of persons")
    ax1.tick_params(axis="x", rotation=0)
    for container in ax1.containers:
        ax1.bar_label(container, fmt="%d", padding=3, fontsize=9)

    # --- 2. MODAL SHARES (TRIP VOLUME) ---
    ax2 = axes[0, 1]
    modal_shares_df.plot(kind="barh", ax=ax2, color=colors_duo, width=0.7)
    ax2.set_title("Trip Modal Shares (%)", fontsize=13, fontweight="bold")
    ax2.set_xlabel("Share (%)")
    ax2.invert_yaxis()
    for container in ax2.containers:
        ax2.bar_label(container, fmt="%.1f%%", padding=3, fontsize=9)

    # --- 3. KILOMETRIC MODAL SHARES ---
    ax3 = axes[1, 0]
    km_modal_shares_df.plot(kind="barh", ax=ax3, color=colors_duo, width=0.7)
    ax3.set_title(
        "Kilometric Modal Shares (%)", fontsize=13, fontweight="bold"
    )
    ax3.set_xlabel("Kilometric share (%)")
    ax3.invert_yaxis()
    for container in ax3.containers:
        ax3.bar_label(container, fmt="%.1f%%", padding=3, fontsize=9)

    # --- 4. TRIP DISTANCES BY MODE (MEAN & MEDIAN) ---
    ax4 = axes[1, 1]
    colors_dist = ["#1f77b4", "#aec7e8", "#d62728", "#ff9896"]
    dist_stats_df.plot(kind="bar", ax=ax4, color=colors_dist, width=0.8)
    ax4.set_title(
        "Trip Distances by Mode: Mean & Median (km)",
        fontsize=13,
        fontweight="bold",
    )
    ax4.set_ylabel("Distance (km)")
    ax4.set_xlabel("Transport mode")
    ax4.tick_params(axis="x", rotation=0)
    for container in ax4.containers:
        ax4.bar_label(container, fmt="%.1f", padding=3, fontsize=8)

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])

    if outpath is not None:
        plt.savefig(outpath + '/comparative_mobility_dashboard.png', dpi=300, bbox_inches='tight', 
            facecolor='white', edgecolor='none')
        plt.savefig(outpath + '/comparative_mobility_dashboard.pdf', dpi=300, bbox_inches='tight', 
            facecolor='white', edgecolor='none')
        print(f"Dashboard saved to: {outpath}")

def configure(context):
    context.stage("data.hts.mobisurvstd.cleaned")
    context.stage("synthesis.output")
    context.config("output_path")
    context.config("output_prefix")

def execute(context):
    output_path = context.config("output_path")

    #Eqasim
    df_households_eq, df_persons_eq, df_trips_eq = context.stage("synthesis.output")
    
    df_trips_eq = prepare_trips_data_eqasim(df_trips_eq)

    #Indicators calculation
    pop_ind = get_population_indicators_eqasim(df_households_eq, df_persons_eq)
    mob_ind = get_mobility_indicators_eqasim(df_households_eq, df_persons_eq, df_trips_eq)
    mod_shares = get_modal_shares_eqasim(df_trips_eq)
    km_shares = get_km_modal_shares_eqasim(df_trips_eq)
    dist_stats = get_distance_stats_by_mode_eqasim(df_trips_eq)

    #HTS
    df_households_ref, df_persons_ref, df_trips_ref = context.stage("data.hts.mobisurvstd.cleaned")
    df_trips_ref = df_trips_ref.to_pandas()
    df_households_ref = df_households_ref.to_pandas()
    df_persons_ref = df_persons_ref.to_pandas()

    df_trips_ref = prepare_trips_data_hts(df_trips_ref)
    
    #Indicators calculation
    pop_ind_ref = get_population_indicators_hts(df_households_ref, df_persons_ref)
    mob_ind_ref = get_mobility_indicators_hts(df_households_ref, df_persons_ref, df_trips_ref)
    mod_shares_ref = get_modal_shares_hts(df_trips_ref)
    km_shares_ref = get_km_modal_shares_hts(df_trips_ref)
    dist_stats_ref = get_distance_stats_by_mode_hts(df_trips_ref)

    pop_df, modal_shares_df, km_modal_shares_df, dist_stats_df = (
        prepare_dashboard_inputs(
            pop_ind,
            pop_ind_ref,
            mod_shares,
            mod_shares_ref,
            km_shares,
            km_shares_ref,
            dist_stats,
            dist_stats_ref,
            eqasim_sample_rate=1.0
        )
    )

    plot_dashboard_hts_eqasim(
        pop_df=pop_df,
        modal_shares_df=modal_shares_df,
        km_modal_shares_df=km_modal_shares_df,
        dist_stats_df=dist_stats_df,
        fig_title="Comparative Dashbord — HTS vs Eqasim",
        outpath= output_path,
    )


    plot_dashboard_eqasim(pop_ind, mod_shares, km_shares, dist_stats, "Tableau de Bord de la Mobilité Synthétique (eqsaim)", output_path)



