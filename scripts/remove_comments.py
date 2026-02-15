utf-8
import sys
import os
import re
import tokenize
from io import BytesIO
def remove_comments_python(source):
    """Remove comments AND docstrings."""
    io_obj = BytesIO(source.encode('utf-8'))
    out = []
    prev_toktype = tokenize.INDENT
    last_lineno = -1
    last_col = 0
    try:
        tokens = list(tokenize.tokenize(io_obj.readline))
        for i, tok in enumerate(tokens):
            token_type = tok.type
            token_string = tok.string
            start_line, start_col = tok.start
            end_line, end_col = tok.end
            if start_line > last_lineno:
                last_col = 0
            if start_col > last_col:
                out.append(" " * (start_col - last_col))
            if token_type == tokenize.COMMENT:
                pass 
            elif token_type == tokenize.STRING:
                is_docstring = False
                j = i - 1
                while j >= 0:
                    if tokens[j].type in [tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENCODING]:
                        j -= 1
                        continue
                    break
                valid_prev = False
                if j >= 0:
                    pt = tokens[j]
                    if pt.type == tokenize.OP and pt.string in ['=', '(', '[', '{', ',', ':']:
                        valid_prev = True
                    elif pt.type == tokenize.NAME and pt.string in ['return', 'yield', 'raise']:
                        valid_prev = True
                    elif pt.type == tokenize.NAME: 
                        pass
                if not valid_prev and j >= 0:
                   pass 
                elif j < 0: 
                   pass 
                else:
                   out.append(token_string)
            else:
                out.append(token_string)
            last_col = end_col
            last_lineno = end_line
    except tokenize.TokenError:
        return source
    return "".join(out)
def process_file(filepath):
    if  in filepath: return
    print(f"Processing {filepath}...")
    ext = os.path.splitext(filepath)[1]
    with open(filepath, 'r') as f:
        content = f.read()
    if ext == :
        new_content = remove_comments_python(content)
        new_content = "\n".join([line for line in new_content.split('\n') if line.strip()])
    elif ext in ['.js', '.jsx', '.ts', '.tsx']:
        pattern = r"(\".*?\"|\'.*?\'|`.*?`)|(//.*|/\*[\s\S]*?\*/)"
        def replace(match):
            if match.group(2): return ""
            return match.group(1)
        new_content = re.sub(pattern, replace, content, flags=re.MULTILINE)
        new_content = "\n".join([line for line in new_content.split('\n') if line.strip()])
    else:
        return
    with open(filepath, 'w') as f:
        f.write(new_content)
if __name__ == :
    target_dir = sys.argv[1] if len(sys.argv) > 1 else 
    for root, dirs, files in os.walk(target_dir):
        if  in root or  in root or  in root or  in root:
            continue
        for file in files:
            if file.endswith((".py", ".js", ".jsx")):
                process_file(os.path.join(root, file))