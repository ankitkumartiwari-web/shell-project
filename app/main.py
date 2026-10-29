import os
import re
import sys
import shutil
import shlex
import subprocess
import readline
from contextlib import contextmanager

BUILTINS = {"exit", "echo", "type", "pwd", "cd", "history", "complete", "jobs", "declare"}
variables = {}  # shell variables (set by `declare` or NAME=value)
NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
jobs = []  # background jobs: {"id", "pids", "cmd", "done"}
completions = {}  # command name -> completer script (set via `complete -C`)
last_appended = 0  # index of last history entry written by `history -a`


def get_var(name):
    return variables[name] if name in variables else os.environ.get(name, "")


def set_var(name, value):
    variables[name] = value
    if name in os.environ:  # already exported: keep the environment in sync
        os.environ[name] = value


def read_var(line, i):
    """line[i] == '$'. Return (value, next_index) for $NAME / ${NAME}, else None."""
    if line[i + 1:i + 2] == "{":
        j = line.find("}", i + 2)
        if j != -1 and NAME_RE.fullmatch(line[i + 2:j]):
            return get_var(line[i + 2:j]), j + 1
        return None
    m = NAME_RE.match(line, i + 1)
    return (get_var(m.group()), m.end()) if m else None


# --------------------------------------------------------------------------
# Tokenizer: quotes, backslashes, and the operators  |  <  >  >>  1>  2>  2>>
# --------------------------------------------------------------------------
def tokenize(line):
    tokens, cur = [], []
    quoted = False  # current token contained any quoting
    in_word = False
    i, n = 0, len(line)

    def flush():
        nonlocal cur, quoted, in_word
        if in_word:
            tokens.append(("word", "".join(cur)))
        cur, quoted, in_word = [], False, False

    while i < n:
        c = line[i]
        if c == "\\":  # backslash outside quotes: keep next char literally
            if i + 1 < n:
                cur.append(line[i + 1])
                in_word = quoted = True
            i += 2
        elif c == "'":  # single quotes: everything literal
            j = line.find("'", i + 1)
            if j == -1:
                raise ValueError("unterminated single quote")
            cur.append(line[i + 1:j])
            in_word = quoted = True
            i = j + 1
        elif c == '"':  # double quotes: backslash escapes only \ " $ `
            i += 1
            while i < n and line[i] != '"':
                if line[i] == "\\" and i + 1 < n and line[i + 1] in '\\"$`':
                    cur.append(line[i + 1])
                    i += 2
                elif line[i] == "$" and (r := read_var(line, i)) is not None:
                    cur.append(r[0])
                    i = r[1]
                else:
                    cur.append(line[i])
                    i += 1
            if i >= n:
                raise ValueError("unterminated double quote")
            i += 1
            in_word = quoted = True
        elif c == "$" and (r := read_var(line, i)) is not None:
            for part in re.split(r"(\s+)", r[0]):
                if not part:
                    continue
                if part.isspace():
                    flush()
                else:
                    cur.append(part)
                    in_word = True
            i = r[1]
        elif c.isspace():
            flush()
            i += 1
        elif c == "|":
            flush()
            tokens.append(("op", "|"))
            i += 1
        elif c == "&":
            flush()
            tokens.append(("op", "&"))
            i += 1
        elif c == "<":
            flush()
            tokens.append(("op", "<"))
            i += 1
        elif c == ">":
            fd = 1
            # "1>" / "2>" : a lone unquoted digit directly before '>'
            if in_word and not quoted and "".join(cur) in ("1", "2"):
                fd = int("".join(cur))
                cur, in_word = [], False
            else:
                flush()
            if i + 1 < n and line[i + 1] == ">":
                tokens.append(("op", (fd, ">>")))
                i += 2
            else:
                tokens.append(("op", (fd, ">")))
                i += 1
        else:
            cur.append(c)
            in_word = True
            i += 1
    flush()
    return tokens


