"""
MPCI Knowledge Base Builder
- Loads the extracted PDF text
- Uses page-based extraction with known TOC structure
- Chunks content for vector retrieval
"""

import os
import re
import json
from typing import List, Dict

CHUNK_DIR = os.path.join(os.path.dirname(__file__), "chunks")

# Known document structure: section -> start_page
# From the Table of Contents of UAE MPCI Business Specification Document V1.0
SECTION_PAGE_MAP = [
    ("1", "Purpose", 5, 5),
    ("2", "Introduction", 6, 7),
    ("2.1", "Overview", 6, 6),
    ("2.2", "Legal Framework", 7, 7),
    ("3", "Scope and Requirements", 8, 12),
    ("3.1", "Filers and Their Roles", 8, 8),
    ("3.2", "Required Documents", 9, 9),
    ("3.3", "Filing Timing", 10, 10),
    ("3.4", "Inclusions", 10, 10),
    ("3.5", "Exclusions", 10, 10),
    ("3.6", "Integration Requirements", 11, 12),
    ("4", "MPCI Business Processes", 13, 25),
    ("4.1", "MPCI Business Process Overview", 13, 13),
    ("4.2", "MPCI Onboarding Process", 14, 14),
    ("4.3", "MPCI Filing Process", 14, 14),
    ("4.3.1", "Shipping Line and Master Co-Loader Filing", 14, 16),
    ("4.3.2", "Freight Forwarder / Sub Co-loader Filing", 17, 18),
    ("4.4", "Message Validation", 19, 20),
    ("4.5", "MPCI Shipment Assessment", 21, 21),
    ("4.6", "Delegation Process", 22, 25),
    ("4.6.1", "Delegation for Freight Forwarders", 22, 23),
    ("4.6.2", "Delegation to Shipping Agents", 24, 25),
    ("4.6.3", "NAIC Responses in Cases of Delegation", 25, 25),
    ("5", "MPCI Business Data Requirements", 26, 31),
    ("5.1", "Business Data Elements", 27, 29),
    ("5.2", "Handling Consignee Data Element Scenarios", 30, 30),
    ("5.3", "MPCI Party ID – Definition and Usage", 31, 31),
    ("5.3.1", "MPCI Party ID Usage", 31, 31),
    ("5.3.2", "MPCI Party ID Issuance and Sharing", 31, 31),
    ("6", "Special Business Scenarios", 32, 41),
    ("6.1", "Consolidation and Co-loading", 32, 35),
    ("6.1.1", "NAIC Requirements Overview", 32, 32),
    ("6.1.2", "Shipping Line Filing", 33, 33),
    ("6.1.3", "Freight Forwarder Filing", 33, 33),
    ("6.1.3.1", "Normal Filing Scenario", 33, 33),
    ("6.1.3.2", "Delegation Options", 33, 33),
    ("6.1.4", "NAIC Assessment Responses", 34, 35),
    ("6.1.5", "Coordination and Linking of Filing", 35, 35),
    ("6.2", "Updating a Bill of Lading", 36, 41),
    ("6.2.1", "Update Scenarios", 36, 37),
    ("6.2.2", "General Considerations for Bill of Lading Updates", 37, 37),
    ("6.2.3", "Split Bill of Lading Handling", 38, 40),
    ("6.2.4", "NAIC Assessment Responses for Updates", 41, 41),
    ("7", "Data Quality Rules", 42, 42),
    ("8", "Communications", 43, 43),
    ("8.1", "Maintaining Up-to-Date Contact Information", 43, 43),
    ("8.2", "Communication from NAIC", 43, 43),
    ("8.3", "Contacting NAIC for Assistance", 43, 43),
    ("9", "Business Continuity", 44, 44),
    ("10", "Glossary", 45, 46),
    ("11", "References", 47, 47),
    ("12", "Appendices", 48, 56),
    ("12.1", "Appendix A – BPMN Annotations", 48, 48),
    ("12.3", "Appendix C – Party Information Guidelines", 49, 50),
    ("12.4", "Appendix D – Goods Description Guidelines", 51, 56),
]


