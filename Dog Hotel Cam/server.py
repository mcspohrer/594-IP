from socket import *
import _thread as t
import threading as tng
import json
import time
import cv2 as cv2
import numpy as np

clients_lock = tng.Lock()
tricks_lock = tng.Lock()
room_lock = tng.Lock()
lock = tng.Lock()
registry = {}
room = {}
tricks = {}
client_ports = {}


def get_dog(client, name):
    # gets the information of a particular dog from the registry and
    # sends it to the client
    dog = {}
    lock.acquire()
    if name not in registry:
        client.send('160'.encode())
        lock.release()
        return
    else:
        dog[name] = registry[name]
        dog = json.dumps(dog).encode()
        client.send(dog)
    lock.release()
    return dog


def play(client):
    # receives the name of the dog from the client
    # gets the dog's information
    # adds the trick the user wants to see the pup do to tricks (to do)
    name = client.recv(1024).decode()
    get_dog(client, name)
    trick = client.recv(1024).decode()
    tricks_lock.acquire()
    tricks[name].append(trick)
    tricks_lock.release()
    if trick in tricks[name]:
        client.send("960".encode())
    else:
        client.send("161".encode())


def watch(client):
    # opens a UDP socket with the client and streams live video to it

    name = client.recv(1024).decode()
    fake_ip = client.recv(1024).decode()
    get_dog(client, name)
    room_lock.acquire()
    if name not in room:
        # if the pup doesn't have a virtual viewing room started for it
        # yet, tis starts it and creates a list of tricks for it to do
        # then spawns a thread to handle the room

        tricks_lock.acquire()
        tricks[name] = []
        tricks_lock.release()

        udp = socket(AF_INET, SOCK_DGRAM)
        room[name] = [udp]
        t.start_new_thread(stream_video, (name,))

    # puts the new client's ip and port in a list and appends it to the
    # virtual viewing room
    c_ip = client.recv(1024).decode()
    c_port = int(client.recv(1024).decode())
    room[name].append([c_ip, fake_ip, c_port])
    room_lock.release()


def stream_video(name):
    # if a room hasn't been started for a pup, this starts it
    # then starts sending video frames
    # for now it is sending simulated video as the camera on
    # my computer is broken

    # cam = cv2.VideoCapture(-1)
    frame = 0

    # gets the udp socket from rooms corresponding to the
    # pup wanting to be watched
    udp = room[name][0]
    # currentFrame = 0
    while True:
        #   ret, frame = cam.read()
        #  if not ret:
        #      print("Can't receive frame")
        #      break
        #  gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        #  cv2.imshow('frame', gray)
        #  if cv2.waitKey(1) == ord('q'):
        #      break

        #  currentFrame += 1
        frame = str(frame)

        # if there is a trick to be done by the named pup it is done
        if len(tricks[name]) != 0:
            tricks_lock.acquire()
            trick = name + ' ' + tricks[name][0] + '!'
            for i in room[name][1:]:
                udp.sendto(trick.encode(), (i[0], i[2]))
            tricks[name] = tricks[name][1:]
            tricks_lock.release()
            time.sleep(0.5)

        # iterates through the pups list of clients watching
        # and sends them the frame
        for i in room[name][1:]:
            udp.sendto(frame.encode(), (i[0], i[2]))
        time.sleep(0.5)

        # increments the frame and reconverts it to a str to be sent
        frame = int(frame)
        frame += 1

        room_lock.acquire()
        if len(room[name]) == 1:
            # if no one is watching there is no need to send the data
            del room[name]
            room_lock.release()
            t.exit_thread()
        else:
            room_lock.release()


def check_registry(client):
    # converts the pups' names to a list which is converted to bytes
    # and sent to the client to be displayed
    lock.acquire()
    names = json.dumps(registry)
    lock.release()
    client.send(names.encode())


def remove(client):
    # removes the dog the user wants removed from the registry
    # returns 940 on success
    # returns 140 on the name not being found
    name = client.recv(1024).decode()
    if name in registry:
        lock.acquire()
        del registry[name]
        success = '940'
        lock.release()
    else:
        success = '140'
    client.send(success.encode())


def add_trick(client):
    # adds checks/adds a trick to a puppy's repertoire
    # returns success code (930)
    # returns 131 if already known
    # returns 130 if the dog was not in the registry
    lock.acquire()
    name = client.recv(1024).decode()
    trick = client.recv(1024).decode()
    if name in registry:
        if trick not in registry[name]:
            registry[name].append(trick)
            success = '930'
        else:
            success = '131'
    else:
        success = '130'
    lock.release()
    client.send(success.encode())


def add_pup(client):
    # gets the lock to registry, receives the name from client to add
    # if already used, responds sends an error code (110) to the client
    # indicating as such otherwise sends a success code (910).
    while True:
        lock.acquire()
        name = client.recv(1024).decode()
        if name in registry.keys():
            client.send('110'.encode())
            lock.release()
        else:
            client.send('910'.encode())
            break

    # receives the new entry from the client to add to the registry
    entry = client.recv(1024).decode()
    entry = json.loads(entry)
    registry.update(entry)
    lock.release()
    if name in registry.keys():
        client.send('911'.encode())
    else:
        client.send('111'.encode())