# --------------------------------------------------------------------------
# Parser: tokens -> list of stages {"args": [...], "redirs": [(fd, path, flags)]}
# --------------------------------------------------------------------------
def parse(tokens):
    stages = [{"args": [], "redirs": []}]
    background = False
    i = 0
    while i < len(tokens):
        kind, val = tokens[i]
        if kind == "word":
            stages[-1]["args"].append(val)
        elif val == "|":
            if not stages[-1]["args"] and not stages[-1]["redirs"]:
                raise ValueError("syntax error near unexpected token `|'")
            stages.append({"args": [], "redirs": []})
        elif val == "&":
            if i != len(tokens) - 1:
                raise ValueError("syntax error near unexpected token `&'")
            background = True
        else:  # redirection operator
            if i + 1 >= len(tokens) or tokens[i + 1][0] != "word":
                raise ValueError("syntax error: missing redirection target")
            path = tokens[i + 1][1]
            if val == "<":
                stages[-1]["redirs"].append((0, path, os.O_RDONLY))
            else:
                fd, mode = val
                flags = os.O_WRONLY | os.O_CREAT | (os.O_APPEND if mode == ">>" else os.O_TRUNC)
                stages[-1]["redirs"].append((fd, path, flags))
            i += 1
        i += 1
    if not stages[-1]["args"] and not stages[-1]["redirs"]:
        raise ValueError("syntax error: unexpected end of input")
    return stages, background


# --------------------------------------------------------------------------
# Builtins
# --------------------------------------------------------------------------
def do_exit(args):
    try:
        code = int(args[0]) if args else 0
    except ValueError:
        code = 2
    raise SystemExit(code)


def do_echo(args):
    print(" ".join(args))
    return 0


def do_pwd(args):
    print(os.getcwd())
    return 0


def do_cd(args):
    target = args[0] if args else "~"
    try:
        os.chdir(os.path.expanduser(target))
        return 0
    except FileNotFoundError:
        print(f"cd: {target}: No such file or directory", file=sys.stderr)
    except NotADirectoryError:
        print(f"cd: {target}: Not a directory", file=sys.stderr)
    except PermissionError:
        print(f"cd: {target}: Permission denied", file=sys.stderr)
    return 1


def do_type(args):
    status = 0
    for name in args:
        if name in BUILTINS:
            print(f"{name} is a shell builtin")
        elif path := shutil.which(name):
            print(f"{name} is {path}")
        else:
            print(f"{name}: not found")
            status = 1
    return status


def do_history(args):
    global last_appended
    total = readline.get_current_history_length()
    if args and args[0] in ("-r", "-w", "-a") and len(args) > 1:
        flag, path = args[0], args[1]
        try:
            if flag == "-r":
                readline.read_history_file(path)
            elif flag == "-w":
                readline.write_history_file(path)
            else:
                readline.append_history_file(total - last_appended, path)
                last_appended = total
        except OSError as e:
            print(f"history: {path}: {e.strerror}", file=sys.stderr)
            return 1
        return 0
    start = 1
    if args:
        try:
            start = max(1, total - int(args[0]) + 1)
        except ValueError:
            print(f"history: {args[0]}: numeric argument required", file=sys.stderr)
            return 1
    for idx in range(start, total + 1):
        print(f"{idx:5d}  {readline.get_history_item(idx)}")
    return 0


def do_declare(args):
    status, show, export, names = 0, False, False, []
    for a in args:
        if a.startswith("-") and len(a) > 1 and not names:
            for ch in a[1:]:
                if ch == "p":
                    show = True
                elif ch == "x":
                    export = True
                else:
                    print(f"declare: -{ch}: invalid option", file=sys.stderr)
                    return 2
        else:
            names.append(a)

    if show:
        for t in names or sorted(variables):
            name = t.split("=")[0]
            if name in variables or name in os.environ:
                flag = "-x" if name in os.environ else "--"
                value = get_var(name)
                for ch in '\\"$`':
                    value = value.replace(ch, "\\" + ch)
                print(f'declare {flag} {name}="{value}"')
            else:
                print(f"declare: {name}: not found", file=sys.stderr)
                status = 1
        return status

    for item in names:
        name, eq, value = item.partition("=")
        if not NAME_RE.fullmatch(name):
            print(f"declare: `{item}': not a valid identifier", file=sys.stderr)
            status = 1
            continue
        if eq:
            set_var(name, value)
        elif name not in variables:
            variables[name] = ""
        if export:
            os.environ[name] = variables[name]
    return status


def update_jobs():
    """Non-blocking check of which background processes have finished."""
    for job in jobs:
        for pid in job["pids"]:
            if pid in job["done"]:
                continue
            try:
                if os.waitpid(pid, os.WNOHANG)[0] == pid:
                    job["done"].add(pid)
            except ChildProcessError:
                job["done"].add(pid)


