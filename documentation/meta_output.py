import os, datetime, json
import subprocess as sp

import matsim.runtime.git as git

def configure(context):
    git.configure(context)

    context.config("output_path")
    context.config("output_prefix", "ile_de_france_")

    for option in ("sampling_rate", "hts", "random_seed", "hts_year"):
        context.config(option)

def get_version():
    version_path = os.path.dirname(os.path.realpath(__file__))
    version_path = os.path.realpath("{}/../version.txt".format(version_path))

    with open(version_path) as f:
        return f.read().strip()

def get_commit(context):
    root_path = os.path.dirname(os.path.realpath(__file__))
    root_path = os.path.realpath("{}/..".format(root_path))

    try:
        return git.run(context, ["rev-parse", "HEAD"], cwd = root_path, catch_output = True)
    except sp.CalledProcessError:
        return "unknown"

def execute(context):
    # Write meta information
    information = dict(
        sampling_rate = context.config("sampling_rate"),
        hts = context.config("hts"),
        mobisurvstd_version = "1.1.0",
        random_seed = context.config("random_seed"),
        created = datetime.datetime.now(datetime.timezone.utc).isoformat(),
        version = get_version(),
        commit = get_commit(context),
        eqasim_version= "1.5.0",
        census_year= 2022,
        iris_year= 2024,
        bpe_year= 2024,
        bd_topo_year= 2024,
        hts_year= context.config("hts_year")
    )

    with open("%s/%smeta.json" % (context.config("output_path"), context.config("output_prefix")), "w+") as f:
        json.dump(information, f, indent = 4)

def validate(context):
    git.validate(context)
    return get_version() + get_commit(context)
