"""Safe local input and portable evidence-pack exports."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from io import BytesIO
import json
from pathlib import Path
import re
from typing import BinaryIO
import zipfile

import pandas as pd

from . import limits
from .errors import DataProblem


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".xlsm", ".json"}
# Run locally there are no size limits; a public demo (SIGNAL_PUBLIC=1) applies the caps in limits.py.
# Large files are parsed in chunks with text stored as categories and whole numbers as small integers.
CSV_CHUNK_ROWS = 1_000_000
JSON_CHUNK_RECORDS = 100_000
_TYPE_SAMPLE_ROWS = 10_000
_WHITESPACE = " \t\r\n"
_SEPARATORS = ", \t\r\n"
ILLEGAL_XML_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


@dataclass(frozen=True)
class LoadedData:
    tables: dict[str, pd.DataFrame]
    source_name: str


def _unique_column_names(columns: list[object]) -> list[str]:
    result: list[str] = []
    used: set[str] = set()
    for index, column in enumerate(columns):
        base = str(column).strip() or f"column_{index + 1}"
        candidate = base
        suffix = 2
        while candidate in used:
            candidate = f"{base}__{suffix}"
            suffix += 1
        used.add(candidate)
        result.append(candidate)
    return result


def _source_bytes(source: str | Path | bytes | BinaryIO) -> tuple[bytes, str]:
    if isinstance(source, (str, Path)):
        path = Path(source)
        return path.read_bytes(), path.name
    if isinstance(source, bytes):
        return source, "uploaded.csv"
    name = Path(getattr(source, "name", "uploaded.csv")).name
    if hasattr(source, "seek"):
        source.seek(0)
    return source.read(), name


def load_data(source: str | Path | bytes | BinaryIO, name: str | None = None) -> LoadedData:
    """Read CSV, Excel, or JSON without executing uploaded content."""
    raw, detected_name = _source_bytes(source)
    source_name = name or detected_name
    extension = Path(source_name).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise DataProblem("Please use CSV, Excel, or JSON data.")
    if limits.exceeds(len(raw), limits.max_upload_bytes()):
        raise DataProblem(limits.demo_message(f"Files are limited to {limits.DEMO_MAX_UPLOAD_MB} MB here."))
    if extension == ".json" and limits.exceeds(len(raw), limits.max_json_bytes()):
        raise DataProblem(limits.demo_message(f"JSON files are limited to {limits.DEMO_MAX_JSON_MB} MB here."))
    if not raw:
        raise DataProblem("This file is empty.")

    try:
        if extension == ".csv":
            tables = {"ratings": _read_csv(raw)}
        elif extension in {".xlsx", ".xls", ".xlsm"}:
            if extension in {".xlsx", ".xlsm"}:
                with zipfile.ZipFile(BytesIO(raw)) as workbook:
                    expanded = sum(member.file_size for member in workbook.infolist())
                if limits.exceeds(expanded, limits.max_expanded_workbook_bytes()):
                    raise DataProblem(
                        limits.demo_message(
                            f"Workbooks may expand to at most {limits.DEMO_MAX_EXPANDED_WORKBOOK_MB} MB here."
                        )
                    )
            tables = pd.read_excel(BytesIO(raw), sheet_name=None)
        else:
            tables = _read_json(raw)
    except DataProblem:
        raise
    except MemoryError as exc:
        raise DataProblem(limits.MEMORY_MESSAGE) from exc
    except Exception as exc:
        raise DataProblem(
            "The file could not be read. Check that it opens normally and that the first row contains column names."
        ) from exc

    clean: dict[str, pd.DataFrame] = {}
    total_cells = 0
    for table_name, frame in tables.items():
        if frame is None or (frame.empty and len(frame.columns) == 0):
            continue
        # The loader owns these frames, so they are renamed and compacted in place rather than copied.
        frame.columns = _unique_column_names(list(frame.columns))
        total_cells += int(frame.shape[0] * frame.shape[1])
        if _too_large(len(frame), total_cells):
            raise DataProblem(_size_message())
        try:
            clean[str(table_name)] = _compact(frame)
        except MemoryError as exc:
            raise DataProblem(limits.MEMORY_MESSAGE) from exc
    if not clean:
        raise DataProblem("No usable tables were found in this file.")
    return LoadedData(tables=clean, source_name=source_name)


def _too_large(rows: int, cells: int) -> bool:
    return limits.exceeds(rows, limits.max_table_rows()) or limits.exceeds(cells, limits.max_total_cells())


def _size_message() -> str:
    return limits.demo_message(
        f"Files are limited to {limits.DEMO_MAX_TABLE_ROWS:,} rows and {limits.DEMO_MAX_TOTAL_CELLS:,} cells here."
    )


def _compact(frame: pd.DataFrame) -> pd.DataFrame:
    """Store text as categories and whole numbers in the smallest integer type; values are unchanged."""
    for column in frame.columns:
        series = frame[column]
        if series.dtype == object and pd.api.types.infer_dtype(series, skipna=True) == "string":
            frame[column] = series.astype("category")
        elif pd.api.types.is_integer_dtype(series.dtype) and not pd.api.types.is_bool_dtype(series.dtype):
            frame[column] = pd.to_numeric(series, downcast="integer")
    return frame


def _concat_compact(chunks: list[pd.DataFrame]) -> pd.DataFrame:
    """Concatenate chunks, keeping categorical columns categorical across differing category sets."""
    if not chunks:
        return pd.DataFrame()
    if len(chunks) == 1:
        return chunks[0]
    if len({tuple(chunk.columns) for chunk in chunks}) > 1:
        return _compact(pd.concat(chunks, ignore_index=True))
    columns: dict[object, pd.Series] = {}
    for column in chunks[0].columns:
        parts = [chunk[column] for chunk in chunks]
        if all(isinstance(part.dtype, pd.CategoricalDtype) for part in parts):
            combined = pd.api.types.union_categoricals([part.array for part in parts], ignore_order=True)
            columns[column] = pd.Series(combined, name=column)
        else:
            columns[column] = pd.concat(
                [part.astype(object) if isinstance(part.dtype, pd.CategoricalDtype) else part for part in parts],
                ignore_index=True,
            )
    return _compact(pd.DataFrame(columns))


def _sniff_delimiter(raw: bytes) -> str:
    """Detect the delimiter from the header line, as pandas' ``sep=None`` does, then parse with the fast C reader."""
    head = raw[:1_000_000]
    end = head.find(b"\n")
    first_line = (head if end < 0 else head[:end]).decode("utf-8-sig", errors="replace").rstrip("\r")
    return csv.Sniffer().sniff(first_line).delimiter


