from XPPython3 import xp
import math
import numpy as np
import socket
import pickle

HOST = '127.0.0.1'
PORT = 6969
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))
except ConnectionRefusedError:
    xp.log('Please ensure relay server is listening before starting X-Plane.')

rad_to_deg = 180/math.pi
xz_normal = np.array((0, 1, 0))
z_unit = np.array((0, 0, -1))

FLOAT_DREFS = (
    'sim/flightmodel/position/indicated_airspeed',
    'sim/flightmodel/position/alpha'
)

INT_DREFS = (
    'sim/flightmodel/failures/stallwarning',
    'sim/flightmodel2/misc/has_crashed'
)

STR_DREFS = (
    'sim/aircraft/view/acf_descrip'
)

class PythonInterface:
    def __init__(self):
        self.my_plane = None
        self.ias_dataRef = None
        self.aoa_dataRef = None
        self.sideslip_dataRef = None
        self.stall_warning_dataRef = None
        self.has_crashed_dataRef = None

        self.ai_plane = None
        self.manoeuvre = 'before enemy aircraft starts manoeuvre'
        self.loop_count = 0
#        self.first_run = True
        self.first_elapsedTime = None
        self.manoeuvre_started = False
        self.yoke_reset = False
#        self.elapsed_time = 0
        
        self.spawn_flight_loop = None
        self.straight_level_flight_loop = None
        self.report_flight_loop = None
        
    def XPluginStart(self):
        return "PI_spawnAI", "xppython3.spawnAI", "Spawn AI Aircraft"
    
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
        self.straight_level_flight_loop = xp.createFlightLoop(self.straight_level)
        xp.scheduleFlightLoop(self.straight_level_flight_loop, -1)
        self.manoeuvre_flight_loop = xp.createFlightLoop(self.schedule_manoeuvre)
        xp.scheduleFlightLoop(self.manoeuvre_flight_loop, -1)
#        self.makeshift_pitch_flight_loop = xp.createFlightLoop(self.makeshift_pitch)
#        xp.scheduleFlightLoop(self.makeshift_pitch_flight_loop, -1)
#        self.makeshift_bank_flight_loop = xp.createFlightLoop(self.makeshift_bank)
#        xp.scheduleFlightLoop(self.makeshift_bank_flight_loop, -1)
        self.report_flight_loop = xp.createFlightLoop(self.reportVars)
        xp.scheduleFlightLoop(self.report_flight_loop, -1)
        return 1
    
    def XPluginStop(self):
        sock.sendall(pickle.dumps('stop'))
        sock.close()

    def XPluginDisable(self):
        pass
    
    def spawnMe(self, _sinceLast, _elapsedTime, _counter, _refcon):
        report_aircraft_type()
        
        distance_from_ai = 400

        ai_heading = self.ai_plane.heading

        ai_x, ai_y, ai_z = self.ai_plane.position
        shifted_x = ai_x - distance_from_ai * math.sin(math.radians(ai_heading))
        shifted_z = ai_z + distance_from_ai * math.cos(math.radians(ai_heading))
        ai_lat, ai_long, ai_elevation = xp.localToWorld(shifted_x, ai_y, shifted_z)

        ai_speed = np.linalg.norm(self.ai_plane.velocity, ord=2)

        xp.placeUserAtLocation(ai_lat, ai_long, ai_elevation, ai_heading, ai_speed)
        xp.log(f'Placed user at latitude: {ai_lat}, longitude: {ai_long}, elevation: {ai_elevation} with heading: {ai_heading}, speed: {ai_speed}')
        return 0
        
    def schedule_manoeuvre(self, sinceLast, elaspedTime, _counter, _refcon):
        start_time = 7
        yoke_end_time = 10
        manoeuvre_end_time = 17
        roll = True
        pitch = True
        roll_ratio = 0.3
        pitch_ratio = 0.15
        manoeuvre_description = 'enemy aircraft turning right'

        if self.loop_count < 3:
            self.loop_count += 1
            self.first_elapsedTime = elaspedTime
            xp.log(f'first elapsed time: {self.first_elapsedTime}')
            return -1
        
        elapsed_time = elaspedTime - self.first_elapsedTime

        if elapsed_time > start_time and not self.manoeuvre_started:
            self.manoeuvre = manoeuvre_description
            xp.scheduleFlightLoop(self.straight_level_flight_loop, 0)
            self.manoeuvre_started = True
            if roll and pitch:
                self.ai_plane.yoke_roll_ratio = roll_ratio
                self.ai_plane.yoke_pitch_ratio = pitch_ratio
                xp.log(f'at time {elapsed_time} ai yoke roll ratio set to {self.ai_plane.yoke_roll_ratio} and pitch ratio set to {self.ai_plane.yoke_pitch_ratio} and throttle ratio set to {self.ai_plane.throttle_ratio}')
            elif roll:
                self.ai_plane.yoke_roll_ratio = roll_ratio
                xp.log(f'at time {elapsed_time} ai yoke roll ratio set to {self.ai_plane.yoke_roll_ratio}')
            elif pitch:
                self.ai_plane.yoke_pitch_ratio = pitch_ratio
                xp.log(f'at time {elapsed_time} ai yoke pitch ratio set to {self.ai_plane.yoke_pitch_ratio}')
            else:
                xp.log('uh so what do you want to change???')
        elif elapsed_time > yoke_end_time and not self.yoke_reset:
            self.yoke_reset = True
            self.ai_plane.yoke_roll_ratio = 0
            if pitch and not roll:
                self.ai_plane.yoke_pitch_ratio = 0
            xp.log(f'at time {elapsed_time} ai yoke roll ratio set to {self.ai_plane.yoke_roll_ratio} and pitch ratio set to {self.ai_plane.yoke_pitch_ratio} and throttle ratio set to {self.ai_plane.throttle_ratio}')
        elif elapsed_time > manoeuvre_end_time:
            self.ai_plane.yoke_pitch_ratio = 0
            self.manoeuvre = 'enemy aircraft finished manoeuvre'
            self.manoeuvre_started = False
            self.yoke_reset = False
            self.loop_count = 0
            self.first_elapsedTime = None
            xp.scheduleFlightLoop(self.straight_level_flight_loop, -1)
            xp.log(f'at time {elapsed_time} schedule manoeuvre flight loop GONE and teardown done')
            return 0
        return -1

    def straight_level(self, _sinceLast, elapsedTime, _counter, _refcon):
