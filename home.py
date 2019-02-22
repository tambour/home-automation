'''
Home automation using raspberry pi
'''
import os
import sys
import time
import traceback
import subprocess

COLE_MAC = '00:00:00:00:00:00'
MONI_MAC = '11:11:11:11:11:11'
TEST_MAC = '70:ef:00:4a:cf:1f'

COLE_IP = '193.168.1.200'
MONI_IP = '193.168.1.200'
TEST_IP = '192.168.0.208'

INTERFACE = 'wlx00c0ca97a345'
TIMEOUT = 120

class Person():
    def __init__(self, name, mac, ip):
        self.name = name
        self.mac  = mac
        self.ip   = ip
        self.home = False
        self.home_time   = time.time()
        self.home_count  = 0
        self.leave_time  = time.time()
        self.leave_count = 0
        self.timestamp   = time.time()

class Status():
    def __init__(self):
        self.dark = False
        self.lights_on = False
        self.someone_home = False
        self.everyone_home = False
        self.longest_idle = -1

def turn_on_lights(status):
    '''
    turn on the lights
    '''
    print('lights on!')
    status.lights_on = True
    #proc = subprocess.Popen(['hue', 'lights', '3', 'on'], stdout=subprocess.PIPE)
    #out, err = proc.communicate()
    return

def turn_off_lights(status):
    '''
    turn off the lights
    '''
    print('lights off!')
    status.lights_on = False
    #proc = subprocess.Popen(['hue', 'lights', '3', 'off'], stdout=subprocess.PIPE)
    #out, err = proc.communicate()
    return


def detect_newcomer(members):
    '''
    ping devices and update member status
    '''

    #packets = sniff(timeout=2, iface=INTERFACE)

    # check for MAC
    # for packet in packets:
    #     for member in members:
    #         if (not member.home) and (member.mac in packet.summary()):
    #             # someone is home!
    #             print('{} is home!'.format(member.name))
    #             member.timestamp = time.time()
    #             member.home = True
    #             return member

    # try pinging
    for member in members:
        if not member.home:
            proc = subprocess.Popen(['ping', member.ip, '-c', '1', '-w', '1'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = proc.communicate()
            if '0 received' not in out:
                # member responded to ping!
                member.home = True
                member.home_count += 1
                member.timestamp = time.time()
                member.home_time = time.time()
                print('{} is home! count: {}, duration: {}'.format(member.name, member.home_count, round(member.home_time - member.leave_time, 2)))
                return member

    return None

def heartbeat(members):
    '''
    monitor for continued presence of devices
    '''
    for member in members:
        if member.home:
            proc = subprocess.Popen(['ping', member.ip, '-c', '1', '-w', '1'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = proc.communicate()
            if '0 received' not in out:
                # member responded to ping!
                last_timestamp = member.timestamp
                member.timestamp = time.time()
                #print('pinged {}: {}'.format(member.name, round(member.timestamp - last_timestamp, 2)))

def darkness_comes():
    '''
    return true if the sun has set
    '''
    return True

def update(status, members):
    '''
    check member status to set program state
    '''
    status.someone_home = False
    for member in members:
        if member.home:
            status.someone_home = True

    status.everyone_home = True
    for member in members:
        if not member.home:
            status.everyone_home = False

def main():
    '''
    main state machine
    '''

    #os.system('sudo ifconfig {} down'.format(INTERFACE))
    #os.system('sudo iwconfig {} mode monitor'.format(INTERFACE))
    #os.system('sudo ifconfig {} up'.format(INTERFACE))

    #members = [Person('Cole', COLE_MAC), Person('Monica', MONI_MAC)]
    members = [Person('Danny', TEST_MAC, TEST_IP)]
    status = Status()

    while True:
        try:

            # check for darkness
            status.dark = darkness_comes()

            # no one home
            if not status.someone_home:

                # turn off lights if they're on
                if status.lights_on:
                    turn_off_lights(status)

                # check for someone to arrive
                newcomer = detect_newcomer(members)
                if newcomer:
                    update(status, members)
                    if status.dark:
                        # turn on lights if it's dark outside
                        turn_on_lights(status)

            # everyone home
            elif status.everyone_home:

                # check for someone to leave
                heartbeat(members)
                for member in members:
                    if member.home:
                        if time.time() - member.timestamp > TIMEOUT:
                            # member left
                            member.home = False
                            member.leave_count += 1
                            member.leave_time = time.time()
                            print('{} has left! count: {}, duration: {}'.format(member.name, member.leave_count, round(member.leave_time - member.home_time, 2)))
                            update(status, members)

            # someone home
            elif status.someone_home:
                
                # check for someone to leave
                heartbeat(members)
                for member in members:
                    if member.home:
                        if time.time() - member.timestamp > TIMEOUT:
                            # member left
                            member.home = False
                            member.leave_count += 1
                            member.leave_time = time.time()
                            print('{} has left! count: {}, duration: {}'.format(member.name, member.leave_count, round(member.leave_time - member.home_time, 2)))
                            update(status, members)
                            if not status.someone_home:
                                # turn off lights if no one is home
                                turn_off_lights(status)

                # check for someone to arrive
                newcomer = detect_newcomer(members)
                if newcomer:
                    update(status, members)

            for member in members:
                print('{}: {}'.format(member.name, round(time.time() - member.timestamp, 2)))
                if (time.time() - member.timestamp) > status.longest_idle:
                    status.longest_idle = time.time() - member.timestamp

            time.sleep(4)

        except KeyboardInterrupt:
            print('\n')
            for member in members:
                if member.home:
                    print('{}: {}'.format(member.name, round(time.time() - member.timestamp, 2)))
            print('Longest idle: {}'.format(round(status.longest_idle, 2)))
            print('Sun down:  {}'.format(status.dark))
            print('Lights on: {}'.format(status.lights_on))
            print('\n')
            sys.exit(0)

        except:
            traceback.print_exc()


if __name__ == '__main__':
    main()