def _read_csv(raw: bytes) -> pd.DataFrame:
    """Parse in large chunks so an oversized file stops early; text columns go straight into categories."""
    delimiter = _sniff_delimiter(raw)
    sample = pd.read_csv(BytesIO(raw), sep=delimiter, nrows=_TYPE_SAMPLE_ROWS)
    text_columns = {column: "category" for column in sample.columns if sample[column].dtype == object}
    chunks: list[pd.DataFrame] = []
    rows = 0
    cells = 0
    reader = pd.read_csv(BytesIO(raw), sep=delimiter, dtype=text_columns or None, chunksize=CSV_CHUNK_ROWS)
    with reader:
        for chunk in reader:
            rows += len(chunk)
            cells += int(chunk.shape[0] * chunk.shape[1])
            if _too_large(rows, cells):
                raise DataProblem(_size_message())
            chunks.append(_compact(chunk))
    if not chunks:
        return sample.iloc[0:0]
    return _concat_compact(chunks)


def _skip(text: str, position: int, characters: str) -> int:
    length = len(text)
    while position < length and text[position] in characters:
        position += 1
    return position


def _records_frame(text: str, position: int, decoder: json.JSONDecoder) -> tuple[pd.DataFrame, int]:
    """Parse one JSON array starting at ``position`` into a compact DataFrame, a chunk of records at a time."""
    position += 1  # the opening bracket
    chunks: list[pd.DataFrame] = []
    records: list[object] = []
    rows = 0
    while True:
        position = _skip(text, position, _SEPARATORS)
        if position >= len(text):
            raise ValueError("Unterminated JSON array.")
        if text[position] == "]":
            position += 1
            break
        record, position = decoder.raw_decode(text, position)
        records.append(record)
        if len(records) >= JSON_CHUNK_RECORDS:
            rows += len(records)
            if limits.exceeds(rows, limits.max_table_rows()):
                raise DataProblem(_size_message())
            chunks.append(_compact(pd.DataFrame(records)))
            records = []
    if records or not chunks:
        chunks.append(_compact(pd.DataFrame(records)))
    return _concat_compact(chunks), position