def job_lines(only_done):
    """Format job lines (markers are based on the full job list); drop finished jobs."""
    update_jobs()
    lines = []
    for idx, job in enumerate(jobs):
        marker = "+" if idx == len(jobs) - 1 else "-" if idx == len(jobs) - 2 else " "
        finished = len(job["done"]) == len(job["pids"])
        if only_done and not finished:
            continue
        status, cmd = ("Done", job["cmd"]) if finished else ("Running", job["cmd"] + " &")
        lines.append(f"[{job['id']}]{marker}  {status:<24}{cmd}")
    jobs[:] = [j for j in jobs if len(j["done"]) != len(j["pids"])]  # reap finished
    return lines


def do_jobs(args):
    for line in job_lines(only_done=False):
        print(line)
    return 0


def do_complete(args):
    status = 0
    if len(args) >= 2 and args[0] == "-p":
        for name in args[1:]:
            if name in completions:
                print(f"complete -C '{completions[name]}' {name}")
            else:
                print(f"complete: {name}: no completion specification")
                status = 1
    elif len(args) >= 3 and args[0] == "-C":
        for name in args[2:]:
            completions[name] = args[1]
    elif len(args) >= 2 and args[0] == "-r":
        for name in args[1:]:
            if completions.pop(name, None) is None:
                print(f"complete: {name}: no completion specification")
                status = 1
    else:
        print("complete: usage: complete [-p name] [-C command name] [-r name]", file=sys.stderr)
        status = 2
    return status


BUILTIN_FUNCS = {
    "exit": do_exit, "echo": do_echo, "pwd": do_pwd,
    "cd": do_cd, "type": do_type, "history": do_history,
    "complete": do_complete, "jobs": do_jobs, "declare": do_declare,
}


# --------------------------------------------------------------------------
# Redirection helpers
# --------------------------------------------------------------------------
def apply_redirs(redirs):
    sys.stdout.flush()
    sys.stderr.flush()
    for fd, path, flags in redirs:
        try:
            new_fd = os.open(path, flags, 0o644)
        except OSError as e:
            print(f"{path}: {e.strerror}", file=sys.stderr)
            return False
        os.dup2(new_fd, fd)
        os.close(new_fd)
    return True


@contextmanager
def redirected(redirs):
    """Temporarily apply redirections in the shell process (for single builtins)."""
    sys.stdout.flush()
    sys.stderr.flush()
    saved = {fd: os.dup(fd) for fd in (0, 1, 2)}
    try:
        yield apply_redirs(redirs)
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        for fd, s in saved.items():
            os.dup2(s, fd)
            os.close(s)


# --------------------------------------------------------------------------
# Execution
# --------------------------------------------------------------------------
def run_stage(args):
    """Run one command inside a forked child; returns an exit status."""
    if not args:
        return 0
    if args[0] in BUILTIN_FUNCS:
        return BUILTIN_FUNCS[args[0]](args[1:])
    try:
        os.execvp(args[0], args)
    except FileNotFoundError:
        print(f"{args[0]}: command not found", file=sys.stderr)
        return 127
    except PermissionError:
        print(f"{args[0]}: Permission denied", file=sys.stderr)
        return 126
    except OSError as e:
        print(f"{args[0]}: {e.strerror}", file=sys.stderr)
        return 126


def execute(stages, background=False, cmd=""):
    # A lone builtin runs in the shell process so cd/exit/history affect the shell.
    if (not background and len(stages) == 1 and stages[0]["args"]
            and stages[0]["args"][0] in BUILTIN_FUNCS):
        st = stages[0]
        with redirected(st["redirs"]) as ok:
            if ok:
                BUILTIN_FUNCS[st["args"][0]](st["args"][1:])
        return

    sys.stdout.flush()
    sys.stderr.flush()
    n = len(stages)
    pipes = [os.pipe() for _ in range(n - 1)]
    pids = []

    for i, st in enumerate(stages):
        pid = os.fork()
        if pid == 0:  # child
            code = 1
            try:
                if background:
                    os.setpgid(0, 0)
                    if i == 0 and not any(r[0] == 0 for r in st["redirs"]):
                        nul = os.open(os.devnull, os.O_RDONLY)
                        os.dup2(nul, 0)
                        os.close(nul)
                if i > 0:
                    os.dup2(pipes[i - 1][0], 0)
                if i < n - 1:
                    os.dup2(pipes[i][1], 1)
                for r, w in pipes:
                    os.close(r)
                    os.close(w)
                if apply_redirs(st["redirs"]):  # redirections override pipes
                    code = run_stage(st["args"])
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else 0
            except BaseException:
                code = 1
            finally:
                try:
                    sys.stdout.flush()
                    sys.stderr.flush()
                finally:
                    os._exit(code)
        pids.append(pid)

    for r, w in pipes:
        os.close(r)
        os.close(w)
    if background:
        job_id = max((j["id"] for j in jobs), default=0) + 1
        jobs.append({"id": job_id, "pids": pids, "cmd": cmd, "done": set()})
        print(f"[{job_id}] {pids[-1]}")
        return
    for pid in pids:
        os.waitpid(pid, 0)