def load_extracted_text(filepath: str = None) -> str:
    """Load the extracted PDF text."""
    if filepath is None:
        candidates = [
            os.path.join(os.path.dirname(__file__), "..", "pdf_text.txt"),
            os.path.join(os.path.dirname(__file__), "..", "pdf_text_clean.txt"),
        ]
        for p in candidates:
            if os.path.exists(p):
                filepath = p
                break
        if filepath is None:
            raise FileNotFoundError("Cannot find extracted PDF text file.")

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def split_into_pages(text: str) -> Dict[int, str]:
    """
    Split the document into pages based on '--- Page N ---' markers.
    Returns {page_number: page_content}.
    """
    # Normalize page markers
    text = re.sub(r'--- Page (\d+) ---', r'\n--- PAGE_BREAK:\1 ---\n', text)

    pages = {}
    current_page = None
    current_content = []

    for line in text.split('\n'):
        m = re.match(r'--- PAGE_BREAK:(\d+) ---', line)
        if m:
            if current_page is not None:
                pages[current_page] = '\n'.join(current_content).strip()
            current_page = int(m.group(1))
            current_content = []
        else:
            current_content.append(line)

    # Last page
    if current_page is not None:
        pages[current_page] = '\n'.join(current_content).strip()

    return pages


def clean_page_content(content: str) -> str:
    """Clean a single page's content."""
    # Remove empty lines with just spaces and numbers (page numbers in text)
    lines = content.split('\n')
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Skip lines that are just numbers (page numbers) or empty
        if re.match(r'^\s*\d+\s*$', stripped) and len(stripped) < 5:
            continue
        # Skip lines that are just the document version
        if stripped.startswith('Document Version:'):
            continue
        # Skip pure whitespace lines
        if not stripped:
            continue
        cleaned.append(stripped)

    return '\n'.join(cleaned)


def extract_page_content(pages: Dict[int, str], start_page: int, end_page: int) -> str:
    """Extract clean content from a range of pages."""
    content_parts = []
    for p in range(start_page, end_page + 1):
        if p in pages:
            cleaned = clean_page_content(pages[p])
            if cleaned:
                content_parts.append(cleaned)
    return '\n\n'.join(content_parts)


def _section_heading_pattern(sec_num: str) -> str:
    escaped = re.escape(sec_num)
    return rf'(?m)^{escaped}\s+[^\n]+$'


def extract_section_content(content: str, sec_num: str, next_sec_num: str = None) -> str:
    """Trim a page range to the exact section when headings are available."""
    start_match = re.search(_section_heading_pattern(sec_num), content)
    if not start_match:
        return content

    start = start_match.start()
    end = len(content)

    if next_sec_num:
        next_match = re.search(_section_heading_pattern(next_sec_num), content[start_match.end():])
        if next_match:
            end = start_match.end() + next_match.start()

    trimmed = content[start:end].strip()
    return trimmed if trimmed else content


def build_knowledge_base(text_file: str = None) -> List[Dict]:
    """
    Build knowledge base using known section-to-page mapping.
    """
    print("Loading extracted text...")
    text = load_extracted_text(text_file)
    print(f"Text length: {len(text)} chars")

    print("Splitting into pages...")
    pages = split_into_pages(text)
    print(f"Found {len(pages)} pages")

    chunks = []

    for idx, (sec_num, sec_title, start_p, end_p) in enumerate(SECTION_PAGE_MAP):
        content = extract_page_content(pages, start_p, end_p)
        next_sec_num = SECTION_PAGE_MAP[idx + 1][0] if idx + 1 < len(SECTION_PAGE_MAP) else None
        content = extract_section_content(content, sec_num, next_sec_num)

        if not content:
            print(f"  WARNING: No content for §{sec_num} {sec_title} (pages {start_p}-{end_p})")
            continue

        # For appendices with long tables, split into smaller chunks
        if sec_num == "12.4":  # Appendix D (Goods Description)
            sub_chunks = _split_appendix_d(content, sec_num, sec_title)
            chunks.extend(sub_chunks)
        elif end_p - start_p > 2 and len(content) > 3000:
            # Split long sections into page-based sub-chunks
            sub_chunks = _split_long_section(content, sec_num, sec_title, pages, start_p, end_p)
            chunks.extend(sub_chunks)
        else:
            chunks.append({
                "section_num": sec_num,
                "title": sec_title,
                "content": content,
                "id": f"sec_{sec_num.replace('.', '_')}",
                "page_ref": f"p.{start_p}" if start_p == end_p else f"p.{start_p}-{end_p}"
            })

    print(f"\nTotal chunks: {len(chunks)}")
    return chunks


