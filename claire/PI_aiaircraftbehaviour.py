from XPPython3 import xp
from XPPython3.utils import commands
import math
import numpy as np
import wave
import socket
import pickle
import time
import subprocess

HOST = '127.0.0.1'
PORT = 8888
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((HOST, PORT))

class PythonInterface:
    def XPluginStart(self):
        self.Name = 'adaptive training'
        self.Sig = 'stsh.atg'
        self.Desc = 'simulates aircraft movements adaptively'

        return self.Name, self.Sig, self.Desc

    def XPluginStop(self):
        xp.destroyFlightLoop(self.bankID)
        xp.destroyFlightLoop(self.spawnID)
        xp.destroyFlightLoop(self.dataID)
        xp.destroyFlightLoop(self.changepitchID)
        xp.destroyFlightLoop(self.quitID)

        if self.diff != 0 and self.diff != 8:
            PATH_TO_RECORDING = r"C:\Users\user\Videos\video.mkv"
            PATH_TO_VLC = r"C:\Program Files\VideoLAN\VLC\vlc.exe"
            subprocess.Popen([PATH_TO_VLC, '--play-and-exit', PATH_TO_RECORDING])
        sock.close()

    def XPluginEnable(self):
        # DATAREFS
        self.aioverrideDR = xp.findDataRef('sim/operation/override/override_plane_ai_autopilot')
        self.aiheadingDR = xp.findDataRef('sim/multiplayer/position/plane1_psi')
        self.airollDR = xp.findDataRef('sim/multiplayer/position/plane1_phi')
        self.aipitchDR = xp.findDataRef('sim/multiplayer/position/plane1_the')
        self.aispeedDR_x = xp.findDataRef('sim/multiplayer/position/plane1_v_x')
        self.aispeedDR_y = xp.findDataRef('sim/multiplayer/position/plane1_v_y')
        self.aispeedDR_z = xp.findDataRef('sim/multiplayer/position/plane1_v_z')
        self.aipos_xDR = xp.findDataRef('sim/multiplayer/position/plane1_x')
        self.aipos_yDR = xp.findDataRef('sim/multiplayer/position/plane1_y')
        self.aipos_zDR = xp.findDataRef('sim/multiplayer/position/plane1_z')
        self.aipitchcontrolDR = xp.findDataRef('sim/multiplayer/controls/yoke_pitch_ratio')
        self.aiheadingcontrolDR = xp.findDataRef('sim/multiplayer/controls/yoke_heading_ratio')
        self.airollcontrolDR = xp.findDataRef('sim/multiplayer/controls/yoke_roll_ratio')
        self.aitrimDR = xp.findDataRef('sim/multiplayer/controls/elevator_trim')
        self.aithrottleDR = xp.findDataRef('sim/multiplayer/position/plane1_throttle')
        self.headingDR = xp.findDataRef('sim/flightmodel/position/psi')
        self.pitchDR = xp.findDataRef('sim/flightmodel/position/theta')
        self.rollDR = xp.findDataRef('sim/flightmodel/position/phi')
        self.pos_xDR = xp.findDataRef('sim/flightmodel/position/local_x')
        self.pos_yDR = xp.findDataRef('sim/flightmodel/position/local_y')
        self.pos_zDR = xp.findDataRef('sim/flightmodel/position/local_z')
        self.throttleDR = xp.findDataRef('sim/cockpit2/engine/actuators/throttle_ratio_all')
        self.pitchcontrolDR = xp.findDataRef('sim/cockpit2/controls/yoke_pitch_ratio')
        self.headingcontrolDR = xp.findDataRef('sim/cockpit2/controls/yoke_heading_ratio')
        self.rollcontrolDR = xp.findDataRef('sim/cockpit2/controls/yoke_roll_ratio')
        self.crashedDR = xp.findDataRef('sim/flightmodel2/misc/has_crashed')

        xp.setDatavi(self.aioverrideDR, [1], 1)
        xp.acquirePlanes()

        self.vars = (
                    (0, 120, 0.9, 0, 0, 'Welcome to flight training! You have 2 minutes to get familiar with the controls. Enjoy!'),
                    (1, 30, 0.9, 0, 0, 'Hold steady and fly level'),
                    (2, 30, 0.9, -5, 0, 'Try descending with the plane'),
                    (3, 30, 1, 5, 0, 'Try climbing with the plane'),
                    (4, 30, 1, 0, 30, 'Execute a gentle turn now'),
                    (5, 30, 1, 0, 50, 'Now execute a steep turn'),
                    (6, 30, 1, -5, 30, 'Can you try a descending turn?'),
                    (7, 30, 1, 5, 30, 'Do a climbing turn!'),
                    (8, 30, 1, 5, 30, 'Track the enemy plane as best as you can')
                    )
        
        #spawn function
        self.spawned = False

        #bank function
        self.bank_scheduled = False
        self.direction = 1
        self.t_bank = 0
        self.reset_bank = False

        #climb function
        self.climbing = False
        self.t_climb = 0
        self.reset_climb = False

        #adaptive function
        self.diff = 1
        self.spawn_time = 0

        #performance data function
        self.ideal_pitch = 0
        self.ideal_heading = 0

        #quit function
        self.timer = 0

        #window
        self.once = False

        #schedule flight loop
        self.bankID = xp.createFlightLoop(self.rollAI)
        self.spawnID = xp.createFlightLoop(self.spawn)
        self.dataID = xp.createFlightLoop(self.performance_data)
        self.changepitchID = xp.createFlightLoop(self.pitchAI)
        self.quitID = xp.createFlightLoop(self.quit)

        xp.scheduleFlightLoop(self.spawnID, 0.05, 1)
        xp.scheduleFlightLoop(self.dataID, 0.05, 1)
        xp.scheduleFlightLoop(self.quitID, 0.02, 1)
        
        return 1
    
    
    def spawn(self, sinceLast, elapsedSim, counter, refCon):
        ai_heading = xp.getDataf(self.aiheadingDR)
        ai_roll = xp.getDataf(self.airollDR)
        ai_speedx = xp.getDataf(self.aispeedDR_x)
        ai_speedy = xp.getDataf(self.aispeedDR_y)
        ai_speedz = xp.getDataf(self.aispeedDR_z)
        distance_behind = 350

        if not self.spawned:
            ai_posx = -10923
            ai_posy = 350
            ai_posz = 17443
            xp.setDatad(self.aipos_xDR, ai_posx)
            xp.setDatad(self.aipos_yDR, ai_posy)
            xp.setDatad(self.aipos_zDR, ai_posz)

            posx = ai_posx-distance_behind*math.sin(math.radians(ai_heading))
            posz = ai_posz+distance_behind*math.cos(math.radians(ai_heading))
            
            net_speed = ((ai_speedx**2)+(ai_speedy**2)+(ai_speedz**2))**0.5
            lat , lon, alt = xp.localToWorld(posx, ai_posy, posz)

            data = sock.recv(1024)
            self.diff = pickle.loads(data)[0]
            self.direction = pickle.loads(data)[1]
            xp.log(f'DIFFICULTY {self.diff}')

            if self.diff == 0:
                if ai_heading < 180:
                    heading = ai_heading + 180
                else:
                    heading = ai_heading - 180
                xp.placeUserAtLocation(lat, lon, 3000, heading, net_speed)
            else:
                xp.placeUserAtLocation(lat, lon, alt, ai_heading, net_speed)

            state = self.vars[self.diff][-1]
            xp.speakString(f'{state}')

            time.sleep(3)
            if self.diff in (2,3,6,7,8):
                self.climbing = True

            if self.diff in (4,5,6,7,8):
                self.bank_scheduled = True

            if self.diff in (1,2,3,4,5,6,7,8):
                sock.send(pickle.dumps('start recording'))

            xp.scheduleFlightLoop(self.bankID, 0.02, 1)
            xp.scheduleFlightLoop(self.changepitchID, 0.02, 1)
            self.spawned = True

        return 0.05
    
    def pitchAI(self, sinceLast, elapsedSim, counter, refCon):
        speed_y = xp.getDataf(self.aispeedDR_y)
      
        timing = self.vars[self.diff][1]
        throttle = self.vars[self.diff][2]
        target_speed = self.vars[self.diff][3]

        if self.climbing:
            #if not self.reset_climb:
                #self.t_climb = -sinceLast
                #self.reset_climb = True

            if self.t_climb > timing-15:
                self.climbing = False
                self.t_climb = -sinceLast
                self.diff = 1

            self.t_climb += sinceLast

        ratio = math.tanh((target_speed - speed_y)/20)
        xp.setDatavf(self.aipitchcontrolDR, [ratio], 1)
        xp.setDatavf(self.aithrottleDR, [throttle], 0)

        return 0.02
        
    def rollAI(self, sinceLast, elapsedSim, counter, refCon):
        roll = xp.getDataf(self.airollDR)
        target_roll = self.vars[self.diff][4]*self.direction
        timing = self.vars[self.diff][1]
        ratio = 0

        if self.bank_scheduled:
            #if not self.reset_bank:
                #self.t_bank = -sinceLast
                #self.reset_bank = True

            if self.t_bank > timing-15:
                self.diff = 1
                self.bank_scheduled = False
                self.t_bank = -sinceLast

            self.t_bank += sinceLast
            xp.log(f'{self.t_bank}: roll ratio: {ratio}, roll:{xp.getDataf(self.airollDR)} altitude:{xp.getDataf(self.aipos_yDR)}')

        roll = math.tanh(target_roll - roll)
        xp.setDatavf(self.airollcontrolDR, [ratio], 1)
        
        return 0.02
    
    def performance_data(self, sinceLast, elapsedSim, counter, refCon):
        my_pitch = xp.getDataf(self.pitchDR)
        my_heading = xp.getDataf(self.headingDR)
        my_pos = np.array([xp.getDataf(self.pos_xDR),
                           xp.getDataf(self.pos_yDR),
                           xp.getDataf(self.pos_zDR)])
        ai_pos = np.array([xp.getDataf(self.aipos_xDR),
                              xp.getDataf(self.aipos_yDR),
                              xp.getDataf(self.aipos_zDR)])
        
        #DISTANCE
        vector_diff = ai_pos - my_pos
        distance_apart = np.linalg.norm(vector_diff)
        
        #PITCH DEV
        y_axis = np.array((0, 1, 0))
        vector_diff_unit = vector_diff/distance_apart
        self.ideal_pitch = 90 - math.degrees(math.acos(np.dot(vector_diff_unit, y_axis)))
        pitch_dev = my_pitch - self.ideal_pitch 

        #HEADING DEV
        proj_vector_diff = vector_diff_unit - np.dot(vector_diff_unit, y_axis) * y_axis
        v_proj_unit = proj_vector_diff/np.linalg.norm(proj_vector_diff)
        z_axis = np.array((0, 0, -1))
        self.ideal_heading = math.degrees(math.acos(np.dot(v_proj_unit, z_axis)))
        cross = np.cross(v_proj_unit, z_axis)

        if cross[1] < 0:
            self.ideal_heading = 360 - self.ideal_heading
        heading_dev = my_heading - self.ideal_heading
        if heading_dev > 180:
            heading_dev = heading_dev - 360
        elif heading_dev < -180:
            heading_dev = heading_dev + 360

        #COMPILE
        perf_data = [elapsedSim, distance_apart, pitch_dev, heading_dev]
        sock.send(pickle.dumps(perf_data))

        return 0.05
    
    def quit(self, sinceLast, elapsedSim, counter, refCon):
        crashed = xp.getDatai(self.crashedDR)
        if self.spawned:
            self.timer += sinceLast
            if self.timer >= self.vars[self.diff][1]+9 or crashed == 1:
                if self.diff != 0 and self.diff != 8:
                    sock.send(pickle.dumps('stop recording'))
                sock.send(pickle.dumps('end'))
        return 0.02

    def XPluginDisable(self):
        pass

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
        pass
