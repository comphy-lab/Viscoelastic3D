#!/usr/bin/env python3
import os, subprocess, re, shutil, argparse, html, json
from pathlib import Path
from urllib.parse import quote
from typing import Dict, List, Optional, Any, Union

# Parse args
parser = argparse.ArgumentParser(description='Generate docs from source files')
parser.add_argument('--debug', action='store_true', help='Enable debug output')
parser.add_argument('--force-rebuild', action='store_true', help='Force rebuild all HTML files')
args = parser.parse_args()
DEBUG = args.debug
FORCE_REBUILD = args.force_rebuild

def debug_print(msg):
    """
    Prints a debug message if debug mode is enabled.
    
    Args:
        msg: The message to print when debugging is active.
    """
    if DEBUG: print(msg)

def calculate_asset_prefix(output_path: Path, docs_dir: Path) -> str:
    """
    Returns the relative path prefix to reference assets from an HTML file based on its location within the documentation directory.
    
    Args:
        output_path: The path to the generated HTML file.
        docs_dir: The root directory of the documentation output.
    
    Returns:
        A string representing the relative path prefix (e.g., ".", "..", "../..") to use for asset references.
    """
    try:
        if output_path.name == "index.html" and output_path.parent == docs_dir:
            return "."
        depth = len(output_path.relative_to(docs_dir).parents) - 1
        return "." if depth <= 0 else "/".join([".."] * depth)
    except ValueError:
        return "."

def extract_seo_metadata(file_path: Path, content: str) -> Dict[str, str]:
    """
    Extracts SEO metadata such as description and keywords from file content.
    
    If embedded SEO metadata is present (as a JSON object in an HTML comment), it is parsed and sanitized. Otherwise, the function generates a description from the first paragraph or header and derives keywords from the filename and code patterns (functions, classes, includes). The resulting metadata is suitable for use in HTML meta tags.
    
    Args:
        file_path: Path to the source file.
        content: The content of the file as a string.
    
    Returns:
        A dictionary containing SEO metadata fields such as 'description' and 'keywords'.
    """
    metadata = {}
    
    # Check for embedded SEO metadata (used by Jupyter notebooks)
    seo_match = re.search(r'<!--SEO_METADATA:(.*?)-->', content)
    if seo_match:
        try:
            debug_print(f"Found embedded SEO metadata in {file_path}")
            embedded_metadata = json.loads(seo_match.group(1))
            if isinstance(embedded_metadata, dict):
                metadata.update(embedded_metadata)
                # Extra sanitization of description to be absolutely safe
                if "description" in metadata:
                    metadata["description"] = re.sub(r'<[^>]*>', '', metadata["description"])
                    metadata["description"] = re.sub(r'["\'\\\<>]', '', metadata["description"])
                return metadata
        except Exception as e:
            debug_print(f"Error parsing embedded SEO metadata: {e}")
    
    # Extract first paragraph as description (fallback for non-notebook files)
    desc_match = re.search(r'^\s*#\s*(.*?)\s*$\s*([a-zA-Z].*?)(?=^\s*#|\Z)', 
                          content, re.MULTILINE | re.DOTALL)
    if desc_match:
        description = desc_match.group(2).strip()
        if not description or description.startswith(('```', '`', '#', '//')):
            description = desc_match.group(1).strip()
        
        # Clean up description and truncate to ~160 chars
        description = re.sub(r'[#`*_]', '', description)
        description = re.sub(r'\s+', ' ', description).strip()
        if len(description) > 160:
            description = description[:157] + "..."
        metadata["description"] = description
    
    # Extract keywords by analyzing content
    keywords = set()
    # Add filename-based keywords
    name_parts = file_path.stem.replace('_', ' ').replace('-', ' ').split()
    keywords.update([p.lower() for p in name_parts if len(p) > 3])
    
    # Add common technical terms if found in content
    tech_patterns = [
        r'function\s+([a-zA-Z_][a-zA-Z0-9_]*)',
        r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)',
        r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)',
        r'#include\s+["<]([^">]+)[">]'
    ]
    for pattern in tech_patterns:
        for match in re.finditer(pattern, content):
            if match.group(1) and len(match.group(1)) > 3:
                keywords.add(match.group(1).lower())
    
    # Format keywords as comma-separated string
    if keywords:
        metadata["keywords"] = ", ".join(sorted(list(keywords)[:10]))
    
    # Ensure description is safe for HTML attributes
    if "description" in metadata:
        # Remove HTML tags and replace quotes
        metadata["description"] = re.sub(r'<[^>]*>', '', metadata["description"])
        metadata["description"] = re.sub(r'"', '\'', metadata["description"])
        
        # Truncate if still too long
        if len(metadata["description"]) > 160:
            metadata["description"] = metadata["description"][:157] + "..."
    
    return metadata

# Configuration
REPO_ROOT = Path(__file__).parent.parent.parent
SOURCE_DIRS = ['src-local', 'simulationCases', 'postProcess']
DOCS_DIR = REPO_ROOT / 'docs'
README_PATH = REPO_ROOT / 'README.md'
INDEX_PATH = DOCS_DIR / 'index.html'
BASILISK_DIR = REPO_ROOT / 'basilisk'
DARCSIT_DIR = BASILISK_DIR / 'src' / 'darcsit'
TEMPLATE_PATH = REPO_ROOT / '.github' / 'assets' / 'custom_template.html'
LITERATE_C_SCRIPT = DARCSIT_DIR / 'literate-c'
BASE_URL = "/"
CSS_PATH = REPO_ROOT / '.github' / 'assets' / 'css' / 'custom_styles.css'

# Get repository name from directory
REPO_NAME = REPO_ROOT.name

# Read domain from CNAME file or use default
try:
    CNAME_PATH = REPO_ROOT / 'CNAME'
    BASE_DOMAIN = f"https://{CNAME_PATH.read_text().strip()}" if CNAME_PATH.exists() else "https://test.comphy-lab.org"
except Exception as e:
    print(f"Warning: Could not read CNAME file: {e}")
    BASE_DOMAIN = "https://test.comphy-lab.org"

def extract_h1_from_readme(readme_path: Path) -> str:
    """
    Extracts the first H1 markdown header from a README file.
    
    If no H1 header is found or the file cannot be read, returns "Documentation".
    """
    try:
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
            h1_match = re.search(r'^# (.+)$', content, re.MULTILINE)
            if h1_match:
                return h1_match.group(1).strip()
            debug_print("Warning: No h1 heading found in README.md")
            return "Documentation"
    except Exception as e:
        print(f"Error reading README.md: {e}")
        return "Documentation"

# Dynamically get the wiki title from README.md
WIKI_TITLE = extract_h1_from_readme(README_PATH)

def process_template_for_assets(template_path: Path) -> str:
    """
    Reads and returns the content of the HTML template file for asset path processing.
    
    Args:
        template_path: Path to the HTML template file.
    
    Returns:
        The content of the template file as a string, or an empty string if an error occurs.
    """
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        print(f"Repository name: {REPO_NAME}")
        debug_print("Template processed for correct asset paths")
        return template_content
    except Exception as e:
        print(f"Error processing template: {e}")
        return ""

def validate_config() -> bool:
    """
    Validates the existence of essential directories and files required for documentation generation.
    
    Checks for the presence of core directories and files, processes the HTML template for Pandoc, and creates a temporary template file for use during conversion. Updates the global template path if successful.
    
    Returns:
        True if all required paths exist and the template is processed successfully; False otherwise.
    """
    global TEMPLATE_PATH
    
    essential_paths = [
        (BASILISK_DIR, "BASILISK_DIR"),
        (DARCSIT_DIR, "DARCSIT_DIR"),
        (TEMPLATE_PATH, "TEMPLATE_PATH"),
        (LITERATE_C_SCRIPT, "literate-c script")
    ]

    for path, name in essential_paths:
        if not (path.is_dir() if name.endswith("DIR") else path.is_file()):
            print(f"Error: {name} not found at {path}")
            return False
    
    processed_template = process_template_for_assets(TEMPLATE_PATH)
    if not processed_template:
        return False
        
    temp_template_path = TEMPLATE_PATH.with_suffix('.temp.html')
    
    if temp_template_path.exists():
        try:
            temp_template_path.unlink()
        except Exception as e:
            print(f"Warning: Could not delete existing temporary template: {e}")
    
    try:
        with open(temp_template_path, 'w', encoding='utf-8') as f:
            f.write(processed_template)
        TEMPLATE_PATH = temp_template_path
    except Exception as e:
        print(f"Error creating temporary template file: {e}")
        return False
    
    return True

def find_source_files(root_dir: Path, source_dirs: List[str]) -> List[Path]:
    """
    Finds all supported source files in the specified directories and root directory.
    
    Searches recursively within each source directory and non-recursively in the root directory for files with supported extensions (.c, .h, .py, .sh, .ipynb) or named 'Makefile', excluding files ending with '.dat'.
    
    Args:
        root_dir: The root directory to search for source files.
        source_dirs: List of subdirectory names to search recursively.
    
    Returns:
        A sorted list of Paths to the discovered source files.
    """
    valid_exts = {'.c', '.h', '.py', '.sh', '.ipynb'}
    valid_names = {'Makefile'}
    files = set()

    for dir_name in source_dirs:
        src_path = root_dir / dir_name
        if src_path.is_dir():
            for f in src_path.rglob('*'):
                if f.is_file():
                    if f.name in valid_names:
                        files.add(f)
                    elif f.suffix in valid_exts and not f.name.endswith('.dat'):
                        files.add(f)

    # Search for .sh files and Makefiles in root directory
    for f in root_dir.iterdir():
        if f.is_file():
            if f.name in valid_names:
                files.add(f)
            elif f.suffix in valid_exts and not f.name.endswith('.dat'):
                files.add(f)

    return sorted(files)

