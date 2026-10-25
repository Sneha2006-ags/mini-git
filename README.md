# mini-git

A from-scratch implementation of Git's core in Python (~250 lines), built by reverse engineering real Git's `.git` folder.

## Features
- `init`, `add`, `commit`, `log`, `status`, `branch`, `checkout`
- Content-addressed object store (blobs, trees, commits) with SHA-1 and zlib
- Staging area (index)
- Nested folders via recursive tree objects
- **Compatible with real Git**: `git --git-dir=.mygit log` reads repos created by this tool

## Usage
    python mygit.py init
    python mygit.py add file.txt
    python mygit.py commit "message"
    python mygit.py log

## How I built it
I inspected real Git's `.git/objects` with `git cat-file` and `git hash-object`, worked out the exact object formats (e.g. `blob <size>\0<content>`, trees with 20-byte raw hashes), then reimplemented them and verified my hashes matched real Git's byte for byte.

## Limitations
No merge, remote, or diff yet; checkout does not check for uncommitted changes.
