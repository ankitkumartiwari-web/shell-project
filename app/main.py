import sys


def main():
    # TODO: Uncomment the code below to pass the first stage
    # sys.stdout.write("$ ")
    while True:
        print("$ ", end="")
        command = input()
        print(f"{command}: command not found")

        if command == "exit":
            break



if __name__ == "__main__":
    main()
