"""Streaming 8 kHz speech high-pass filter before D-STAR encoding."""
import math, struct

class SpeechFilter:
    def __init__(self):
        self.sections=[]
        omega=2*math.pi*350/8000
        cosine=math.cos(omega);sine=math.sin(omega)
        for k in range(4):
            q=1/(2*math.cos((2*k+1)*math.pi/16))
            alpha=sine/(2*q);a0=1+alpha
            self.sections.append(((1+cosine)/(2*a0),-(1+cosine)/a0,(1+cosine)/(2*a0),-2*cosine/a0,(1-alpha)/a0))
        self.reset()
    def reset(self):self.state=[[0.,0.] for _ in self.sections]
    def process(self,pcm):
        samples=struct.unpack('<160h',pcm);result=[]
        for sample in samples:
            value=float(sample)
            for coefficients,state in zip(self.sections,self.state):
                b0,b1,b2,a1,a2=coefficients
                output=b0*value+state[0]
                state[0]=b1*value-a1*output+state[1]
                state[1]=b2*value-a2*output
                value=output
            result.append(max(-32768,min(32767,round(value))))
        return struct.pack('<160h',*result)