def process_markdown_file(file_path: Path) -> str:
    """
    Reads and returns the content of a Markdown file for further processing or conversion.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()

def process_shell_file(file_path: Path) -> str:
    """
    Reads a shell script file and returns its content as a Markdown-formatted bash code block.
    
    The script content is escaped to prevent Pandoc from interpreting shell variables or boolean assignments.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        # Escape any potential variables that could conflict with Pandoc
        content = content.replace("$", "\\$")
        # Escape variable assignments with true/false values
        content = content.replace("=true", "=\\true")
        content = content.replace("=false", "=\\false")
        return f"# {file_path.name}\n\n```bash\n{content}\n```"

def inert_notebook_text(value: str) -> str:
    """Render notebook-supplied text as one line of plain text.

    The text is used both in raw HTML and in a Markdown heading, where pandoc
    would read braces as heading attributes, brackets as links and backticks as
    a fence. Every ASCII character that is not a letter, digit or space is
    written as a numeric character reference, which is text in both places.
    """
    text = "".join(ch for ch in " ".join(value.split()) if ord(ch) >= 32)
    return "".join(ch if ch == " " or ch.isalnum() or ord(ch) > 126 else f"&#{ord(ch)};"
                   for ch in text)


def seo_metadata_comment(metadata: dict) -> str:
    """Serialise metadata so no value can end the surrounding HTML comment."""
    encoded = json.dumps(metadata).replace("<", "\\u003c").replace(">", "\\u003e")
    return f"<!--SEO_METADATA:{encoded}-->"


def process_jupyter_notebook(file_path: Path) -> str:
    """
    Generates an HTML snippet to embed a Jupyter notebook with preview, download, and external viewing options.
    
    Reads the notebook file, extracts the title, description, and up to three key features from the first markdown cell (if present), and sanitizes metadata for safe HTML embedding. The output includes a preview iframe (using nbviewer), download and external links (nbviewer, Colab), and fallback messaging if the preview cannot be loaded. SEO metadata is embedded in an HTML comment for later extraction.
    
    Args:
        file_path: Path to the Jupyter notebook file.
    
    Returns:
        A Markdown-formatted string containing the HTML embed for the notebook, including metadata and interactive elements.
    """
    notebook_filename = file_path.name
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            notebook_content = f.read()
        
        rel_path = file_path.relative_to(REPO_ROOT).parent
        notebook_path = notebook_filename if rel_path.as_posix() == '.' else f"{rel_path}/{notebook_filename}"
            
        notebook_title = notebook_filename
        notebook_description = ""
        notebook_features = []
        
        try:
            notebook_data = json.loads(notebook_content)
            for cell in notebook_data.get('cells', []):
                if cell.get('cell_type') == 'markdown':
                    source = ''.join(cell.get('source', []))
                    title_match = re.search(r'^#\s+(.+)$', source, re.MULTILINE)
                    if title_match:
                        notebook_title = title_match.group(1).strip()
                        desc_match = re.search(r'^#\s+.+\n\n(.+?)(?=\n\n|\Z)', source, re.DOTALL | re.MULTILINE)
                        if desc_match:
                            notebook_description = desc_match.group(1).strip()
                            features_match = re.findall(r'^\s*[\*\-\+]\s+(.+)$', source, re.MULTILINE)
                            if features_match:
                                notebook_features = [f.strip() for f in features_match[:3]]
                        break
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
            
        if not notebook_description:
            notebook_description = f"This notebook provides visualization and analysis related to {notebook_filename.split('.')[0].replace('-', ' ').replace('_', ' ')}."
            
        if not notebook_features:
            notebook_features = [
                "Visualization of data and results",
                "Analysis of simulation outputs",
                "Interactive exploration of parameters"
            ]
        
        # Clean all strings to prevent HTML injection and attribute issues
        # This is critical to prevent meta tag corruption
        
        # Step 1: Remove all HTML tags from the description
        notebook_description = re.sub(r'<[^>]*>', '', notebook_description)
        
        # Step 2: Remove any potential content that might break attributes
        notebook_description = re.sub(r'["\'>]', '', notebook_description)
        
        # Step 3: Create a highly sanitized version for use in meta tags
        meta_safe_description = re.sub(r'[^\w\s.,;:!?()-]', '', notebook_description)
        meta_safe_description = meta_safe_description.strip()
        if len(meta_safe_description) > 160:
            meta_safe_description = meta_safe_description[:157] + "..."
        
        # Properly escape all content for HTML use
        safe_filename_link = quote(notebook_filename, safe="")
        notebook_path = quote(str(notebook_path), safe="/")
        notebook_id = re.sub(r'[^A-Za-z0-9_-]', '-', notebook_filename)
        safe_notebook_title = inert_notebook_text(notebook_title)
        safe_notebook_description = inert_notebook_text(notebook_description)
        safe_notebook_features = [inert_notebook_text(f) for f in notebook_features]
        features_html = "\n".join([f'<li>{feature}</li>' for feature in safe_notebook_features])
        
        # Store meta description for later use in SEO metadata
        seo_metadata = {
            "title": notebook_title,
            "description": meta_safe_description,
            "meta_tags": f'<meta name="description" content="{meta_safe_description}">\n'
        }
        
        embed_html = f"""# {safe_notebook_title}

```{{=html}}
<div class="jupyter-notebook-embed">
    <h2>Jupyter Notebook: {safe_notebook_title}</h2>
    
    <div class="notebook-action-buttons">
        <a href="{safe_filename_link}" download class="notebook-btn download-btn">
            <i class="fa-solid fa-download"></i> Download Notebook
        </a>
        <a href="https://nbviewer.org/github/comphy-lab/{REPO_NAME}/blob/main/{notebook_path}" 
           target="_blank" class="notebook-btn view-btn">
            <i class="fa-solid fa-eye"></i> View in nbviewer
        </a>
        <a href="https://colab.research.google.com/github/comphy-lab/{REPO_NAME}/blob/main/{notebook_path}" 
           target="_blank" class="notebook-btn colab-btn">
            <i class="fa-solid fa-play"></i> Open in Colab
        </a>
    </div>
    
    <div class="notebook-preview">
        <h3>About this notebook</h3>
        <p>{safe_notebook_description}</p>
        
        <h3>Key Features:</h3>
        <ul>
            {features_html}
        </ul>
    </div>
    
    <div class="notebook-tip">
        <p><strong>Tip:</strong> For the best interactive experience, download the notebook or open it in Google Colab.</p>
    </div>

    <!-- Embedded Jupyter Notebook -->
    <div class="embedded-notebook">
        <h3>Notebook Preview</h3>
        <div id="notebook-container-{notebook_id}" >
            <iframe id="notebook-iframe-{notebook_id}" 
                    src="https://nbviewer.org/github/comphy-lab/{REPO_NAME}/blob/main/{notebook_path}" 
                    width="100%" height="800px" frameborder="0"
                    onload="checkIframeLoaded('{notebook_id}')"
                    onerror="handleIframeError('{notebook_id}')"></iframe>
            <div id="notebook-error-{notebook_id}" 
                 class="notebook-error-message" style="display: none;">
                <div class="error-container">
                    <i class="fa-solid fa-exclamation-triangle"></i>
                    <h4>Notebook Preview Unavailable</h4>
                    <p>The notebook preview could not be loaded. This may be because:</p>
                    <ul>
                        <li>The notebook file is not yet available in the repository</li>
                        <li>The nbviewer service is temporarily unavailable</li>
                        <li>The repository is private or has access restrictions</li>
                    </ul>
                    <p>You can still download the notebook using the button above or view it directly through one of the external services.</p>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
    function checkIframeLoaded(id) {{
        try {{
            const iframe = document.getElementById('notebook-iframe-' + id);
            const iframeContent = iframe.contentWindow || iframe.contentDocument;
            try {{
                if (iframeContent.document.title.includes('404') || 
                    iframeContent.document.body.textContent.includes('404 Not Found')) {{
                    handleIframeError(id);
                }}
            }} catch (e) {{}}
        }} catch (e) {{
            handleIframeError(id);
        }}
    }}
    
    function handleIframeError(id) {{
        const iframe = document.getElementById('notebook-iframe-' + id);
        const errorDiv = document.getElementById('notebook-error-' + id);
        
        if (iframe && errorDiv) {{
            iframe.style.display = 'none';
            errorDiv.style.display = 'block';
        }}
    }}
    
    document.addEventListener('DOMContentLoaded', function() {{
        const iframes = document.querySelectorAll('iframe[id^="notebook-iframe-"]');
        iframes.forEach(iframe => {{
            iframe.addEventListener('load', function() {{
                const id = iframe.id.replace('notebook-iframe-', '');
                setTimeout(function() {{ checkIframeLoaded(id); }}, 1000);
            }});
        }});
    }});
</script>
```
"""
        # Add metadata to the embed_html for extraction later
        embed_html = seo_metadata_comment(seo_metadata) + "\n" + embed_html
        return embed_html
    except Exception as e:
        return "# Notebook\n\nError processing notebook."

