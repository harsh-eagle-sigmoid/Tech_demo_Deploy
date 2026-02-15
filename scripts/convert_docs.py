import markdown
import pdfkit
import os
import sys

# ------------------------------------------------------------------
# PREREQUISITES
# 1. Install Python packages: pip install markdown pdfkit
# 2. Install wkhtmltopdf tool:
#    - Ubuntu: sudo apt-get install wkhtmltopdf
#    - Mac: brew install wkhtmltopdf
#    - Windows: Download installer from wkhtmltopdf.org
# ------------------------------------------------------------------

def convert_md_to_pdf(input_file, output_file):
    """
    Converts a Markdown file to PDF using intermediate HTML.
    """
    if not os.path.exists(input_file):
        print(f"Error: Input file not found: {input_file}")
        return

    print(f"Reading {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        md_content = f.read()

    # Convert MD to HTML
    try:
        html_content = markdown.markdown(
            md_content,
            extensions=['extra', 'codehilite', 'tables']
        )
    except Exception:
        # Fallback if extensions fail
        html_content = markdown.markdown(md_content)

    # Add some CSS for styling (Make it look like a document)
    styled_html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 40px; }}
            h1, h2, h3 {{ color: #333; border-bottom: 1px solid #ddd; padding-bottom: 10px; }}
            pre {{ background: #f4f4f4; padding: 15px; border-radius: 5px; overflow-x: auto; }}
            code {{ background: #eee; padding: 2px 5px; border-radius: 3px; font-family: monospace; }}
            table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            blockquote {{ border-left: 4px solid #ccc; margin: 10px 0; padding-left: 10px; color: #666; }}
            img {{ max-width: 100%; height: auto; }}
        </style>
    </head>
    <body>
        <div class="content">
            {html_content}
        </div>
    </body>
    </html>
    """

    print(f"Converting to PDF: {output_file}...")
    try:
        # Configuration for PDFKit
        options = {
            'page-size': 'A4',
            'margin-top': '20mm',
            'margin-right': '20mm',
            'margin-bottom': '20mm',
            'margin-left': '20mm',
            'encoding': "UTF-8",
        }
        
        pdfkit.from_string(styled_html, output_file, options=options)
        print("Success! PDF created.")

    except OSError as e:
        print("Error: weakhtmltopdf not found or configuration error.")
        print(f"Details: {e}")
        print("Please ensure wkhtmltopdf is installed and in your PATH.")
    except Exception as e:
        print(f"Unexpected Error: {e}")

if __name__ == "__main__":
    # Correct Path to Artifact
    DEFAULT_INPUT = "/home/lenovo/.gemini/antigravity/brain/088065bd-5728-493d-b390-af05d2f60c48/architecture_overview.md"
    DEFAULT_OUTPUT = "architecture_overview.pdf"

    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = DEFAULT_INPUT
        
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    else:
        output_file = DEFAULT_OUTPUT

    convert_md_to_pdf(input_file, output_file)
