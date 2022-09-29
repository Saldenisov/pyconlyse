# -*- coding: utf-8 -*-
"""
Created on Sun Nov 13 15:31:15 2016

@author: saldenisov
"""

import sys
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from scipy.integrate import trapz
from scipy.optimize.optimize import OptimizeWarning

from usefull import *


def main():
    Norm = False
    command = []

    while 'quit' not in command and 'q' not in command:
        if 'set' in command:
            command.remove('set')
            try:
                if 'EXP' in command:
                    command.remove('EXP')
                    Xexp, YEXP = openXYtxt(command)
                    print('EXP is uploaded')
                    if Norm:
                        Yexp = Yexp / np.max(YEXP)
                        print('Exp data is normalized as well')
                    else:
                        Yexp = YEXP

                elif 'kinf' in command:
                    command.remove('kinf')
                    kinf = setvalue('Write kinf in 10^10: ', 'kinf is set to: ')
                elif 'pulse_w' in command:
                    command.remove('pulse_w')
                    pulse_w = 12#setvalue('Write pulse width in ps: ', 'pulse width is set to: ')
                elif 'Cq' in command:
                    command.remove('Cq')
                    Cq = 25#setvalue('Concentraion of quencher in mM: ', 'Concentration of quencher is set to mM: ')
                elif 'Norm' in command:
                    command.remove('Norm')
                    com = input('type False of True: ')
                    com = str.split(com)[0]
                    if com == 'True':
                        Norm = True
                    elif com == 'False':
                        Norm = False
                    else:
                        print('Did not get it!')
                    if 'Yexp' in locals():
                        if Norm:
                            Yexp = Yexp / np.max(YEXP)
                            print('Exp data is normalized')
                        else:
                            Yexp = YEXP
                            print('Exp data is not normalized')
            except (MyException, FileNotFoundError, ValueError) as e:
                print(e)
        
        elif 'give' in command:
            command.remove('give')
            if 'EXP' in command:
                command.remove('EXP')
                if testifallin(['Yexp', 'Xexp'], locals()):
                    plt.plot(Xexp, Yexp)
                else:
                    print('Xexp and Yexp are empty')
            if 'model' in command:
                command.remove('model')
                if testifallin(['model', 'Xexp'], locals()):
                    plt.plot(Xexp, model)
                else:
                    print('model is not calculated')
            elif 'kinf' in command:
                command.remove('kinf')
                if 'kinf' in locals():
                    print('kinf is: %s *10^10' % kinf)
                else:
                    print('kinf is not defined')
            elif 'pulse_w' in command:
                command.remove('pulse_w')
                if 'pulse_w' in locals():
                    print('pulse width is: %s ps' % pulse_w)
                else:
                    print('pulse width is not defined')
            elif 'Cq' in command:
                command.remove('Cq')
                if 'Cq' in locals():
                    print('concentration of quencher is: %s mM' % Cq)
                else:
                    print('concentration of quencher is not defined')
                    
            plt.show()   

        elif 'fit' in command:
            command.remove('fit')
            if testifallin(['Yexp'], locals()):             
                A = .1
                t0 = -0.01
                tau1 = 1. / 100
                tau2 = 0.5
                sigma = .02
                part=0.5
                y0 = -0.0027
        #        A, t0, tau, sigma, y0
        #        bounds = ([0.001, -.5, .1, 0.001, -.005], [10, .5, 50, 0.1, 0.1])
        #        bi: A, t0, tau1, tau2, part, sigma, y0
        #        bounds = ([0.001, -1, 0.005, .02, 0.001, 0.001, -.001], [100, 1, 100, 1000, 1, 1, 0.1])
        #        rising A, t0, tau, part, sigma, y0
        #        AtoBtoC: A, t0, tau1, tau2,  sigma, y0
                bounds = ([0, -0.03, 1. / 1000, 0.001, 0.001, -.0035], #min
                          [10, 0.03, 100, 5, 0.085, .0027]) # max


                try:
                    #guess = [A, t0, tau1, sigma, 0.001]
                    #guess = [A, t0, tau1, tau2, part, sigma, 0]
                    #guess = [A, t0, tau1, tau2, sigma, 0.001]
                    #guess = [A, t0, tau1,part, sigma,0.01]
                    guess_ABC= [A, t0, tau1, tau2, sigma, y0]
                    res = mfit.fitAABC(Xexp, Yexp, 
                                      guess_ABC, 
                                      bounds,
                                      extraN=10,
                                      method='dogbox')
                    Yexpf = res[1]
                    print(res[0])
                    parameters = res[0]
                    plt.plot(Xexp,Yexp)
                    plt.plot(Xexp, Yexpf)
                   # plt.ylim(ymin=0.08)
                    plt.show()
                except (FittingError, OptimizeWarning) as e:
                    print(e)
            else:
                print('Something is missing for fit')
        
        elif 'calc' in command:
            command.remove('calc')
            if 'parameters' in locals():
                t = Xexp
                R = parameters['R'] * 10**-9
                D = parameters['D'] * 10**-9
                t[0] = 0.2 * 10**-12
                model = np.exp(-4 * 1000 * 3.14 * R * D * Cq / 10000 * 6.02 * 10**23 * (1 + 2 * R / np.sqrt(3.14 * D * t))*t)
                if Norm:
                    modelfit = np.max(YEXP) * modelfit
                print('Calculation of a model decay is done')


        elif 'save' in command:
            command.remove('save')
            if 'Fit' in command:
                try:
                    out=np.vstack([Xexp, Yexpf])
                    out=np.transpose(out)
                    np.savetxt('result-fit.txt',out,delimiter='\t')
                except Exception as e:
                    print(e)
            if 'model' in command:
                try:
                    out=np.vstack([Xexp,model])
                    out=np.transpose(out)
                    np.savetxt('result-model.txt',out,delimiter='\t')
                except Exception as e:
                    print(e)

        elif 'help' in command:
            pass

        command = inputcommand()
    print('Quitting. Прощай.')
        
if __name__ == '__main__':
    main()