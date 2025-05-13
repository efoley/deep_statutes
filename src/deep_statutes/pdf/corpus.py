import argparse
from pathlib import Path
from typing import Iterator
import uuid

import pyarrow as pa
import pyarrow.parquet as pq
import pymupdf
from pydantic import BaseModel


class Document(BaseModel):
    uuid: str
    pdf_path: str
    pdf_bytes: bytes
    page_text: list[str]
    page_image: list[bytes]


# we could just generate this schema from the Document model...
SCHEMA = pa.schema(
    [
        pa.field("uuid", pa.string()),
        pa.field("pdf_path", pa.string()),
        pa.field("pdf_bytes", pa.binary()),
        pa.field("page_text", pa.list_(pa.string())),
        pa.field("page_image", pa.list_(pa.binary())),
    ]
)


def write_documents_to_parquet(
    doc_generator: Iterator[Document],
    output_path: str,
    batch_size: int = 5,  # Number of documents to batch before writing
):
    """
    Writes a stream of Document objects from a generator to a Parquet file.

    Args:
        doc_generator: A generator yielding Document instances.
        output_path: The path to the output Parquet file.
        batch_size: The number of documents to accumulate before writing a row group.
    """
    writer = None
    current_batch = []

    try:
        for i, doc in enumerate(doc_generator):
            # Convert Pydantic model to dictionary
            current_batch.append(doc.model_dump())  # Use .dict() for Pydantic V1

            if (i + 1) % batch_size == 0:
                if not current_batch:  # Should not happen if i+1 > 0
                    continue

                # Convert list of dicts to a PyArrow Table
                # Transpose the list of dicts into a dict of lists
                data_for_arrow = {
                    key: [dic[key] for dic in current_batch] for key in current_batch[0]
                }
                arrow_table = pa.Table.from_pydict(data_for_arrow, schema=SCHEMA)

                if writer is None:
                    # Initialize ParquetWriter on the first batch
                    writer = pq.ParquetWriter(output_path, SCHEMA)

                writer.write_table(arrow_table)
                print(
                    f"Written batch of {len(current_batch)} documents to {output_path}"
                )
                current_batch = []  # Reset batch

        # Write any remaining documents in the last batch
        if current_batch:
            data_for_arrow = {
                key: [dic[key] for dic in current_batch] for key in current_batch[0]
            }
            arrow_table = pa.Table.from_pydict(data_for_arrow, schema=SCHEMA)

            if writer is None:  # Handle case where total docs < batch_size
                writer = pq.ParquetWriter(output_path, SCHEMA)
            writer.write_table(arrow_table)
            print(
                f"Written final batch of {len(current_batch)} documents to {output_path}"
            )

    finally:
        if writer:
            writer.close()
            print(f"Parquet file '{output_path}' closed.")
        elif not output_path:  # If no writer was created because generator was empty
            print("No documents were generated, Parquet file not created.")


def generate_documents(pdf_paths: Iterator[Path]) -> Iterator[Document]:
    for pdf_path in pdf_paths:
        print(pdf_path)
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
            f.seek(0)
            doc = pymupdf.open(f)
            page_text = []
            page_image = []
            for page in doc:
                page_text.append(page.get_text())
                pix = page.get_pixmap()
                page_image.append(pix.tobytes("png"))

        yield Document(
            uuid=uuid.uuid4().hex,
            pdf_path=str(pdf_path),
            pdf_bytes=pdf_bytes,
            page_text=page_text,
            page_image=page_image,
        )


def generate_documents_from_dir(pdf_dir: Path) -> Iterator[Document]:
    pdf_paths = list(pdf_dir.glob("*.pdf"))
    pdf_paths.sort()
    return generate_documents(pdf_paths)


def main():
    parser = argparse.ArgumentParser(
        description="Convert a directory of PDF files to a Parquet file."
    )

    parser.add_argument(
        "input_dir", type=Path, help="Directory containing the PDF files."
    )
    parser.add_argument("output_file", type=Path, help="Output Parquet file path.")
    parser.add_argument(
        "--batch_size",
        "-b",
        type=int,
        default=5,
        help="Number of documents to batch before writing.",
    )
    args = parser.parse_args()

    doc_gen = generate_documents_from_dir(args.input_dir)
    write_documents_to_parquet(
        doc_gen,
        args.output_file,
        batch_size=args.batch_size,
    )
