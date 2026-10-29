import sys


def main():
    # TODO: Uncomment the code below to pass the first stage
    # sys.stdout.write("$ ")
    while True:

        print("$ ", end="") # It prints $ sign to indicate the shell prompt
        command = input() # takes str input from user
        
        if command == "exit": #if user types exit, the program will terminate
            break

        elif command.startswith("type"): #if user types type, echo or exit, it will print the message
            cmd = command[5:] # Extract the command after "type "

            if cmd in ["echo", "exit", "type"]:
                print(f"{cmd} is a shell builtin") #prints the message

            elif cmd in ["grep"]:
                print(f"{cmd} is /usr/bin/grep") #prints the message

            else:
                print(f"{cmd}: not found") #prints the message
        
        elif command.startswith("echo "): #if user types echo, it will print the message
            message = command[5:] # Extract the message after "echo "
            print(message) #prints the message
            
        
        else:
            print(f"{command}: command not found") #else it will print command not found message


if __name__ == "__main__":
    main()
