import click
import pandas as pd
import structlog
from rich.progress import track

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

    log.info("bulk_backport.start", n=len(df))

    for ds in track(df.itertuples(), description="Backporting", total=len(df)):
        log.info("bulk_backport", dataset_id=ds.id, name=ds.name)
        backport(
            dataset_id=ds.id,
            dry_run=dry_run,
            # short_name
        )

    log.info("backport.finished")


if __name__ == "__main__":
    # Example (run against staging DB):
    #   bulk_backport -d 20 -d 21 --dry-run
    bulk_backport()
