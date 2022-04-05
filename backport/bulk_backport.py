import click
import pandas as pd
import structlog
from owid.catalog.utils import underscore

from etl.db import get_engine

from .backport import backport

log = structlog.get_logger()


@click.command()
@click.option("--dataset-ids", "-d", type=int, multiple=True)
@click.option(
    "--dry-run/--no-dry-run",
    default=False,
    type=bool,
    help="Do not add dataset to a catalog on dry-run",
)
def bulk_backport(
    dataset_ids: list[int],
    dry_run: bool,
) -> None:
    engine = get_engine()

    q = """
    select id, name, dataEditedAt, metadataEditedAt from datasets
    where not isPrivate
        and id in (
            select distinct v.datasetId from chart_variables as cv
            join variables as v on cv.variableId = v.id
        )
    """
    df = pd.read_sql(q, engine)

    if dataset_ids:
        df = df[df.id.isin(dataset_ids)]

    df["short_name"] = df.name.map(underscore)

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


if __name__ == "__main__":
    # Example (run against staging DB):
    #   bulk_backport -d 20 -d 21 -d 5426 --dry-run
    bulk_backport()
