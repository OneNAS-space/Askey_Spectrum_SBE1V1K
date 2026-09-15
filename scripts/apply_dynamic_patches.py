#!/usr/bin/env python3
import os, sys, re, glob, difflib, tempfile, subprocess
 
from patch_specs import PATCH_SPECS

# ---- Definition of multiple source code trees: env var provides the actual directory 
# and the relative path of the final landing of the patch ----
TREES = {
    'kernel': {
        'dir_env': 'KERNEL_DIR',
        'patch_dir_rel': 'target/linux/qualcommbe/patches-6.18',
    },
    'mac80211': {
        'dir_env': 'MAC80211_DIR',
        'patch_dir_rel': 'package/kernel/mac80211/patches/ath12k',
    },
}

def resolve_tree_dir(tree_key):
    env_name = TREES[tree_key]['dir_env']
    d = os.environ.get(env_name)
    if not d:
        if tree_key == 'kernel':
            matches = glob.glob('build_dir/target-*/linux-*')
            if matches:
                d = matches[0]
        elif tree_key == 'mac80211':
            matches = glob.glob('build_dir/target-*/mac80211-*') or glob.glob('build_dir/target-*/backports-*')
            if matches:
                d = matches[0]

    if not d or not os.path.isdir(d):
        print(f"Error: {env_name} Not set or the directory does not exist: {d}")
        sys.exit(1)
    return os.path.abspath(d)

def find_file(base_dir, filename, path_must_contain=(), parent_dir_exact=None):
    matches = []
    seen_real = set()
    for root, dirs, files in os.walk(base_dir):
        if filename in files:
            full_path = os.path.join(root, filename)
            if not all(part in full_path for part in path_must_contain):
                continue
            if parent_dir_exact is not None and os.path.basename(root) != parent_dir_exact:
                continue
            real = os.path.realpath(full_path)
            if real in seen_real:
                continue
            seen_real.add(real)
            matches.append(full_path)
    return matches

def format_diff_range(start, stop):
    length = stop - start
    if length == 1:
        return f"{start + 1}"
    if length == 0:
        return f"{start},0"  # Take the line number of the line before the insertion position when inserting purely.
    return f"{start + 1},{length}"

def make_unified_diff(base_dir, path, original, updated):
    relpath = os.path.relpath(path, base_dir)
    
    # ---- Give priority to using the system's git diff --no-index or diff -u to generate Linux kernel-level specification patches ----
    f1_path, f2_path = None, None
    try:
        with tempfile.NamedTemporaryFile('w', delete=False, encoding='utf-8') as f1, \
             tempfile.NamedTemporaryFile('w', delete=False, encoding='utf-8') as f2:
            f1.write(original)
            f2.write(updated)
            f1_path, f2_path = f1.name, f2.name

        # 1. Try git diff --no-index (with indentation inspirational algorithm, will not misplace the brackets)
        cmd = ['git', 'diff', '--no-index', '-u', f1_path, f2_path]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.stdout:
            lines = res.stdout.splitlines(keepends=True)
            out = [f'--- a/{relpath}\n', f'+++ b/{relpath}\n']
            for line in lines:
                if line.startswith('--- ') or line.startswith('+++ ') or line.startswith('diff --git') or line.startswith('index '):
                    continue
                out.append(line)
            return ''.join(out)

        # 2. Try the system diff -u
        cmd = ['diff', '-u', f1_path, f2_path]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.stdout:
            lines = res.stdout.splitlines(keepends=True)
            out = [f'--- a/{relpath}\n', f'+++ b/{relpath}\n']
            for line in lines[2:]:
                out.append(line)
            return ''.join(out)
    except Exception:
        pass
    finally:
        if f1_path and os.path.exists(f1_path):
            os.remove(f1_path)
        if f2_path and os.path.exists(f2_path):
            os.remove(f2_path)

    # ---- 3. Python pure difflib ----
    a = original.splitlines(keepends=True)
    b = updated.splitlines(keepends=True)
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)

    lines = [f'--- a/{relpath}\n', f'+++ b/{relpath}\n']

    for group in matcher.get_grouped_opcodes(n=3):
        first, last = group[0], group[-1]
        file1_range = format_diff_range(first[1], last[2])
        file2_range = format_diff_range(first[3], last[4])
        lines.append(f'@@ -{file1_range} +{file2_range} @@\n')

        for tag, i1, i2, j1, j2 in group:
            if tag == 'equal':
                for line in a[i1:i2]:
                    lines.append(' ' + line)
            elif tag in ('replace', 'delete'):
                for line in a[i1:i2]:
                    lines.append('-' + line)
            if tag in ('replace', 'insert'):
                for line in b[j1:j2]:
                    lines.append('+' + line)

    return ''.join(lines)

