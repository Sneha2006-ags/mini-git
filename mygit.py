import os
import sys
import time
import hashlib
import zlib

GIT_DIR = ".mygit"
AUTHOR = "Sneha <snehaags2006@gmail.com>"
TZ = "+0530"


def init():
    os.makedirs(os.path.join(GIT_DIR, "objects"), exist_ok=True)
    os.makedirs(os.path.join(GIT_DIR, "refs", "heads"), exist_ok=True)
    with open(os.path.join(GIT_DIR, "HEAD"), "w") as f:
        f.write("ref: refs/heads/main\n")
    print("Initialized empty mygit repository")


def write_object(obj_type, data):
    store = f"{obj_type} {len(data)}".encode() + b"\x00" + data
    sha = hashlib.sha1(store).hexdigest()
    folder = os.path.join(GIT_DIR, "objects", sha[:2])
    os.makedirs(folder, exist_ok=True)
    obj_path = os.path.join(folder, sha[2:])
    if not os.path.exists(obj_path):
        with open(obj_path, "wb") as f:
            f.write(zlib.compress(store))
    return sha


def hash_object(path):
    with open(path, "rb") as f:
        return write_object("blob", f.read())


def cat_file(sha):
    obj_path = os.path.join(GIT_DIR, "objects", sha[:2], sha[2:])
    with open(obj_path, "rb") as f:
        raw = zlib.decompress(f.read())
    header, _, content = raw.partition(b"\x00")
    return header.decode(), content


def current_branch_path():
    with open(os.path.join(GIT_DIR, "HEAD")) as f:
        ref = f.read().strip().split(" ")[1]
    return os.path.join(GIT_DIR, ref)


def current_branch_name():
    return os.path.basename(current_branch_path())


def current_commit():
    path = current_branch_path()
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    return None


def read_index():
    path = os.path.join(GIT_DIR, "index")
    entries = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                sha, name = line.rstrip("\n").split(" ", 1)
                entries[name] = sha
    return entries


def write_index(entries):
    with open(os.path.join(GIT_DIR, "index"), "w") as f:
        for name in sorted(entries):
            f.write(f"{entries[name]} {name}\n")


def add(files):
    entries = read_index()
    for name in files:
        name = name.replace("\\", "/")
        entries[name] = hash_object(name)
        print(f"added {name}")
    write_index(entries)


def build_tree(entries):
    """entries: {path: sha}. Builds a tree object, folders become sub-trees."""
    files, dirs = {}, {}
    for path, sha in entries.items():
        if "/" in path:
            top, rest = path.split("/", 1)
            dirs.setdefault(top, {})[rest] = sha
        else:
            files[path] = sha
    items = []
    for name, sha in files.items():
        items.append((name, b"100644", bytes.fromhex(sha)))
    for name, sub in dirs.items():
        items.append((name + "/", b"40000", bytes.fromhex(build_tree(sub))))
    data = b""
    for key, mode, raw in sorted(items, key=lambda x: x[0]):
        data += mode + b" " + key.rstrip("/").encode() + b"\x00" + raw
    return write_object("tree", data)


def tree_from_index():
    return build_tree(read_index())


def commit_tree(commit_sha):
    _, content = cat_file(commit_sha)
    first_line = content.decode().split("\n")[0]
    return first_line.split(" ")[1]


def read_tree(tree_sha, prefix=""):
    """Returns {full_path: blob_sha}, walking into sub-trees."""
    _, data = cat_file(tree_sha)
    entries = {}
    i = 0
    while i < len(data):
        sp = data.index(b" ", i)
        nul = data.index(b"\x00", sp)
        mode = data[i:sp]
        fname = data[sp + 1:nul].decode()
        sha = data[nul + 1:nul + 21].hex()
        if mode == b"40000":
            entries.update(read_tree(sha, prefix + fname + "/"))
        else:
            entries[prefix + fname] = sha
        i = nul + 21
    return entries