#        if self.ai_plane.pitch > 3.5:
#            self.ai_plane.yoke_pitch_ratio = 0.25
#        elif self.ai_plane.pitch < 3.5:
#            self.ai_plane.yoke_pitch_ratio = 0.3

        if self.ai_plane.roll > 0:
            self.ai_plane.yoke_roll_ratio = -1 * self.ai_plane.roll/90
        else:
            self.ai_plane.yoke_roll_ratio = 1 * self.ai_plane.roll/90
        xp.log(f'at time {elapsedTime} ai yoke roll ratio set to {self.ai_plane.yoke_roll_ratio}')
        return 0.1

    def reportVars(self, _sinceLast, elapsedTime, _counter, _refcon):
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
#        xp.log(f'aspect angle: {aspect_angle}')

        sock.sendall((pickle.dumps((elapsedTime, 
                                    self.manoeuvre, 
                                    distance, aspect_angle,
                                    self.my_plane.pitch, ideal_pitch, self.my_plane.roll, self.my_plane.heading, ideal_heading, 
                                    xp.getDataf(self.aoa_dataRef), xp.getDataf(self.sideslip_dataRef),
                                    self.my_plane.yoke_pitch_ratio, self.my_plane.yoke_roll_ratio, self.my_plane.yoke_heading_ratio, self.my_plane.throttle_ratio, 
                                    xp.getDataf(self.ias_dataRef), 
                                    xp.getDatai(self.stall_warning_dataRef), xp.getDatai(self.has_crashed_dataRef)))))
        return 0.2

def override_ai_autopilot(plane_index=None):
    '''off the autopilot for the AI plane'''
    if plane_index:
        dataRef = xp.findDataRef('sim/operation/override/override_plane_ai_autopilot')
        xp.setDatavi(dataRef, [1], plane_index)
        xp.log(f"overrode plane of index {plane_index} autopilot")
    else:
        raise ValueError("provide plane_index")

def report_aircraft_type():
    aircraft_type = xp.getDatas(xp.findDataRef('sim/aircraft/view/acf_descrip'))
    sock.sendall(pickle.dumps(aircraft_type))

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
    def position(self):
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

#    @position.setter
#    def position(self, position):
#        x, y, z = position
#        xp.setDatad(self.x_dataRef, x)
#        xp.setDatad(self.y_dataRef, y)
#        xp.setDatad(self.z_dataRef, z)