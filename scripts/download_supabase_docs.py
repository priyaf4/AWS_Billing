"""Download every .mdx file under supabase/supabase apps/docs/content, keeping the folder structure.

Usage:
    python scripts/download_supabase_docs.py
    python scripts/download_supabase_docs.py --out data/supabase_docs --workers 16

Optional: set GITHUB_TOKEN to raise the GitHub API rate limit (only a few API calls are made).
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

OWNER = "supabase"
REPO = "supabase"
BRANCH = "master"
CONTENT_PATH = "apps/docs/content"
EXTENSION = ".mdx"

API = f"https://api.github.com/repos/{OWNER}/{REPO}"
RAW = f"https://raw.githubusercontent.com/{OWNER}/{REPO}"


def http_get(url, retries=3):
    headers = {"User-Agent": "deskcopilot-docs-downloader"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com"):
        headers["Authorization"] = f"Bearer {token}"

    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as res:
                return res.read()
        except urllib.error.HTTPError as err:
            # 404 / 403 won't fix themselves on retry
            if err.code in (403, 404) or attempt == retries:
                raise
        except urllib.error.URLError:
            if attempt == retries:
                raise
        time.sleep(2 * attempt)


def get_json(url):
    return json.loads(http_get(url))


def find_content_tree_sha(commit_sha):
    """Walk apps -> docs -> content from the commit's root tree, one level at a time.

    Listing the whole repo recursively gets truncated (it is very large), so we
    only recurse from the content folder.
    """
    tree_sha = get_json(f"{API}/git/commits/{commit_sha}")["tree"]["sha"]
    for part in CONTENT_PATH.split("/"):
        tree = get_json(f"{API}/git/trees/{tree_sha}")
        match = next((e for e in tree["tree"] if e["path"] == part and e["type"] == "tree"), None)
        if match is None:
            sys.exit(f"Folder '{part}' not found while looking for {CONTENT_PATH}")
        tree_sha = match["sha"]
    return tree_sha


def list_mdx_files(content_sha):
    tree = get_json(f"{API}/git/trees/{content_sha}?recursive=1")
    if tree.get("truncated"):
        print("Warning: GitHub truncated the file list; some files may be missing.")
    return [e["path"] for e in tree["tree"] if e["type"] == "blob" and e["path"].endswith(EXTENSION)]


def download(commit_sha, rel_path, out_dir):
    dest = out_dir / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(http_get(f"{RAW}/{commit_sha}/{CONTENT_PATH}/{rel_path}"))
    return rel_path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="data/supabase_docs", help="output folder (default: data/supabase_docs)")
    parser.add_argument("--workers", type=int, default=16, help="parallel downloads (default: 16)")
    args = parser.parse_args()
    out_dir = Path(args.out)

    # Pin to one commit so the file list and the downloads always match.
    commit_sha = get_json(f"{API}/commits/{BRANCH}")["sha"]
    print(f"Using {OWNER}/{REPO}@{commit_sha[:7]} ({BRANCH})")

    files = list_mdx_files(find_content_tree_sha(commit_sha))
    print(f"Found {len(files)} {EXTENSION} files under {CONTENT_PATH}")

    failed = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(download, commit_sha, f, out_dir): f for f in files}
        for i, future in enumerate(as_completed(futures), 1):
            try:
                future.result()
            except Exception as err:
                failed.append((futures[future], err))
            if i % 100 == 0 or i == len(files):
                print(f"  {i}/{len(files)} done")

    print(f"\nDownloaded {len(files) - len(failed)} files to {out_dir.resolve()}")
    if failed:
        print(f"{len(failed)} failed:")
        for path, err in failed:
            print(f"  {path}: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
