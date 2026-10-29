def parse_command(text):
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

        # Handle input and output redirection
        if token in ("<", ">", ">>", "1>", "1>>", "2>", "2>>"):
            if i + 1 >= len(tokens):
                raise ValueError(f"Missing filename after {token}")

            filename = tokens[i + 1]

            if token == "<":
                stdin_file = filename
            elif token in (">", "1>"):
                stdout_file = filename
            elif token in (">>", "1>>"):
                stdout_file = filename
                append_stdout = True
            elif token == "2>":
                stderr_file = filename
            elif token == "2>>":
                stderr_file = filename
                append_stderr = True

            i += 2

        # Handle tokenized forms such as 1 followed by >
        elif token in ("1", "2") and i + 1 < len(tokens) and tokens[i + 1] in (">", ">>"):
            operator = token + tokens[i + 1]

            if i + 2 >= len(tokens):
                raise ValueError(f"Missing filename after {operator}")

            filename = tokens[i + 2]

            if token == "1":
                stdout_file = filename
                append_stdout = tokens[i + 1] == ">>"
            else:
                stderr_file = filename
                append_stderr = tokens[i + 1] == ">>"

            i += 3

        else:
            args.append(token)
            i += 1

    return (
        args,
        stdin_file,
        stdout_file,
        stderr_file,
        append_stdout,
        append_stderr,
    )