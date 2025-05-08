import argparse
from concurrent.futures import ThreadPoolExecutor
import io
import json
import logging
from pathlib import Path

from google import genai
from google.genai import types
import numpy as np
from pydantic import TypeAdapter

from deep_statutes.config import GEMINI_API_KEY
from deep_statutes.pdf.toc import Header, HeaderTreeNode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SUMMARIZE_MODEL = "gemini-2.5-flash-preview-04-17"


def _read_info(info_path: Path) -> tuple[HeaderTreeNode, list[Header]]:
    """Read the info file and return the data."""
    with open(info_path, "r") as f:
        data = json.load(f)

    header_tree_node = HeaderTreeNode.model_validate(data["root"])

    ta = TypeAdapter(list[Header])
    header_path = ta.validate_python(data["path"])

    return header_tree_node, header_path


class Summarizer:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key)

    def summarize_pdf(
        self,
        info_path: Path,
        pdf_path: Path,
        num_candidates: int = 3,
    ) -> types.GenerateContentResponse:
        """Summarize the PDF using Gemini."""
        logger.info(f"Summarizing PDF: {pdf_path}")

        header_tree, header_path = _read_info(info_path)

        prompt = io.StringIO()

        header_desc = f"{header_tree.header.text} ({header_tree.header.sub_text})"

        prompt.write("This PDF is a portion of the Colorado Revised Statutes.\n")
        prompt.write(f"It contains the text of {header_tree.header.text}.\n")
        if len(header_path) > 1:
            prompt.write("This section is nested under the following headers:\n")
            for header in header_path[:-1]:
                prompt.write(f"- {header.text} ({header.sub_text})\n")
        prompt.write("\n")
        prompt.write(
            f"Please summarize the text of {header_desc}. Just go straight into the summary in your response.\n"
        )

        logger.info(f"Using prompt:\n```{prompt.getvalue()}```")

        if not pdf_path.suffix == ".pdf":
            raise ValueError(f"File {pdf_path} is not a PDF")

        file = self.client.files.upload(file=pdf_path)

        assert file.mime_type == "application/pdf", f"File {pdf_path} is not a PDF"

        config = types.GenerateContentConfig(
            temperature=0.5,
            candidate_count=num_candidates,
        )

        response = self.client.models.generate_content(
            model=SUMMARIZE_MODEL,
            contents=[file, prompt.getvalue()],
            config=config,
        )

        # print out token use info
        cached_tokens = response.usage_metadata.cached_content_token_count
        prompt_tokens = response.usage_metadata.prompt_token_count
        cand_tokens = response.usage_metadata.candidates_token_count
        thinking_tokens = response.usage_metadata.thoughts_token_count
        total_tokens = response.usage_metadata.total_token_count

        logger.info(
            f"Token use: {cached_tokens} cached, {prompt_tokens} prompt, {cand_tokens} candidate, {thinking_tokens} thinking, {total_tokens} total"
        )

        return response


def _process_pdf(
    summarizer: Summarizer,
    pdf_path: Path,
    summary_dir: Path,
):
    logger.info(f"Summarizing PDF: {pdf_path}")

    info_path = pdf_path.parent / f"{pdf_path.stem}_info.json"

    summary = summarizer.summarize_pdf(
        info_path=info_path,
        pdf_path=pdf_path,
    )

    with open(summary_dir / f"{pdf_path.stem}_summary.json", "w") as f:
        s = summary.model_dump_json(indent=2)
        f.write(s)

    for i, candidate in enumerate(summary.candidates):
        output_path = summary_dir / f"{pdf_path.stem}_summary_{i + 1}.txt"

        if candidate.content is None:
            # NOTE EDF I have no idea why this happens, but it does
            logger.warning(
                f"Candidate {i + 1} has no content. Skipping writing to {output_path}"
            )
            continue

        with open(output_path, "w") as f:
            for part in candidate.content.parts:
                if part.thought:
                    f.write(f"# Thought\n\n{part.text}\n")
                else:
                    f.write(f"# Summary\n\n{part.text}\n")


def main():
    parser = argparse.ArgumentParser(description="Summarize a PDF using Gemini.")

    parser.add_argument(
        "input_dir", type=Path, help="Directory containing the PDFs to summarize."
    )
    parser.add_argument(
        "output_dir", type=Path, help="Directory to save the summaries."
    )

    parser.add_argument(
        "-j",
        "--num_jobs",
        type=int,
        default=1,
        help="Number of jobs to run in parallel.",
    )

    parser.add_argument(
        "--num_candidates",
        type=int,
        default=3,
        help="Number of summary candidates to generate.",
    )

    parser.add_argument(
        "--subsample_count",
        type=int,
        default=0,
        help="Number of PDFs to summarize. 0 means all. Otherwise, a random sample of this size will be taken.",
    )

    parser.add_argument(
        "--subsample_seed",
        type=int,
        default=0,
        help="Seed for the random number generator used to sample the PDFs. 0 means not to set a seed.",
    )

    args = parser.parse_args()

    input_dir = args.input_dir

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    summarizer = Summarizer(api_key=GEMINI_API_KEY)

    p_args = []
    for p in input_dir.glob("**/*.pdf"):
        summary_dir = output_dir / p.relative_to(input_dir).parent
        summary_dir.mkdir(parents=True, exist_ok=True)
        p_args.append((summarizer, p, summary_dir))

    if args.subsample_count > 0:
        gen = np.random.default_rng(args.subsample_seed)
        selected_indices = gen.choice(len(p_args), args.subsample_count, replace=False)
        p_args = [p_args[i] for i in sorted(selected_indices)]

    logger.info(f"Summarizing {len(p_args)} PDFs.")

    if args.num_jobs == 1:
        for a in p_args:
            _process_pdf(*a)
    else:
        with ThreadPoolExecutor(max_workers=args.num_jobs) as executor:
            res = executor.map(
                _process_pdf,
                *zip(*p_args),
            )

            # Wait for all tasks to complete
            for _ in res:
                pass
