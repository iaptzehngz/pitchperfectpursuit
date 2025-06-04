import os
import subprocess
import time
import zmq
import obsws_python as obs # https://github.com/aatikturk/obsws-python

HOST = "127.0.0.1"
PORT_MANOEUVRE = 5555
PORT_STREAM = 6666

def communicate_xp(i):
    with zmq.Context() as c:
        with c.socket(zmq.PUSH) as s:
            s.connect(f'tcp://{HOST}:{PORT_MANOEUVRE}')
            s.send_json(i)
        with c.socket(zmq.PULL) as s:
            s.bind(f'tcp://{HOST}:{PORT_STREAM}')
            s.recv_json()

def main():
    for i in range(7):
        subprocess.run(['start', f'steam://run/2014780'], shell=True)
        communicate_xp(i)

if __name__ == "__main__":
    main()