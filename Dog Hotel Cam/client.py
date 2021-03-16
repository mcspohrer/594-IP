# still todo :
#  list others in the room
# send msg to a specific room

from socket import *
import _thread as t
from tkinter import *
from threading import *
import random
import json
import time
import sys

# sets a global fake ip for each client to be used for room management on localhost
ip = ''
random.seed()
temp = [127, random.randint(0, 255), random.randint(0, 255), random.randint(1, 254)]
for i in range(0, len(temp)):
    ip = ip + '.' + str(temp[i])
fake_ip = ip[1:]

room_lock = Lock()
port_lock = Lock()
rooms = {}
t_exit = 1
open_ports = []


def leave():
    t.exit()


def get_dog(s):
    # gets a dog's entry in the registry from the server
    dog = s.recv(1024).decode()
    if dog == '160':
        print("Sorry, but your dog got out! Or... we never had it "
              "to begin with, either way it's not in the registry.\n")
    else:
        dog = json.loads(dog)
    return dog


def play(s):
    # User picks certain tricks for the pup to perform
    # gets the names of all the pups the user is currently watching
    room_lock.acquire()
    names = list(rooms.keys())
    try:
        print("Which dog would you like to play with?"
              " These are the pups you're currently watching:")
        n = len(names)
        for l in range(n):
            print(str(l) + ") " + names[l])
        choice = int(input())

        s.send(names[choice].encode())
        dog = get_dog(s)
        # gets all of the tricks known by the pup
        tricks = dog[names[choice]]
        print("Which trick would you like to have your pup do?"
              " Please enter the number corresponding to the trick.")

        n = len(tricks)
        if n == 0:
            # if no tricks are known by the pup then just return
            print("Bad Human! You need to teach your pup some tricks!\n")
            return
        for k in range(n):
            # list the tricks
            print(str(k) + ") " + tricks[k])
        choice = int(input())
        # send the user''s choice to the server
        s.send(tricks[choice].encode())
        room_lock.release()
        # receive server's response
        success = s.recv(1024).decode()
        if success == '960':
            print("Success! The trick has been added to the list of"
                  " tricks to be called!")
        else:
            print("Something went horribly wrong!")
    except IndexError:
        print("Bad Human! Bad Entry!")
        room_lock.release()
        return


def watch(s):
    # gets the dog's information the user would like to interact with and
    # spins off a thread to display the video
    name = input("What is the name of the dog you'd like to watch?\n")
    s.send(name.encode())
    s.send(fake_ip.encode())
    dog = get_dog(s)
    room_lock.acquire()
    if name not in rooms:
        rooms[name] = t.start_new_thread(video, (s, dog,))
    else:
        print("You are already watching that one!")
    room_lock.release()
    return


def video(s, dog):
    # establishes a udp connection with the server to
    # receive and display video. The video is just simulated for now
    name = ''
    # opens a UDP socket and sends its information over the open TCP
    # socket to the server
    try:
        name = list(dog.keys())[0]
    except AttributeError:
        print("Bad Human! You entered invalid input!")
        t.exit_thread()

    # create udp socket and sends its info to the server
    udp = socket(AF_INET, SOCK_DGRAM)
    c_ip = s.getsockname()[0]
    host = (c_ip, 0)
    udp.bind(host)
    c_port = udp.getsockname()[1]
    s.send(c_ip.encode())
    s.send(str(c_port).encode())

    # adds the port to the active ports list
    port_lock.acquire()
    open_ports.append(c_port)
    port_lock.release()

    # creates a separate window for streaming
    win = Tk()
    win.title(name)
    win.geometry('800x480')
    label = Label(win, text="Here's " + name + "!")
    label.place(x=350, y=200)
    # button didn't work (I'm guessing because of some concurrency issue)
    # button = Button(win, text="Quit", command=leave)
    # button.grid(row=1, column=3, padx=4)
    win.update()

    print("\nHit the 'x' button in the top right to exit stream")

    while True:
        try:
            # receives the frame from the server over the udp socket
            data, addr = udp.recvfrom(1024)
            data = data.decode()
            # print(data)
            # updates the tkinter window
            label["text"] = data
            win.update()
        except TclError:
            # removes this udp port from the active ports list
            # closes the udp socket and exits the thread
            port_lock.acquire()
            open_ports.remove(c_port)
            port_lock.release()
            del rooms[name]
            udp.close()
            t.exit_thread()


def check_registry(s):
    # displays the names of the pups on the registry
    names = s.recv(1024)
    names = json.loads(names)
    print("The dogs currently in the registry: ")
    for p in names:
        print("Pupper's name: ", p)


def remove(s):
    # user inputs the name of the dog to remove from the registry
    # and sends it to the server
    name = input("what is the name of the dog you'd like removed?\n")
    s.send(name.encode())
    success = s.recv(1024).decode()
    if success == '940':
        print("Your dog was removed from the registry.\n")
    else:
        print("Your dog's name was not in the registry.\n")


def add_trick(s):
    # add a trick to your pups repertoire
    name = input("What is your pup's name?\n")
    s.send(name.encode())
    trick = input("What is your pup's new trick?\n")
    s.send(trick.encode())
    success = s.recv(1024).decode()
    if success == '930':
        print("The trick was added.\n")
    elif success == '131':
        print("Your pup already knew that trick.\n")
    else:
        print("That puppy was not in our registry. Please add "
              "it before changing its tricks.\n")


