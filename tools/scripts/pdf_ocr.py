"""Structured OCR for Sanskrit documents using Gemini API.

This script processes PDF files containing Sanskrit texts (Upanishads, etc.)
by splitting them into manageable chunks and using Google Gemini API to extract
structured Devanagari text with proper Mantra and Commentary formatting.

Features:
- Intelligent PDF chunking with caching to avoid redundant splitting
- Time-aware file upload caching to minimize API calls
- Automatic cache cleanup for expired entries
- Retry logic with exponential backoff for handling transient API errors
- Automatic merging of chunk files into final combined output
- Structured output with Mantra and Commentary sections

Typical usage:
    python pdf_ocr.py document.pdf --pages-per-chunk 10 --output-dir output/
"""

import argparse
from datetime import datetime
import logging
from pathlib import Path
import sys
import time
from typing import Optional

import pypdf
from google import genai

from gemini_processor.client import GeminiClient
from gemini_processor.file_manager import get_file_hash

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_MODEL: str = "gemini-2.5-pro"
DEFAULT_PAGES_PER_CHUNK: int = 10
DEFAULT_OUTPUT_DIR: Path = Path("ocr_output")
UPLOAD_CACHE_FILE: Path = Path.cwd() / ".file_upload_cache.json"

# Gemini config for PDF OCR - disables thinking mode for faster processing
#PDF_OCR_CONFIG = GenerateContentConfig(thinking_config={"thinking_budget": 0})
PDF_OCR_CONFIG = genai.types.GenerateContentConfig(
    media_resolution='MEDIA_RESOLUTION_MEDIUM',
)

# Retry configuration for API calls
MAX_RETRY_ATTEMPTS: int = 3
INITIAL_RETRY_DELAY_SECONDS: float = 2.0
RETRY_BACKOFF_MULTIPLIER: float = 2.0

# Path to OCR instruction prompt file
SCRIPT_DIR: Path = Path(__file__).parent
PROMPT_FILE: Path = SCRIPT_DIR / "prompt_pdf_ocr.txt"



def strip_markdown_fences(text: str) -> str:
    """Strip markdown code fences from Gemini response.

    Removes opening and closing code fences like ```xml, ```markdown, ```, etc.
    that Gemini sometimes wraps responses in.

    Args:
        text: The text content to clean.

    Returns:
        Text with markdown code fences removed.

    Example:
        >>> strip_markdown_fences("```xml\\n<tag>content</tag>\\n```")
        '<tag>content</tag>'
        >>> strip_markdown_fences("```\\nplain text\\n```")
        'plain text'
        >>> strip_markdown_fences("no fences here")
        'no fences here'
    """
    text = text.strip()

    # Remove opening fence (```xml, ```markdown, ```, etc.)
    if text.startswith("```"):
        # Find the end of the first line (the opening fence)
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]

    # Remove closing fence
    if text.endswith("```"):
        # Find the start of the last line (the closing fence)
        last_newline = text.rfind("\n```")
        if last_newline != -1:
            text = text[:last_newline]

    return text.strip()


