import os

import mobisurvstd

"""
This stage standardize the input HTS to the MobiSurvStd format.
"""


def configure(context):
    context.config("data_path")
    context.config("mobisurvstd.path")
    context.config("output_path")

def survey_path(context):
    return os.path.join(context.config("data_path"), context.config("mobisurvstd.path"))


def execute(context):
    #std_survey = mobisurvstd.standardize(
    #    source=survey_path(context), output_directory=None, skip_spatial=True
    #)
    std_survey = mobisurvstd.standardize(
        source=survey_path(context), output_directory=context.config("output_path"), skip_spatial=True
    , survey_type="egt2010")

    if std_survey is None:
        raise RuntimeError("The HTS survey could not be imported by MobiSurvStd")
    return std_survey


def validate(context):
    path = survey_path(context)
    assert os.path.isfile(path) or os.path.isdir(path), f"Cannot read HTS survey from `{path}`"