def add_pup(s):
    # gets the pups information from the client to add to the registry
    entry = {}
    trick = []

    # gets the name of the Pup
    name = input("What is the pup's name?\n")

    while True:
        # user inputs the tricks the dog knows
        cont = input("Does your little one know any(more) tricks (y/n)?\n")
        if cont == 'n':
            break
        trick.append(input("What is the name of the trick?\n"))

    while True:
        # checks if the name is already taken
        s.send(name.encode())
        good_name = s.recv(1024).decode()
        if good_name == '110':
            name = input("Unfortunately your dog's name is already being used. "
                         "Please alter the name in some way (add a last name?).\n"
                         "Enter the new name?\n")
        else:
            break

    # converts to a json str then bytes to be sent to the server
    entry[name] = trick
    entry = json.dumps(entry).encode()
    s.send(entry)

    success = s.recv(1024).decode()
    if success == '911':
        print("Your pup was added to the registry!")
    else:
        print("Bad Human! Ya basically peed inside! (Or the programmer is no good)!")


def what_to_do():
    # asks the user what they would like to do.
    while True:
        try:
            print("\nWhat would you like to do? Please enter the number "
                  "of what you would like to do.\n1) Add a pup\n2) Check "
                  "in on a pup\n3) Your pup learned a new trick\n4) Remove "
                  "a pup\n5) Check the registry")
            if len(rooms.keys()) != 0:
                print("6) Play with a pup")
            print("0) Exit")
            response = input()

            if not response or int(response) < 0 or int(response) > 6:
                print("I'm not sure what you're trying to do here, bad person!"
                      "\nYou gave no response or an unacceptable one, the equivalent"
                      " of peeing inside.\nLet's try this again!")
            else:
                return response
        except ValueError:
            print("\nBad Human! Let's try that again!!")
            continue


def room_daemon(host, d_port):
    # room daemon used to talk with the server's room daemon to
    # keep the communication ports up to date
    # creates a seperate TCP socket to talk to the server's daemon
    d = -1
    try:
        d = socket(AF_INET, SOCK_STREAM)
        d.connect((host, d_port))
        d.settimeout(1)

        # adds the new TCP socket's port to the active ports list
        port_lock.acquire()
        open_ports.append(d.getsockname()[1])
        port_lock.release()

        while True:
            # every 5 seconds it sends the server a list of active ports
            # so it can manage the rooms
            try:
                ports = json.dumps(open_ports).encode()
                d.send(ports)
                time.sleep(5)
            except ConnectionResetError:
                print('Lost the server, exiting...')
                d.close()
                t.interrupt_main()
                sys.exit(0)
            except ConnectionRefusedError:
                break
            except BrokenPipeError:
                print('Lost the server, exiting...')
                break
        port_lock.acquire()
        open_ports.remove(d.getsockname()[1])
        port_lock.release()
        # letting the room daemon on the server side know this client is exiting
        d.send('1000'.encode())
        d.close()
        t.interrupt_main()
        sys.exit(0)
    except BrokenPipeError:
        if d != -1:
            d.close()
        exit()


def Main():
    # server's IP addr to connect to and its port
    host = '127.0.1.1'
    s = 0
    try:
        port = int(input("Enter the port number listed when the server was started: "))

        # connect to server on local computer
        s = socket(AF_INET, SOCK_STREAM)
        s.connect((host, port))

        # creates a list of active ports
        port_lock.acquire()
        open_ports.append(s.getsockname()[0])
        open_ports.append(fake_ip)
        open_ports.append(s.getsockname()[1])
        port_lock.release()

        # receive the port number for the room managing daemon in the server
        # opens a separate TCP socket for this client to talk to said daemon
        # spawns a thread to handle heartbeat messages from the server
        d_port = int(s.recv(1024).decode())
        t.start_new_thread(room_daemon, (host, d_port,))

        funcs = {1: add_pup,
                 2: watch,
                 3: add_trick,
                 4: remove,
                 5: check_registry,
                 6: play
                 }
        while t_exit == 1:
            try:
                heartbeat = 0
                response = what_to_do()
                s.send(response.encode())
                heartbeat = s.recv(1024).decode()

                # if user wants to quit then close the connection or
                # or if the heartbeat fails then exit
                if int(response) == 0:
                    s.send('0'.encode())
                    print("Exiting...You've been a good human!")
                    break
                elif heartbeat != 'heartbeat':
                    print("Exiting...You've been a good human!")
                    print("Server d/c'd")
                    break

                # calls the appropriate function as entered by the user
                else:
                    funcs[int(response)](s, )

            except KeyboardInterrupt:
                print('Exiting...')
                break
            except ConnectionResetError:
                print("The programmer must have been pretty bad because "
                      "the the connection was reset. Please let your pup "
                      "know this is not its fault!")
                break
            except ConnectionRefusedError:
                print('Wrong server, exiting...')
                break
            except OverflowError:
                print("Enter a valid port, huh!?! Qiut trying to break me")
                break
    except ValueError:
        print("Bad Human! You entered the wrong stuff! Shoo!")
    except ConnectionRefusedError:
        print("Your pup must have been acting up the last time "
              "because the connection was refused :(")
    except SystemExit:
        exit()
    except KeyboardInterrupt:
        print('Exiting...')
        if s != 0:
            s.close()
        exit()
    if s != 0:
        s.close()
    exit()


if __name__ == '__main__':
    Main()