def apply_spec(content, spec, label):
    applied_count = 0
    for idx, (pat, repl) in enumerate(spec['replacements'], 1):
        if spec['kind'] == 'regex':
            new_content, n = re.subn(pat, repl, content)
        else:
            n = content.count(pat)
            new_content = content.replace(pat, repl) if n else content
        if n == 0:
            print(f"  !! [{label}] 第 {idx}/{len(spec['replacements'])} The replacement is not hit. Please check the context there.")
        else:
            if n > 1:
                print(f"  !! [{label}] 第 {idx}/{len(spec['replacements'])} Strip replacement hit {n} times (expected 1 time), please check manually.")
            content = new_content
            applied_count += n
    return content, applied_count

def main():
    grouped = {}
    for spec in PATCH_SPECS:
        tree_key = spec.get('tree', 'kernel')
        grouped.setdefault((tree_key, spec['name']), []).append(spec)

    tree_dirs = {}
    total_patched = 0
    root_dir = os.environ.get('ROOT_DIR', '.')

    for (tree_key, name), specs in grouped.items():
        if tree_key not in tree_dirs:
            tree_dirs[tree_key] = resolve_tree_dir(tree_key)
            print(f"Targeting {tree_key} directory: {tree_dirs[tree_key]}")
        base_dir = tree_dirs[tree_key]

        combined_diff = ''
        for spec in specs:
            candidates = find_file(
                base_dir,
                spec['filename'],
                spec['path_must_contain'],
                parent_dir_exact=spec.get('parent_dir_exact'),
            )
            if len(candidates) > 1:
                print(f"  !! [{name}] Warning: {spec['filename']} Find {len(candidates)} candidates, and there may be residual copies:")
                for c in candidates:
                    print(f"       - {c}")
            
            if not candidates:
                print(f"  !! [{name}] Error: The target file was not found {spec['filename']} (QUALIFIED CONDITIONS: {spec['path_must_contain']})")
                continue

            spec_matched = False
            for p in candidates:
                with open(p, 'r', encoding='utf-8', errors='ignore') as f:
                    original = f.read()
                
                content, applied_count = apply_spec(original, spec, name)
                if content != original:
                    spec_matched = True
                    with open(p, 'w', encoding='utf-8') as f:
                        f.write(content)
                    combined_diff += make_unified_diff(base_dir, p, original, content)
                    total_patched += 1
                    print(f"  [{name}] Modified: {os.path.relpath(p, base_dir)}")

            if not spec_matched:
                print(f"  !! [{name}] Tip: The file {spec['filename']} was found, but it did not match the replacement content (the code has been modified or the context is inconsistent)")

        if combined_diff:
            patch_dir = os.path.join(root_dir, TREES[tree_key]['patch_dir_rel'])
            os.makedirs(patch_dir, exist_ok=True)
            out_path = os.path.join(patch_dir, f'{name}.patch')
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(combined_diff)
            print(f"✅ Generated {out_path}")

    if total_patched == 0:
        print("❌ Error: No documents have been modified.")
        sys.exit(1)

if __name__ == '__main__':
    main()
