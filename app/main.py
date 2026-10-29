import sys


def main():
    # TODO: Uncomment the code below to pass the first stage
    # sys.stdout.write("$ ")
    while True:
        if command == "exit":
            break
        print("$ ", end="")
        command = input()
        print(f"{command}: command not found")
        


if __name__ == "__main__":
    main()
