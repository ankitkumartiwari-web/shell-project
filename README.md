# Shell Project — Build Your Own Shell in Python

[![CodeCrafters Progress](https://backend.codecrafters.io/progress/shell/4ff02cdc-6425-4380-ae4b-32d223f54930)](https://app.codecrafters.io/users/ankitkumartiwari-web?r=2qF)

A Unix-like command-line shell implemented in Python as part of the [CodeCrafters Build Your Own Shell challenge](https://app.codecrafters.io/courses/shell/overview).

The project explores how command-line shells work internally, including command parsing, built-in commands, external process execution, pipes, and input/output redirection.

## Features

- **Interactive REPL:** Continuously accepts and processes user commands.
- **Built-in Commands:** Implements shell commands such as `echo`, `cd`, `pwd`, `type`, and `exit`.
- **External Command Execution:** Locates and executes external programs available in the system PATH.
- **Command Parsing:** Handles command arguments and quoted strings.
- **Input/Output Redirection:** Supports redirecting command input and output.
- **Pipes:** Enables communication between commands through pipelines.

*Note: Adjust this list to match the features actually implemented and tested in your code.*

## Tech Stack

- Python
- `subprocess`
- `shlex`
- `os`
- `shutil`

## Project Structure

```text
shell-project/
├── app/
│   └── main.py
├── your_program.sh
├── pyproject.toml
├── README.md
└── .gitignore
```

## Getting Started

### Prerequisites

- Python
- Git
- uv

### Clone the Repository

```bash
git clone https://github.com/ankitkumartiwari-web/shell-project.git
cd shell-project
```

### Run the Shell

```bash
./your_program.sh
```

On Windows, use the appropriate shell environment configured for the project.

## Example Commands

```bash
$ pwd
$ echo Hello World
$ cd ..
$ type echo
$ ls
$ cat file.txt
```

## Learning Outcomes

Building this project helped me understand:

- How a shell reads and interprets user commands.
- How built-in commands differ from external programs.
- How processes are created and executed.
- How command arguments and quoted strings are parsed.
- How pipes and redirection work in command-line environments.

## Acknowledgements

Built as part of the [CodeCrafters Build Your Own Shell challenge](https://codecrafters.io/).

Thanks to the CodeCrafters team for creating an excellent hands-on learning experience.

## Author

**Ankit Kumar Tiwari**

- GitHub: [@ankitkumartiwari-web](https://github.com/ankitkumartiwari-web)
- Project: [shell-project](https://github.com/ankitkumartiwari-web/shell-project)