def _read_json(raw: bytes) -> dict[str, pd.DataFrame]:
    """Read a record list, or an object mapping table names to record lists, without one Python object per cell."""
    text = raw.decode("utf-8-sig")
    decoder = json.JSONDecoder()
    position = _skip(text, 0, _WHITESPACE)
    if position < len(text) and text[position] == "[":
        frame, position = _records_frame(text, position, decoder)
        if _skip(text, position, _WHITESPACE) != len(text):
            raise ValueError("Unexpected content after the JSON array.")
        return {"ratings": frame}
    if position < len(text) and text[position] == "{":
        tables: dict[str, pd.DataFrame] = {}
        position += 1
        while True:
            position = _skip(text, position, _SEPARATORS)
            if position < len(text) and text[position] == "}":
                position += 1
                break
            key, position = decoder.raw_decode(text, position)
            position = _skip(text, position, _WHITESPACE)
            if position >= len(text) or text[position] != ":":
                raise ValueError("Malformed JSON object.")
            position = _skip(text, position + 1, _WHITESPACE)
            if position < len(text) and text[position] == "[":
                tables[str(key)], position = _records_frame(text, position, decoder)
            else:
                # Not a mapping of record lists (for example column-oriented JSON): use the general reader.
                return {"ratings": pd.DataFrame(json.loads(text))}
        if _skip(text, position, _WHITESPACE) != len(text):
            raise ValueError("Unexpected content after the JSON object.")
        return tables
    return {"ratings": pd.DataFrame(json.loads(text))}


def safe_for_spreadsheet(frame: pd.DataFrame) -> pd.DataFrame:
    """Neutralize strings (cell values and column headers) that spreadsheet programs could interpret as formulas."""
    safe = frame.copy()

    def neutralize(value: object) -> object:
        if not isinstance(value, str):
            return value
        cleaned = ILLEGAL_XML_CHARACTERS.sub("", value)
        return "'" + cleaned if cleaned.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")) else cleaned

    safe.columns = _unique_column_names([neutralize(str(column)) for column in safe.columns])
    for column in safe.columns:
        series = safe[column].astype(object) if isinstance(safe[column].dtype, pd.CategoricalDtype) else safe[column]
        safe[column] = series.map(neutralize)
    return safe


def results_to_excel(tables: dict[str, pd.DataFrame]) -> bytes:
    """Create an in-memory Excel evidence pack with readable sheets."""
    output = BytesIO()
    used_names: set[str] = set()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for raw_name, frame in tables.items():
            base = re.sub(r"[\\/*?:\[\]]", "-", str(raw_name))[:31] or "Results"
            sheet_name = base
            suffix = 2
            while sheet_name in used_names:
                tail = f"_{suffix}"
                sheet_name = base[: 31 - len(tail)] + tail
                suffix += 1
            used_names.add(sheet_name)
            safe = safe_for_spreadsheet(frame)
            safe.to_excel(writer, sheet_name=sheet_name, index=False)
            sheet = writer.sheets[sheet_name]
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for cells in sheet.columns:
                values = [len(str(cell.value)) if cell.value is not None else 0 for cell in cells[:2000]]
                sheet.column_dimensions[cells[0].column_letter].width = min(max(values, default=8) + 2, 42)
    return output.getvalue()


def results_to_json(tables: dict[str, pd.DataFrame], metadata: dict | None = None) -> bytes:
    """Serialize evidence tables and reproducibility metadata as UTF-8 JSON."""
    payload: dict[str, object] = {
        name: json.loads(frame.to_json(orient="records", date_format="iso")) for name, frame in tables.items()
    }
    if metadata:
        payload["analysis_metadata"] = metadata
    return json.dumps(payload, indent=2, default=str, allow_nan=False).encode("utf-8")


def tables_to_csv_zip(tables: dict[str, pd.DataFrame]) -> bytes:
    """Package equivalent accessible CSV tables in one archive."""
    output = BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for raw_name, frame in tables.items():
            filename = re.sub(r"[^A-Za-z0-9._-]+", "_", str(raw_name).strip()).strip("_") or "results"
            archive.writestr(f"{filename}.csv", safe_for_spreadsheet(frame).to_csv(index=False))
    return output.getvalue()
