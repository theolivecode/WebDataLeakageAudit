import json
import os
import asyncio
import time
import logging
import argparse
from typing import TextIO
from prompts import LEAKAGE_JUDGE_PROMPT

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def call_llm_and_extract_json_tags(prompt: str) -> dict:
    """
    Send prompt to an LLM and return the dict parsed from
    <JSON>...</JSON> tags in the response.
    """
    raise NotImplementedError


def is_valid_schema(data: dict) -> bool:
    """
    Checks if the JSON response has the correct keys and value types.
    """
    if not isinstance(data, dict):
        return False

    required_keys = {"reasoning", "contains_post_cutoff_info", "leakage_score"}
    if not required_keys.issubset(data.keys()):
        return False

    if not isinstance(data["reasoning"], str):
        return False
    if not isinstance(data["contains_post_cutoff_info"], bool):
        return False
    if isinstance(data["leakage_score"], bool) or not isinstance(data["leakage_score"], int):
        return False

    if not (0 <= data["leakage_score"] <= 4):
        return False

    return True


async def process_llm_data_leakage_judge(
    entry: dict,
    f_lock: asyncio.Lock,
    f_out: TextIO,
    rate_limiter: asyncio.Semaphore,
    max_retries: int = 3,
) -> bool:
    q = entry["question"]
    url = entry["url"]
    context = entry["context"]

    async with rate_limiter:
        item_start_time = time.perf_counter()

        prompt = LEAKAGE_JUDGE_PROMPT.format(
            question=q["title"],
            resolution_criteria=q["resolution_criteria"],
            resolved_answer=q["resolution"],
            background=q["description"],
            information_cutoff_date=q["open_time"],
            context=context,
        )

        valid_response = None
        for attempt in range(max_retries):
            try:
                response_obj = await call_llm_and_extract_json_tags(prompt)

                if is_valid_schema(response_obj):
                    valid_response = response_obj
                    break
                else:
                    logger.warning(
                        f"Invalid schema on attempt {attempt + 1} for URL: {url}\nResponse: {response_obj}"
                    )
            except Exception as e:
                logger.error(f"Error calling LLM on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                sleep_time = 1 * (2**attempt)
                await asyncio.sleep(sleep_time)

        if valid_response:
            duration = time.perf_counter() - item_start_time
            logger.info(f"Finished ID:{q['id']} | {url} | Time: {duration:.2f}s")
            output_entry = {
                "question": q,
                "url": url,
                "LLM_leakage_eval": valid_response,
                "context": context,
            }
            async with f_lock:
                f_out.write(json.dumps(output_entry) + "\n")
                f_out.flush()
            return True
        return False


async def main(input_file: str, output_file: str, max_concurrent_llm_requests: int):

    llm_rate_limiter = asyncio.Semaphore(max_concurrent_llm_requests)
    file_lock = asyncio.Lock()

    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    processed_pairs = set()
    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f_in:
            for line in f_in:
                entry = json.loads(line)
                q = entry["question"]
                url = entry["url"]
                if (q["id"], url) in processed_pairs:
                    logger.warning(f"Duplicate. QID: {q['id']}, url: {url}")
                processed_pairs.add((q["id"], url))

    logger.info(
        f"Starting run. Skipping {len(processed_pairs)} previously processed items."
    )

    background_tasks = set()
    with (
        open(input_file, "r", encoding="utf-8") as f_in,
        open(output_file, "a", encoding="utf-8") as f_out,
    ):
        for line_idx, line in enumerate(f_in):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                logger.error(f"Skipping bad JSON at line {line_idx}")
                continue

            # Check duplication
            q_id = entry["question"]["id"]
            url = entry["url"]
            if (q_id, url) in processed_pairs:
                continue
            processed_pairs.add((q_id, url))

            task = asyncio.create_task(
                process_llm_data_leakage_judge(
                    entry, file_lock, f_out, llm_rate_limiter
                )
            )

            background_tasks.add(task)
            task.add_done_callback(background_tasks.discard)

            if len(background_tasks) >= max_concurrent_llm_requests * 2:
                await asyncio.wait(
                    background_tasks, return_when=asyncio.FIRST_COMPLETED
                )

        if background_tasks:
            logger.info(f"Waiting for remaining {len(background_tasks)} tasks...")
            await asyncio.wait(background_tasks)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run LLM Data Leakage Judge")

    parser.add_argument(
        "--input", "-i", type=str, required=True, help="Path to the input ndjson file"
    )
    parser.add_argument(
        "--output", "-o", type=str, required=True, help="Path to the output ndjson file"
    )

    parser.add_argument(
        "--concurrency",
        "-c",
        type=int,
        default=2,
        help="Maximum number of concurrent LLM requests",
    )

    args = parser.parse_args()
    asyncio.run(main(args.input, args.output, args.concurrency))