# --------------------------------------------------------------------------
# Tab completion (commands for the first word, files afterwards)
# --------------------------------------------------------------------------
def all_commands():
    names = set(BUILTINS)
    for d in os.environ.get("PATH", "").split(os.pathsep):
        try:
            for f in os.listdir(d):
                full = os.path.join(d, f)
                if os.path.isfile(full) and os.access(full, os.X_OK):
                    names.add(f)
        except OSError:
            continue
    return names


def programmable_matches(cmd, text, begin):
    """Run a `complete -C` script: COMP_LINE/COMP_POINT in env, args = cmd, word, previous word."""
    line = readline.get_line_buffer()
    point = len(line)
    before = line[:begin].split()
    prev = before[-1] if before else ""
    env = dict(os.environ, COMP_LINE=line, COMP_POINT=str(point))
    try:
        result = subprocess.run(
            shlex.split(completions[cmd]) + [cmd, text, prev],
            env=env, capture_output=True, text=True,
        )
    except (OSError, ValueError):
        return []
    return sorted(l for l in result.stdout.splitlines() if l)


def compute_matches(text):
    line = readline.get_line_buffer()
    begin = readline.get_begidx()
    words = line[:begin].split()
    if not words:
        matches = sorted(c for c in all_commands() if c.startswith(text))
    elif words[0] in completions:
        matches = programmable_matches(words[0], text, begin)
    else:
        dirname, base = os.path.split(text)
        try:
            entries = os.listdir(dirname or ".")
        except OSError:
            entries = []
        matches = []
        for f in sorted(entries):
            if f.startswith(base):
                p = os.path.join(dirname, f)
                matches.append(p + "/" if os.path.isdir(p) else p)
    # Exactly one match: finish it with a space (directories end in "/" instead).
    if len(matches) == 1 and not matches[0].endswith("/"):
        matches[0] += " "
    return matches


_current_matches = []


def completer(text, state):
    global _current_matches
    if state == 0:  # compute once per Tab press, not once per candidate
        _current_matches = compute_matches(text)
    return _current_matches[state] if state < len(_current_matches) else None


def setup_readline():
    readline.set_completer_delims(" \t\n")
    readline.set_completer(completer)
    if "libedit" in (readline.__doc__ or ""):
        readline.parse_and_bind("bind ^I rl_complete")
    else:
        readline.parse_and_bind("tab: complete")
    histfile = os.environ.get("HISTFILE")
    if histfile and os.path.exists(histfile):
        try:
            readline.read_history_file(histfile)
        except OSError:
            pass


def save_history():
    histfile = os.environ.get("HISTFILE")
    if histfile:
        try:
            readline.write_history_file(histfile)
        except OSError:
            pass


# --------------------------------------------------------------------------
def main():
    global last_appended
    setup_readline()
    last_appended = readline.get_current_history_length()

    while True:
        for note in job_lines(only_done=True):  # report finished background jobs
            print(note)
        hist_len = readline.get_current_history_length()
        try:
            line = input("$ ")
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            continue

        if not line.strip():
            continue
        # On a terminal, input() already records the line; only add it ourselves if it didn't.
        if readline.get_current_history_length() == hist_len:
            readline.add_history(line)

        try:
            stages, bg = parse(tokenize(line))
        except ValueError as e:
            print(f"shell: {e}", file=sys.stderr)
            continue

        if (len(stages) == 1 and not bg and stages[0]["args"]
                and all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", a, re.S) for a in stages[0]["args"])):
            for a in stages[0]["args"]:
                set_var(*a.split("=", 1))
            continue

        try:
            execute(stages, bg, line.strip()[:-1].rstrip() if bg else line.strip())
        except SystemExit as e:
            save_history()
            sys.exit(e.code)

    save_history()


if __name__ == "__main__":
    main()