def _split_long_section(content: str, sec_num: str, sec_title: str,
                         pages: Dict[int, str], start_p: int, end_p: int) -> List[Dict]:
    """Split a long section into smaller page-based sub-chunks."""
    chunks = []
    # Group 2-3 pages per chunk for better granularity
    group_size = 2

    for i in range(start_p, end_p + 1, group_size):
        group_end = min(i + group_size - 1, end_p)
        sub_content = extract_page_content(pages, i, group_end)
        if sub_content:
            chunks.append({
                "section_num": sec_num,
                "title": f"{sec_title} (p.{i}-{group_end})",
                "content": sub_content,
                "id": f"sec_{sec_num.replace('.', '_')}_p{i}",
                "page_ref": f"p.{i}-{group_end}"
            })
    return chunks


def _split_appendix_d(content: str, sec_num: str, sec_title: str) -> List[Dict]:
    """Split Appendix D (Goods Description) into meaningful sub-chunks."""
    chunks = []

    # Split by category groups
    categories = re.split(r'\n(?=[A-Z][A-Za-z\s/]+(?:\n|$))', content)
    current = []
    current_len = 0
    chunk_idx = 0

    for cat in categories:
        cat = cat.strip()
        if not cat:
            continue
        if current_len + len(cat) > 1500 and current:
            chunks.append({
                "section_num": sec_num,
                "title": f"{sec_title} - 货物描述规范 (part {chunk_idx + 1})",
                "content": '\n\n'.join(current),
                "id": f"sec_{sec_num.replace('.', '_')}_g{chunk_idx + 1}",
                "page_ref": "p.51-56"
            })
            chunk_idx += 1
            current = [cat]
            current_len = len(cat)
        else:
            current.append(cat)
            current_len += len(cat)

    if current:
        chunks.append({
            "section_num": sec_num,
            "title": f"{sec_title} - 货物描述规范 (part {chunk_idx + 1})",
            "content": '\n\n'.join(current),
            "id": f"sec_{sec_num.replace('.', '_')}_g{chunk_idx + 1}",
            "page_ref": "p.51-56"
        })

    return chunks if chunks else [{
        "section_num": sec_num,
        "title": sec_title,
        "content": content,
        "id": f"sec_{sec_num.replace('.', '_')}",
        "page_ref": "p.51-56"
    }]


def export_chunks(chunks: List[Dict]):
    """Export chunks for inspection."""
    os.makedirs(CHUNK_DIR, exist_ok=True)
    path = os.path.join(CHUNK_DIR, "mpci_chunks.json")
    data = [{
        "id": c["id"],
        "title": c["title"],
        "section_num": c.get("section_num", ""),
        "page_ref": c.get("page_ref", ""),
        "content_length": len(c["content"])
    } for c in chunks]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Exported to {path}")


if __name__ == "__main__":
    chunks = build_knowledge_base()
    export_chunks(chunks)
    print(f"\n=== Sample chunks ===")
    for c in chunks[:15]:
        print(f"  [§{c['section_num']:>6}] {c['title'][:55]} ({len(c['content'])} chars)")