def process_python_file(file_path: Path) -> str:
    """
    Converts a Python source file into Markdown by extracting docstrings as prose and wrapping code sections in fenced code blocks.
    
    Args:
        file_path: Path to the Python source file.
    
    Returns:
        A Markdown-formatted string with docstrings as paragraphs and code as Python code blocks.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        file_content = f.read()
    
    lines = file_content.split('\n')
    processed_lines = []
    in_code_block = False
    code_block = []
    in_docstring = False
    docstring_lines = []
    
    for line in lines:
        if line.strip().startswith('"""') or line.strip().startswith("'''"):
            if in_docstring:
                in_docstring = False
                clean_docstring = []
                for doc_line in docstring_lines:
                    if doc_line.strip() in ('"""', "'''"):
                        continue
                    doc_line = doc_line.strip()
                    if doc_line.startswith('"""') or doc_line.startswith("'''"):
                        doc_line = doc_line[3:]
                    if doc_line.endswith('"""') or doc_line.endswith("'''"):
                        doc_line = doc_line[:-3]
                    clean_docstring.append(doc_line.strip())
                
                if clean_docstring:
                    processed_lines.append("")
                    processed_lines.extend(clean_docstring)
                    processed_lines.append("")
                docstring_lines = []
            else:
                in_docstring = True
                if in_code_block:
                    processed_lines.append("```python")
                    processed_lines.extend(code_block)
                    processed_lines.append("```")
                    code_block = []
                    in_code_block = False
            continue
        
        if in_docstring:
            docstring_lines.append(line)
            continue
        
        if not in_code_block and line.strip():
            in_code_block = True
            code_block.append(line)
        elif in_code_block:
            code_block.append(line)
        else:
            processed_lines.append(line)
    
    if in_code_block:
        processed_lines.append("```python")
        processed_lines.extend(code_block)
        processed_lines.append("```")
    
    if in_docstring:
        processed_lines.append("")
        processed_lines.extend(docstring_lines)
        processed_lines.append("")
    
    return '\n'.join(processed_lines)

def process_c_file(file_path: Path, literate_c_script: Path) -> str:
    """
    Converts a C or C++ source file to Markdown using a literate-C preprocessor.
    
    Attempts to process the file with the specified literate-C script. If preprocessing fails,
    returns the file content wrapped in a Markdown C code block.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        file_content = f.read()
    
    markdown_content = f"""# {file_path.name}\n\n```c\n{file_content}\n```"""
    
    literate_c_cmd = [str(literate_c_script), str(file_path), '0']
    
    try:
        preproc_proc = subprocess.Popen(
            literate_c_cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True, 
            encoding='utf-8'
        )
        content, stderr = preproc_proc.communicate()

        if preproc_proc.returncode == 0 and content.strip():
            return content.replace('~~~literatec', '~~~c')
        else:
            debug_print(f"  [Debug] Using simple markdown for {file_path} due to literate-c error: {stderr}")
            return markdown_content
            
    except Exception as e:
        debug_print(f"  [Debug] Using simple markdown for {file_path} due to error: {e}")
        return markdown_content

def prepare_pandoc_input(file_path: Path, literate_c_script: Path) -> str:
    """
    Prepares the content of a source file for Pandoc conversion based on its type.
    
    Selects the appropriate processing function for the given file, converting it to Markdown or HTML as needed for Pandoc input. Supports Markdown, Python, shell scripts, Jupyter notebooks, Makefiles, and C/C++ files.
    """
    file_suffix = file_path.suffix.lower()
    file_name = file_path.name
    
    if file_suffix == '.md':
        return process_markdown_file(file_path)
    elif file_suffix == '.py':
        return process_python_file(file_path)
    elif file_suffix == '.sh':
        return process_shell_file(file_path)
    elif file_suffix == '.ipynb':
        return process_jupyter_notebook(file_path)
    elif file_name == 'Makefile':
        return process_shell_file(file_path)
    else:  # C/C++ files
        return process_c_file(file_path, literate_c_script)

