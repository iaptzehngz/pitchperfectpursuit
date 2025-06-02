from XPPython3 import xp
import math
import numpy as np
import wave
import copy

class PythonInterface:
    def XPluginStart(self):
        self.Name = 'adaptive training'
        self.Sig = 'stsh.atg'
        self.Desc = 'simulates aircraft movements adaptively'

        self.commandRef = xp.createCommand('custom/sound/gunshot', 'makes a gun sound')
        xp.registerCommandHandler(self.commandRef, self.Callback, 1, None)
        return self.Name, self.Sig, self.Desc

    def XPluginStop(self):
        xp.destroyFlightLoop(self.bankID)
        xp.destroyFlightLoop(self.spawnID)
        xp.destroyFlightLoop(self.adaptiveID)
        xp.destroyFlightLoop(self.climbID)
        xp.destroyFlightLoop(self.pitch_constantID)
        xp.destroyFlightLoop(self.dataID)
        xp.destroyFlightLoop(self.autopilotID)
        xp.unregisterCommandHandler(self.commandRef, self.Callback,1, None)
        xp.destroyWindow(self.windowID)

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

        xp.setDatavi(self.aioverrideDR, [1], 1)
        xp.acquirePlanes()

        self.diff = 1

        #spawn function
        self.spawned = False

        #bank function
        self.bank_scheduled = False
        self.direction = 1
        self.t_bank = 0

        #climb function
        self.climbing = False
        self.t_climb = 0

        #autopilot function
        self.lost = 0
        self.leveling = 0
        self.current_hdgdev = 0
        self.prev_hdgdev = 0

        #performance data function
        self.data = []
        self.ideal_pitch = 0
        self.ideal_heading = 0

        #window
        self.windowID = xp.createWindowEx(left=50, top=530, right=300, bottom=500, visible=1, draw=self.states)

        #schedule flight loop
        self.bankID = xp.createFlightLoop(self.bank_ai)
        self.pitch_constantID = xp.createFlightLoop(self.pitch_constant)
        self.spawnID = xp.createFlightLoop(self.spawn)
        self.climbID = xp.createFlightLoop(self.climb)
        self.adaptiveID = xp.createFlightLoop(self.adaptive)
        self.autopilotID = xp.createFlightLoop(self.autopilot)
        self.dataID = xp.createFlightLoop(self.performance_data)

        xp.scheduleFlightLoop(self.spawnID, 0.05, 1)
        xp.scheduleFlightLoop(self.adaptiveID, 40, 120)
        xp.scheduleFlightLoop(self.pitch_constantID, 0.02, 1)
        xp.scheduleFlightLoop(self.dataID, 0.02, 1)
        xp.scheduleFlightLoop(self.climbID, 0.02, 1)
        xp.scheduleFlightLoop(self.bankID, 0.02, 1)
        #xp.scheduleFlightLoop(self.autopilotID, 0.02, 120)

        return 1
    
    
    def spawn(self, sinceLast, elapsedSim, counter, refCon):
        ai_posx = xp.getDatad(self.aipos_xDR)
        ai_posy = xp.getDatad(self.aipos_yDR)
        ai_posz = xp.getDatad(self.aipos_zDR)
        ai_heading = xp.getDataf(self.aiheadingDR)
        ai_roll = xp.getDataf(self.airollDR)
        ai_speedx = xp.getDataf(self.aispeedDR_x)
        ai_speedy = xp.getDataf(self.aispeedDR_y)
        ai_speedz = xp.getDataf(self.aispeedDR_z)
        distance_behind = 250

        if not self.spawned:
            posx = ai_posx-distance_behind*math.sin(math.radians(ai_heading))
            posz = ai_posz+distance_behind*math.cos(math.radians(ai_heading))
            
            net_speed = ((ai_speedx**2)+(ai_speedy**2)+(ai_speedz**2))**0.5
            lat , lon, alt = xp.localToWorld(posx, ai_posy, posz)
            xp.placeUserAtLocation(lat, lon, alt, ai_heading, net_speed)
            self.spawned = True

        if not self.bank_scheduled:
            if ai_roll > 0:
                xp.setDatavf(self.airollcontrolDR, [-0.2], 1)
            elif ai_roll < 0:
                xp.setDatavf(self.airollcontrolDR, [0.2], 1)

        return 0.05
    
    def pitch_constant (self, sinceLast, elapsedSim, counter, refCon):
        ai_pitch = xp.getDataf(self.aipitchDR)
        ratio = 0.1
        if self.bank_scheduled:
            ratio = 1
        if not self.climbing:
            ratio = math.tanh(4-ai_pitch)

        xp.setDatavf(self.aipitchcontrolDR, [ratio], 1)

        return 0.02

    def climb(self, sinceLast, elapsedSim, counter, refCon):
        pitch = xp.getDataf(self.aipitchDR)
        ratio = 0.3
        throttle = 0.9
        time = 15

        if self.diff == 6 or self.diff == 7:
            time = 20

        if self.climbing:
            if self.t_climb <= time:
                if self.diff == 2 or self.diff == 6:
                    if pitch < 10:
                        ratio = 0.1
                    elif pitch > 10:
                        ratio = -0.2
                    throttle = 1
                elif self.diff == 3 or self.diff == 7:
                    if pitch < -7:
                        ratio = 0.1
                    elif pitch > -7:
                        ratio = -0.3
                
            else:
                self.climbing = False
                self.t_climb = -sinceLast

            self.t_climb += sinceLast

            xp.setDatavf(self.aipitchcontrolDR, [ratio], 1)
            xp.setDatavf(self.aithrottleDR, [throttle], 0)
            xp.log(f'[{self.t_climb}] control: {ratio}, pitch:{xp.getDataf(self.aipitchDR)}, altitude: {xp.getDataf(self.aipos_yDR)}')
        
        return 0.02
        
    def bank_ai(self, sinceLast, elapsedSim, counter, refCon):
        target_roll = 25*self.direction
        roll = xp.getDataf(self.airollDR)
        time = 15

        if self.diff == 4 and self.direction == -1 or self.diff == 6 or self.diff == 7:
            time = 20
        elif self.diff == 5:
            target_roll = 50*self.direction

        if self.bank_scheduled:
            if self.t_bank <= time:
                if roll < target_roll:
                    roll_ratio = 0.2
                elif roll > target_roll:
                    roll_ratio = -0.2
            else:
                roll_ratio = 0
                self.bank_scheduled = False
                self.t_bank = -sinceLast
                self.direction *= -1
        
            xp.setDatavf(self.airollcontrolDR, [roll_ratio], 1)
            xp.log(f'{self.t_bank}: roll ratio: {roll_ratio}, roll:{xp.getDataf(self.airollDR)} altitude:{xp.getDataf(self.aipos_yDR)}')
            
            self.t_bank += sinceLast

        return 0.02
    
    
    def autopilot(self, sinceLast, elapsedSim, counter, refCon):
        self.current_pitchdev = self.data[-1][2]
        self.current_hdgdev = self.data[-1][3]
        if len(self.data) > 1:
            self.prev_hdgdev = self.data[-2][3]
            self.prev_pitchdev = self.data[-2][2]
        heading_limit = 30
        pitch_limit = 10

        ai_y = xp.getDataf(self.aipos_yDR)
        my_y = xp.getDataf(self.pos_yDR)
        y_dev = ai_y - my_y
        pitch = xp.getDataf(self.pitchDR)
        roll = xp.getDataf(self.rollDR)

        pitch_ratio = 0
        roll_ratio = 0
       
        if abs(self.current_pitchdev) > pitch_limit or abs(self.current_hdgdev) > heading_limit:
            self.lost += sinceLast
            self.level = 0
        elif abs(y_dev) < 300 and abs(self.current_hdgdev) < 5:
            self.levelling += sinceLast
            if self.levelling >= 5:
                self.lost = 0
                self.diff = 1
                xp.log('autopilot turning off')
       
        if self.lost >= 8:

            if pitch < -30:
                pitch_ratio = 1

                if roll > 0:
                    roll_ratio = -1
                elif roll < 0:
                    roll_ratio = 1

            else:
                if self.current_pitchdev > 0:
                    pitch_ratio = 0.3
                elif self.current_pitchdev < 0:
                    pitch_ratio = 0.6
 

                if abs(self.current_hdgdev) > 0:
                    dedt = (self.current_hdgdev - self.prev_hdgdev)/sinceLast
                    roll_ratio = -0.0016*self.current_hdgdev - 0.00018*self.current_hdgdev*sinceLast - 0.02*dedt

            #in case autopilot doesnt work, self.spawn will reposition you directly
            #self.spawned = False 
            xp.setDataf(self.pitchcontrolDR, pitch_ratio)
            xp.setDataf(self.rollcontrolDR, roll_ratio)
           

            xp.log(f'pitch dev:{self.current_pitchdev}, pitch ratio:{pitch_ratio}|heading dev:{self.current_hdgdev}, roll ratio{roll_ratio}')
           
        return 0.02
    
    def adaptive(self, sinceLast, elapsedSim, counter, refCon):
        self.diff = 3
        self.climbing = True
        
        #self.diff = min(max(self.diff+self.ass_diff(elapsedSim)[0], 1), 7)

        #if self.diff == 2 or self.diff == 3:
         #   xp.log('prepare to pitch')
          #  self.climbing = True
        #elif self.diff == 4 or self.diff == 5:
         #   xp.log('prepare to bank')
          #  xp.scheduleFlightLoop(self.bankID, 0.02, 1)
           # self.bank_scheduled = True

        #xp.log(f'DIFFICULTY {self.diff}')

        return 40

    
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
        self.data += [[elapsedSim, distance_apart, pitch_dev, heading_dev],]

        return 0.02
    
    def ass_diff(self, elapsedSim):
        #GET DATA
        dataset_raw = list(filter(lambda x : x[0]>=elapsedSim - 25, self.data))
        dataset = copy.deepcopy(dataset_raw)
        for i in range(len(dataset)-1):
            dataset[i][0] = dataset_raw [i+1][0] - dataset_raw[i][0] 

        def percentage_time(data, lower, upper, index):
            within_range = list(filter(lambda x:lower <= x[index] <= upper, data))
            time_within_range = 0
            for i in range(len(within_range)):
                time_within_range += within_range[i][0]
            percentage_time = (time_within_range/30)*100

            if percentage_time >= 75:
                diff = 2
            elif percentage_time >=50:
                diff = 1
            elif percentage_time >= 20:
                diff = 0
            else:
                diff = -1
            
            return diff
        
        distance_diff = percentage_time(dataset, 152.4, 457.2, 1)
        pitch_diff = percentage_time(dataset, -5, 5, 2)
        heading_diff = percentage_time(dataset, -5, 5, 3)
    
        net_diff = min(distance_diff[0], pitch_diff[0], heading_diff[0])

        return net_diff
    
    def states(self, windowID, refCon):
        if self.diff == 1:
            state = 'Hold steady now'
        elif self.diff == 2:
            state = 'Prepare to climb'
        elif self.diff == 3:
            state = 'Descending'
        elif self.diff == 4:
            state = 'Looks like we are banking'
        elif self.diff == 5:
            state = 'Steep bank coming up'
        elif self.diff == 6:
            state = 'Execute a climbing turn'            
        elif self.diff == 7:
            state = 'Now do a descending turn'

        (left, top, right, bottom) = xp.getWindowGeometry(windowID)
        
        xp.drawTranslucentDarkBox(left, top, right, bottom)
        color = 1.0, 1.0, 1.0

        desc = f'{state}'

        xp.drawString(color, left + 8, top - 18, desc, 0, xp.Font_Proportional)
        

    def Callback(self, commandRef, phase, refCon):
        if phase == 0:
            w = wave.open('Resources/sounds/weapons/gunshot.wav')
            xp.playWaveOnBus(w, loop = 0, audioType = 7)
        return 1

    def XPluginDisable(self):
        pass

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
        pass
