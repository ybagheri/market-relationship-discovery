from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd


class ParquetQuoteRepository:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def write(self, quotes: pd.DataFrame) -> Path:
        self._directory.mkdir(parents=True, exist_ok=True)
        symbol = str(quotes["symbol"].iloc[0]) if len(quotes) else "quotes"
        broker = str(quotes["broker"].iloc[0]) if len(quotes) else "broker"
        target = self._directory / f"{broker}_{symbol}.parquet"
        with NamedTemporaryFile(dir=self._directory, suffix=".parquet", delete=False) as temporary:
            temporary_path = Path(temporary.name)
        try:
            quotes.to_parquet(temporary_path, index=False)
            temporary_path.replace(target)
        finally:
            temporary_path.unlink(missing_ok=True)
        return target

    def read(self, path: Path) -> pd.DataFrame:
        return pd.read_parquet(path)
