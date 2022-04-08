import click
import pandas as pd
import structlog
from owid.catalog.utils import underscore
from owid import walden

from etl.db import get_engine

from .backport import backport, WALDEN_NAMESPACE

log = structlog.get_logger()


@click.command()
@click.option("--dataset-ids", "-d", type=int, multiple=True)
@click.option(
    "--dry-run/--no-dry-run",
    default=False,
    type=bool,
    help="Do not add dataset to a catalog on dry-run",
)
@click.option(
    "--limit",
    default=1000000,
    type=int,
)
def bulk_backport(dataset_ids: list[int], dry_run: bool, limit: int) -> None:
    engine = get_engine()

    q = f"""
    select id, name, dataEditedAt, metadataEditedAt from datasets
    where not isPrivate
        and id in (
            select distinct v.datasetId from chart_dimensions as cd
            join variables as v on cd.variableId = v.id
        )
    limit {limit}
    """
    df = pd.read_sql(q, engine)

    if dataset_ids:
        df = df[df.id.isin(dataset_ids)]

    df["short_name"] = df.name.map(underscore)

    # add timestamp from existing datasets
    # existing_ds = _existing_backport_datasets()
    # __import__("ipdb").set_trace()
    # df = df.merge(
    #     existing_ds[["short_name", "date_accessed"]],
    #     how="left",
    #     left_on="short_name",
    #     right_on="short_name",
    # )

    # df = df[["date_accessed", "dataEditedAt", "metadataEditedAt"]]

    # __import__("ipdb").set_trace()

    log.info("bulk_backport.start", n=len(df))

    for i, ds in enumerate(df.itertuples()):
        log.info(
            "bulk_backport",
            dataset_id=ds.id,
            name=ds.name,
            progress=f"{i + 1}/{len(df)}",
        )
        backport(
            dataset_id=ds.id,
            short_name=ds.short_name,
            dry_run=dry_run,
        )

    log.info("bulk_backport.finished")


def _existing_backport_datasets():
    catalog = walden.Catalog()
    df = pd.DataFrame(ds.to_dict() for ds in catalog.find(namespace=WALDEN_NAMESPACE))

    # keep only one from both `values` and `config`
    df["short_name"] = df["short_name"].str.replace("_values|_config", "")
    df = df.drop_duplicates(["short_name"])

    df["date_accessed"] = pd.to_datetime(df["date_accessed"])

    return df


if __name__ == "__main__":
    # Example (run against staging DB):
    #   bulk_backport -d 20 -d 21 -d 5426 --dry-run
    bulk_backport()
