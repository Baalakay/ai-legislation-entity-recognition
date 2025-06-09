import os
import sys
import json
from pathlib import Path
import fitz  # PyMuPDF
import boto3
import base64
import io
from PIL import Image
import re
import csv
import time
import botocore
import datetime
import pandas as pd
from zoneinfo import ZoneInfo

def detect_pdf_type(pdf_path):
    doc = fitz.open(pdf_path)
    has_text = False
    has_images = False
    for page in doc:
        if page.get_text().strip():
            has_text = True
        img_list = page.get_images(full=True)
        if img_list:
            has_images = True
    if has_text:
        return "text"
    elif has_images:
        return "scanned"
    else:
        return "other"

def resize_and_compress_image(image_path, max_size_bytes=3_700_000, max_dim=4096, jpeg_quality_min=30):
    """
    Resize and compress an image to fit within max_size_bytes and max_dim (pixels).
    Uses JPEG for better compression. Overwrites the original image if changes are made.
    """
    with Image.open(image_path) as img:
        # Convert to RGB for JPEG
        if img.mode != "RGB":
            img = img.convert("RGB")
        # Resize if necessary
        if max(img.size) > max_dim:
            scale = max_dim / max(img.size)
            new_size = tuple([int(x * scale) for x in img.size])
            img = img.resize(new_size, Image.LANCZOS)
        # Compress to fit size
        quality = 85
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality, optimize=True)
        while buffer.tell() > max_size_bytes and quality > jpeg_quality_min:
            quality -= 5
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=quality, optimize=True)
            if buffer.tell() <= max_size_bytes:
                break
            # If still too large, reduce dimensions further
            img = img.resize((int(img.size[0]*0.9), int(img.size[1]*0.9)), Image.LANCZOS)
        # Save back to disk as JPEG
        with open(image_path, "wb") as f:
            f.write(buffer.getvalue())

def ensure_base64_under_limit(image_path, max_b64_bytes=5_000_000):
    """
    Ensures the base64-encoded image is under the Bedrock limit. If not, further compresses.
    """
    with open(image_path, "rb") as img_file:
        b64 = base64.b64encode(img_file.read())
    if len(b64) <= max_b64_bytes:
        return
    # If too large, further reduce size/quality
    with Image.open(image_path) as img:
        if img.mode != "RGB":
            img = img.convert("RGB")
        quality = 60
        while len(b64) > max_b64_bytes and quality >= 20:
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=quality, optimize=True)
            with open(image_path, "wb") as f:
                f.write(buffer.getvalue())
            with open(image_path, "rb") as img_file:
                b64 = base64.b64encode(img_file.read())
            quality -= 10
        # If still too large, reduce dimensions
        while len(b64) > max_b64_bytes and max(img.size) > 500:
            img = img.resize((int(img.size[0]*0.9), int(img.size[1]*0.9)), Image.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=quality, optimize=True)
            with open(image_path, "wb") as f:
                f.write(buffer.getvalue())
            with open(image_path, "rb") as img_file:
                b64 = base64.b64encode(img_file.read())

