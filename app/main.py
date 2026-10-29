import os
import sys
import shutil
import subprocess
import shlex


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

            if cmd in ["echo", "exit", "type", "pwd", "cd"]: #if user types echo, exit, type or pwd, it will print the message
                print(f"{cmd} is a shell builtin") #prints the message

            elif path := shutil.which(cmd): # shutil.which() is used to find the path of the command
                print(f"{cmd} is {path}") 
            
            else:
                print(f"{cmd}: not found") #prints the message

        
        elif command.startswith("echo "):
            message = shlex.split(command)[1:]
            print(" ".join(message))


        elif command == "pwd": #if user types pwd, it will print the current working directory
            print(os.getcwd()) #prints the current working directory


        elif command.startswith("cd "): #if user types cd, it will change the current working directory
            path = command[3:] # Extract the path after "cd "
            
            if path == "~":
                path = os.path.expanduser("~")

            try:
                os.chdir(path) #changes the current working directory
            except FileNotFoundError:
                print(f"{path}: No such file or directory") #prints the message if the path is not found


        elif shutil.which(shlex.split(command)[0]): #if the command is found in the system path, it will execute the command using subprocess.run()
            subprocess.run(shlex.split(command))   # it will execute the command using subprocess.run() and print the output as well as the error message if any

        
        else:
            print(f"{command}: command not found") #else it will print command not found message


if __name__ == "__main__":
    main()