def run_pandoc(pandoc_input: str, output_html_path: Path, template_path: Path, 
               base_url: str, wiki_title: str, page_url: str, page_title: str,
               asset_path_prefix: str, seo_metadata: Dict[str, str] = None,
               source_path: str = None) -> str:
    """
               Converts Markdown input to standalone HTML using Pandoc.
               
               Runs Pandoc with a custom template and variables for SEO metadata, repository info, and asset paths to generate an HTML file from Markdown input. Handles SEO metadata and fixes malformed meta description tags. Returns Pandoc's standard output as a string.
               
               Note: HTML cleaning (removal of empty anchor tags) is now handled by the separate clean_html.py script.
               
               Args:
                   pandoc_input: Markdown content to convert.
                   output_html_path: Path to write the generated HTML file.
                   template_path: Path to the Pandoc HTML template.
                   base_url: Base URL for the documentation site.
                   wiki_title: Title of the wiki or documentation set.
                   page_url: URL of the current page.
                   page_title: Title of the current page.
                   asset_path_prefix: Relative path prefix for assets.
                   seo_metadata: Optional dictionary with SEO metadata (description, keywords, image).
                   source_path: Optional source file path for reference.
               
               Returns:
                   The standard output from the Pandoc process as a string, or an empty string if Pandoc fails.
               """
    if seo_metadata is None:
        seo_metadata = {}
    
    # Determine if this is for a shell script file
    is_shell_script = output_html_path.name.endswith('.sh.html') or output_html_path.name == 'Makefile.html'
    
    pandoc_cmd = [
        'pandoc',
        '-f', 'markdown+smart+raw_html+tex_math_dollars',
        '-t', 'html5',
        '--standalone',
        '--mathjax',
        '--template', str(template_path),
        '-V', f'base={base_url}',
        '-V', f'wikititle={wiki_title}',
        '-V', f'pageUrl={page_url}',
        '-V', f'pagetitle={page_title}',
        '-V', f'reponame={REPO_NAME}',
        '-V', f'description={seo_metadata.get("description", "")}',
        '-V', f'keywords={seo_metadata.get("keywords", "")}',
        '-V', f'image={seo_metadata.get("image", "")}',
        '-V', f'asset_path_prefix={asset_path_prefix}',
        '-V', f'repo_name={REPO_NAME}',
        '-V', f'source_path={source_path if source_path else ""}',
    ]
    
    # For shell scripts and Jupyter notebooks, explicitly set mathjax to null to avoid template variable conflicts
    is_jupyter_html = output_html_path.name.endswith('.ipynb.html')
    if is_shell_script or is_jupyter_html:
        pandoc_cmd.extend(['-V', 'mathjax=null'])
        
    pandoc_cmd.extend(['-o', str(output_html_path)])
    
    debug_print(f"  [Debug Pandoc] Command: {' '.join(pandoc_cmd)}")
    debug_print(f"  [Debug Pandoc] Input content length: {len(pandoc_input)} chars")
    
    process = subprocess.run(pandoc_cmd, input=pandoc_input, text=True, capture_output=True)
    
    debug_print(f"  [Debug Pandoc] Return Code: {process.returncode}")
    if process.stdout: debug_print(f"  [Debug Pandoc] STDOUT:\n{process.stdout}")
    if process.stderr: debug_print(f"  [Debug Pandoc] STDERR:\n{process.stderr}")
    
    if process.returncode != 0:
        print(f"Error running pandoc: {process.stderr}")
        return ""
    
    try:
        with open(output_html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Fix any malformed meta description tags, especially for Jupyter notebooks
        desc_meta_pattern = r'<meta\s+name="description"\s+content="([^"]*(?:target|href|class|style|onclick)[^"]*)"[^>]*>'
        if re.search(desc_meta_pattern, content):
            print(f"  Fixing malformed meta description tag in {output_html_path.name}")
            # Remove the problematic description meta tags
            content = re.sub(desc_meta_pattern, '', content)
            
            # Add a clean description meta tag in the head section if we have a description
            if seo_metadata and "description" in seo_metadata and seo_metadata["description"]:
                # Extra sanitization to be absolutely safe
                clean_desc = re.sub(r'<[^>]*>', '', seo_metadata.get("description", ""))
                clean_desc = re.sub(r'["\'<>\\\]', '', clean_desc)
                clean_desc = html.escape(clean_desc)
                
                head_pos = content.find('</head>')
                if head_pos > 0:
                    meta_tag = f'  <meta name="description" content="{clean_desc}">\n  '
                    content = content[:head_pos] + meta_tag + content[head_pos:]
        
        # Check if file has proper HTML structure
        if '<!DOCTYPE' not in content or '<html' not in content:
            print(f"Warning: Generated HTML for {output_html_path} is missing DOCTYPE or html tag")
            fixed_content = f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <title>{wiki_title} - {page_title}</title>
    <meta name="description" content="{seo_metadata.get('description', '')}" />
    <meta name="keywords" content="{seo_metadata.get('keywords', '')}" />
</head>
<body>
{content}
</body>
</html>"""
            content = fixed_content
            
        with open(output_html_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
    except Exception as e:
        print(f"Error verifying HTML structure: {e}")
    
    return process.stdout

def post_process_python_shell_html(html_content: str) -> str:
    """
    Enhances HTML generated from Python or shell files for improved display and navigation.
    
    Wraps code blocks in container divs for styling, updates documentation links to use `.html` extensions, removes dynamic path resolution scripts, and injects a JavaScript variable with the repository name into the HTML body.
    
    Note: HTML cleaning (removal of empty anchor tags) is now handled by the separate clean_html.py script.
    
    Args:
        html_content: The HTML content to be post-processed.
    
    Returns:
        The processed HTML content with enhanced formatting and navigation.
    """
    # Wrap code blocks with container divs
    def wrap_pre_code(match):
        """
        Wraps a matched <pre><code> HTML block in a container div for styling.
        
        Args:
            match: A regex match object containing a <pre><code> HTML block.
        
        Returns:
            The HTML block wrapped in a div with class "code-block-container".
        """
        return f'<div class="code-block-container">{match.group(0)}</div>'
    
    processed_html = re.sub(
        r'<pre[^>]*><code[^>]*>.*?</code></pre>', 
        wrap_pre_code, 
        html_content, 
        flags=re.DOTALL | re.IGNORECASE
    )
    
    def wrap_source_code(match):
        """
        Wraps matched source code in a div container for styling.
        
        Args:
            match: A regex match object containing the code block as group 1.
        
        Returns:
            The code block wrapped in a div with class "code-block-container".
        """
        return f'<div class="code-block-container">{match.group(1)}</div>'
    
    processed_html = re.sub(
        r'<div class="sourceCode" id="cb\d+"[^>]*>(.*?)</div>', 
        wrap_source_code, 
        processed_html, 
        flags=re.DOTALL | re.IGNORECASE
    )
    
    # Fix links to docs by adding .html extension
    def fix_doc_links(match):
        """
        Appends '.html' to local documentation links in HTML anchor tags if missing.
        
        This function is intended for use as a replacement callback in regular expression operations. It modifies anchor tags so that links to source files (with extensions .c, .h, .py, .sh, .md) are updated to point to their corresponding HTML documentation, unless the link is already external, an anchor, or already ends with '.html'.
        """
        link_tag = match.group(0)
        href_match = re.search(r'href="([^"]+)"', link_tag)
        
        if href_match:
            href = href_match.group(1)
            if (href.startswith('http') or href.startswith('https') or 
                href.startswith('#') or href.endswith('.html')):
                return link_tag
                
            if re.search(r'\.(c|h|py|sh|md)$', href):
                return re.sub(r'href="([^"]+)"', f'href="{href}.html"', link_tag)
        
        return link_tag
    
    processed_html = re.sub(
        r'<a[^>]+href="[^"]+">[^<]+</a>',
        fix_doc_links,
        processed_html
    )
    
    # Remove dynamic path related scripts
    processed_html = re.sub(r'<script[^>]*>\s*// Dynamic base path resolution.*?</script>', '', processed_html, flags=re.DOTALL)
    processed_html = re.sub(r'<script[^>]*>\s*// Helper function to create dynamic asset paths.*?</script>', '', processed_html, flags=re.DOTALL)
    processed_html = re.sub(r'<script[^>]*>\s*window\.basePath\s*=.*?</script>', '', processed_html, flags=re.DOTALL)
    processed_html = re.sub(r'<script[^>]*>\s*function\s+assetPath.*?</script>', '', processed_html, flags=re.DOTALL)

    # Add repoName variable
    repo_script = f'\n<script>window.repoName = "{REPO_NAME}";</script>\n'
    processed_html = re.sub(r'<body[^>]*>', lambda m: m.group(0) + repo_script, processed_html)

    return processed_html

def run_awk_post_processing(html_content: str, file_path: Path, 
                           repo_root: Path, darcsit_dir: Path) -> str:
    """
                           Runs an AWK script to add declaration anchors to HTML content generated from C files.
                           
                           Args:
                               html_content: The HTML content to process.
                               file_path: Path to the original C source file.
                               repo_root: Path to the repository root for relative path resolution.
                               darcsit_dir: Path to the directory containing the AWK script.
                           
                           Returns:
                               The post-processed HTML content with declaration anchors added.
                           
                           Raises:
                               FileNotFoundError: If the required AWK script is not found.
                               RuntimeError: If the AWK post-processing fails.
                           """
    decl_anchors_script = darcsit_dir / 'decl_anchors.awk'
    if not decl_anchors_script.is_file():
        raise FileNotFoundError(f"decl_anchors.awk script not found at {decl_anchors_script}")
    
    try:
        relative_tags_path = file_path.relative_to(repo_root).with_suffix(file_path.suffix + '.tags')
    except ValueError:
        print(f"Error: {file_path} is not under repository root {repo_root}")
        return html_content
    temp_output_path = Path(f"{file_path}.temp.html")
    
    try:
        with open(temp_output_path, 'w', encoding='utf-8') as f_out:
            postproc_cmd = ['awk', '-v', f'tags={relative_tags_path}', '-f', str(decl_anchors_script)]
            postproc_proc = subprocess.Popen(
                postproc_cmd, 
                stdin=subprocess.PIPE, 
                stdout=f_out, 
                stderr=subprocess.PIPE, 
                text=True, 
                encoding='utf-8'
            )
            _, stderr = postproc_proc.communicate(input=html_content)

            if postproc_proc.returncode != 0:
                raise RuntimeError(f"Awk post-processing failed: {stderr}")
        
        with open(temp_output_path, 'r', encoding='utf-8') as f:
            processed_content = f.read()
        
        return processed_content
    finally:
        if temp_output_path.exists():
            temp_output_path.unlink()

def post_process_c_html(html_content: str, file_path: Path, 
                      repo_root: Path, darcsit_dir: Path, docs_dir: Path) -> str:
    """
                      Post-processes HTML generated from C or C++ source files for enhanced documentation.
                      
                      Removes trailing line numbers, wraps code blocks in container divs for styling, and converts `#include` statements into links to local documentation or the Basilisk source if unavailable locally. Cleans out dynamic path resolution scripts and injects a JavaScript variable with the repository name into the HTML body.
                      
                      Note: HTML cleaning (removal of empty anchor tags) is now handled by the separate clean_html.py script.
                      
                      Args:
                          html_content: The HTML content to process.
                          file_path: Path to the original source file.
                          repo_root: Path to the repository root.
                          darcsit_dir: Path to the Darcsit directory.
                          docs_dir: Path to the documentation output directory.
                      
                      Returns:
                          The post-processed HTML content as a string.
                      """
    # Remove trailing line numbers
    cleaned_html = re.sub(
        r'(\s*(?:<span class="[^"]*">\s*\d+\s*</span>|\s+\d+)\s*)+(\s*</span>)', 
        r'\2', 
        html_content
    )
    
    # Wrap code blocks with container divs
    def wrap_pre_code(match):
        """
        Wraps a matched code block in a container div for styling.
        
        Args:
            match: A regex match object representing a code block.
        
        Returns:
            The HTML string with the code block wrapped in a div.
        """
        return f'<div class="code-block-container">{match.group(0)}</div>'
    
    cleaned_html = re.sub(
        r'<pre[^>]*><code[^>]*>.*?</code></pre>', 
        wrap_pre_code, 
        cleaned_html, 
        flags=re.DOTALL | re.IGNORECASE
    )
    
    def wrap_source_code(match):
        """
        Wraps matched source code in a div container for styling.
        
        Args:
            match: A regex match object containing the code block as group 1.
        
        Returns:
            The code block wrapped in a div with class "code-block-container".
        """
        return f'<div class="code-block-container">{match.group(1)}</div>'
    
    cleaned_html = re.sub(
        r'<div class="sourceCode" id="cb\d+"[^>]*>(.*?)</div>', 
        wrap_source_code, 
        cleaned_html, 
        flags=re.DOTALL | re.IGNORECASE
    )
    
    # Add links to #include statements
    def create_include_link(match):
        """
        Generates an HTML link for a C/C++ #include statement, pointing to local documentation if available or to the Basilisk source otherwise.
        
        Args:
            match: A regex match object capturing the include statement components.
        
        Returns:
            An HTML anchor tag wrapping the original include span, linking to the appropriate documentation or source file.
        """
        prefix = match.group(1)
        span_tag_open = match.group(2)
        filename = match.group(3)
        span_tag_close = match.group(4)
        
        original_span_tag = f'{span_tag_open}\"{filename}\"{span_tag_close}'
        
        check_filename = filename.split('/')[-1]
        local_file_path = repo_root / 'src-local' / check_filename
        
        if local_file_path.is_file():
            target_html_path = (docs_dir / 'src-local' / check_filename).with_suffix(local_file_path.suffix + '.html')
            try:
                relative_link = os.path.relpath(target_html_path, start=file_path.parent)
                link_url = relative_link.replace('\\', '/')
                link_url = link_url.replace('/docs/', '/')
            except ValueError:
                link_url = target_html_path.as_uri()
            link_title = f"Link to local documentation for {filename}"
        else:
            link_url = f"http://basilisk.fr/src/{filename}"
            link_title = f"Link to Basilisk source for {filename}"
        
        return f'{prefix}<a href="{link_url}" title="{link_title}">{original_span_tag}</a>'
    
    include_pattern = r'(<span class="pp">#include\s*</span>)(<span class=\"im\">)(?:\"|&quot;)(.*?)(?:\"|&quot;)(</span>)'
    cleaned_html = re.sub(include_pattern, create_include_link, cleaned_html, flags=re.DOTALL)
    
    # Remove script tags related to dynamic paths
    cleaned_html = re.sub(r'<script[^>]*>\s*// Dynamic base path resolution.*?</script>', '', cleaned_html, flags=re.DOTALL)
    cleaned_html = re.sub(r'<script[^>]*>\s*// Helper function to create dynamic asset paths.*?</script>', '', cleaned_html, flags=re.DOTALL)
    cleaned_html = re.sub(r'<script[^>]*>\s*window\.basePath\s*=.*?</script>', '', cleaned_html, flags=re.DOTALL)
    cleaned_html = re.sub(r'<script[^>]*>\s*function\s+assetPath.*?</script>', '', cleaned_html, flags=re.DOTALL)
    
    # Add repoName variable
    repo_script = f'\n<script>window.repoName = "{REPO_NAME}";</script>\n'
    cleaned_html = re.sub(r'<body[^>]*>', lambda m: m.group(0) + repo_script, cleaned_html)
    
    return cleaned_html

def insert_css_link_in_html(html_file_path: Path, css_path: Path, is_root: bool = True) -> bool:
    """
    Inserts a CSS link tag into the <head> section of an HTML file.
    
    If the <head> tag is missing, creates a minimal HTML structure with the CSS link included. Returns True on success, or False if an error occurs.
    """
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        css_name = str(Path(css_path).name)
        css_link = f'<link href="{css_name}" rel="stylesheet" type="text/css" />' if is_root else \
                  f'<link href="../{css_name}" rel="stylesheet" type="text/css" />'
        
        if f'link href="{css_name}"' in content or f'link href="../{css_name}"' in content:
            return True
        
        head_end_idx = content.find('</head>')
        if head_end_idx == -1:
            head_start_idx = content.find('<head>')
            if head_start_idx != -1:
                modified_content = content[:head_start_idx + 6] + '\n    ' + css_link + content[head_start_idx + 6:]
            else:
                debug_print(f"Warning: No head tag found in {html_file_path}, creating complete HTML structure")
                modified_content = f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    {css_link}
</head>
<body>
{content}
</body>
</html>"""
        else:
            modified_content = content[:head_end_idx] + '    ' + css_link + '\n    ' + content[head_end_idx:]
        
        with open(html_file_path, 'w', encoding='utf-8') as f:
            f.write(modified_content)
        
        return True
    except Exception as e:
        print(f"Error inserting CSS link in {html_file_path}: {e}")
        return False

def insert_javascript_in_html(html_file_path: Path) -> bool:
    """
    Inserts inline JavaScript into an HTML file to add copy-to-clipboard buttons on code blocks.
    
    Adds a "Copy" button to each code block container, enabling users to copy code snippets to the clipboard. If the HTML file lacks a <body> tag, a minimal HTML structure is created. Returns True if the script is inserted or already present, False on error.
    """
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # JS for copy functionality
        copy_js = '''
<script type="text/javascript">
document.addEventListener('DOMContentLoaded', function() {
    // Add copy button to each code block container
    const codeBlocks = document.querySelectorAll('.code-block-container pre');
    codeBlocks.forEach(function(codeBlock, index) {
        // Create button element
        const button = document.createElement('button');
        button.className = 'copy-button';
        button.textContent = 'Copy';
        button.setAttribute('aria-label', 'Copy code to clipboard');
        button.setAttribute('data-copy-state', 'copy');
        
        // Get the code block container (parent of the pre)
        const container = codeBlock.parentNode;
        
        // Add the button to the container
        container.appendChild(button);
        
        // Set up click event
        button.addEventListener('click', async function() {
            const codeText = codeBlock.textContent;
            
            try {
                // Try to use the modern clipboard API first
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    await navigator.clipboard.writeText(codeText);
                    updateButtonState(button, 'success');
                } else {
                    // Fall back to the deprecated execCommand method
                    const textarea = document.createElement('textarea');
                    textarea.value = codeText;
                    textarea.style.position = 'fixed';  // Prevent scrolling to the bottom
                    document.body.appendChild(textarea);
                    textarea.select();
                    
                    const successful = document.execCommand('copy');
                    document.body.removeChild(textarea);
                    
                    if (successful) {
                        updateButtonState(button, 'success');
                    } else {
                        updateButtonState(button, 'error');
                    }
                }
            } catch (err) {
                console.error('Copy failed:', err);
                updateButtonState(button, 'error');
            }
        });
    });
    
    // Function to update button state
    function updateButtonState(button, state) {
        if (state === 'success') {
            button.textContent = 'Copied!';
            button.classList.add('copied');
        } else if (state === 'error') {
            button.textContent = 'Error!';
            button.classList.add('error');
        }
        
        // Reset button state after 2 seconds
        setTimeout(function() {
            button.textContent = 'Copy';
            button.classList.remove('copied', 'error');
        }, 2000);
    }
});
</script>
        '''
        
        if 'class="copy-button"' in content:
            return True
        
        body_end_idx = content.find('</body>')
        if body_end_idx == -1:
            body_start_idx = content.find('<body>')
            if body_start_idx != -1:
                modified_content = content + copy_js
            else:
                debug_print(f"Warning: No body tag found in {html_file_path}, creating complete HTML structure")
                modified_content = f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
</head>
<body>
{content}
{copy_js}
</body>
</html>"""
        else:
            modified_content = content[:body_end_idx] + copy_js + content[body_end_idx:]
        
        with open(html_file_path, 'w', encoding='utf-8') as f:
            f.write(modified_content)
        
        return True
    except Exception as e:
        print(f"Error inserting JavaScript in {html_file_path}: {e}")
        return False

def process_file_with_page2html_logic(file_path: Path, output_html_path: Path, repo_root: Path, 
                                     basilisk_dir: Path, darcsit_dir: Path, template_path: Path, 
                                     base_url: str, wiki_title: str, literate_c_script: Path, docs_dir: Path) -> bool:
    """
                                     Converts a source file to an HTML documentation page with type-specific post-processing.
                                     
                                     Handles copying Jupyter notebooks, prepares input for Pandoc conversion, extracts SEO metadata, and applies appropriate post-processing for Python, shell, Markdown, Jupyter, or C/C++ files. Inserts JavaScript for code block copy functionality. Returns True on success, False on error.
                                     """
    
    # Function to ensure script tags are properly sanitized during the conversion process
    def sanitize_pandoc_input(input_content: str) -> str:
        """
        Pre-processes Pandoc input to prevent script-related issues in the output HTML.
        Removes any malformed HTML constructs that could cause problems after conversion.
        """
        # Convert self-closing a tags to proper a tags to avoid malformed HTML after conversion
        input_content = re.sub(r'<a([^>]*)/>',
                              r'<a\1></a>',
                              input_content)
        
        # Escape or convert script blocks in code examples to avoid JavaScript syntax errors  
        def escape_script_blocks(match):
            html_content = match.group(1)
            # Replace any potential anchor tags in script examples with harmless placeholders
            html_content = re.sub(r'<a\s+[^>]*>\s*</a>',
                                '/* anchor tag removed */',
                                html_content)
            return f"{html_content}"
            
        input_content = re.sub(r'```html(.*?)```',
                              escape_script_blocks,
                              input_content,
                              flags=re.DOTALL)
                              
        return input_content
    
    print(f"  Processing {file_path.relative_to(repo_root)} -> {output_html_path.relative_to(repo_root / 'docs')}")

    try:
        # Handle Jupyter notebook special case
        is_jupyter_notebook = file_path.suffix.lower() == '.ipynb'
        if is_jupyter_notebook:
            notebook_dest = output_html_path.parent / file_path.name
            try:
                shutil.copy2(file_path, notebook_dest)
                print(f"  Copied notebook {file_path.name} to {notebook_dest.relative_to(repo_root / 'docs')}")
            except Exception as e:
                print(f"  Warning: Failed to copy notebook file: {e}")
        
        # Prepare pandoc input
        pandoc_input_content = prepare_pandoc_input(file_path, literate_c_script)
        
        # Apply additional pre-processing to sanitize input
        pandoc_input_content = sanitize_pandoc_input(pandoc_input_content)
        
        # Calculate relative URL path
        page_url = (base_url + output_html_path.relative_to(repo_root / 'docs').as_posix()).replace('//', '/')
        
        # Clean up page title
        page_title = file_path.relative_to(repo_root).as_posix().strip('- \t')
        
        # Debug info
        print(f"Processing file: {file_path.name} with REPO_NAME={REPO_NAME}")
        
        # Get SEO metadata
        seo_metadata = extract_seo_metadata(file_path, pandoc_input_content)
        
        # Calculate asset path prefix
        asset_path_prefix = calculate_asset_prefix(output_html_path, docs_dir)
        
        # Get source path relative to repo root
        source_path = file_path.relative_to(repo_root).as_posix()
        
        # Run pandoc for conversion
        pandoc_stdout = run_pandoc(
            pandoc_input_content, 
            output_html_path, 
            template_path, 
            base_url, 
            wiki_title, 
            page_url, 
            page_title,
            asset_path_prefix,
            seo_metadata,
            source_path
        )
        
        # Determine file type for post-processing
        is_python_file = file_path.suffix.lower() == '.py'
        is_shell_file = file_path.suffix.lower() == '.sh'
        is_markdown_file = file_path.suffix.lower() == '.md'
        
        # Apply appropriate post-processing
        if is_python_file or is_shell_file or is_markdown_file or is_jupyter_notebook:
            with open(output_html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            processed_html = post_process_python_shell_html(html_content)
            
            with open(output_html_path, 'w', encoding='utf-8') as f:
                f.write(processed_html)
        else:
            # For C/C++ files
            with open(output_html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Use awk for post-processing
            processed_html = run_awk_post_processing(html_content, file_path, repo_root, darcsit_dir)
            
            # Further post-process
            cleaned_html = post_process_c_html(processed_html, file_path, repo_root, darcsit_dir, docs_dir)
            
            with open(output_html_path, 'w', encoding='utf-8') as f:
                f.write(cleaned_html)
        
        # Insert JavaScript for code blocks
        insert_javascript_in_html(output_html_path)
        
        return True
    
    except Exception as e:
        print(f"  Error processing {file_path}: {e}")
        return False

def convert_directory_tree_to_html(readme_content: str) -> str:
    """
    Converts a plain text directory tree block in README content into an HTML-formatted site map.
    
    The function searches for a code block representing a directory tree (using ASCII tree characters) in the README content, parses its structure, and replaces it with an HTML div containing a formatted list of directories and files. Directory and file names are converted into Markdown links pointing to their respective documentation pages, and descriptions are preserved if present.
    
    Args:
        readme_content: The content of the README file as a string.
    
    Returns:
        The modified README content with the directory tree replaced by an HTML site map.
    """
    tree_pattern = r'```\s*\n(├.*?\n.*?└.*?)\n```'
    tree_match = re.search(tree_pattern, readme_content, re.DOTALL)
    
    if not tree_match:
        return readme_content
        
    tree_text = tree_match.group(1)
    
    html_structure = ['<div class="repository-structure">']
    
    path_stack = []
    prev_indent = -1
    
    for line in tree_text.split('\n'):
        if not line.strip():
            continue
            
        indent_level = 0
        
        if '│   ' in line:
            indent_level = line.count('│   ')
        elif '    ' in line and ('├── ' in line or '└── ' in line):
            spaces_before_item = len(line) - len(line.lstrip(' '))
            indent_level = spaces_before_item // 4
        
        clean_line = line.replace('├── ', '').replace('└── ', '').replace('│   ', '')
        
        parts = clean_line.strip().split(None, 1)
        path = parts[0]
        description = parts[1] if len(parts) > 1 else ''
        
        is_dir = path.endswith('/')
        
        if indent_level > prev_indent:
            if path_stack and prev_indent >= 0:
                path_stack.append(path_stack[-1])
        elif indent_level < prev_indent:
            for _ in range(prev_indent - indent_level):
                if path_stack:
                    path_stack.pop()
        
        indent = '  ' * indent_level
        
        item_html = f"{indent}* "
        
        if is_dir:
            dir_name = path.rstrip('/')
            if dir_name == "basilisk/src":
                item_html += f"**{path}** - {description}"
            else:
                item_html += f"**[{path}]({dir_name})** - {description}"
            
            if len(path_stack) <= indent_level:
                path_stack.append(dir_name)
            else:
                path_stack[indent_level] = dir_name
        else:
            parent_path = path_stack[indent_level-1] if indent_level > 0 and path_stack else ""
            
            file_path = f"{parent_path}/{path}" if parent_path else path
            file_path = file_path.lstrip('/')
            
            item_html += f"**[{path}]({file_path}.html)** - {description}"
        
        html_structure.append(item_html)
        prev_indent = indent_level
    
    html_structure.append('</div>')
    
    html_tree = '\n'.join(html_structure)
    modified_content = readme_content.replace(tree_match.group(0), html_tree)
    
    return modified_content

def generate_directory_index(directory_name: str, directory_path: Path, generated_files: Dict[Path, Path], docs_dir: Path, repo_root: Path) -> bool:
    """
    Generates an index.html page for a directory, listing all generated documentation files.
    
    Creates a directory index page that displays links to all HTML documentation files within the specified directory, including file descriptions extracted from meta tags. The output uses a template, formats the directory name for display, and includes file-type icons and descriptions. Returns True on success, or False if an error occurs.
    """
    try:
        index_path = directory_path / "index.html"
        
        # Filter files in this directory
        directory_files = {}
        for original_path, html_path in generated_files.items():
            if html_path.parent == directory_path and html_path.name != "index.html":
                relative_original_path = original_path.relative_to(repo_root)
                relative_html_path = html_path.relative_to(directory_path)
                directory_files[html_path] = {
                    "html_path": relative_html_path,
                    "original_path": relative_original_path,
                    "name": relative_original_path.name,
                    "description": "",
                }
                
        # Extract descriptions
        for html_path, info in directory_files.items():
            try:
                html_content = html_path.read_text(encoding='utf-8')
                desc_match = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html_content)
                if desc_match:
                    description = desc_match.group(1).strip()
                    if len(description) > 120:
                        description = description[:117] + "..."
                    info["description"] = description
            except Exception as e:
                print(f"Error extracting description from {html_path}: {e}")
        
        # Read template
        template_path = TEMPLATE_PATH
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
        except Exception as e:
            print(f"Error reading template: {e}")
            return False
            
        # Format directory name for title
        formatted_dir_name = directory_name.capitalize()
        if formatted_dir_name == 'Src-local':
            formatted_dir_name = "Local Source Files"
        elif formatted_dir_name == 'Simulationcases':
            formatted_dir_name = "Simulation Cases"  
        elif formatted_dir_name == 'Postprocess':
            formatted_dir_name = "Post-Processing Tools"
            
        # Create TOC content
        toc_html = f"<h1>{formatted_dir_name}</h1>\n\n"
        
        if directory_files:
            toc_html += '<div class="documentation-section">\n'
            toc_html += '<table class="documentation-files">\n'
            
            # Sort files by name
            sorted_files = sorted(directory_files.values(), key=lambda x: x['original_path'].name.lower())
            
            for info in sorted_files:
                file_extension = info["original_path"].suffix.lower()
                file_type_class = "file-other"
                
                if file_extension in [".c", ".h"]:
                    file_type_class = "file-c"
                elif file_extension in [".py"]:
                    file_type_class = "file-python"
                elif file_extension in [".ipynb"]:
                    file_type_class = "file-jupyter"
                    
                file_name = info["name"]
                
                toc_html += f'<tr>\n'
                toc_html += f'  <td class="file-icon"><span class="{file_type_class}"></span></td>\n'
                toc_html += f'  <td class="file-link" style="padding-right: 2em;"><a href="{info["html_path"]}" class="doc-link-button">{file_name}</a></td>\n'
                toc_html += f'  <td class="file-desc">{info["description"]}</td>\n'
                toc_html += f'</tr>\n'
                
            toc_html += '</table>\n'
            toc_html += '</div>\n'
        else:
            toc_html += '<p>No documentation files found in this directory.</p>\n'
            
        # Replace template variables
        page_title = f"{formatted_dir_name} | Documentation"
        html_content = template_content
        html_content = html_content.replace("$if(pagetitle)$$pagetitle$$endif$$if(wikititle)$ | $wikititle$$endif$", page_title)
        html_content = html_content.replace(
            "$if(description)$$description$$else$Computational fluid dynamics simulations using Basilisk C framework.$endif$", 
            "Documentation for the CoMPhy-Lab computational fluid dynamics framework."
        )
        html_content = html_content.replace(
            "$if(keywords)$$keywords$$else$fluid dynamics, CFD, Basilisk, multiphase flow, computational physics$endif$", 
            f"fluid dynamics, CFD, Basilisk, {directory_name}, documentation"
        )
        html_content = html_content.replace("$if(reponame)$$reponame$$else$Documentation$endif$", REPO_NAME)
        
        # Replace asset prefix based on depth
        asset_path_prefix = calculate_asset_prefix(index_path, docs_dir)
        html_content = html_content.replace("$asset_path_prefix$", asset_path_prefix)
        
        # Handle conditional blocks
        if "$if(tabs)$" in html_content:
            html_content = re.sub(r'\$if\(tabs\)\$(.*?)\$tabs\$(.*?)\$endif\$', '', html_content, flags=re.DOTALL)
        
        # Replace main content
        content_replacement = toc_html
        html_content = re.sub(
            r'<div class="page-content">\s*.*?\$body\$.*?</div>', 
            f'<div class="page-content">\n{content_replacement}\n</div>', 
            html_content, flags=re.DOTALL
        )
        
        # Remove remaining template variables
        html_content = re.sub(r'\$[a-zA-Z0-9_]+\$', '', html_content)
        html_content = re.sub(r'\$if\([^)]+\)\$.*?\$endif\$', '', html_content, flags=re.DOTALL)
        
        # Clean up any dynamic path scripts
        html_content = re.sub(r'<script[^>]*>\s*// Dynamic base path resolution.*?</script>', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<script[^>]*>\s*// Helper function to create dynamic asset paths.*?</script>', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<script[^>]*>\s*window\.basePath\s*=.*?</script>', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<script[^>]*>\s*function\s+assetPath.*?</script>', '', html_content, flags=re.DOTALL)

        # Write the HTML file
        index_path.write_text(html_content, encoding='utf-8')
        print(f"Generated index page for directory: {directory_name}")
        return True
        
    except Exception as e:
        print(f"Error generating directory index for {directory_name}: {e}")
        import traceback
        traceback.print_exc()
        return False

def get_title_from_filename(filename: str) -> str:
    """
    Converts a filename into a human-readable title.
    
    Removes the file extension, replaces dashes and underscores with spaces, and capitalizes each word.
    """
    name = filename.split('.')[0]
    name = name.replace('-', ' ').replace('_', ' ')
    return ' '.join(word.capitalize() for word in name.split())

def generate_index(readme_path: Path, index_path: Path, generated_files: Dict[Path, Path], 
                  docs_dir: Path, repo_root: Path) -> bool:
    """
                  Generates the main index.html page from README.md, appending grouped documentation links.
                  
                  Reads the README.md file, converts any directory tree blocks to HTML, and appends a section listing links to all generated documentation files, grouped by top-level directory. Converts the combined content to HTML using Pandoc with the project template, post-processes code blocks, and injects JavaScript for enhanced code block interaction.
                  
                  Args:
                      readme_path: Path to the README.md file.
                      index_path: Output path for the generated index.html.
                      generated_files: Mapping of source file paths to their corresponding generated HTML paths.
                      docs_dir: Path to the documentation output directory.
                      repo_root: Path to the repository root.
                  
                  Returns:
                      True if index.html was generated successfully, False otherwise.
                  """
    if not readme_path.exists():
        print(f"Warning: README.md not found at {readme_path}")
        readme_content = "# Project Documentation\n"
    else:
        readme_content = readme_path.read_text(encoding='utf-8')
        
    # Convert directory tree to HTML
    readme_content = convert_directory_tree_to_html(readme_content)

    # Add documentation links section
    links_markdown = "\n\n## Generated Documentation\n\n"
    
    # Group links by top-level directory
    grouped_links = {}
    for original_path, html_path in generated_files.items():
        relative_html_path = html_path.relative_to(docs_dir)
        relative_original_path = original_path.relative_to(repo_root)
        
        top_dir = "root" if len(relative_original_path.parts) == 1 else relative_original_path.parts[0]
            
        if top_dir not in grouped_links:
            grouped_links[top_dir] = []
        
        grouped_links[top_dir].append(f"- [{relative_original_path}]({relative_html_path})")

    # Add root directory section
    if 'root' in grouped_links and grouped_links['root']:
        links_markdown += f"### Root Directory\n\n"
        links_markdown += "\n".join(sorted(grouped_links['root']))
        links_markdown += "\n\n"
    
    # Add sections for source directories
    for top_dir in sorted(grouped_links.keys()):
        if top_dir in SOURCE_DIRS:
            links_markdown += f"### {top_dir}\n\n"
            links_markdown += "\n".join(sorted(grouped_links[top_dir]))
            links_markdown += "\n\n"

    # Append links to the end
    final_readme_content = readme_content + links_markdown

    # Convert to HTML for index.html
    print(f"Generating index.html with REPO_NAME={REPO_NAME}")
    
    # Use "." as asset path prefix for main index
    asset_path_prefix = "."
    
    pandoc_cmd = [
        'pandoc',
        '-f', 'markdown+tex_math_dollars+raw_html',
        '-t', 'html5',
        '--standalone',
        '--mathjax',
        '--template', str(TEMPLATE_PATH),
        '-V', f'wikititle={WIKI_TITLE}',
        '-V', f'reponame={REPO_NAME}',
        '-V', 'base=/',
        '-V', 'notitle=true',
        '-V', f'pagetitle={WIKI_TITLE}',
        '-V', f'asset_path_prefix={asset_path_prefix}',
        '-o', str(index_path)
    ]

    debug_print(f"  [Debug Index] Target path: {index_path}")
    debug_print(f"  [Debug Index] Command: {' '.join(pandoc_cmd)}")

    process = subprocess.run(pandoc_cmd, input=final_readme_content, text=True, capture_output=True, check=False)

    if process.returncode != 0:
        print(f"Error generating index.html: {process.stderr}")
        return False
    
    # Post-process index.html for code blocks
    try:
        with open(index_path, 'r', encoding='utf-8') as f_in:
            index_html_content = f_in.read()
        
        processed_html = post_process_python_shell_html(index_html_content)
        
        with open(index_path, 'w', encoding='utf-8') as f_out:
            f_out.write(processed_html)
            
    except Exception as e:
        print(f"Warning: Failed to process code blocks in {index_path}: {e}")

    # Insert JavaScript
    insert_javascript_in_html(index_path)
    
    return True

def generate_robots_txt(docs_dir: Path) -> bool:
    """
    Creates a robots.txt file in the documentation directory to allow all user agents and specify the sitemap location.
    
    Args:
        docs_dir: Path to the documentation output directory.
    
    Returns:
        True if the robots.txt file was generated successfully, False otherwise.
    """
    robots_path = docs_dir / 'robots.txt'
    
    try:
        with open(robots_path, 'w', encoding='utf-8') as f:
            f.write('User-agent: *\n')
            f.write('Allow: /\n\n')
            f.write(f'Sitemap: {BASE_DOMAIN}/sitemap.xml\n')
        
        debug_print(f"Generated robots.txt at {robots_path}")
        return True
        
    except Exception as e:
        print(f"Error generating robots.txt: {e}")
        return False

def generate_sitemap(docs_dir: Path, generated_files: Dict[Path, Path]) -> bool:
    """
    Generates a sitemap.xml file listing all generated HTML documentation pages for search engines.
    
    The sitemap includes the homepage and all generated HTML files, assigning higher priority to index pages and files in key directories. Returns True if the sitemap is created successfully, otherwise False.
    """
    sitemap_path = docs_dir / 'sitemap.xml'
    
    try:
        with open(sitemap_path, 'w', encoding='utf-8') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
            
            # Add homepage
            f.write('  <url>\n')
            f.write(f'    <loc>{BASE_DOMAIN}/</loc>\n')
            f.write('    <changefreq>weekly</changefreq>\n')
            f.write('    <priority>1.0</priority>\n')
            f.write('  </url>\n')
            
            # Add all HTML files
            for _, html_path in generated_files.items():
                relative_path = html_path.relative_to(docs_dir)
                url_path = str(relative_path).replace('\\', '/')
                
                f.write('  <url>\n')
                f.write(f'    <loc>{BASE_DOMAIN}/{url_path}</loc>\n')
                f.write('    <changefreq>monthly</changefreq>\n')
                
                # Higher priority for important files
                if 'index' in url_path or url_path.startswith('src-local/'):
                    f.write('    <priority>0.8</priority>\n')
                else:
                    f.write('    <priority>0.6</priority>\n')
                    
                f.write('  </url>\n')
            
            f.write('</urlset>\n')
        
        debug_print(f"Generated sitemap at {sitemap_path}")
        return True
        
    except Exception as e:
        print(f"Error generating sitemap: {e}")
        return False

def copy_css_file(css_path: Path, docs_dir: Path) -> bool:
    """
    Copies a CSS file to the documentation directory.
    
    Args:
    	css_path: Path to the source CSS file.
    	docs_dir: Path to the documentation output directory.
    
    Returns:
    	True if the file was copied successfully, False otherwise.
    """
    try:
        shutil.copy2(css_path, docs_dir / css_path.name)
        debug_print(f"Copied CSS file to {docs_dir / css_path.name}")
        return True
    except Exception as e:
        print(f"Error copying CSS file: {e}")
        return False

def create_favicon_files(docs_dir: Path, logos_dir: Path) -> bool:
    """
    Creates favicon files and a web manifest in the documentation assets directory.
    
    Copies existing favicon files from the source favicon directory to `docs/assets/favicon`. If a logo file is found in the logos directory, generates a `site.webmanifest` file if it does not already exist.
    
    Args:
        docs_dir: Path to the documentation output directory.
        logos_dir: Path to the directory containing logo files.
    
    Returns:
        True if favicon files and manifest are created successfully, False otherwise.
    """
    try:
        favicon_dir = docs_dir / "assets" / "favicon"
        favicon_dir.mkdir(exist_ok=True)
        
        # Copy existing favicon files if available
        source_favicon_dir = Path(logos_dir.parent, "favicon")
        if source_favicon_dir.exists() and source_favicon_dir.is_dir():
            for item in source_favicon_dir.glob('*'):
                if item.is_file():
                    shutil.copy2(item, favicon_dir / item.name)
                    debug_print(f"Copied favicon file: {item.name}")
        
        # Find logo file
        logo_file = None
        for logo_name in ["CoMPhy-Lab.svg", "CoMPhy-Lab-no-name.png", "logoBasilisk_TransparentBackground.png"]:
            if (logos_dir / logo_name).exists():
                logo_file = logos_dir / logo_name
                break
        
        if logo_file:
            # Create webmanifest if missing
            webmanifest_path = favicon_dir / "site.webmanifest"
            if not webmanifest_path.exists():
                with open(webmanifest_path, 'w', encoding='utf-8') as f:
                    f.write('''{
  "name": "CoMPhy Lab",
  "short_name": "CoMPhy",
  "icons": [
    {
      "src": "/assets/favicon/android-chrome-192x192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/assets/favicon/android-chrome-512x512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ],
  "theme_color": "#ffffff",
  "background_color": "#ffffff",
  "display": "standalone"
}''')
                debug_print(f"Created site.webmanifest")
        
        return True
    except Exception as e:
        print(f"Error creating favicon files: {e}")
        return False

def copy_assets(assets_dir: Path, docs_dir: Path) -> bool:
    """
    Copies all asset files (CSS, JavaScript, images, logos, and favicons) from the source assets directory to the documentation output directory, migrating legacy files and ensuring required assets are present.
    
    Returns:
        True if all assets are copied successfully, False if any error occurs.
    """
    try:
        debug_print(f"Copying assets from {assets_dir} to {docs_dir}")
        
        # Create assets directory
        docs_assets_dir = docs_dir / "assets"
        docs_assets_dir.mkdir(exist_ok=True)
        
        # Copy CSS files
        css_dir = assets_dir / "css"
        docs_css_dir = docs_assets_dir / "css"
        docs_css_dir.mkdir(exist_ok=True, parents=True)
        
        if css_dir.exists():
            for css_file in css_dir.glob("**/*"):
                if css_file.is_file():
                    rel_path = css_file.relative_to(css_dir)
                    dest_path = docs_css_dir / rel_path
                    dest_path.parent.mkdir(exist_ok=True, parents=True)
                    shutil.copy2(css_file, dest_path)
                    debug_print(f"Copied {css_file} to {dest_path}")
        
        # Copy JS files
        js_dir = assets_dir / "js"
        docs_assets_js_dir = docs_assets_dir / "js"
        docs_assets_js_dir.mkdir(exist_ok=True, parents=True)

        if js_dir.exists():
            for js_file in js_dir.glob("**/*"):
                if js_file.is_file():
                    rel_path = js_file.relative_to(js_dir)
                    dest_path = docs_assets_js_dir / rel_path
                    dest_path.parent.mkdir(exist_ok=True, parents=True)
                    try:
                        shutil.copy2(js_file, dest_path)
                        debug_print(f"Copied {js_file} to {dest_path}")
                    except Exception as e:
                        print(f"Error copying JS file {js_file}: {e}")

        # Handle legacy JS files
        legacy_js_dir = docs_dir / "js"
        if legacy_js_dir.exists() and legacy_js_dir.is_dir():
            for legacy_file in legacy_js_dir.glob("*"):
                if legacy_file.is_file():
                    try:
                        shutil.copy2(legacy_file, docs_assets_js_dir / legacy_file.name)
                        debug_print(f"Migrated legacy JS file {legacy_file}")
                    except Exception as e:
                        print(f"Error migrating legacy JS file {legacy_file}: {e}")
            try:
                for legacy_file in legacy_js_dir.glob("*"):
                    legacy_file.unlink()
                legacy_js_dir.rmdir()
                debug_print("Removed legacy docs/js directory.")
            except Exception as e:
                print(f"Error removing legacy docs/js directory: {e}")

        # Ensure required JS files
        required_js = ["search_db.json", "command-palette.js", "command-data.js"]
        for req_file in required_js:
            src_file = js_dir / req_file
            dest_file = docs_assets_js_dir / req_file
            if not dest_file.exists() and src_file.exists():
                try:
                    shutil.copy2(src_file, dest_file)
                    debug_print(f"Copied required JS file {src_file}")
                except Exception as e:
                    print(f"Error copying required JS file {src_file}: {e}")

        # Copy images
        img_dir = assets_dir / "images"
        docs_img_dir = docs_assets_dir / "images"
        
        if img_dir.exists():
            docs_img_dir.mkdir(exist_ok=True, parents=True)
            for img_file in img_dir.glob("**/*"):
                if img_file.is_file():
                    rel_path = img_file.relative_to(img_dir)
                    dest_path = docs_img_dir / rel_path
                    dest_path.parent.mkdir(exist_ok=True, parents=True)
                    shutil.copy2(img_file, dest_path)
                    debug_print(f"Copied {img_file} to {dest_path}")
                    
        # Copy logos
        logos_dir = assets_dir / "logos"
        docs_logos_dir = docs_assets_dir / "logos"
        
        if logos_dir.exists():
            docs_logos_dir.mkdir(exist_ok=True, parents=True)
            for logo_file in logos_dir.glob("**/*"):
                if logo_file.is_file():
                    rel_path = logo_file.relative_to(logos_dir)
                    dest_path = docs_logos_dir / rel_path
                    dest_path.parent.mkdir(exist_ok=True, parents=True)
                    shutil.copy2(logo_file, dest_path)
                    debug_print(f"Copied {logo_file} to {dest_path}")
        
        # Copy custom CSS to root
        if css_dir.exists():
            custom_styles_path = css_dir / "custom_styles.css"
            if custom_styles_path.exists():
                shutil.copy2(custom_styles_path, docs_dir / "custom_styles.css")
                debug_print(f"Copied custom_styles.css to root directory")
        
        # Create favicon files
        logos_dir = assets_dir / "logos"
        if logos_dir.exists():
            create_favicon_files(docs_dir, logos_dir)

        # Copy favicon files to root
        favicon_source_dir = assets_dir / "favicon"
        if favicon_source_dir.exists() and favicon_source_dir.is_dir():
            for fav_file in favicon_source_dir.glob("*"):
                if fav_file.is_file():
                    shutil.copy2(fav_file, docs_dir / fav_file.name)
                    debug_print(f"Copied {fav_file.name} to root")

        # Copy Basilisk JS files
        static_js_dir = DARCSIT_DIR / "static" / "js"
        docs_assets_js_dir = docs_dir / "assets" / "js"
        docs_assets_js_dir.mkdir(exist_ok=True, parents=True)
        if static_js_dir.exists() and static_js_dir.is_dir():
            for js_file in static_js_dir.glob("*.js"):
                try:
                    shutil.copy2(js_file, docs_assets_js_dir / js_file.name)
                    debug_print(f"Copied Basilisk JS file: {js_file.name}")
                except Exception as e:
                    print(f"Error copying Basilisk JS file {js_file}: {e}")

        return True
    except Exception as e:
        print(f"Error copying assets: {e}")
        return False

def main():
    """
    Generates the complete HTML documentation site for the project.
    
    Creates the documentation output directory, optionally cleans existing HTML files if force rebuild is enabled, copies all required assets, processes each supported source file into HTML with appropriate post-processing, generates index pages for directories and the main index from README.md, and creates robots.txt and sitemap.xml for search engines. Also copies additional JavaScript files required for Basilisk integration and cleans up temporary files.
    """
    if not validate_config():
        return
    
    try:
        # Create docs directory
        DOCS_DIR.mkdir(exist_ok=True)
        
        # Clean docs if force-rebuild enabled
        if FORCE_REBUILD:
            print("\nForce rebuild enabled. Cleaning docs directory...")
            for html_file in DOCS_DIR.rglob('*.html'):
                try:
                    html_file.unlink()
                    debug_print(f"Removed {html_file}")
                except Exception as e:
                    print(f"Warning: Could not remove {html_file}: {e}")
        
        # Copy assets
        print("\nCopying assets...")
        assets_dir = REPO_ROOT / '.github' / 'assets'
        if not copy_assets(assets_dir, DOCS_DIR):
            print("Failed to copy assets.")
            return
        
        # Find source files
        source_files = find_source_files(REPO_ROOT, SOURCE_DIRS)
        if not source_files:
            print("No source files found.")
            return
        
        # Dictionary for generated files
        generated_files = {}
        
        # Process each file
        for file_path in source_files:
            # Create output path
            relative_path = file_path.relative_to(REPO_ROOT)
            output_html_path = DOCS_DIR / relative_path.with_suffix(relative_path.suffix + '.html')
            
            # Create output directory
            output_html_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Skip if not forced and file exists
            if not FORCE_REBUILD and output_html_path.exists():
                print(f"  Skipping existing file: {output_html_path.relative_to(DOCS_DIR)}")
                generated_files[file_path] = output_html_path
                continue
            
            # Process file
            if process_file_with_page2html_logic(
                file_path, 
                output_html_path, 
                REPO_ROOT, 
                BASILISK_DIR, 
                DARCSIT_DIR, 
                TEMPLATE_PATH, 
                BASE_URL, 
                WIKI_TITLE, 
                LITERATE_C_SCRIPT,
                DOCS_DIR
            ):
                generated_files[file_path] = output_html_path
        
        # Generate folder index pages
        print("\nGenerating folder index pages...")
        for source_dir in SOURCE_DIRS:
            docs_source_dir = DOCS_DIR / source_dir
            if docs_source_dir.exists():
                if not generate_directory_index(source_dir, docs_source_dir, generated_files, DOCS_DIR, REPO_ROOT):
                    print(f"Failed to generate index for {source_dir}.")
        
        # Generate main index.html
        print("\nGenerating main index.html...")
        if not generate_index(README_PATH, INDEX_PATH, generated_files, DOCS_DIR, REPO_ROOT):
            print("Failed to generate index.html.")
            return
        
        # Generate robots.txt and sitemap
        print("\nGenerating robots.txt...")
        generate_robots_txt(DOCS_DIR)
        
        print("\nGenerating sitemap...")
        generate_sitemap(DOCS_DIR, generated_files)
        
        print("\nDocumentation generation complete.")
        print(f"Output generated in: {DOCS_DIR}")

        # Copy Basilisk JS to assets
        js_src_dir = BASILISK_DIR / 'src' / 'darcsit' / 'static' / 'js'
        js_dest_dir = DOCS_DIR / 'assets' / 'js'
        js_dest_dir.mkdir(parents=True, exist_ok=True)
        for js_file in ['jquery.min.js', 'jquery-ui.packed.js', 'plots.js']:
            src = js_src_dir / js_file
            dst = js_dest_dir / js_file
            if src.exists():
                shutil.copy2(src, dst)
                print(f"Copied Basilisk JS file {src} to {dst}")
            else:
                print(f"Warning: Basilisk JS file {src} not found")
        
    finally:
        # Clean up temporary template
        temp_template_path = TEMPLATE_PATH.parent / (TEMPLATE_PATH.stem.replace('.temp', '') + '.temp.html')
        if temp_template_path.exists():
            try:
                temp_template_path.unlink()
                debug_print(f"Cleaned up temporary template file")
            except Exception as e:
                print(f"Warning: Could not delete temporary template file: {e}")

if __name__ == "__main__":
    main()