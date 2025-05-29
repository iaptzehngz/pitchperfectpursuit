import pandas as pd
from datetime import datetime
import os

print(list(filter(lambda x : x >= 3, [1,2,3,4,5])))

b=True
pp = 0 if b else 1
print(pp)

my_list = [10, 20, 30, 40, 50]
first_element = my_list.pop(0)

print(f"Removed element: {first_element}")
print(f"Modified list: {my_list}")


try:
    print(p)
except:
    print('errr')


print('afterwards')


now = datetime.now()
str_date_time = now.strftime("%d-%m-%Y %H%M%S")
print(now)
cwd = os.getcwd
print(cwd())

path = os.path.dirname(os.path.realpath(__file__))
os.chdir(path)
print(path)

os.mkdir('values_and_plots/' + str_date_time)
print(cwd())
