'''
Home automation using raspberry pi
'''
import os
import sys
import time
import datetime
import traceback
import subprocess

PRINT_INTERVAL = 10

COLE_MAC = '00:00:00:00:00:00'
MONICA_MAC = '11:11:11:11:11:11'
DANNY_MAC = '70:ef:00:4a:cf:1f'
RACHEL_MAC = '04:4B:ED:56:E4:F3'

COLE_IP   = '10.0.0.20'
MONICA_IP = '10.0.0.10'
RACHEL_IP = '10.0.0.8'
DANNY_IP  = '10.0.0.5'

INTERFACE = 'wlx00c0ca97a345'
TIMEOUT = 300

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
        self.longest_idle = -1

class Status():
    def __init__(self):
        self.dark = False
        self.lights_on = False
        self.someone_home = False
        self.everyone_home = False
        self.last_print = -10


def turn_on_lights(status):
    '''
    turn on the lights
    '''
    event('[*] lights on!')
    status.lights_on = True

    try:
        proc = subprocess.Popen(['hue', 'lights', '3', 'on'], stdout=subprocess.PIPE)
        out, err = proc.communicate()
    except:
        # wrong lights or not connected
        pass

    return

def turn_off_lights(status):
    '''
    turn off the lights
    '''
    event('[*] lights off!')
    status.lights_on = False
    try:
        proc = subprocess.Popen(['hue', 'lights', '3', 'off'], stdout=subprocess.PIPE)
        out, err = proc.communicate()
    except:
        # wrong lights or not connected
        pass

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
    #             debug('{} is home!'.format(member.name))
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
                event('[*] {} is home! count: {}, duration: {}'.format(member.name, member.home_count, round(member.home_time - member.leave_time, 2)))
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
                #debug('pinged {}: {}'.format(member.name, round(member.timestamp - last_timestamp, 2)))

def darkness_comes():
    '''
    return true if the sun has set
    '''
    return True

def debug(print_str):
    print(print_str)
    f = open('./out.txt', 'a')
    f.write(print_str)
    f.close()

def event(event_str):
    print(event_str)
    f = open('./event.txt', 'a')
    f.write('[{}]: {}\n'.format(datetime.datetime.now(), event_str))
    f.close()

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
    members = [Person('Waldo', DANNY_MAC, DANNY_IP), Person('Oat', MONICA_MAC, MONICA_IP), Person('Rachel', MONICA_MAC, RACHEL_IP)]
    status = Status()

    while True:
        try:

            # print status
            if time.time() - status.last_print > PRINT_INTERVAL:
                status.last_print = time.time()
                debug('\n')
                for member in members:
                    if (time.time() - member.timestamp) > member.longest_idle:
                        member.longest_idle = round(time.time() - member.timestamp, 2)
                    debug('{}:\n  home:    {}\n  latest:  {}\n  longest: {}\n'\
                        .format(member.name, member.home, round(time.time() - member.timestamp, 2), member.longest_idle))

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
                            event('[*] {} has left! count: {}, duration: {}'.format(member.name, member.leave_count, round(member.leave_time - member.home_time, 2)))
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
                            event('[*] {} has left! count: {}, duration: {}'.format(member.name, member.leave_count, round(member.leave_time - member.home_time, 2)))
                            update(status, members)
                            if not status.someone_home:
                                # turn off lights if no one is home
                                turn_off_lights(status)

                # check for someone to arrive
                newcomer = detect_newcomer(members)
                if newcomer:
                    update(status, members)

            time.sleep(0.1)

        except KeyboardInterrupt:
            debug('\n')
            for member in members:
                if member.home:
                    debug('{}: {}'.format(member.name, round(time.time() - member.timestamp, 2)))
            debug('[*] Sun down:  {}'.format(status.dark))
            debug('[*] Lights on: {}'.format(status.lights_on))
            debug('\n')
            sys.exit(0)

        except:
            traceback.print_exc()


if __name__ == '__main__':
    main()