def threaded(client, addr):
    # spins off a thread once a client chooses an action
    funcs = {1: add_pup,
             2: watch,
             3: add_trick,
             4: remove,
             5: check_registry,
             6: play
             }

    # routes control to the appropriate function
    while True:
        # in a separate thread the server asks the client
        # what they want to do by sending an encoded string
        # and gets the response from the client
        try:
            response = int(client.recv(1024).decode())
            client.send('heartbeat'.encode())
            if response == 0:
                save_registry()
                print("Client at: ", addr[0], ':', addr[1],
                      "has gone to another dog park.")
                break
            else:
                # calls the function specified by the user
                funcs[response](client)
        except ValueError:
            break
        except KeyboardInterrupt:
            print("Client at: ", addr[0], ':', addr[1],
                  "has gone to another dog park.")
            save_registry()
            break
        except ConnectionResetError:
            print("Client at: ", addr[0], ':', addr[1],
                  "has gone to another dog park.")
            save_registry()
            break
    client.close()


def save_registry():
    # writes the registry to the file as registry.txt
    f = open('registry.txt', 'w')
    for k in registry:
        to_write = k
        for t in registry[k]:
            to_write = to_write + ' ' + t
        to_write = to_write + '\n'
        f.write(to_write)
    f.close()


def read_registry():
    # reads loads the registry from registry.txt
    # returns if the file is not found
    try:
        f = open('registry.txt', 'r')
        l = f.readline().split()
        while l:
            registry[l[0]] = []
            for i in l[1:]:
                registry[l[0]].append(i)
            l = f.readline().split()
    except FileNotFoundError:
        return


def room_daemon(d_client, d_addr):
    # oof, this is a doozy!
    # manages the connections with the client
    old_port = []
    fake_ip = -1
    while True:
        try:
            # receives the active ports from the clients and checks them
            # against what is in the room channel. If there is a port in
            # the room info but not in the active port list, it is removed
            ports = d_client.recv(1024).decode()
            if ports == '1000':
                #if the client exited
                d_client.close()
                t.exit_thread()
            ports = json.loads(ports)
            # fake_ip is used for localhost
            fake_ip = ports[1]
            ip = ports[0]
            # ports first two indices are fake_ip and ip
            ports = ports[2:]

            ports.sort()
            old_port.sort()

            if ports != old_port:
                # the active ports here is the same as before then don't bother checking
                room_lock.acquire()
                for name in room.keys():
                    # for all the rooms check if they are still sending to active watchers
                    num_rooms = len(room[name])
                    for i in range(1, num_rooms):
                        if (room[name][i][2] not in ports) and (fake_ip == room[name][i][1]):
                            # if the port isn't active for this ip then remove it
                            room[name].pop(i)
                            i -= 1
                room_lock.release()
            old_port = ports
        except IndexError:
            if room_lock.locked():
                room_lock.release()
            continue
        except ConnectionResetError:
            print('Client with (fake) ip: ' + fake_ip + ' has left')
            for name in room.keys():
                for i in range(1, len(room[name])):
                    if fake_ip == room[name][i][1]:
                        del room[name][i]
            if room_lock.locked():
                room_lock.release()
            d_client.close()
            t.exit_thread()
        except json.decoder.JSONDecodeError:
            print('Client with (fake) ip: ' + fake_ip + ' has left')
            for name in room.keys():
                for i in range(1, len(room[name])):
                    if fake_ip == room[name][i][1]:
                        del room[name][i]
            if room_lock.locked():
                room_lock.release()
            d_client.close()
            t.exit_thread()
        finally:
            if room_lock.locked():
                room_lock.release()


def Main():
    host = '127.0.1.1'
    daemon, server_socket, client, port = 0, 0, 0, 0
    addr = [0, 0]

    try:
        # create a TCP socket and bind it to the server
        server_socket = socket(AF_INET, SOCK_STREAM)
        server_socket.bind((host, port))
        s_port = server_socket.getsockname()[1]
        print("host IP: ", host)
        print("socket bound to host: ", s_port)
        print("When you start the client, enter that port number in when prompted.")

        read_registry()
        # make server listen on the socket, accept when a client tries to connect
        server_socket.listen(100)

        # creates a daemon to maintain the rooms and whatnot
        daemon = socket(AF_INET, SOCK_STREAM)
        daemon.bind((host, port))
        d_port = str(daemon.getsockname()[1])
        daemon.listen(100)
        # infinite loop to always have the server listening, accepts SYN from client
        # prints the client's address and port then spawns a thread to handle the
        # with the client
        while True:
            client, addr = server_socket.accept()
            client.send(d_port.encode())
            print("Connected to: ", addr[0], ':', addr[1])
            d_client, d_addr = daemon.accept()
            print("Connected to Daemon: ", d_addr[0], ':', d_addr[1])

            t.start_new_thread(threaded, (client, addr,))
            t.start_new_thread(room_daemon, (d_client, d_addr,))

    except KeyboardInterrupt:
        print('Exiting...')
        client.close()
        if daemon != 0:
            daemon.close()
        if server_socket != 0:
            server_socket.close()
        exit()
    except ConnectionResetError:
        print("The programmer must have been pretty bad because "
              "the the connection was reset. Please let your pup "
              "know this is not its fault!\nClient: " + str(addr[0])
              + ":" + str(addr[1]))
        client.close()
        if daemon != 0:
            daemon.close()
    finally:
        save_registry()


if __name__ == '__main__':
    Main()
