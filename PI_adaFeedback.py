from XPPython3 import xp
from XPPython3.utils import commands
import math
import numpy as np
import zmq
import wave

HOST = '127.0.0.1'
PORT_STREAM = 5555
PORT_MANOEUVRE = 6666
context = zmq.Context()
sock = context.socket(zmq.PUSH)
sock.connect(f"tcp://{HOST}:{PORT_STREAM}")

rad_to_deg = 180/math.pi
xz_normal = np.array((0, 1, 0))
z_unit = np.array((0, 0, -1))

class PythonInterface:
    def __init__(self):
        self.my_plane = None
        self.ias_dataRef = None
        self.aoa_dataRef = None
        self.sideslip_dataRef = None
        self.stall_warning_dataRef = None
        self.has_crashed_dataRef = None
        self.ai_plane = None

        self.quit_command = None
        
        self.spawn_flight_loop = None
        self.elapsed_time_flight_loop = None
        self.quit_flight_loop = None
        self.straight_flight_loop = None
        self.bank_ai_flight_loop = None
        self.pitch_ai_flight_loop = None
        self.throttle_ai_flight_loop = None
        self.report_flight_loop = None

        self.loop_count = 0
        self.first_elapsedTime = 0.0
        self.elapsed_time = 0.0

        self.quit_elapsed_time = 0.0
        self.quit_first_run = True

        self.manoeuvre = None
        self.manoeuvre_roll =  0.0 #/ rad_to_deg
        self.manoeuvre_vy = 0.0
        self.manoeuvre_throttle = 0.0
        self.start_time = 10.0
        self.end_time = 25.0
        
    def XPluginStart(self):
        self.windowId = xp.createWindowEx(left=50, top=530, bottom=300, right=400,
                                          visible=1,
                                          draw=self.drawWindowCallback)
        manoeuvres = (
            ('familiarisation', 0, -1000, 1.0, 120), # fam
            ('climbing left turn', -45, 5, 1.0, 30), # pre-training
            ('straight and level flight', 0, 0, 0.75, 30),
            ('descend', 0, -5, 0.5, 30),
            ('climb', 0, 5, 1.0, 30),
            ('gentle right turn', 30, 0, 1.0, 30),
            ('steep left turn', -45, 0, 1.0, 30),
            ('descending right turn', 45, 5, 1.0, 30),
            ('climbing left turn', -45, 5, 1.0, 30),
            ('climbing right turn', 45, 5, 1.0, 30)
        )
        with context.socket(zmq.PULL) as sock_manoeuvre:
            sock_manoeuvre.bind(f"tcp://{HOST}:{PORT_MANOEUVRE}")
            manoeuvre_no = sock_manoeuvre.recv_json()
            xp.log(f'manoeuvre no. {manoeuvre_no} with flight parameters {manoeuvres[manoeuvre_no - 1]}')
            self.manoeuvre, self.manoeuvre_roll, self.manoeuvre_vy, self.manoeuvre_throttle, self.quit_elapsed_time = manoeuvres[manoeuvre_no - 1]

        self.commandRef = xp.createCommand('custom/sound/gunshot', 'makes a gun sound')
        xp.registerCommandHandler(self.commandRef, play_gunshot, 1, None)
        return "PI_stshmybae", "xppython3.ilovedsta", "Spawn aircraft and stream data"
    
    def XPluginEnable(self):
        override_ai_autopilot(plane_index=1)
        self.my_plane = Plane('sim/flightmodel/position/local_x', 
                              'sim/flightmodel/position/local_y', 
                              'sim/flightmodel/position/local_z',
                              vx_dataRef='sim/flightmodel/position/local_vx',
                              vy_dataRef='sim/flightmodel/position/local_vy',
                              vz_dataRef='sim/flightmodel/position/local_vz',
                              pitch_dataRef='sim/flightmodel/position/theta',
                              roll_dataRef='sim/flightmodel/position/phi',
                              heading_dataRef='sim/flightmodel/position/psi',
                              yoke_pitch_ratio_dataRef='sim/cockpit2/controls/yoke_pitch_ratio',
                              yoke_roll_ratio_dataRef='sim/cockpit2/controls/yoke_roll_ratio',
                              yoke_heading_ratio_dataRef='sim/cockpit2/controls/yoke_heading_ratio',
                              throttle_ratio_dataRef='sim/cockpit2/engine/actuators/throttle_ratio_all')
        self.ias_dataRef = xp.findDataRef('sim/flightmodel/position/indicated_airspeed')
        self.aoa_dataRef = xp.findDataRef('sim/flightmodel/position/alpha')
        self.sideslip_dataRef = xp.findDataRef('sim/flightmodel/position/beta')
        self.stall_warning_dataRef = xp.findDataRef('sim/flightmodel/failures/stallwarning')
        self.has_crashed_dataRef = xp.findDataRef('sim/flightmodel2/misc/has_crashed')
        self.ai_plane = Plane('sim/multiplayer/position/plane1_x', 
                              'sim/multiplayer/position/plane1_y', 
                              'sim/multiplayer/position/plane1_z',
                              vx_dataRef='sim/multiplayer/position/plane1_v_x',
                              vy_dataRef='sim/multiplayer/position/plane1_v_y',
                              vz_dataRef='sim/multiplayer/position/plane1_v_z',
                              pitch_dataRef='sim/multiplayer/position/plane1_the',
                              roll_dataRef='sim/multiplayer/position/plane1_phi',
                              heading_dataRef='sim/multiplayer/position/plane1_psi',
                              yoke_pitch_ratio_dataRef='sim/multiplayer/controls/yoke_pitch_ratio',
                              yoke_roll_ratio_dataRef='sim/multiplayer/controls/yoke_roll_ratio',
                              yoke_heading_ratio_dataRef='sim/multiplayer/controls/yoke_heading_ratio',
                              throttle_ratio_dataRef='sim/multiplayer/controls/engine_throttle_request',
                              multiplayer_plane_index=1)
        self.spawn_flight_loop = xp.createFlightLoop(self.spawnMe)
        xp.scheduleFlightLoop(self.spawn_flight_loop, -1)
        self.elapsed_time_flight_loop = xp.createFlightLoop(self.elapsedTime)
        xp.scheduleFlightLoop(self.elapsed_time_flight_loop, -1)
        self.quit_flight_loop = xp.createFlightLoop(self.quit)
        xp.scheduleFlightLoop(self.quit_flight_loop, 10)
        self.bank_ai_flight_loop = xp.createFlightLoop(self.rollAI)
        xp.scheduleFlightLoop(self.bank_ai_flight_loop, -1)
        self.pitch_ai_flight_loop = xp.createFlightLoop(self.pitchAI)
        xp.scheduleFlightLoop(self.pitch_ai_flight_loop, -1)
        self.throttle_ai_flight_loop = xp.createFlightLoop(self.thrustAI)
        xp.scheduleFlightLoop(self.throttle_ai_flight_loop, -1)
        self.report_flight_loop = xp.createFlightLoop(self.reportVars)
        xp.scheduleFlightLoop(self.report_flight_loop, -1)
        return 1
    
    def spawnMe(self, _sinceLast, _elapsedTime, _counter, _refcon):
        sock.send_json({
            'stream': "aircraft type",
            'data': xp.getDatas(xp.findDataRef('sim/aircraft/view/acf_descrip'))
            })
        sock.send_json({
            'stream': 'manoeuvre',
            'data': f'{self.manoeuvre} from {self.start_time} to {self.end_time} seconds'
            })
        
        distance_from_ai = 300

        # x and z coordinates of paya lebar air base runway 02 for terrain (lack of mountains)
        # but i need to spawn myself into an area close enough to singapore
        ai_x = -10923
        ai_y = 350
        ai_z = 17443
        self.ai_plane.position = (ai_x, ai_y, ai_z)

        ai_heading = self.ai_plane.heading
        ai_heading_rad = ai_heading / rad_to_deg

        shifted_x = ai_x - distance_from_ai * math.sin(ai_heading_rad)
        shifted_z = ai_z + distance_from_ai * math.cos(ai_heading_rad)
        lat, long, elevation = xp.localToWorld(shifted_x, ai_y, shifted_z)

        ai_speed = np.linalg.norm(self.ai_plane.velocity, ord=2)

        if self.manoeuvre == 'familiarisation':
            if ai_heading < 180:
                heading = ai_heading + 180
            else:
                heading = ai_heading - 180
            xp.placeUserAtLocation(lat, long, 3000, heading, ai_speed)
        else:
            xp.placeUserAtLocation(lat, long, elevation, ai_heading, ai_speed)
        xp.log(f'Placed user at latitude: {lat}, longitude: {long}, elevation: {elevation} with heading: {ai_heading}, speed: {ai_speed}')
        return 0
        
    def elapsedTime(self, _sinceLast, elapsedTime, _counter, _refcon):
        if self.loop_count <= 2:
            self.loop_count += 1
            self.first_elapsedTime = elapsedTime
            if self.loop_count == 2:
                sock.send_json({
                    'stream': 'recording',
                    'data': 'start'
                })
            return -1
        
        self.elapsed_time = elapsedTime - self.first_elapsedTime
        return -1
    
    def quit(self, _sinceLast, _elapsedTime, _counter, _refcon):
        if self.elapsed_time > self.quit_elapsed_time:
            if self.quit_first_run:            
                sock.send_json({
                    'stream': 'recording',
                    'data': 'stop'
                    })
                self.quit_first_run = False
            commands.find_command('sim/operation/quit').once()
        return 1
    
    def rollAI(self, _sinceLast, _elapsedTime, _counter, _refcon):
        current_roll = self.ai_plane.roll / rad_to_deg

        if self.elapsed_time > self.start_time and self.elapsed_time < self.end_time:
            difference = current_roll - self.manoeuvre_roll / rad_to_deg
            self.ai_plane.yoke_roll_ratio = math.tanh(difference) * -1
            return 0.5
                
        self.ai_plane.yoke_roll_ratio = math.tanh(current_roll) * -1
        return 1
    
    def pitchAI(self, _sinceLast, _elapsedTime, _counter, _refcon):
        vx, vy, vz = self.ai_plane.velocity

        if self.elapsed_time > self.start_time and self.elapsed_time < self.end_time:
            difference = vy - self.manoeuvre_vy
            self.ai_plane.yoke_pitch_ratio = math.tanh(difference / 20) * -1
            xp.log(f'at time {self.elapsed_time}, ai plane vy is {vy} and yoke pitch ratio is {self.ai_plane.yoke_pitch_ratio}')
            return 0.5

        self.ai_plane.yoke_pitch_ratio = math.tanh(vy / 20) * -1
        xp.log(f'at time {self.elapsed_time}, ai plane vy is {vy} and yoke pitch ratio is {self.ai_plane.yoke_pitch_ratio}')
        return 1
    
    def thrustAI(self, _sinceLast, _elaspedTime, _counter, _refcon):
        if self.elapsed_time > self.start_time and self.elapsed_time < self.end_time:
            self.ai_plane.throttle_ratio = self.manoeuvre_throtle
            xp.log(f'at time {self.elapsed_time}, throttle ratio is {self.ai_plane.throttle_ratio}')
            return 0.5
        
        self.ai_plane.throttle_ratio = 0.75
        return 1

    def thrustAISpeed(self, _sinceLast, _elapsedTime, _counter, _refcon):
        v_ai = np.linalg.norm(self.ai_plane.velocity, ord=2)
        v_ai_knots = v_ai * 1.94384
        target_v = 90
        difference = v_ai_knots - target_v

        self.ai_plane.throttle_ratio = math.tanh(difference / 4) * -0.5 + 0.5
        xp.log(f'at time {self.elapsed_time}, ai plane velocity is {v_ai_knots} and throttle ratio is {self.ai_plane.throttle_ratio}')
        return 1

    def reportVars(self, _sinceLast, _elapsedTime, _counter, _refcon):
        if not self.elapsed_time:
            return -1
        vector_diff = self.ai_plane.position - self.my_plane.position
        distance = float(np.linalg.norm(vector_diff, ord=2))
        vector_diff_unit = vector_diff / distance

        ideal_pitch = 90 - math.acos(np.dot(vector_diff_unit, xz_normal)) * rad_to_deg

        vdu_proj_xz = vector_diff_unit - np.dot(vector_diff_unit, xz_normal) * xz_normal
        vdu_proj_unit = vdu_proj_xz / np.linalg.norm(vdu_proj_xz, ord=2)
        ideal_heading = math.acos(np.dot(vdu_proj_unit, z_unit)) * rad_to_deg
        cross = np.cross(vdu_proj_unit, z_unit)
        if cross[1] < 0:
            ideal_heading = 360 - ideal_heading

        ai_v_unit = self.ai_plane.velocity / np.linalg.norm(self.ai_plane.velocity, ord=2)
        aspect_angle = math.acos((np.dot(vector_diff_unit, ai_v_unit))) * rad_to_deg

        variables = {
            't': self.elapsed_time,
            'distance': distance, 
            'aspect angle': aspect_angle,
            'pitch': self.my_plane.pitch, 'ideal pitch': ideal_pitch, 'roll': self.my_plane.roll, 'heading': self.my_plane.heading, 'ideal heading': ideal_heading,
            'angle of attack': xp.getDataf(self.aoa_dataRef), 'sideslip angle': xp.getDataf(self.sideslip_dataRef),
            'centre stick pitch ratio': self.my_plane.yoke_pitch_ratio, 'centre stick roll ratio': self.my_plane.yoke_roll_ratio, 'rudder pedal ratio': self.my_plane.yoke_heading_ratio, 'throttle ratio': self.my_plane.throttle_ratio,
            'indicated airspeed': xp.getDataf(self.ias_dataRef),
            'stall warning': xp.getDatai(self.stall_warning_dataRef)
        }

        sock.send_json({
            'stream': 'variables',
            'data': variables
            })
        
        if xp.getDatai(self.has_crashed_dataRef):
            sock.send_json({
                'stream': 'crashed',
                'data': round(self.elapsed_time, 2)
            })
            if self.quit_elapsed_time > self.elapsed_time + 2:
                self.quit_elapsed_time = self.elapsed_time + 2
                xp.log(f'plane crashed so i changed quit time to {self.quit_elapsed_time} s')
        return 0.3
    
    def drawWindowCallback(self, inWindowID, inRefcon):
        (left, top, right, bottom) = xp.getWindowGeometry(inWindowID)
        xp.drawTranslucentDarkBox(left, top, right, bottom)
        color = 1.0, 1.0, 1.0
        xp.drawString(color, left + 8, top - 18, self.manoeuvre, 0, xp.Font_Proportional)
        
    def XPluginStop(self):
        if self.quit_first_run and self.loop_count: # to stop recording when flight starts and self.quit_elapsed_time is never reached - happens when quit xplane in flight on my own
            sock.send_json({
                'stream': 'recording',
                'data': 'stop'
                })
        sock.send_json({
            'stream': 'stop',
            'data': None
            })
        sock.close()
        context.destroy()
        xp.destroyWindow(self.windowId)
        xp.unregisterCommandHandler(self.commandRef, play_gunshot, 1, None)

    def XPluginDisable(self):
        pass