def retry_with_exponential_backoff(
    func,
    max_attempts: int = MAX_RETRY_ATTEMPTS,
    initial_delay: float = INITIAL_RETRY_DELAY_SECONDS,
    backoff_multiplier: float = RETRY_BACKOFF_MULTIPLIER,
):
    """Retry a function with exponential backoff on failure.

    Args:
        func: Callable function to retry.
        max_attempts: Maximum number of retry attempts. Defaults to MAX_RETRY_ATTEMPTS.
        initial_delay: Initial delay in seconds before first retry. Defaults to
            INITIAL_RETRY_DELAY_SECONDS.
        backoff_multiplier: Multiplier for exponential backoff. Each retry waits
            delay * (backoff_multiplier ** attempt). Defaults to RETRY_BACKOFF_MULTIPLIER.

    Returns:
        Result from the function if successful.

    Raises:
        The last exception encountered if all retry attempts fail.

    Example:
        >>> result = retry_with_exponential_backoff(
        ...     lambda: client.generate_content(model, prompt),
        ...     max_attempts=3
        ... )
    """
    last_exception = None

    for attempt in range(1, max_attempts + 1):
        try:
            return func()
        except Exception as e:
            last_exception = e
            error_msg = str(e)

            # Check if it's a 500 error (retryable)
            is_500_error = "500" in error_msg or "INTERNAL" in error_msg

            if attempt < max_attempts and is_500_error:
                delay = initial_delay * (backoff_multiplier ** (attempt - 1))
                logger.warning(
                    f"Attempt {attempt}/{max_attempts} failed with 500 error. "
                    f"Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)
            elif attempt < max_attempts:
                # Non-500 error, but still retry
                delay = initial_delay * (backoff_multiplier ** (attempt - 1))
                logger.warning(
                    f"Attempt {attempt}/{max_attempts} failed: {error_msg}. "
                    f"Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)
            else:
                # Final attempt failed
                logger.error(
                    f"All {max_attempts} attempts failed. Last error: {error_msg}"
                )
                raise last_exception

    # Should never reach here, but satisfy type checker
    raise last_exception


class PdfChunkManager:
    """Manages PDF chunking with intelligent caching.

    Organizes chunks in a structured workdir and caches them to avoid
    redundant splitting operations. Uses content-based hashing to create
    unique workdir per PDF.

    Directory structure:
        pdf_ocr_workdir/<pdf_filename>-<hash>/chunks/chunk_<from>-<to>.pdf

    Attributes:
        pdf_path: Path to the source PDF file.
        pages_per_chunk: Number of pages in each chunk.
        workdir: Base working directory for all PDFs.
        pdf_workdir: Specific workdir for this PDF (includes hash for uniqueness).
        chunks_dir: Directory containing chunk files.

    Example:
        manager = PdfChunkManager(Path("document.pdf"), pages_per_chunk=10)
        chunks = manager.get_chunks()  # Returns cached chunks if available
        for chunk_path in chunks:
            process_chunk(chunk_path)
    """

    def __init__(
        self,
        pdf_path: Path,
        pages_per_chunk: int = 20,
        workdir: Optional[Path] = None,
    ) -> None:
        """Initialize PdfChunkManager with PDF file and chunking configuration.

        Args:
            pdf_path: Path to the source PDF file. Must exist.
            pages_per_chunk: Number of pages in each chunk. Defaults to 20.
            workdir: Base working directory for chunk storage. If None, uses
                'pdf_ocr_workdir' in current directory.

        Raises:
            FileNotFoundError: If pdf_path doesn't exist.

        Example:
            >>> manager = PdfChunkManager(
            ...     Path("document.pdf"),
            ...     pages_per_chunk=10,
            ...     workdir=Path("/tmp/pdf_chunks")
            ... )
        """
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        self.pdf_path: Path = pdf_path
        self.pages_per_chunk: int = pages_per_chunk

        # Convert None to default workdir, ensuring self.workdir is always Path
        if workdir is not None:
            self.workdir: Path = workdir
        else:
            self.workdir: Path = Path.cwd() / "pdf_ocr_workdir"

        # Create uniquifying hash (first 8 chars of SHA256)
        file_hash: str = get_file_hash(pdf_path)[:8]
        pdf_basename: str = pdf_path.stem  # filename without extension

        # Setup directory structure
        self.pdf_workdir: Path = self.workdir / f"{pdf_basename}-{file_hash}"
        self.chunks_dir: Path = self.pdf_workdir / "chunks"

    def _get_chunk_path(self, start_page: int, end_page: int) -> Path:
        """Generate chunk file path for a page range.

        Args:
            start_page: Starting page number (1-indexed).
            end_page: Ending page number (inclusive, 1-indexed).

        Returns:
            Path to the chunk file.
        """
        return self.chunks_dir / f"chunk_{start_page}-{end_page}.pdf"

    def _split_pdf(
        self, start_page: int = 1, num_pages: Optional[int] = None
    ) -> list[Path]:
        """Split PDF into chunks and save to chunks directory.

        Args:
            start_page: Starting page number (1-indexed). Defaults to 1.
            num_pages: Number of pages to process from start_page. If None,
                processes all pages from start_page to end of document.

        Returns:
            List of paths to created chunk files.

        Raises:
            ValueError: If start_page is invalid.

        Example:
            >>> # Process pages 20-30
            >>> chunks = manager._split_pdf(start_page=20, num_pages=10)
        """
        # Create chunks directory
        self.chunks_dir.mkdir(parents=True, exist_ok=True)

        pdf_reader = pypdf.PdfReader(self.pdf_path)
        total_pages = len(pdf_reader.pages)
        print("XXX 1: ", num_pages)

        # Calculate actual page range to process
        start_idx = start_page - 1  # Convert to 0-indexed
        if num_pages is None:
            end_idx = total_pages
            actual_num_pages = total_pages - start_idx
        else:
            end_idx = min(start_idx + num_pages, total_pages)
            actual_num_pages = end_idx - start_idx

        print("XXX 2")

        if start_idx < 0 or start_idx >= total_pages:
            raise ValueError(
                f"Invalid start_page {start_page}. PDF has {total_pages} pages."
            )

        chunk_paths = []

        #logger.info(
        print(
            f"Splitting pages {start_page}-{start_page + actual_num_pages - 1} "
            f"from '{self.pdf_path.name}' into chunks of {self.pages_per_chunk} pages..."
        )

        # Process page range in chunks
        for i in range(start_idx, end_idx, self.pages_per_chunk):
            pdf_writer = pypdf.PdfWriter()
            chunk_start = i + 1  # 1-indexed for display
            chunk_end = min(i + self.pages_per_chunk, end_idx)

            # Add pages to chunk (pypdf uses 0-indexed internally)
            for page_num in range(i, chunk_end):
                pdf_writer.add_page(pdf_reader.pages[page_num])

            # Write chunk file
            chunk_path = self._get_chunk_path(chunk_start, chunk_end)
            with open(chunk_path, "wb") as output_pdf:
                pdf_writer.write(output_pdf)

            chunk_paths.append(chunk_path)
            logger.info(
                f"  Created chunk: {chunk_path.name} ({chunk_end - chunk_start + 1} pages)"
            )

        logger.info(f"PDF splitting complete. Created {len(chunk_paths)} chunks.")
        return chunk_paths

    def _check_cache(
        self, start_page: int = 1, num_pages: Optional[int] = None
    ) -> list[Path] | None:
        """Check if valid cached chunks exist for the specified page range.

        Args:
            start_page: Starting page number (1-indexed). Defaults to 1.
            num_pages: Number of pages to process from start_page. If None,
                checks for chunks covering all pages from start_page to end.

        Returns:
            List of chunk paths if cache is valid, None otherwise.
        """
        if not self.chunks_dir.exists():
            return None

        # Get expected chunk ranges for the specified page range
        try:
            pdf_reader = pypdf.PdfReader(self.pdf_path)
            total_pages = len(pdf_reader.pages)
        except Exception as e:
            logger.warning(f"Could not read PDF for cache validation: {e}")
            return None

        # Calculate actual page range to check
        start_idx = start_page - 1  # Convert to 0-indexed
        if num_pages is None:
            end_idx = total_pages
        else:
            end_idx = min(start_idx + num_pages, total_pages)

        # Build expected chunks for this page range
        expected_chunks = []
        for i in range(start_idx, end_idx, self.pages_per_chunk):
            chunk_start = i + 1  # 1-indexed
            chunk_end = min(i + self.pages_per_chunk, end_idx)
            chunk_path = self._get_chunk_path(chunk_start, chunk_end)
            expected_chunks.append(chunk_path)

        # Verify all expected chunks exist
        if expected_chunks and all(chunk.exists() for chunk in expected_chunks):
            logger.info(f"Using cached chunks from {self.chunks_dir}")
            return expected_chunks

        return None

    def get_chunks(
        self,
        force_resplit: bool = False,
        start_page: int = 1,
        num_pages: Optional[int] = None,
    ) -> list[Path]:
        """Get list of PDF chunk paths, creating them if needed.

        Args:
            force_resplit: Force re-splitting even if cache exists.
            start_page: Starting page number (1-indexed). Defaults to 1.
            num_pages: Number of pages to process from start_page. If None,
                processes all pages from start_page to end of document.

        Returns:
            List of paths to chunk PDF files.

        Example:
            >>> # Get all chunks
            >>> chunks = manager.get_chunks()
            >>> # Get chunks for pages 20-30 only
            >>> chunks = manager.get_chunks(start_page=20, num_pages=10)
        """
        if not force_resplit:
            cached_chunks = self._check_cache(start_page, num_pages)
            if cached_chunks:
                return cached_chunks

        # Cache miss or force_resplit - create chunks
        return self._split_pdf(start_page=start_page, num_pages=num_pages)

    def clear_cache(self) -> bool:
        """Remove all cached chunks for this PDF.

        Returns:
            True if cache was cleared successfully.
        """
        if not self.pdf_workdir.exists():
            return True

        try:
            import shutil

            shutil.rmtree(self.pdf_workdir)
            logger.info(f"Cleared cache: {self.pdf_workdir}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return False


def save_output(content: str, output_path: Path) -> None:
    """Save extracted OCR content to a file.

    Creates parent directories if they don't exist. Logs success or failure.

    Args:
        content: The extracted text content to save.
        output_path: Destination file path.

    Raises:
        IOError: If file cannot be written.

    Example:
        >>> save_output("देवनागरी text", Path("output/page1.md"))
        INFO - Output successfully saved to 'output/page1.md'
    """
    try:
        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"✓ Output saved to '{output_path}'")
    except IOError as e:
        logger.error(f"Failed to write output file {output_path}: {e}")
        raise


def merge_chunk_files(
    input_pdf: Path, output_dir: Path, num_chunks: int
) -> Optional[Path]:
    """Merge all chunk output files into a single final markdown file.

    Reads all chunk files in order and concatenates them with double newline
    separators between chunks. Creates a merged file named <pdf_name>_merged.md.

    Args:
        input_pdf: Path to the original PDF file (used for naming merged output).
        output_dir: Directory containing chunk output files.
        num_chunks: Number of chunks to merge.

    Returns:
        Path to the merged output file if successful, None if merge failed.

    Raises:
        IOError: If chunk files cannot be read or merged file cannot be written.

    Example:
        >>> merged_path = merge_chunk_files(
        ...     Path("document.pdf"),
        ...     Path("ocr_output"),
        ...     num_chunks=5
        ... )
        INFO - Merging chunk files into final output...
        INFO - ✓ Merged 5 chunks into: document_merged.md
    """
    logger.info(f"\n{'='*60}")
    logger.info("Merging chunk files into final output...")
    logger.info(f"{'='*60}")

    # Collect all chunk files in order
    chunk_files = []
    for chunk_index in range(1, num_chunks + 1):
        chunk_filename = f"{input_pdf.stem}_chunk_{chunk_index:03d}.md"
        chunk_path = output_dir / chunk_filename
        if not chunk_path.exists():
            logger.error(f"Missing chunk file: {chunk_path}")
            return None
        chunk_files.append(chunk_path)

    # Merge all chunks into single output
    merged_content = []
    for chunk_index, chunk_path in enumerate(chunk_files, start=1):
        logger.info(f"  Reading chunk {chunk_index}/{num_chunks}: {chunk_path.name}")
        content = chunk_path.read_text(encoding="utf-8")
        merged_content.append(content)

    # Join with double newline separator between chunks
    final_content = "\n\n".join(merged_content)

    # Save merged output
    merged_filename = f"{input_pdf.stem}_merged.md"
    merged_path = output_dir / merged_filename
    merged_path.write_text(final_content, encoding="utf-8")

    logger.info(f"✓ Merged {num_chunks} chunks into: {merged_path.name}")
    logger.info(f"  Total size: {len(final_content):,} characters")

    return merged_path


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed command-line arguments.

    Example:
        >>> args = parse_args()
        >>> print(args.input_pdf)
        document.pdf
    """
    parser = argparse.ArgumentParser(
        description="Extract structured Sanskrit text from PDF using Gemini OCR",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage - process PDF with default settings
  %(prog)s document.pdf

  # Custom chunk size and output directory
  %(prog)s document.pdf --pages-per-chunk 15 --output-dir results/

  # Custom prompt from a file
  %(prog)s document.pdf --prompt-file my_prompt.txt

  # Custom prompt as a string
  %(prog)s document.pdf --prompt "Extract all text."

  # Process only first 3 chunks for testing
  %(prog)s document.pdf --max-chunks 3

  # Process specific page range (pages 20-30)
  %(prog)s document.pdf --start-page 20 --num-pages 10

  # Process 5 pages starting from page 1
  %(prog)s document.pdf --num-pages 5

  # Clear expired upload cache before processing
  %(prog)s document.pdf --clear-upload-cache

  # Force re-upload (ignore upload cache)
  %(prog)s document.pdf --no-upload-cache
        """,
    )

    parser.add_argument(
        "input_pdf",
        type=Path,
        help="Path to input PDF file",
    )

    prompt_group = parser.add_mutually_exclusive_group()
    prompt_group.add_argument(
        "--prompt",
        type=str,
        help="Prompt to use for OCR",
    )
    prompt_group.add_argument(
        "--prompt-file",
        type=Path,
        help="Path to a file containing the prompt for OCR",
    )

    parser.add_argument(
        "--pages-per-chunk",
        type=int,
        default=DEFAULT_PAGES_PER_CHUNK,
        help=f"Number of pages per chunk (default: {DEFAULT_PAGES_PER_CHUNK})",
    )

    parser.add_argument(
        "--max-chunks",
        type=int,
        help="Maximum number of chunks to process (useful for testing)",
    )

    parser.add_argument(
        "--start-page",
        type=int,
        default=1,
        help="Starting page number (1-indexed, default: 1)",
    )

    parser.add_argument(
        "--num-pages",
        type=int,
        default=None,
        help="Number of pages to process from start-page (default: None [all])",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for extracted text (default: {DEFAULT_OUTPUT_DIR})",
    )

    parser.add_argument(
        "--workdir",
        type=Path,
        help="Working directory for PDF chunks (default: pdf_ocr_workdir in current directory)",
    )

    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Gemini model to use (default: {DEFAULT_MODEL})",
    )

    parser.add_argument(
        "--clear-upload-cache",
        action="store_true",
        help="Clear expired entries (>48h old) from upload cache before processing",
    )

    parser.add_argument(
        "--no-upload-cache",
        action="store_true",
        help="Disable upload caching (always upload fresh files)",
    )

    parser.add_argument(
        "--force-resplit",
        action="store_true",
        help="Force re-splitting PDF even if cached chunks exist",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser.parse_args()


def process_pdf(
    input_pdf: Path,
    output_dir: Path,
    pages_per_chunk: int,
    model: str,
    use_upload_cache: bool,
    clear_upload_cache: bool,
    force_resplit: bool,
    verbose: bool,
    ocr_prompt: str,
    max_chunks: Optional[int] = None,
    workdir: Optional[Path] = None,
    start_page: int = 1,
    num_pages: int = 10,
) -> int:
    """Process a PDF file and extract structured Sanskrit text.

    Args:
        input_pdf: Path to input PDF file.
        output_dir: Directory for output files.
        pages_per_chunk: Number of pages per chunk.
        model: Gemini model name.
        use_upload_cache: Whether to use upload caching.
        clear_upload_cache: Whether to clean up expired cache entries.
        force_resplit: Force re-splitting PDF chunks.
        verbose: Enable verbose output.
        ocr_prompt: The prompt to use for OCR.
        max_chunks: Maximum number of chunks to process. If None, processes all.
        workdir: Working directory for PDF chunks. If None, uses default.
        start_page: Starting page number (1-indexed).
        num_pages: Number of pages to process from start_page.

    Returns:
        Exit code (0 for success, 1 for failure).

    Raises:
        FileNotFoundError: If input PDF doesn't exist.
        ValueError: If upload or processing fails.
    """
    # Validate input file
    if not input_pdf.exists():
        logger.error(f"Input PDF not found: {input_pdf}")
        return 1

    # Create timestamped subdirectory for this run
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    timestamped_output_dir = output_dir / f"{input_pdf.stem}_{timestamp}"
    timestamped_output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"📂 Output directory: {timestamped_output_dir}")

    # Setup Gemini client with upload caching
    client = GeminiClient(upload_cache_file=UPLOAD_CACHE_FILE)
    logger.info(f"📁 Upload cache: {UPLOAD_CACHE_FILE}")

    # Clean up expired cache entries if requested
    if clear_upload_cache:
        removed_count = client.cleanup_cache_expired()
        if removed_count > 0:
            logger.info(f"🧹 Cleaned up {removed_count} expired upload cache entries")
        else:
            logger.info("✓ Upload cache is clean (no expired entries)")

    # Create chunk manager and get chunks
    chunk_manager = PdfChunkManager(
        input_pdf, pages_per_chunk=pages_per_chunk, workdir=workdir
    )
    chunk_files = chunk_manager.get_chunks(
        force_resplit=force_resplit, start_page=start_page, num_pages=num_pages
    )

    # Limit chunks if max_chunks specified
    if max_chunks is not None and max_chunks > 0:
        chunk_files = chunk_files[:max_chunks]
        logger.info(
            f"📄 Processing {len(chunk_files)} chunks (limited by --max-chunks) "
            f"from '{input_pdf.name}'"
        )
    else:
        logger.info(f"📄 Processing {len(chunk_files)} chunks from '{input_pdf.name}'")

    # Process each chunk
    for chunk_index, chunk_path in enumerate(chunk_files, start=1):
        logger.info(f"\n{'='*60}")
        logger.info(
            f"Processing chunk {chunk_index}/{len(chunk_files)}: {chunk_path.name}"
        )
        logger.info(f"{'='*60}")

        # Upload chunk to Gemini (with correct PDF MIME type)
        uploaded_file = client.upload_file(
            file_path=chunk_path,
            use_upload_cache=use_upload_cache,
            verbose=verbose,
            mime_type="application/pdf",
        )

        if not uploaded_file:
            logger.error(f"Failed to upload chunk {chunk_path.name}")
            return 1

        # Extract text using Gemini OCR with retry logic
        try:
            extracted_text = retry_with_exponential_backoff(
                lambda: client.generate_content(
                    model=model,
                    prompt=ocr_prompt,
                    uploaded_file=uploaded_file,
                    config=PDF_OCR_CONFIG
                )
            )
        except Exception as e:
            logger.error(f"Failed to extract text from {chunk_path.name}: {e}")
            return 1

        extracted_text = strip_markdown_fences(extracted_text)

        # Preview extracted content
        preview = extracted_text[:200].replace("\n", " ")
        logger.info(f"✓ Extraction successful. Preview: {preview}...")

        # Save output with descriptive filename
        output_filename = f"{input_pdf.stem}_chunk_{chunk_index:03d}.md"
        output_path = timestamped_output_dir / output_filename
        save_output(extracted_text, output_path)

    logger.info(f"\n{'='*60}")
    logger.info(f"✅ Successfully processed all {len(chunk_files)} chunks")
    logger.info(f"📁 Output directory: {timestamped_output_dir.absolute()}")
    logger.info(f"{'='*60}")

    # Merge all chunks into final output file
    merged_path = merge_chunk_files(input_pdf, timestamped_output_dir, len(chunk_files))
    if merged_path:
        logger.info(f"\n{'='*60}")
        logger.info(f"📄 Final merged output: {merged_path.absolute()}")
        logger.info(f"{'='*60}")
    else:
        logger.warning("⚠️  Failed to merge chunk files")

    return 0