def pdf_to_images(pdf_path, output_dir):
    doc = fitz.open(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    image_paths = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(dpi=300)
        img_path = output_dir / f"{Path(pdf_path).stem}_{page_num+1}.jpg"
        pix.save(str(img_path))
        resize_and_compress_image(img_path)  # Ensure image fits raw size limit
        ensure_base64_under_limit(img_path)  # Ensure base64 fits Bedrock limit
        image_paths.append(img_path)
    return image_paths

def image_to_base64(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")

def ask_bedrock_vision_model(document_image_paths, example_image_paths, prompt, model_id="us.amazon.nova-pro-v1:0"):
    """
    Sends all document images first, then all example images, with a dynamically constructed prompt.
    """
    debug_log_path = os.path.join(os.getcwd(), 'bedrock_api_debug.log')
    client = boto3.client("bedrock-runtime")
    max_retries = 5
    delay = 2
    # Read all document images
    doc_images_bytes = []
    for img_path in document_image_paths:
        with open(img_path, "rb") as img_file:
            doc_images_bytes.append(img_file.read())
    # Read all example images
    ex_images_bytes = []
    for ex_path in example_image_paths:
        with open(ex_path, "rb") as ex_img_file:
            ex_images_bytes.append(ex_img_file.read())
    # Build messages for Converse API
    content = [{"text": prompt}]
    for img_bytes in doc_images_bytes:
        content.append({"image": {"format": "jpeg", "source": {"bytes": img_bytes}}})
    for img_bytes in ex_images_bytes:
        content.append({"image": {"format": "jpeg", "source": {"bytes": img_bytes}}})
    messages = [{"role": "user", "content": content}]
    converse_kwargs = {
        "modelId": model_id,
        "messages": messages,
        "inferenceConfig": {"temperature": 0.0, "topP": 0.1}
    }
    # Log the full payload (with image bytes redacted)
    safe_converse_kwargs = json.loads(json.dumps(converse_kwargs, default=lambda o: '[BINARY]' if isinstance(o, (bytes, bytearray)) else str(o)))
    with open(debug_log_path, 'a', encoding='utf-8') as dbg:
        dbg.write(f"[{datetime.datetime.now().isoformat()}] [DEBUG] converse_kwargs payload (image bytes redacted):\n{json.dumps(safe_converse_kwargs, indent=2)}\n")
    for attempt in range(max_retries):
        try:
            with open(debug_log_path, 'a', encoding='utf-8') as dbg:
                dbg.write(f"\n[{datetime.datetime.now().isoformat()}] [DEBUG] About to call Bedrock Converse API...\n")
            response = client.converse(**converse_kwargs)
            with open(debug_log_path, 'a', encoding='utf-8') as dbg:
                dbg.write(f"[{datetime.datetime.now().isoformat()}] [DEBUG] Received response from Bedrock. Type: {type(response)}, Keys: {list(response.keys())}\n")
            response_body = response
            if "output" in response_body and "message" in response_body["output"]:
                content = response_body["output"]["message"]["content"]
                text_parts = [part["text"] for part in content if "text" in part]
                if text_parts:
                    text = "".join(text_parts)
                    import re
                    code_block = re.match(r"^```(?:json)?\s*([\s\S]+?)\s*```$", text.strip())
                    if code_block:
                        return code_block.group(1).strip()
                    return text.strip()
                return str(content)
            else:
                return str(response_body)
        except Exception as e:
            import traceback
            with open(debug_log_path, 'a', encoding='utf-8') as dbg:
                dbg.write(f"[{datetime.datetime.now().isoformat()}] [ERROR] Exception in ask_bedrock_vision_model:\n")
                dbg.write(traceback.format_exc())
            raise

def run_ner_on_claude_json(claude_json):
    try:
        data = json.loads(claude_json)
        entities = []
        for item in data:
            if 'entities' in item:
                entities.extend(item['entities'])
        return entities if entities else data
    except Exception as e:
        print(f"Failed to parse Claude JSON: {e}")
        return []

def clean_chunks_folders(root_folder):
    root = Path(root_folder)
    for parent in root.rglob(""):
        if parent.is_dir():
            chunks = parent / "chunks"
            if chunks.exists():
                for item in chunks.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        import shutil
                        shutil.rmtree(item)
                chunks.rmdir()

def extract_json_from_response(response):
    """
    Extracts the first valid JSON array or object from a string.
    Returns the JSON substring, or raises ValueError if not found.
    """
    # Try to find a JSON array
    array_match = re.search(r'(\[.*?\])', response, re.DOTALL)
    if array_match:
        return array_match.group(1)
    # Try to find a JSON object
    obj_match = re.search(r'(\{.*?\})', response, re.DOTALL)
    if obj_match:
        return obj_match.group(1)
    raise ValueError("No JSON array or object found in response.")

def fix_missing_commas_in_json_array(json_str):
    """
    Attempts to insert missing commas between objects in a JSON array string.
    Returns the fixed string.
    """
    # Insert a comma between }{ or ]{ or }[ (common LLM mistakes)
    import re
    fixed = re.sub(r'}\s*{', '}, {', json_str)
    fixed = re.sub(r']\s*{', '], {', fixed)
    fixed = re.sub(r'}\s*\[', '}, [', fixed)
    return fixed

def process_pdf(pdf_path, chunk_dir=None, prompt=None, model_id="us.amazon.nova-pro-v1:0"):
    pdf_type = detect_pdf_type(pdf_path)
    chunks = []
    aggregated_results = []
    if chunk_dir is None:
        chunk_dir = Path(pdf_path).parent / "chunks"
    image_paths = pdf_to_images(pdf_path, chunk_dir)
    # Example images
    example_image_paths = [
        "data/prompt_hints/redline_examples.jpg",
        "data/prompt_hints/adoption_date_examples.jpg"
    ]
    # Dynamically construct prompt with correct indices
    N = len(image_paths)
    M = len(example_image_paths)
    prompt_dynamic = (
        f"You will receive multiple images in this order:\n"
        f"- Images 1 to {N}: Legislative document pages to analyze and extract fields from.\n"
        f"- Images {N+1} to {N+M}: Example images for reference only (not for extraction).\n"
        f"\n"
        f"--- BEGIN DOCUMENT IMAGES (1-{N}) ---\n"
        f"[Images 1 to {N}: analyze and extract fields from these]\n"
        f"--- END DOCUMENT IMAGES (1-{N}) ---\n"
        f"\n"
        f"--- BEGIN EXAMPLES ({N+1}-{N+M}) ---\n"
        f"[Images {N+1} to {N+M}: use only as visual reference for REDLINE and ADOPTION_DATE. Do NOT extract any fields from these.]\n"
        f"--- END EXAMPLES ({N+1}-{N+M}) ---\n"
        f"\n"
        f"Extract the required fields ONLY from the document images. Ignore the example images for extraction. Use the example images ONLY as visual reference for REDLINE and ADOPTION_DATE.\n"
    )
    # Append the rest of the static prompt
    prompt_dynamic += (
        "\nYou are a legislative document analysis assistant. Given the following page image from a legislative or ordinance document, extract ONLY the following fields as a JSON object or array (one object per legislative action if needed). Use the rules, patterns, and examples from the specification document 'AI Analyzing the Legislation and Extracting Data.pdf'. Return ONLY valid JSON. Do not include any explanation, preamble, or formatting outside the JSON object or array.\n"
        "\nFields to extract:\n"
        "- LEGNO: Legislation number or identifier (e.g., '2025-04'). Only search for this on the first page/chunk; for subsequent pages, enter a blank value ('').\n"
        "- STATE: Output the official two-letter U.S. state abbreviation (e.g., 'RI' for Rhode Island) only if the full state name (e.g., 'Rhode Island') appears as a complete word anywhere in the document, including in legal citations, headers, or body text. Do NOT infer the state from city names, abbreviations, or context. If the state name appears in a legal citation (e.g., 'R.I. Gen. Laws'), treat this as a valid mention and output the corresponding two-letter abbreviation. If more than one state name is present, select the one that appears most frequently; if tied, use the first found. If no valid state name is found, output an empty string (''). Output only the two-letter abbreviation in uppercase (e.g., 'RI'), not the full name.\n"
        "- CITY/TOWN: City or Town (output only if explicitly mentioned on the page; never infer from context; search all chunks and use the value if found).\n"
        "- LEGTYPE: Legislation type (e.g., ordinance, resolution, bill, etc.). Only search for this on the first page/chunk; for subsequent pages, enter a blank value ('').\n"
        "- ADOPTION_DATE: Extract the adoption date only if it visually matches the attached example image (adoption_date_examples.jpg) and is clearly labeled as adopted, passed, approved, or enacted. Use the example image ONLY as a reference; do NOT extract any data from the example image itself. Do not extract vote tallies, numbers in parentheses, or unrelated dates. If no such date is found, return an empty string.\n"
        "- CHAPTER/TITLE: The chapter or title number (e.g., '255' from 'CHAPTER 255 Nonconforming Development'); 'Chapter' and 'Title' are interchangeable—extract whichever is present. Only search for this on the first page/chunk; for subsequent pages, enter a blank value ('').\n"
        "- LONG_TITLE: The long title of the legislation (often all caps, near the top of the first image); if all caps, convert to sentence case. Only get from the first chunk_filename in the array (e.g. '2343853_1.jpg', and not '2343853_[2-30].jpg').\n"
        "- LONG_TITLE_SUMMARY: Write a concise summary (2–6 words) that captures the main subject or action described in the LONG_TITLE field. Base the summary only on the extracted LONG_TITLE text; do not use information from other parts of the document. Use clear, specific language that reflects the core purpose or effect of the legislation. Avoid generic phrases (e.g., 'An ordinance' or 'A bill'); instead, focus on the unique topic or action (e.g., 'Rezoning residential lots' or 'Third-party billing procedures'). Output only for the first chunk/page containing the LONG_TITLE; for all others, output an empty string ('').\n"
        "- ARTICLE: Article number or name (e.g., 'VIII' from 'Article VIII, Chapter 255 - Zoning'). Only extract if it appears in document titles, page/paragraph/section headers, or as an explicit heading. Do NOT extract from regular body text, lists of code citations, or any strikeout/strikethrough text. Ignore references not in a heading or title context. Only search for this on the first page/chunk; for subsequent pages, enter a blank value ('').\n"
        "- SECTION: Only extract if it appears in document titles, page/paragraph/section headers, or as an explicit heading. Do NOT extract from regular body text, lists of code citations, or any strikeout/strikethrough text. (e.g., 'Section 1' from 'Section 1. The Town of' or 'Section 2' of 'Section 2. Amend § 1- 16 of the Code of Ordinances') Ignore references not in a heading or title context.\n"
        "- ACTION_CLASSIFICATION: One of Add, Amend, Repeal, or NCM (Non-Code Material). If any page or chunk has REDLINE marked as 'X', the aggregated ACTION_CLASSIFICATION for the document must be only 'Amend'. Do not include 'Add' if REDLINE is present anywhere in the document. If there is any evidence of amendment (e.g., redline, strikethrough, or language indicating changes to existing code), always classify as 'Amend' and do NOT classify as 'Add'. Only use 'Add' if the document is clearly introducing entirely new material, with no indication of amendment or redline. If in doubt, prefer 'Amend' over 'Add'. Only flag as NCM if it matches the definition in the specification document.\n"
        "- DISPOSITION: Only extract if it appears in document titles, page/paragraph/section headers, or as an explicit heading. Do NOT extract from regular body text, lists of code citations, or any strikeout/strikethrough text. Ignore references not in a heading or title context. For each location in the Code affected by the legislation, extract the marker (e.g., '§1-16' from 'Section 1. Amend § 1- 16 of the Code of Ordinances'). If multiple, separate with semicolons.\n"
        "- REDLINE: Mark REDLINE as 'X' only if you see text visually matching the attached example image (redline.jpg) under the 'Strikethrough' section. Use the example image ONLY as a reference; do NOT extract any data from the example image itself. Do not mark with an 'X' if it more visually matches the 'Not Strikethrough' section. Do not infer from context or language.\n"
        "- EXAMPLES_SUMMARY: In addition to the above, return a field called EXAMPLES_SUMMARY containing a brief description of the two example images provided: (1) redline.jpg and (2) adoption_date_examples.jpg. For each, summarize what you see in the image in 1-2 sentences. This is to confirm you have received and processed the example images.\n"
        "\nAdditional Instructions:\n"
        "- Ignore line numbers or document metadata in all analysis and extracted values.\n"
        "- For multi-page documents, aggregate all chunk results into a single record. For fields with differing values across chunks, deduplicate case-insensitively and reason as a senior legislation, summarization, and date-identification specialist to select the correct value. For ARTICLE, SECTION, ACTION_CLASSIFICATION, and DISPOSITION, allow multiple values (separated by semicolons). Allow only a single value in all other fields, and if the value is a date, select the most recent date only. Output all fields in sentence case (except for dates and numbers). Convert roman numerals to whole numbers.\n"
        "- For multi-page documents, if more than one date is found, return only the ONE most recent date in the entire document (closest to today).\n"
        "- For multi-page documents, if more than one LONG_TITLE_SUMMARY is found, return only the ONE from the first page of the entire document.\n"
    )
    # Call the LLM once for all images
    model_response = ask_bedrock_vision_model(image_paths, example_image_paths, prompt_dynamic, model_id=model_id)
    try:
        json_str = extract_json_from_response(model_response)
        chunk_json = json.loads(json_str)
    except Exception as e:
        # Redact base64-like blobs from the raw response for safety
        import re
        def redact_base64(s):
            return re.sub(r'[A-Za-z0-9+/=]{50,}', '[REDACTED_BASE64]', s)
        redacted_response = redact_base64(repr(model_response))
        debug_filename = os.path.join(os.getcwd(), f"debug_model_response_{Path(pdf_path).stem}.txt")
        with open(debug_filename, "w", encoding="utf-8") as debug_file:
            debug_file.write(redacted_response[:1000])
        try:
            import json5
            chunk_json = json5.loads(json_str)
        except Exception:
            fixed_str = fix_missing_commas_in_json_array(json_str)
            try:
                chunk_json = json.loads(fixed_str)
            except Exception:
                chunk_json = {"raw_response": model_response}
    # Only keep 'model_json' in output
    chunks.append({
        "chunk_filename": str(Path(pdf_path).name),
        "model_json": chunk_json
    })
    # Aggregate for summary if needed
    if isinstance(chunk_json, list):
        aggregated_results.extend(chunk_json)
    else:
        aggregated_results.append(chunk_json)
    time.sleep(2)  # Add delay to avoid Bedrock throttling
    return {
        "filename": str(Path(pdf_path).name),
        "type": pdf_type,
        "chunks": chunks,
        "aggregated_results": aggregated_results
    }

def process_folder(folder_path, prompt, model_id="us.amazon.nova-pro-v1:0"):
    folder = Path(folder_path)
    clean_chunks_folders(folder)
    results = []
    for pdf_file in folder.glob("*.pdf"):
        result = process_pdf(pdf_file, chunk_dir=folder/"chunks", prompt=prompt, model_id=model_id)
        # --- Begin aggregation logic ---
        agg = {}
        # Collect all keys from all chunks
        all_keys = set()
        for item in result["aggregated_results"]:
            all_keys.update(item.keys())
        # For each key, gather all non-empty, non-'None' values
        for key in all_keys:
            values = [str(item.get(key, '')).strip() for item in result["aggregated_results"]]
            # Remove blanks and 'None' (case-insensitive)
            values = [v for v in values if v and v.lower() != 'none']
            # Deduplicate case-insensitively
            seen = set()
            unique_values = []
            for v in values:
                v_lower = v.lower()
                if v_lower not in seen:
                    seen.add(v_lower)
                    # Remove qualifiers for LEGNO and CITY/TOWN
                    if key == 'LEGNO':
                        v = v.replace('No. ', '').replace('No ', '').strip()
                    if key == 'CITY/TOWN':
                        v = v.replace('Town of ', '').replace('Town Of ', '').strip()
                    # Convert to title case, except roman numerals for ARTICLE
                    if v:
                        if key == 'ARTICLE' and v.isupper() and all(c in 'IVXLCDM' for c in v):
                            v_s = v.upper()
                        elif key == 'ARTICLE' and v.upper() == v and all(c in 'IVXLCDM' for c in v.upper()):
                            v_s = v.upper()
                        elif key == 'ARTICLE' and all(c in 'ivxlcdm' for c in v.lower()):
                            v_s = v.upper()
                        elif key == 'STATE':
                            # Abbreviate state to two-letter code, all caps
                            state_map = {
                                'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR', 'california': 'CA', 'colorado': 'CO',
                                'connecticut': 'CT', 'delaware': 'DE', 'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI', 'idaho': 'ID',
                                'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS', 'kentucky': 'KY', 'louisiana': 'LA',
                                'maine': 'ME', 'maryland': 'MD', 'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS',
                                'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV', 'new hampshire': 'NH', 'new jersey': 'NJ',
                                'new mexico': 'NM', 'new york': 'NY', 'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK',
                                'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC', 'south dakota': 'SD',
                                'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT', 'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA',
                                'west virginia': 'WV', 'wisconsin': 'WI', 'wyoming': 'WY',
                                'district of columbia': 'DC', 'washington dc': 'DC', 'dc': 'DC'
                            }
                            v_norm = v.strip().lower()
                            v_s = state_map.get(v_norm, v.upper() if len(v) == 2 else v.title())
                        else:
                            v_s = v.title()
                    else:
                        v_s = ''
                    unique_values.append(v_s)
            if not unique_values:
                agg[key] = ''
            elif len(unique_values) == 1:
                agg[key] = unique_values[0]
            else:
                agg[key] = ','.join(f'({v})' for v in unique_values)
        # Ensure all output values are blank string if empty or 'None'
        for k in agg:
            if not agg[k] or agg[k].lower() == 'none':
                agg[k] = ''
        # Add LFID as the PDF name (without .pdf)
        lfid = Path(pdf_file).stem
        agg_ordered = {'LFID': lfid}
        ordered_keys = [
            'CITY/TOWN', 'STATE', 'LEGTYPE', 'LEGNO', 'ADOPTION_DATE',
            'LONG_TITLE_SUMMARY', 'ACTION_CLASSIFICATION',
            'CHAPTER/TITLE', 'ARTICLE', 'SECTION', 'DISPOSITION', 'REDLINE',
            'EXAMPLES_SUMMARY'
        ]
        agg_ordered.update({k: agg.get(k, '') for k in ordered_keys})
        result["aggregated_results"] = agg_ordered
        results.append(result)
    # Write aggregated results to Excel in the root of the input directory
    df = pd.DataFrame([r["aggregated_results"] for r in results])
    # Model short name mapping
    model_map = {
        'nova-micro': 'NovaMicro',
        'nova-lite': 'NovaLite',
        'nova-pro': 'NovaPro',
        'nova-premier': 'NovaPremier',
        'claude-3-opus': 'Claude3Opus',
        'claude-3-sonnet': 'Claude3Sonnet',
        'claude-3-7-sonnet': 'Claude3_7Sonnet',
        'claude-opus-4': 'ClaudeOpus4',
        'claude-sonnet-4': 'ClaudeSonnet4',
        'deepseek.r1': 'DeepseekR1',
    }
    def get_model_short(model_id):
        for k, v in model_map.items():
            if k in model_id:
                return v
        return 'Model'
    model_short = get_model_short(model_id)
    # Compose filename: index_<ParentDir>_<WorkingFolder>_<ModelShortName>_<DateTimestamp>.xlsx
    working_folder = folder.name
    parent_dir = folder.parent.name
    central = datetime.datetime.now(ZoneInfo("America/Chicago"))
    timestamp = central.strftime("%Y%m%d_%H%M")
    excel_filename = f"index_{parent_dir}_{working_folder}_{model_short}_{timestamp}.xlsx"
    # Determine output directory based on parent_dir
    if parent_dir == 'Train':
        output_dir = Path('data/Train/.csv')
    elif parent_dir == 'Test':
        output_dir = Path('data/Test/.csv')
    else:
        output_dir = folder
    output_dir.mkdir(parents=True, exist_ok=True)
    excel_path = output_dir / excel_filename
    df.to_excel(excel_path, index=False)
    # --- Post-processing for ACTION_CLASSIFICATION, ADOPTION_DATE, and STATE output ---
    # 1. If REDLINE is 'X', set ACTION_CLASSIFICATION to only 'Amend'
    if agg_ordered.get('REDLINE', '').strip().upper() == 'X':
        agg_ordered['ACTION_CLASSIFICATION'] = 'Amend'
    # 2. For ADOPTION_DATE, if multiple dates, keep only the most recent valid date
    import re
    date_str = agg_ordered.get('ADOPTION_DATE', '')
    if date_str:
        # Extract all date-like substrings
        date_candidates = re.findall(r'(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|[A-Za-z]+ \d{1,2}, \d{4})', date_str)
        parsed_dates = []
        for d in date_candidates:
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%B %d, %Y", "%b %d, %Y"):
                try:
                    parsed = datetime.datetime.strptime(d, fmt)
                    parsed_dates.append((parsed, d))
                    break
                except Exception:
                    continue
        if parsed_dates:
            # Keep only the most recent date
            most_recent = max(parsed_dates, key=lambda x: x[0])[1]
            agg_ordered['ADOPTION_DATE'] = most_recent
        else:
            # If no valid date, blank
            agg_ordered['ADOPTION_DATE'] = ''
    # 3. For STATE, only output a valid US state abbreviation
    state_str = agg_ordered.get('STATE', '')
    if state_str:
        # List of valid US state abbreviations
        valid_states = set([
            'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC'
        ])
        # Extract all two-letter uppercase codes
        state_candidates = re.findall(r'\b([A-Z]{2})\b', state_str.upper())
        filtered = [s for s in state_candidates if s in valid_states]
        agg_ordered['STATE'] = filtered[0] if filtered else ''
    # 4. Suppress LONG_TITLE from Excel output, but keep in data
    if 'LONG_TITLE' in agg_ordered:
        agg_ordered.pop('LONG_TITLE')
    return results

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pipeline.py <folder_path>")
        exit(1)
    folder_path = sys.argv[1]
    prompt = (
        "You will receive multiple images in this order:\n"
        "- Images 1 to N: Legislative document pages to analyze and extract fields from.\n"
        "- Images N+1 to N+M: Example images for reference only (not for extraction).\n"
        "\n"
        "--- BEGIN DOCUMENT IMAGES ---\n"
        "[Images 1 to N: analyze and extract fields from these]\n"
        "--- END DOCUMENT IMAGES ---\n"
        "\n"
        "--- BEGIN EXAMPLES ---\n"
        "[Images N+1 to N+M: use only as visual reference for REDLINE and ADOPTION_DATE. Do NOT extract any fields from these.]\n"
        "--- END EXAMPLES ---\n"
        "\n"
        "Extract the required fields ONLY from the document images. Ignore the example images for extraction. Use the example images ONLY as visual reference for REDLINE and ADOPTION_DATE.\n"
        "\n"
        "You are a legislative document analysis assistant. Given the following page image from a legislative or ordinance document, extract ONLY the following fields as a JSON object or array (one object per legislative action if needed). Use the rules, patterns, and examples from the specification document 'AI Analyzing the Legislation and Extracting Data.pdf'. Return ONLY valid JSON. Do not include any explanation, preamble, or formatting outside the JSON object or array.\n"
        "\nFields to extract:\n"
        "- LEGNO: Legislation number or identifier (e.g., '2025-04'). Only search for this on the first page/chunk; for subsequent pages, enter a blank value ('').\n"
        "- STATE: Output the official two-letter U.S. state abbreviation (e.g., 'RI' for Rhode Island) only if the full state name (e.g., 'Rhode Island') appears as a complete word anywhere in the document, including in legal citations, headers, or body text. Do NOT infer the state from city names, abbreviations, or context. If the state name appears in a legal citation (e.g., 'R.I. Gen. Laws'), treat this as a valid mention and output the corresponding two-letter abbreviation. If more than one state name is present, select the one that appears most frequently; if tied, use the first found. If no valid state name is found, output an empty string (''). Output only the two-letter abbreviation in uppercase (e.g., 'RI'), not the full name.\n"
        "- CITY/TOWN: City or Town (output only if explicitly mentioned on the page; never infer from context; search all chunks and use the value if found).\n"
        "- LEGTYPE: Legislation type (e.g., ordinance, resolution, bill, etc.). Only search for this on the first page/chunk; for subsequent pages, enter a blank value ('').\n"
        "- ADOPTION_DATE: Extract the adoption date only if it visually matches the attached example image (adoption_date_examples.jpg) and is clearly labeled as adopted, passed, approved, or enacted. Use the example image ONLY as a reference; do NOT extract any data from the example image itself. Do not extract vote tallies, numbers in parentheses, or unrelated dates. If no such date is found, return an empty string.\n"
        "- CHAPTER/TITLE: The chapter or title number (e.g., '255' from 'CHAPTER 255 Nonconforming Development'); 'Chapter' and 'Title' are interchangeable—extract whichever is present. Only search for this on the first page/chunk; for subsequent pages, enter a blank value ('').\n"
        "- LONG_TITLE: The long title of the legislation (often all caps, near the top of the first image); if all caps, convert to sentence case. Only get from the first chunk_filename in the array (e.g. '2343853_1.jpg', and not '2343853_[2-30].jpg').\n"
        "- LONG_TITLE_SUMMARY: Write a concise summary (2–6 words) that captures the main subject or action described in the LONG_TITLE field. Base the summary only on the extracted LONG_TITLE text; do not use information from other parts of the document. Use clear, specific language that reflects the core purpose or effect of the legislation. Avoid generic phrases (e.g., 'An ordinance' or 'A bill'); instead, focus on the unique topic or action (e.g., 'Rezoning residential lots' or 'Third-party billing procedures'). Output only for the first chunk/page containing the LONG_TITLE; for all others, output an empty string ('').\n"
        "- ARTICLE: Article number or name (e.g., 'VIII' from 'Article VIII, Chapter 255 - Zoning'). Only extract if it appears in document titles, page/paragraph/section headers, or as an explicit heading. Do NOT extract from regular body text, lists of code citations, or any strikeout/strikethrough text. Ignore references not in a heading or title context. Only search for this on the first page/chunk; for subsequent pages, enter a blank value ('').\n"
        "- SECTION: Only extract if it appears in document titles, page/paragraph/section headers, or as an explicit heading. Do NOT extract from regular body text, lists of code citations, or any strikeout/strikethrough text. (e.g., 'Section 1' from 'Section 1. The Town of' or 'Section 2' of 'Section 2. Amend § 1- 16 of the Code of Ordinances') Ignore references not in a heading or title context.\n"
        "- ACTION_CLASSIFICATION: One of Add, Amend, Repeal, or NCM (Non-Code Material). If any page or chunk has REDLINE marked as 'X', the aggregated ACTION_CLASSIFICATION for the document must be only 'Amend'. Do not include 'Add' if REDLINE is present anywhere in the document. If there is any evidence of amendment (e.g., redline, strikethrough, or language indicating changes to existing code), always classify as 'Amend' and do NOT classify as 'Add'. Only use 'Add' if the document is clearly introducing entirely new material, with no indication of amendment or redline. If in doubt, prefer 'Amend' over 'Add'. Only flag as NCM if it matches the definition in the specification document.\n"
        "- DISPOSITION: Only extract if it appears in document titles, page/paragraph/section headers, or as an explicit heading. Do NOT extract from regular body text, lists of code citations, or any strikeout/strikethrough text. Ignore references not in a heading or title context. For each location in the Code affected by the legislation, extract the marker (e.g., '§1-16' from 'Section 1. Amend § 1- 16 of the Code of Ordinances'). If multiple, separate with semicolons.\n"
        "- REDLINE: Mark REDLINE as 'X' only if you see text visually matching the attached example image (redline.jpg) under the 'Strikethrough' section. Use the example image ONLY as a reference; do NOT extract any data from the example image itself. Do not mark with an 'X' if it more visually matches the 'Not Strikethrough' section. Do not infer from context or language.\n"
        "- EXAMPLES_SUMMARY: In addition to the above, return a field called EXAMPLES_SUMMARY containing a brief description of the two example images provided: (1) redline.jpg and (2) adoption_date_examples.jpg. For each, summarize what you see in the image in 1-2 sentences. This is to confirm you have received and processed the example images.\n"
        "\nAdditional Instructions:\n"
        "- Ignore line numbers or document metadata in all analysis and extracted values.\n"
        "- For multi-page documents, aggregate all chunk results into a single record. For fields with differing values across chunks, deduplicate case-insensitively and reason as a senior legislation, summarization, and date-identification specialist to select the correct value. For ARTICLE, SECTION, ACTION_CLASSIFICATION, and DISPOSITION, allow multiple values (separated by semicolons). Allow only a single value in all other fields, and if the value is a date, select the most recent date only. Output all fields in sentence case (except for dates and numbers). Convert roman numerals to whole numbers.\n"
        "- For multi-page documents, if more than one date is found, return only the ONE most recent date in the entire document (closest to today).\n"
        "- For multi-page documents, if more than one LONG_TITLE_SUMMARY is found, return only the ONE from the first page of the entire document.\n"
    )
    output = process_folder(folder_path, prompt, model_id="us.amazon.nova-pro-v1:0")
    print(json.dumps(output, indent=2)) 