from typing import cast

import structlog
import pandas as pd
from owid.catalog import Dataset, Table
from owid.catalog.utils import underscore_table
from owid.walden import Catalog

from etl.grapher_model import GrapherConfig
from etl.steps.data.converters import convert_grapher_dataset, convert_grapher_variable


log = structlog.get_logger()


def load_values(short_name: str) -> pd.DataFrame:
    walden_ds = Catalog().find_one(short_name=f"{short_name}_values")
    local_path = walden_ds.ensure_downloaded()
    return cast(pd.DataFrame, pd.read_feather(local_path))


def load_config(short_name: str) -> GrapherConfig:
    walden_ds = Catalog().find_one(short_name=f"{short_name}_config")
    local_path = walden_ds.ensure_downloaded()
    return GrapherConfig.parse_file(local_path)


def create_dataset(dest_dir: str, short_name: str) -> Dataset:
    """Create Dataset from backported dataset in walden. Convert
    it into wide format and add metadata."""
    values = load_values(short_name)
    config = load_config(short_name)

    # find sources belonging to this dataset
    ds_sources = [s for s in config.sources if s.datasetId == config.dataset.id]

    # create dataset with metadata
    ds = Dataset.create_empty(
        dest_dir, convert_grapher_dataset(config.dataset, ds_sources, short_name)
    )

    # convert to wide format
    long_mem_usage_mb = values.memory_usage().sum() / 1e6
    df = values.pivot(
        index=["entity_name", "year"], columns="variable_name", values="value"
    )

    # convert to float all columns we can
    # NOTE: this is also done later before adding the dataset into catalog
    for col in df.columns:
        if df[col].dtype != float:
            df[col] = df[col].astype(float, errors="ignore")

    # report compression ratio if the file is larger than >1MB
    wide_mem_usage_mb = df.memory_usage().sum() / 1e6
    if wide_mem_usage_mb > 1:
        log.info(
            "backport.long_to_wide_format",
            short_name=short_name,
            wide_mb=wide_mem_usage_mb,
            long_mb=long_mem_usage_mb,
            compression=f"{wide_mem_usage_mb / long_mem_usage_mb:.1%}",
        )

    # TODO: what about Table metadata? should I reuse what I have in a dataset?
    t = Table(df)
    t.metadata.short_name = short_name

    # add variables metadata
    for col in t.columns:
        variable = [v for v in config.variables if v.name == col][0]
        variable_source = [s for s in config.sources if s.id == variable.sourceId][0]
        t[col].metadata = convert_grapher_variable(
            variable,
            variable_source,
        )

    ds.add(underscore_table(t))
    return ds
