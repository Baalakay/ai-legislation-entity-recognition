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

def ask_claude_bedrock_vision(image_path, prompt, model_id="anthropic.claude-3-sonnet-20240229-v1:0"):
    with open(image_path, "rb") as img_file:
        image_b64 = base64.b64encode(img_file.read()).decode("utf-8")
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": image_b64,
                    },
                },
            ],
        }
    ]
    body = {
        "messages": messages,
        "max_tokens": 4096,
        "anthropic_version": "bedrock-2023-05-31"
    }
    client = boto3.client("bedrock-runtime")
    response = client.invoke_model(
        modelId=model_id,
        body=json.dumps(body),
        accept="application/json",
        contentType="application/json"
    )
    response_body = json.loads(response["body"].read())
    return response_body["content"][0]["text"]

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

def process_pdf(pdf_path, chunk_dir=None, prompt=None, model_id="anthropic.claude-3-sonnet-20240229-v1:0"):
    pdf_type = detect_pdf_type(pdf_path)
    chunks = []
    aggregated_results = []
    if chunk_dir is None:
        chunk_dir = Path(pdf_path).parent / "chunks"
    image_paths = pdf_to_images(pdf_path, chunk_dir)
    for img_path in image_paths:
        claude_response = ask_claude_bedrock_vision(img_path, prompt, model_id=model_id)
        try:
            json_str = extract_json_from_response(claude_response)
            chunk_json = json.loads(json_str)
        except Exception as e:
            print(f"Failed to parse Claude response for {img_path}: {e}")
            print(f"Raw Claude response for {img_path}: {repr(claude_response)}")
            if hasattr(e, 'pos'):
                pos = e.pos
                print(f"Error near: ...{json_str[max(0,pos-40):pos+40]}...")
            try:
                import json5
                try:
                    chunk_json = json5.loads(json_str)
                    print(f"Parsed with json5 fallback for {img_path}.")
                except Exception as e2:
                    print(f"json5 also failed: {e2}")
                    fixed_str = fix_missing_commas_in_json_array(json_str)
                    try:
                        chunk_json = json.loads(fixed_str)
                        print(f"Parsed with auto-fix for missing commas for {img_path}.")
                    except Exception as e3:
                        print(f"Auto-fix also failed: {e3}")
                        chunk_json = {"raw_response": claude_response}
            except ImportError:
                print("json5 is not installed. To enable tolerant JSON parsing, run: uv pip install json5")
                fixed_str = fix_missing_commas_in_json_array(json_str)
                try:
                    chunk_json = json.loads(fixed_str)
                    print(f"Parsed with auto-fix for missing commas for {img_path}.")
                except Exception as e3:
                    print(f"Auto-fix also failed: {e3}")
                    chunk_json = {"raw_response": claude_response}
        # Only keep 'claude_json' in output
        chunks.append({
            "chunk_filename": str(img_path.name),
            "claude_json": chunk_json
        })
        # Aggregate for summary if needed
        if isinstance(chunk_json, list):
            aggregated_results.extend(chunk_json)
        else:
            aggregated_results.append(chunk_json)
    return {
        "filename": str(Path(pdf_path).name),
        "type": pdf_type,
        "chunks": chunks,
        "aggregated_results": aggregated_results
    }

