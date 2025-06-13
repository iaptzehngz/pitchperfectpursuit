from XPPython3 import xp
import wave

class PythonInterface:
    def XPluginStart(self):
        self.Name = "gunshot"
        self.Sig = "xppython3.gunshot"
        self.Desc = "makes a gun sound"

        self.commandRef = xp.createCommand('custom/sound/gunshot', 'makes a gun sound')
        xp.registerCommandHandler(self.commandRef, self.Callback, 1, None)
        return self.Name, self.Sig, self.Desc

    def XPluginStop(self):
        xp.unregisterCommandHandler(self.commandRef, self.Callback,1, None)

    def XPluginEnable(self):
        return 1

    def XPluginDisable(self):
        pass

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
        pass

    def Callback(self, commandRef, phase, refCon):
        if phase == 0:
            w = wave.open('Resources/sounds/weapons/gunshot.wav')
            xp.playWaveOnBus(w, loop = 0, audioType = 7)
        return 1