def play_gunshot(commandRef, phase, refCon):
    if phase == 0:
        w = wave.open('Resources/sounds/weapons/marikita.wav')
        xp.playWaveOnBus(w, loop = 0, audioType = 7)
    return 1

def override_ai_autopilot(plane_index=None):
    if plane_index:
        dataRef = xp.findDataRef('sim/operation/override/override_plane_ai_autopilot')
        xp.setDatavi(dataRef, [1], plane_index)
        xp.log(f"overrode plane of index {plane_index} autopilot")
    else:
        raise ValueError("provide plane_index")

class Plane:
    '''Class to represent the position, velocity, orientation and primary controls of a plane in the simulator.'''
    def __init__(self, x_dataRef, y_dataRef, z_dataRef, *, 
                 vx_dataRef=None, vy_dataRef=None, vz_dataRef=None, 
                 pitch_dataRef=None, roll_dataRef=None, heading_dataRef=None, 
                 yoke_pitch_ratio_dataRef=None, yoke_roll_ratio_dataRef=None, yoke_heading_ratio_dataRef=None,
                 throttle_ratio_dataRef=None,
                 multiplayer_plane_index=None):
        self.x_dataRef = xp.findDataRef(x_dataRef)
        self.y_dataRef = xp.findDataRef(y_dataRef)
        self.z_dataRef = xp.findDataRef(z_dataRef)
        self.vx_dataRef = xp.findDataRef(vx_dataRef)
        self.vy_dataRef = xp.findDataRef(vy_dataRef)
        self.vz_dataRef = xp.findDataRef(vz_dataRef)
        self.pitch_dataRef = xp.findDataRef(pitch_dataRef) # theta
        self.roll_dataRef = xp.findDataRef(roll_dataRef) # phi
        self.heading_dataRef = xp.findDataRef(heading_dataRef) # psi
        self.yoke_pitch_ratio_dataRef = xp.findDataRef(yoke_pitch_ratio_dataRef)
        self.yoke_roll_ratio_dataRef = xp.findDataRef(yoke_roll_ratio_dataRef)
        self.yoke_heading_ratio_dataRef = xp.findDataRef(yoke_heading_ratio_dataRef)
        self.throttle_ratio_dataRef = xp.findDataRef(throttle_ratio_dataRef)
        self.multiplayer_plane_index = multiplayer_plane_index

    @property
    def position(self): # cartesian coordinates in metres
        return np.array([xp.getDatad(self.x_dataRef),
                         xp.getDatad(self.y_dataRef),
                         xp.getDatad(self.z_dataRef)])
    
    @property
    def velocity(self): # m/s not knots
        return np.array([xp.getDataf(self.vx_dataRef),
                         xp.getDataf(self.vy_dataRef),
                         xp.getDataf(self.vz_dataRef)])
    
    @property
    def pitch(self):
        return xp.getDataf(self.pitch_dataRef)

    @property
    def roll(self):
        return xp.getDataf(self.roll_dataRef)

    @property
    def heading(self):
        return xp.getDataf(self.heading_dataRef)

    def _get_datavf(self, ref):
        if self.multiplayer_plane_index:
            values = []
            xp.getDatavf(ref, values)
            return values[self.multiplayer_plane_index]
        return xp.getDataf(ref)

    def _set_datavf(self, ref, ratio):
        if self.multiplayer_plane_index:
            xp.setDatavf(ref, [ratio], self.multiplayer_plane_index)
        else:
            raise Exception(f'Why do you want to manipulate your own controls through code?')
    
    @property
    def yoke_pitch_ratio(self):
        return self._get_datavf(self.yoke_pitch_ratio_dataRef)

    @yoke_pitch_ratio.setter
    def yoke_pitch_ratio(self, ratio):
        self._set_datavf(self.yoke_pitch_ratio_dataRef, ratio)

    @property
    def yoke_roll_ratio(self):
        return self._get_datavf(self.yoke_roll_ratio_dataRef)

    @yoke_roll_ratio.setter
    def yoke_roll_ratio(self, ratio):
        self._set_datavf(self.yoke_roll_ratio_dataRef, ratio)

    @property
    def yoke_heading_ratio(self):
        return self._get_datavf(self.yoke_heading_ratio_dataRef)

    @yoke_heading_ratio.setter
    def yoke_heading_ratio(self, ratio):
        self._set_datavf(self.yoke_heading_ratio_dataRef, ratio)

    @property
    def throttle_ratio(self):
        return self._get_datavf(self.throttle_ratio_dataRef)

    @throttle_ratio.setter
    def throttle_ratio(self, ratio):
        self._set_datavf(self.throttle_ratio_dataRef, ratio)

    @position.setter
    def position(self, position):
        x, y, z = position
        xp.setDatad(self.x_dataRef, x)
        xp.setDatad(self.y_dataRef, y)
        xp.setDatad(self.z_dataRef, z)