def process_folder(folder_path, prompt, model_id="anthropic.claude-3-sonnet-20240229-v1:0"):
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
            'LONG_TITLE', 'LONG_TITLE_SUMMARY', 'ACTION_CLASSIFICATION',
            'CHAPTER/TITLE', 'ARTICLE', 'SECTION', 'DISPOSITION', 'REDLINE'
        ]
        agg_ordered.update({k: agg.get(k, '') for k in ordered_keys})
        result["aggregated_results"] = agg_ordered
        results.append(result)
    # Write aggregated results to CSV in the root of the input directory
    csv_fields = [
        'LFID', 'CITY/TOWN', 'STATE', 'LEGTYPE', 'LEGNO', 'ADOPTION_DATE',
        'LONG_TITLE', 'LONG_TITLE_SUMMARY', 'ACTION_CLASSIFICATION',
        'CHAPTER/TITLE', 'ARTICLE', 'SECTION', 'DISPOSITION', 'REDLINE'
    ]
    # Find next available versioned filename
    base_path = folder
    version = 1
    while True:
        csv_path = base_path / f"aggregated_results_{version}.csv"
        if not csv_path.exists():
            break
        version += 1
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=csv_fields)
        writer.writeheader()
        for r in results:
            row = r["aggregated_results"]
            writer.writerow(row)
    return results

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pipeline.py <folder_path>")
        exit(1)
    folder_path = sys.argv[1]
    prompt = (
        "You are a legislative document analysis assistant. Given the following page image from a legislative or ordinance document, extract ONLY the following fields as a JSON object or array (one object per legislative action if needed). Use the rules, patterns, and examples from the specification document 'AI Analyzing the Legislation and Extracting Data.pdf'. Return ONLY valid JSON. Do not include any explanation, preamble, or formatting outside the JSON object or array.\n"
        "\nFields to extract:\n"
        "- LEGNO: Legislation number or identifier (e.g., '2025-04'). Only search for this on the first page/chunk; for subsequent pages, enter a blank value ('').\n"
        "- STATE: State (output only if explicitly mentioned on a page; never infer from city/town; if found in any chunk, use that value for the aggregated result).\n"
        "- CITY/TOWN: City or Town (output only if explicitly mentioned on the page; never infer from context; search all chunks and use the value if found).\n"
        "- LEGTYPE: Legislation type (e.g., ordinance, resolution, bill, etc.). Only search for this on the first page/chunk; for subsequent pages, enter a blank value ('').\n"
        "- ADOPTION_DATE: Date of adoption or passage (return '' unless 90%+ certain it is a date). Only search for this on the first page/chunk; for subsequent pages, enter a blank value ('').\n"
        "- CHAPTER/TITLE: The chapter or title number (e.g., '255' from 'CHAPTER 255 Nonconforming Development'); 'Chapter' and 'Title' are interchangeable—extract whichever is present. Only search for this on the first page/chunk; for subsequent pages, enter a blank value ('').\n"
        "- LONG_TITLE: The long title of the legislation (often all caps, near the top of the first page); if all caps, convert to sentence case. Also, provide a 2–6 word summary of the long title in a field called LONG_TITLE_SUMMARY. Only output these fields on the first page that contains a value; for all other pages, output blank ('').\n"
        "- ARTICLE: Article number or name (e.g., 'VIII' from 'Article VIII, Chapter 255 - Zoning'). Only search for this on the first page/chunk; for subsequent pages, enter a blank value ('').\n"
        "- SECTION: Section number (e.g., 'Section 1'). When extracting SECTION, prioritize section headings (often bold, and often preceded by the section sign '\\u00a7'). Do not extract section/article numbers that are only referenced in paragraph text—only those that are part of a heading or title.\n"
        "- ACTION_CLASSIFICATION: One of Add, Amend, Repeal, or NCM (Non-Code Material). Only flag as NCM if it matches the definition in the specification document. If a chunk does not have a clear action, inherit the ACTION_CLASSIFICATION from the previous chunk (numerically); if that chunk also does not have one, keep going back to the next previous chunk that contains an ACTION_CLASSIFICATION (other than NONE) and use that value.\n"
        "- DISPOSITION: For each location in the Code affected by the legislation, extract the marker (e.g., '1-16' from 'Amend §1-16 of the Code of Ordinances'). If multiple, separate with semicolons.\n"
        "- REDLINE: If any page for a PDF has strikeout text in it, mark this field as 'X'. Ensure detection regardless of font color (red, black, etc.).\n"
        "\nAdditional Instructions:\n"
        "- For multi-page documents, aggregate the results from all chunks into a single record for the document as a whole. For any field where some chunks have different values, reason as a senior legislation specialist to determine the correct value for the aggregated result. For fields ARTICLE, SECTION, ACTION_CLASSIFICATION, and DISPOSITION, multiple values may be present (separated by semicolons). For all fields, deduplicate values case-insensitively and output in sentence case.\n"
        "- When distinguishing between Amend/Repeal/Add vs NCM, reason about the intent: NCM should only be used if the document discusses changes but does not instruct where in the code/legislation to make the changes (i.e., informational, not actionable). If the document instructs changes/additions and provides the sections/articles to be changed, it is not NCM.\n"
        "- Do NOT include any extra fields (such as 'identifier' or 'metadata').\n"
        "- For each field, use the cues, patterns, and synonyms from the specification document.\n"
        "- If a field is not present or cannot be determined, return '' (empty string).\n"
        "- Only extract information relevant to the above fields.\n"
    )
    output = process_folder(folder_path, prompt)
    print(json.dumps(output, indent=2)) 