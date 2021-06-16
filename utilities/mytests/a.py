import random
random.seed()
import matplotlib.pyplot as plt
import numpy as np
from collections import namedtuple
from typing import Union, List
from scipy.optimize import least_squares
from pathlib import Path


Point = namedtuple('Point', 'x y')

source_coordinate = Point(0, 0)
dose_rate_source = 100000  # Gamma*alpha G * cm2 / h

N_points = 10
x_range = 50
y_range = 50

def calc_distance_square(x1, y1, x2, y2) -> float:
    val = (x1-x2)**2 + (y1-y2)**2
    if val == 0:
        val = 10**-4
    return val


def fill_exp_points(x_range, y_range, N_points):
    exp_points = []
    for i in range(N_points):
        x = random.uniform(0, x_range)
        y = random.uniform(0, y_range)
        exp_points.append(Point(x, y))
    return exp_points


def fill_exp_doses(exp_points: List[Point], dose_rate_source, source_coordinate, error=10):
    doses = []
    for point in exp_points:
        distance_square = calc_distance_square(point.x, point.y, source_coordinate.x, source_coordinate.y)
        error = random.uniform(-error, error)
        doses.append(dose_rate_source / distance_square * (1 - error / 100))
    return doses


def show_points_graph(exp_points: List[Point], doses: List[float], source_parameters=None):
    x = []
    y = []
    colors = np.random.rand(len(doses))
    areas = []
    max_dose = max(doses)
    min_dose = min(doses)
    min_rad = 5
    max_rad = 100

    for point, dose in zip(exp_points, doses):
        x.append(point.x)
        y.append(point.y)
        areas.append((dose - (min_dose - min_rad)) / ((max_dose - min_dose) / (max_rad - min_rad)) + min_rad)

    fig, ax = plt.subplots()
    ax.scatter(x, y, s=areas, c=colors, alpha=0.5)

    if isinstance(source_parameters, np.ndarray):
        print('Adding annotation')
        for point, dose in zip(exp_points, doses):
            dose_theoretical = source_parameters[2] / calc_distance_square(point.x, point.y, source_parameters[0],
                                                                           source_parameters[1])
            val = (dose_theoretical-dose) / dose * 100
            if val > 300:
                val = 0
            txt = "{:.1f}".format(val)
            ax.annotate(txt, (point.x, point.y))
        x, y = source_parameters[0], source_parameters[1]

        for dose in range(10, 65, 5):
            rad = (source_parameters[2] / dose)**.5
            circle = plt.Circle((x,y), radius=rad, fill=False)
            ax.add_artist(circle)

    ax.axhline(source_parameters[1], color='r', linewidth=.2)
    ax.axvline(source_parameters[0], color='r', linewidth=.2)
    ax.axvline(0, color='b',  linestyle='--')
    plt.show()

def residuals(x, *args, **kwargs):
    x_s1 = x[0]
    y_s1 = x[1]
    d_s1 = x[2]
    #print(f'Parameters: {x}')
    exp_points = kwargs['exp_points']
    exp_doses = kwargs['exp_doses']
    residuals_array = np.empty(len(exp_points))
    i = 0
    for point, dose in zip(exp_points, exp_doses):
        residuals_array[i] = d_s1/calc_distance_square(point.x, point.y, x_s1, y_s1) - dose
        i += 1
    return residuals_array

#exp_points = fill_exp_points(x_range, y_range, N_points)
#exp_doses = fill_exp_doses(exp_points, dose_rate_source, source_coordinate)

with open(Path('C:/Users/Sergey Denisov/ownCloud/LCP/Projects/Dosimetry/doses.txt'), encoding='utf-8') as file:
    data = np.loadtxt(file, delimiter='\t')
    exp_points = []
    exp_doses = []
    for line in data:
        exp_points.append(Point(line[0], line[1]))
        exp_doses.append(line[2])

x0 = (-23, 34, 10000)
bounds = [(-33, 24, 10), (-13, 44, 10**6)]
res = least_squares(fun=residuals, x0=x0, bounds=bounds, kwargs={'exp_points': exp_points, 'exp_doses': exp_doses})
print(f'x:{res.x}')
source_coordinate = Point(res.x[0], res.x[1])
dose_rate_source = res.x[2]/30000
exp_points.append(source_coordinate)
exp_doses.append(dose_rate_source)
show_points_graph(exp_points, exp_doses, source_parameters=res.x)
