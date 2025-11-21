# Standard library imports
import time
from typing import List, Tuple

# Third-party imports
import diff_match_patch
from aksharamukha import transliterate

# Conditional imports for rich or colorama
try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
    USE_RICH = True
except ImportError:
    try:
        from colorama import Fore, Style, init
        init()
    except ImportError:
        # If neither rich nor colorama is installed, create dummy objects
        class DummyColor:
            def __getattr__(self, name):
                return ""
        Fore = Style = DummyColor()
    USE_RICH = False


def get_transliterated_diffs(diffs: List[Tuple[int, str]], scheme: str = "HK") -> List[Tuple[int, str]]:
    """
    Transliterates the text in a diff list from Devanagari to the specified scheme.
    """
    return [(op, transliterate.process('Devanagari', scheme, text)) for op, text in diffs]


def print_visual_diff(
    source_text: str,
    target_text: str,
    context_chars: int = 40,
    max_diffs: int = 10,
    output_style: str = "colorama", # Added parameter
    transliteration_scheme: str = "HK", # Added parameter
):
    """
    Computes and prints a visual, contextual diff between two texts,
    with configurable output style and transliteration scheme.
    """
    start_time = time.perf_counter()

    # Determine which rendering library to use based on output_style preference
    use_rich_renderer = False
    if output_style == "rich":
        try:
            from rich.console import Console
            from rich.table import Table
            from rich.text import Text
            use_rich_renderer = True
        except ImportError:
            print("Warning: 'rich' library not found. Falling back to colorama.", file=sys.stderr)
    
    if not use_rich_renderer:
        try:
            from colorama import Fore, Back, Style, init
            init()
        except ImportError:
            class DummyColor:
                def __getattr__(self, name):
                    return ""
            Fore = Back = Style = DummyColor()
            print("Warning: 'colorama' library not found. Output will not be colored.", file=sys.stderr)

    dmp = diff_match_patch.diff_match_patch()
    diffs = dmp.diff_main(source_text, target_text)
    dmp.diff_cleanupSemantic(diffs)

    num_diffs = sum(1 for op, _ in diffs if op != dmp.DIFF_EQUAL)
    if num_diffs == 0:
        if use_rich_renderer:
            Console().print(Text("✓ No differences found.", style="green"))
        else:
            print(f"{Fore.GREEN}✓ No differences found.{Style.RESET_ALL}")
        return

    print(f"Found {num_diffs} difference(s), showing first {min(num_diffs, max_diffs)}:")

    diff_count = 0
    for i in range(len(diffs)):
        if diff_count >= max_diffs:
            break

        op, text = diffs[i]
        if op == dmp.DIFF_EQUAL:
            continue

        diff_count += 1
        
        # --- CONTEXT SNIPPET LOGIC ---
        # Context before
        start_index = max(0, i - 1)
        pre_context_op, pre_context_text = diffs[start_index]
        if pre_context_op == dmp.DIFF_EQUAL:
            pre_context_text = pre_context_text[-context_chars:]
        else:
            pre_context_text = ""

        # The actual difference
        diff_snippet = [(op, text)]
        
        # Combine consecutive diffs of the same type
        j = i + 1
        while j < len(diffs) and diffs[j][0] != dmp.DIFF_EQUAL:
            diff_snippet.append(diffs[j])
            j += 1
        
        # Context after
        end_index = j
        post_context_op, post_context_text = diffs[end_index] if end_index < len(diffs) else (dmp.DIFF_EQUAL, "")
        if post_context_op == dmp.DIFF_EQUAL:
            post_context_text = post_context_text[:context_chars]
        else:
            post_context_text = ""
            
        dev_snippet = [(dmp.DIFF_EQUAL, pre_context_text)] + diff_snippet + [(dmp.DIFF_EQUAL, post_context_text)]
        hk_snippet = get_transliterated_diffs(dev_snippet, transliteration_scheme)

        # --- RENDER SNIPPET ---
        if use_rich_renderer:
            table = Table(show_header=False, show_edge=False, box=None, padding=0, title=f"\n--- Diff {diff_count} ---")
            table.add_column()
            
            dev_line = Text()
            for op, text in dev_snippet:
                style = "dim" if op == dmp.DIFF_EQUAL else "bold black on green" if op == dmp.DIFF_INSERT else "strike red"
                dev_line.append(text, style=style)

            hk_line = Text()
            for op, text in hk_snippet:
                style = "dim" if op == dmp.DIFF_EQUAL else "bold black on green" if op == dmp.DIFF_INSERT else "strike red"
                hk_line.append(text, style=style)

            table.add_row(dev_line)
            table.add_row(hk_line)
            Console().print(table)
        else: # Colorama fallback
            print(f"\n--- Diff {diff_count} ---")
            dev_parts = []
            for op, text in dev_snippet:
                if op == dmp.DIFF_INSERT: dev_parts.append(f"{Back.GREEN}{Fore.WHITE}{text}{Style.RESET_ALL}")
                elif op == dmp.DIFF_DELETE: dev_parts.append(f"{Back.RED}{Fore.WHITE}{text}{Style.RESET_ALL}")
                else: dev_parts.append(f"{Style.DIM}{text}{Style.RESET_ALL}")
            print("".join(dev_parts))

            hk_parts = []
            for op, text in hk_snippet:
                if op == dmp.DIFF_INSERT: hk_parts.append(f"{Back.GREEN}{Fore.WHITE}{text}{Style.RESET_ALL}")
                elif op == dmp.DIFF_DELETE: hk_parts.append(f"{Back.RED}{Fore.WHITE}{text}{Style.RESET_ALL}")
                else: hk_parts.append(f"{Style.DIM}{text}{Style.RESET_ALL}")
            print("".join(hk_parts))

    end_time = time.perf_counter()
    print(f"\nDiff generated in: {end_time - start_time:.4f}s")