def main() -> int:
    """Main entry point for PDF OCR script.

    Parses command-line arguments and processes the PDF file.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    args = parse_args()

    # Set log level based on verbose flag
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load OCR prompt
    ocr_prompt = ""
    if args.prompt:
        ocr_prompt = args.prompt
        logger.info("📄 Using prompt from command line.")
    elif args.prompt_file:
        try:
            ocr_prompt = args.prompt_file.read_text(encoding="utf-8")
            logger.info(f"📄 Loaded OCR prompt from: {args.prompt_file}")
        except (FileNotFoundError, IOError) as e:
            logger.error(f"Error reading prompt file {args.prompt_file}: {e}")
            return 1
    else:
        try:
            ocr_prompt = PROMPT_FILE.read_text(encoding="utf-8")
            logger.info(f"📄 Loaded default OCR prompt from: {PROMPT_FILE.name}")
        except (FileNotFoundError, IOError) as e:
            logger.error(f"Error reading default prompt file {PROMPT_FILE}: {e}")
            return 1

    try:
        return process_pdf(
            input_pdf=args.input_pdf,
            output_dir=args.output_dir,
            pages_per_chunk=args.pages_per_chunk,
            model=args.model,
            use_upload_cache=not args.no_upload_cache,
            clear_upload_cache=args.clear_upload_cache,
            force_resplit=args.force_resplit,
            verbose=args.verbose,
            max_chunks=args.max_chunks,
            workdir=args.workdir,
            start_page=args.start_page,
            num_pages=args.num_pages,
            ocr_prompt=ocr_prompt,
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