def commit_with_tree(tree, message):
    lines = [f"tree {tree}"]
    parent = current_commit()
    if parent:
        lines.append(f"parent {parent}")
    now = int(time.time())
    lines.append(f"author {AUTHOR} {now} {TZ}")
    lines.append(f"committer {AUTHOR} {now} {TZ}")
    lines.append("")
    lines.append(message)
    data = ("\n".join(lines) + "\n").encode()
    sha = write_object("commit", data)
    with open(current_branch_path(), "w") as f:
        f.write(sha + "\n")
    print(f"[{current_branch_name()} {sha[:7]}] {message}")
    return sha


def commit_staged(message):
    if not read_index():
        print("nothing staged")
        return
    tree = tree_from_index()
    cur = current_commit()
    if cur and commit_tree(cur) == tree:
        print("nothing to commit")
        return
    commit_with_tree(tree, message)


def log():
    sha = current_commit()
    while sha:
        _, content = cat_file(sha)
        headers, _, message = content.decode().partition("\n\n")
        parent = None
        author = ""
        for line in headers.split("\n"):
            if line.startswith("parent "):
                parent = line.split(" ")[1]
            if line.startswith("author "):
                author = line[len("author "):]
        print(f"commit {sha}")
        print(f"Author: {author}")
        print(f"\n    {message.strip()}\n")
        sha = parent


def branch(new_name=None):
    heads = os.path.join(GIT_DIR, "refs", "heads")
    if new_name is None:
        cur = current_branch_name()
        for b in sorted(os.listdir(heads)):
            print(("* " if b == cur else "  ") + b)
        return
    sha = current_commit()
    if not sha:
        print("no commits yet")
        return
    with open(os.path.join(heads, new_name), "w") as f:
        f.write(sha + "\n")
    print(f"created branch {new_name}")


def checkout(target):
    path = os.path.join(GIT_DIR, "refs", "heads", target)
    if not os.path.exists(path):
        print(f"no such branch: {target}")
        return
    with open(path) as f:
        sha = f.read().strip()
    entries = read_tree(commit_tree(sha))
    # delete files that were tracked but don't exist in the target
    for old in read_index():
        if old not in entries and os.path.exists(old):
            os.remove(old)
            folder = os.path.dirname(old)
            if folder:
                try:
                    os.removedirs(folder)  # remove folder if now empty
                except OSError:
                    pass
    # write every file from the target commit's tree
    for fname, blob_sha in entries.items():
        _, content = cat_file(blob_sha)
        folder = os.path.dirname(fname)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(fname, "wb") as f:
            f.write(content)
    write_index(entries)
    with open(os.path.join(GIT_DIR, "HEAD"), "w") as f:
        f.write(f"ref: refs/heads/{target}\n")
    print(f"switched to branch {target}")


def status():
    index = read_index()
    cur = current_commit()
    committed = read_tree(commit_tree(cur)) if cur else {}

    staged = [n for n in index if committed.get(n) != index[n]]
    modified, untracked = [], []

    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in (".git", ".mygit", "__pycache__")]
        for fname in sorted(files):
            name = os.path.relpath(os.path.join(root, fname), ".").replace("\\", "/")
            with open(name, "rb") as f:
                data = f.read()
            sha = hashlib.sha1(f"blob {len(data)}".encode() + b"\x00" + data).hexdigest()
            if name in index:
                if index[name] != sha:
                    modified.append(name)
            else:
                untracked.append(name)

    print(f"On branch {current_branch_name()}")
    if staged:
        print("\nChanges to be committed:")
        for n in sorted(staged):
            print(f"    {n}")
    if modified:
        print("\nModified but not staged:")
        for n in sorted(modified):
            print(f"    {n}")
    if untracked:
        print("\nUntracked files:")
        for n in sorted(untracked):
            print(f"    {n}")
    if not (staged or modified or untracked):
        print("nothing to commit, working tree clean")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python mygit.py <command> [args]")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "init":
        init()
    elif cmd == "hash-object":
        print(hash_object(sys.argv[2]))
    elif cmd == "cat-file":
        header, content = cat_file(sys.argv[2])
        print(header)
        print(content.decode(errors="replace"))
    elif cmd == "add":
        add(sys.argv[2:])
    elif cmd == "commit":
        commit_staged(sys.argv[2])
    elif cmd == "log":
        log()
    elif cmd == "branch":
        branch(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "checkout":
        checkout(sys.argv[2])
    elif cmd == "status":
        status()
    else:
        print("Unknown command:", cmd)
