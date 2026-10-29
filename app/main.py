import sys


def main():
    # TODO: Uncomment the code below to pass the first stage
    # sys.stdout.write("$ ")
    while True:

        print("$ ", end="") # It prints $ sign to indicate the shell prompt
        command = input() # takes str input from user
        
        if command == "exit": #if user types exit, the program will terminate
            break

        
        elif command.startswith("echo "): #if user types echo, it will print the message
            message = command[5:] # Extract the message after "echo "
            print(message) #prints the message

        elif command in ["type", "echo", "exit"]: #if user types type, echo or exit, it will print the message
            print(f"{command} is a shell builtin")

        else:
            print(f"{command}: command not found") #else it will print command not found message


if __name__ == "__main__":
    main()
