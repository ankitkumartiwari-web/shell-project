
import os
import shlex
import shutil
import subprocess
import sys

BUILTINS = {"echo", "cd", "pwd", "type", "exit"}
LAST_STATUS = 0


def expand_variables(text):
    """Expand environment variables such as $HOME and ${PATH}."""
    return os.path.expandvars(text)


def parse_command(text):
    """Parse a command while preserving quoted arguments."""
    lexer = shlex.shlex(text, posix=True, punctuation_chars="<>")
    lexer.whitespace_split = True
    lexer.commenters = ""
    tokens = list(lexer)

    args = []
    stdin_file = None
    stdout_file = None
    stderr_file = None
    append_stdout = False
    append_stderr = False

    i = 0
    while i < len(tokens):
        token = tokens[i]

        if token in ("<", ">", ">>", "2>", "2>>"):
            if i + 1 >= len(tokens):
                raise ValueError(f"Missing filename after {token}")

            filename = tokens[i + 1]

            if token == "<":
                stdin_file = filename
            elif token == ">":
                stdout_file = filename
            elif token == ">>":
                stdout_file = filename
                append_stdout = True
            elif token == "2>":
                stderr_file = filename
            elif token == "2>>":
                stderr_file = filename
                append_stderr = True

            i += 2
        elif token == "2" and i + 1 < len(tokens) and tokens[i + 1] in (">", ">>"):
            op = "2" + tokens[i + 1]
            if i + 2 >= len(tokens):
                raise ValueError(f"Missing filename after {op}")
            stderr_file = tokens[i + 2]
            append_stderr = op == "2>>"
            i += 3
        else:
            args.append(token)
            i += 1

    return args, stdin_file, stdout_file, stderr_file, append_stdout, append_stderr


def run_builtin(args):
    """Run a builtin in the current shell process."""
    global LAST_STATUS

    name = args[0]

    if name == "echo":
        print(" ".join(args[1:]))
        return 0

    if name == "pwd":
        print(os.getcwd())
        return 0

    if name == "cd":
        path = args[1] if len(args) > 1 else "~"
        path = os.path.expanduser(path)

        try:
            os.chdir(path)
            return 0
        except OSError as error:
            print(f"cd: {path}: {error.strerror}", file=sys.stderr)
            return 1

    if name == "type":
        if len(args) < 2:
            print("type: missing operand", file=sys.stderr)
            return 1

        for item in args[1:]:
            if item in BUILTINS:
                print(f"{item} is a shell builtin")
            elif path := shutil.which(item):
                print(f"{item} is {path}")
            else:
                print(f"{item}: not found")
        return 0

    if name == "exit":
        try:
            status = int(args[1]) if len(args) > 1 else LAST_STATUS
        except ValueError:
            print(f"exit: {args[1]}: numeric argument required", file=sys.stderr)
            status = 2
        raise SystemExit(status)

    return 127


def run_pipeline(text):
    """Execute commands connected by pipes."""
    commands = [parse_command(part) for part in text.split("|")]

    if any(not command[0] for command in commands):
        raise ValueError("Empty command in pipeline")

    # Run a standalone builtin in this process so cd changes our directory.
    if len(commands) == 1 and commands[0][0][0] in BUILTINS:
        args, in_path, out_path, err_path, append_out, append_err = commands[0]

        # Redirection for standalone builtins.
        old_stdin, old_stdout, old_stderr = sys.stdin, sys.stdout, sys.stderr
        opened = []

        try:
            if in_path:
                f = open(in_path, "r", encoding="utf-8")
                opened.append(f)
                sys.stdin = f

            if out_path:
                f = open(out_path, "a" if append_out else "w", encoding="utf-8")
                opened.append(f)
                sys.stdout = f

            if err_path:
                f = open(err_path, "a" if append_err else "w", encoding="utf-8")
                opened.append(f)
                sys.stderr = f

            return run_builtin(args)
        finally:
            sys.stdin, sys.stdout, sys.stderr = old_stdin, old_stdout, old_stderr
            for f in opened:
                f.close()

    processes = []
    previous_pipe = None
    opened = []

    try:
        for index, command in enumerate(commands):
            args, in_path, out_path, err_path, append_out, append_err = command

            stdin = previous_pipe
            stdout = subprocess.PIPE if index < len(commands) - 1 else None
            stderr = None

            if in_path:
                f = open(in_path, "r", encoding="utf-8")
                opened.append(f)
                stdin = f

            if out_path:
                f = open(out_path, "a" if append_out else "w", encoding="utf-8")
                opened.append(f)
                stdout = f

            if err_path:
                f = open(err_path, "a" if append_err else "w", encoding="utf-8")
                opened.append(f)
                stderr = f

            if args[0] in BUILTINS:
                # Basic builtin support inside a pipeline.
                if args[0] == "echo":
                    executable = [sys.executable, "-c",
                                  "import sys; print(' '.join(sys.argv[1:]))", *args[1:]]
                elif args[0] == "pwd":
                    executable = [sys.executable, "-c",
                                  "import os; print(os.getcwd())"]
                elif args[0] == "type":
                    print("type is a shell builtin", file=sys.stderr)
                    return 1
                else:
                    print(f"{args[0]}: cannot run in a pipeline", file=sys.stderr)
                    return 1
            else:
                if not shutil.which(args[0]):
                    print(f"{args[0]}: command not found", file=sys.stderr)
                    return 127
                executable = args

            process = subprocess.Popen(
                executable, stdin=stdin, stdout=stdout, stderr=stderr
            )
            processes.append(process)

            if previous_pipe is not None:
                previous_pipe.close()

            previous_pipe = process.stdout

        statuses = [process.wait() for process in processes]
        return statuses[-1] if statuses else 0

    finally:
        for f in opened:
            f.close()


def split_operators(text):
    """Split ;, &&, and || outside quoted strings."""
    lexer = shlex.shlex(text, posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    lexer.commenters = ""
    tokens = list(lexer)

    result = []
    current = []

    for token in tokens:
        if token in (";", "&&", "||"):
            result.append((" ".join(current), token))
            current = []
        else:
            current.append(token)

    result.append((" ".join(current), None))
    return result


def main():
    global LAST_STATUS

    while True:
        try:
            line = input("$ ")
        except EOFError:
            print()
            break

        if not line.strip():
            continue

        try:
            # Preserve operators and quoted arguments when parsing.
            parts = split_operators(line)
            previous_operator = None

            for command_text, operator in parts:
                should_run = (
                    previous_operator is None
                    or previous_operator == ";"
                    or (previous_operator == "&&" and LAST_STATUS == 0)
                    or (previous_operator == "||" and LAST_STATUS != 0)
                )

                if should_run and command_text.strip():
                    expanded = expand_variables(command_text)
                    LAST_STATUS = run_pipeline(expanded)

                previous_operator = operator

        except SystemExit as error:
            return error.code
        except (OSError, ValueError) as error:
            print(f"shell: {error}", file=sys.stderr)
            LAST_STATUS = 1


if __name__ == "__main__":
    main()
