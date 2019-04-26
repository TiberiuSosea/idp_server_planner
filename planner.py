#!/usr/bin/env python
# coding: utf-8

# In[1]:


from copy import copy, deepcopy
from itertools import combinations
import yaml
import time
import sys
import io

# Debug
def printperline(lst):
    for elem in lst:
        print(elem)
        print('\n')

# Constants

RESTRICTED = True
ORDERED_VARIABLES = True
ORDERED_DOMAINS = True
ALLOWED_TIME = int(sys.argv[3])

INF = 1000000000
SECONDS_IN_A_WEEK = 604800

INPUT_FILE = sys.argv[1]
OUTPUT_FILE = sys.argv[2]

START = 'start'
END = 'end'
BEFORE = 'before'
AFTER = 'after'
INTERVAL = 'interval'

ACTIVITY = 'activity'
ACTIVITY_LIST = 'activity_list'
ACTIVITY_TYPE = 'activity_type'
COSTS = 'costs'

SCHEDULING_TYPE = 'scheduling_type'
EXACT_INTERVAL = 'exact_interval'
NR_INSTANCES = 'nr_instances'

INSTANCES_PER_WEEK = 'instances_per_week'
INSTANCES_PER_DAY = 'instances_per_day'

PREFERRED_INTERVALS = 'preferred_intervals'
EXCLUDED_INTERVALS = 'excluded_intervals'
MINIMAL_DISTANCE_FROM = 'minimal_distance_from'

C_PREFERRED_INTERVAL = 'c_preferred_interval'
C_RELATIVE = 'c_relative'
C_EXCLUDED_INTERVAL = 'c_excluded_interval'
C_ACTIVITY_DISTANCE = 'c_activity_distance'
C_MISSING_INSTANCE_DAY = 'c_missing_instance_day'
C_MISSING_INSTANCE_WEEK = 'c_missing_instance_week'

GRANULARITY = 'granularity'
UNIT = 'unit'
MINUTE = 'minute'
HOUR = 'hour'
DAY = 'day'
VALUE = 'value'
DURATION = 'duration'

NAME = 'name'
SELF = 'self'
INSTANCE_ID = 'instance_id'
INSTANCES_NUMBER = 'instances_number'

day_limits = {START : 7 * 60, END: 24*60, GRANULARITY : 5}
day_values = list(range(1,8,1))
my_dict = yaml.load(open(INPUT_FILE))

Activities = list(map(lambda x: x[ACTIVITY], my_dict[ACTIVITY_LIST]))
Costs = my_dict[COSTS]
Domain = [(day, start) for day in day_values for start in range(day_limits[START], day_limits[END], day_limits[GRANULARITY])]

Solution = []
Instances = []
Constraints = {}
allInstances = {}
Result_summary = []
PotentialCosts = {}

# Resolve EXACT_INTERVAL Activities
exactIntervalActivities = list(filter(lambda x: x[SCHEDULING_TYPE] == EXACT_INTERVAL, Activities))
for activity in exactIntervalActivities:
    allInstances[activity[NAME]] = activity
    interval = activity[INTERVAL]
    for time_i in range(interval[START], interval[END], day_limits[GRANULARITY]):
        Domain.remove((interval[DAY], time_i))
    Solution.append(activity)
    Result_summary.append({'activity_type' : activity[NAME], 'total_instances' : 1, 'planned_instances' : 1,                            'unplanned_instances' : 0})
Activities = list(filter(lambda x: x[SCHEDULING_TYPE] != EXACT_INTERVAL, Activities))


# In[4]:


def create_instances (activity):
    default_instances_per_week = 7 if activity[SCHEDULING_TYPE] == NR_INSTANCES else 1
    default_instances_per_day = 1
    
    instances_per_week = activity[INSTANCES_PER_WEEK] if activity[INSTANCES_PER_WEEK] else default_instances_per_week
    instances_per_day = activity[INSTANCES_PER_DAY] if activity[INSTANCES_PER_DAY] else default_instances_per_day
    
    activity[INSTANCES_NUMBER] = instances_per_week * instances_per_day
    instances = []
    
    for nr in range(activity[INSTANCES_NUMBER]):
        copy = activity.copy()
        copy[INSTANCE_ID] = nr
        instances.append(copy)
    return instances

def init_constraints (activity):
    constraints = []
    for i in range(activity[INSTANCES_NUMBER] + 1):
        constraints.append([]) 
    return constraints

def init_potential_costs (activity):
    p_costs = []
    for i in range(activity[INSTANCES_NUMBER] + 1):
        p_costs.append(0) 
    return p_costs


# In[5]:


# Create constraints    

def create_constraints_missing_instances (instances, constraints, hard):
    activity = instances[0]
    instances_per_day = activity[INSTANCES_PER_DAY] if INSTANCES_PER_DAY in activity else 1
    for nr in range(len(instances)):
        start = (nr//instances_per_day)*instances_per_day
        for nr1 in range(start, start + instances_per_day, 1):
            constraints[activity[NAME]][nr].append(([instances[nr], instances[nr1]], check_constraints_missing_instance_day))
            constraints[activity[NAME]][nr1].append(([instances[nr], instances[nr1]], check_constraints_missing_instance_day))
            PotentialCosts[activity[NAME]][nr] += Costs[C_MISSING_INSTANCE_DAY]
            PotentialCosts[activity[NAME]][nr1] += Costs[C_MISSING_INSTANCE_DAY]
    if hard == True:
        for nr in range(instances_per_day, len(instances), instances_per_day):
            constraints[activity[NAME]][nr - 1].append(([instances[nr - 1], instances[nr]],                                                         check_constraints_missing_instance_week_hard))
            constraints[activity[NAME]][nr].append(([instances[nr - 1], instances[nr]],                                                     check_constraints_missing_instance_week_hard))
            PotentialCosts[activity[NAME]][nr - 1] += INF
            PotentialCosts[activity[NAME]][nr] += INF
    else:
        for nr in range(instances_per_day, len(instances), instances_per_day):
            constraints[activity[NAME]][nr - 1].append(([instances[nr - 1], instances[nr]], check_constraints_missing_instance_week))
            constraints[activity[NAME]][nr].append(([instances[nr - 1], instances[nr]], check_constraints_missing_instance_week))
            PotentialCosts[activity[NAME]][nr - 1] += Costs[C_MISSING_INSTANCE_WEEK]
            PotentialCosts[activity[NAME]][nr] += Costs[C_MISSING_INSTANCE_WEEK]
            

def create_constraints_minimal_distance_from (instances, constraints, allInstances):
    for instance in filter(lambda x: MINIMAL_DISTANCE_FROM in x, instances):
        for dependency in map(lambda x: x[ACTIVITY], instance[MINIMAL_DISTANCE_FROM]):
            activity_type = instance[NAME] if dependency[ACTIVITY_TYPE] == SELF else dependency[ACTIVITY_TYPE]
            for dep in filter(lambda x: x != instance, allInstances[activity_type]):
                constraints[instance[NAME]][instance[INSTANCE_ID]].append(([instance, dep, dependency[VALUE],                                                                             dependency[UNIT]],                                                                            check_constraints_minimal_distance_from))
                time_t = convert_to_minutes (dependency[VALUE], dependency[UNIT])
                PotentialCosts[instance[NAME]][instance[INSTANCE_ID]] += Costs[C_ACTIVITY_DISTANCE] * time_t
                if INSTANCE_ID in dep:
                    constraints[dep[NAME]][dep[INSTANCE_ID]].append(([instance, dep, dependency[VALUE], dependency[UNIT]],                                                                      check_constraints_minimal_distance_from))
                    PotentialCosts[dep[NAME]][dep[INSTANCE_ID]] += Costs[C_ACTIVITY_DISTANCE] * time_t

def create_constraints_excluded_intervals (instances, constraints):
    for instance in filter(lambda x: EXCLUDED_INTERVALS in x, instances):
        constraints[instance[NAME]][instance[INSTANCE_ID]].append(([instance], check_constraints_excluded_intervals))
        PotentialCosts[instance[NAME]][instance[INSTANCE_ID]] += Costs[C_EXCLUDED_INTERVAL]

def create_constraints_preferred_intervals (instances, constraints):
    for instance in filter(lambda x: PREFERRED_INTERVALS in x, instances):
        constraints[instance[NAME]][instance[INSTANCE_ID]].append(([instance], check_constraints_preferred_intervals))
        PotentialCosts[instance[NAME]][instance[INSTANCE_ID]] += Costs[C_PREFERRED_INTERVAL]

def create_constraints_relative (instances, constraints, activities):
    for instance in instances:
        if AFTER in instance:
            constraints[instance[NAME]][instance[INSTANCE_ID]].append(([instance], check_constraints_relative_after))
            PotentialCosts[instance[NAME]][instance[INSTANCE_ID]] += Costs[C_RELATIVE] * SECONDS_IN_A_WEEK
            dependencies = get_dependencies_relative (instance, AFTER, activities)
            for dep in dependencies:
                constraints[dep[NAME]][len(constraints[dep[NAME]]) - 1].append(([instance], check_constraints_relative_after))
                PotentialCosts[dep[NAME]][len(constraints[dep[NAME]]) - 1] += Costs[C_RELATIVE] * SECONDS_IN_A_WEEK
        if BEFORE in instance:
            constraints[instance[NAME]][instance[INSTANCE_ID]].append(([instance], check_constraints_relative_before))
            PotentialCosts[instance[NAME]][instance[INSTANCE_ID]] += Costs[C_RELATIVE] * SECONDS_IN_A_WEEK
            dependencies = get_dependencies_relative (instance, BEFORE, activities)
            for dep in dependencies:
                constraints[dep[NAME]][len(constraints[dep[NAME]]) - 1].append(([instance], check_constraints_relative_before))
                PotentialCosts[dep[NAME]][len(constraints[dep[NAME]]) - 1] += Costs[C_RELATIVE] * SECONDS_IN_A_WEEK


# In[6]:


# Check constraints

def get_minutes_for_instance (instance, moment):
    return instance['interval']['day'] * 1440 + instance['interval'][moment]

def get_intersection_for_intervals(x, y):
    if x[START] >= y[END] or x[END] <= y[START]:
        return 0
    return min(x[END], y[END]) - max(x[START], y[START])

def convert_to_minutes(value, unit):
    if unit == MINUTE:
        return value
    value *= 60
    if unit == HOUR:
        return value
    value *= 24
    if unit == DAY:
        return value
    return 0

def check_constraints_missing_instance_day (instance1, instance2, solution):
    if instance1 not in solution or instance2 not in solution:
        return 0
    return 0 if instance1[INTERVAL][DAY] == instance2[INTERVAL][DAY] else Costs[C_MISSING_INSTANCE_DAY]


def check_constraints_missing_instance_week (instance1, instance2, solution):
    if instance1 not in solution or instance2 not in solution:
        return 0
    return 0 if instance1[INTERVAL][DAY] == instance2[INTERVAL][DAY] else Costs[C_MISSING_INSTANCE_WEEK]

def check_constraints_missing_instance_week_hard (instance1, instance2, solution):
    if instance1 not in solution or instance2 not in solution:
        return 0
    return 0 if instance1[INTERVAL][DAY] < instance2[INTERVAL][DAY] else INF

# Minimal distance from
def check_constraints_minimal_distance_from (instance, dependency, value, unit, solution):
    if (instance not in solution or dependency not in solution):
        return 0
    time_inst = convert_to_minutes (instance[INTERVAL][DAY], DAY) + instance[INTERVAL][START]
    time_dep = convert_to_minutes (dependency[INTERVAL][DAY], DAY) + dependency[INTERVAL][START]
    time_t = convert_to_minutes (value, unit)
    if time_inst < time_dep:
        return Costs[C_ACTIVITY_DISTANCE] * get_intersection_for_intervals (dependency[INTERVAL],                                                                      {START : instance[INTERVAL][END],                                                                       END : (instance[INTERVAL][END] + time_t)})
    else:
        return Costs[C_ACTIVITY_DISTANCE] * get_intersection_for_intervals (instance[INTERVAL],                                                                      {START : dependency[INTERVAL][END],                                                                       END : (dependency[INTERVAL][END] + time_t)})
    
# Excluded intervals
def check_constraints_excluded_intervals (instance, solution):
    if instance not in solution:
        return 0
    sum_intersections = 0
    intervals = map(lambda x: x[INTERVAL], instance[EXCLUDED_INTERVALS])
    for interval in intervals:
        sum_intersections += get_intersection_for_intervals(interval, instance[INTERVAL])
    size = instance[INTERVAL][END] - instance[INTERVAL][START]
    return Costs[C_EXCLUDED_INTERVAL] * sum_intersections // size

#Preferred intervals
def check_constraints_preferred_intervals (instance, solution):
    if instance not in solution:
        return 0
    max_intersection = 0
    intervals = map(lambda x: x[INTERVAL], instance[PREFERRED_INTERVALS])
    for interval in intervals:
        intersection = get_intersection_for_intervals(interval, instance[INTERVAL])
        max_intersection = max(max_intersection, intersection)
    size = instance[INTERVAL][END] - instance[INTERVAL][START]
    return Costs[C_PREFERRED_INTERVAL] * (size - max_intersection)//size

# Relative
def check_constraints_relative_after (instance, solution):
    return check_constraints_relative_base (instance, AFTER, solution)

def check_constraints_relative_before (instance, solution):
    return check_constraints_relative_base (instance, BEFORE, solution)

def get_dependencies_relative (instance, moment, solution):
    return list(filter(lambda x: x[NAME] == instance[moment]['activity_type'], solution))

def check_constraints_relative_base (instance, moment, solution):
    checkpoint = START if moment == BEFORE else END
    checkpoint_r = START if checkpoint == AFTER else END
    dependencies = get_dependencies_relative (instance, moment, solution)
    if len(dependencies) == 0 or instance not in solution:
        return 0
    current_min = INF
    instance_minutes = get_minutes_for_instance(instance, checkpoint_r)
    for dep in dependencies:
        if abs(get_minutes_for_instance(dep, checkpoint) - instance_minutes) < current_min:
            current_min = abs(get_minutes_for_instance(dep, checkpoint) - instance_minutes)
    return current_min * 60 * Costs[C_RELATIVE]


# In[7]:


def compute_duration (duration):
    if (duration[UNIT] == MINUTE):
        return duration[VALUE]
    if (duration[UNIT] == HOUR):
        return duration[VALUE] * 60
    if (duration[UNIT] == DAY):
        return duration[VALUE] * 60 * 24
    return 0

def get_value_from_domain (domain, duration, index):
    val = domain[index]
    for i in range(0, duration, day_limits[GRANULARITY]):
        elem = (val[0], val[1] + i)
        if elem not in domain:
            return None
        domain.remove(elem)
    return val

def get_cost_of_constraint (solution, constraint):
    keys = deepcopy(constraint[0])
    function = constraint[1]
    keys.append(solution)
    return function(*tuple(keys))

def hour_format(minutes):
    return "%d:%02d" % (minutes//60, minutes%60)

def exit_backtracking():
    activity_list = []
    for instance in best_solution:
        activity_list.append({'activity_instance' : {'activity_type' : instance[NAME], 'interval' :                                                      {DAY : instance[INTERVAL][DAY],                                                       START : hour_format(instance[INTERVAL][START]),                                                       END : hour_format(instance[INTERVAL][END])}}})
    if best_cost < INF:
        for activity in Activities:
            Result_summary.append({'activity_type' : activity[NAME], 'total_instances' : activity[INSTANCES_NUMBER],                                    'planned_instances' : activity[INSTANCES_NUMBER], 'unplanned_instances' : 0})
    result = {'cost' : best_cost, 'planning_summary' : Result_summary, 'planned_activity_list' : activity_list}
    with io.open(OUTPUT_FILE, 'w') as outfile:
        yaml.dump(result, outfile)
    sys.exit(0)

def backtracking(vars, activity_index, instance_index, domain, domain_index, constraints, acceptable_cost, solution, cost):
    global best_solution
    global best_cost
    global start_time
    
    if time.time() - start_time > ALLOWED_TIME:
        exit_backtracking()
        
    #print(str(activity_index) + " " + str(instance_index) + " " + str(cost) + " " + str(best_cost) + " " + str(domain_index))
    
    if activity_index == len(vars):
        best_solution = solution
        best_cost = cost
        print("New best: " + str(cost))
        if cost <= acceptable_cost:
            return True
        else:
            return False
    if cost == best_cost or domain_index >= len(domain):
        return False
    var = vars[activity_index]
    instance = var[instance_index]    
    duration = compute_duration(instance[DURATION])
    new_domain = deepcopy(domain)
    
    if ORDERED_DOMAINS == True and domain_index == 0:
        ref_vals = compute_ref_vals(instance_index, instance, duration, solution, constraints)
        if len(list(filter(lambda x: x < INF, ref_vals))) == 1:
            return False
        new_domain.sort(reverse=False, key=lambda value: order_domains(value, ref_vals))
        
    val = get_value_from_domain (new_domain, duration, domain_index)
    if val is None and len(new_domain) == 0:
        return False
    if val is None:
        return backtracking (vars, activity_index, instance_index, domain, domain_index + 1, constraints, acceptable_cost, solution, cost)
    
    instance[INTERVAL] = {DAY : val[0], START : val[1], END : (val[1] + duration)}
    new_solution = deepcopy(solution)
    new_solution.append(instance)
    instance_cons = constraints[instance[NAME]][instance_index]
    new_cost = cost
    for cons in instance_cons:
        new_cost += get_cost_of_constraint (new_solution, cons)
    res = False
    next_domain_index = domain_index + 1
    if new_cost >= INF:
        while next_domain_index < len(domain) and domain[next_domain_index][0] == domain[domain_index][0]:
            next_domain_index += 1
    if new_cost < best_cost:
        next_index = instance_index + 1
        if next_index == len(vars[activity_index]):
            activity_cons = constraints[instance[NAME]][next_index]
            for cons in activity_cons:
                new_cost += get_cost_of_constraint (new_solution, cons)
            if new_cost < best_cost:
                res = backtracking (vars, activity_index + 1, 0, new_domain, 0, constraints, acceptable_cost, new_solution, new_cost)
        else:
            res = backtracking (vars, activity_index, next_index, new_domain, 0, constraints, acceptable_cost, new_solution, new_cost)
    if not res:
            return backtracking(vars, activity_index, instance_index, domain, next_domain_index, constraints, acceptable_cost, solution, cost)
    else:
        return True    
    
def run_backtracking():
    global best_solution
    global best_cost
    global INF
    
    global start_time 
    start_time = time.time()
    
    best_solution = Solution
    best_cost = INF
    
    backtracking(Instances, 0, 0, Domain, 0, Constraints, 0, Solution, 0)
    
    print("Best found: " + str(best_cost))
    exit_backtracking()

def order_variables (instances):
    sum = 0
    for instance in instances:
        sum += PotentialCosts[instance[NAME]][instance[INSTANCE_ID]]
    return sum

def compute_ref_vals(instance_index, instance, duration, solution, constraints):
    ref_vals = []
    ref_vals.append(0)
    for day in range(1, 8, 1):
        val = (day, 420)
        instance[INTERVAL] = {DAY : val[0], START : val[1], END : (val[1] + duration)}
        new_solution = deepcopy(solution)
        new_solution.append(instance)
        instance_cons = constraints[instance[NAME]][instance_index]
        new_cost = 0
        for cons in instance_cons:
            new_cost += get_cost_of_constraint (new_solution, cons)
        ref_vals.append(new_cost)
    return ref_vals

def order_domains (val, ref_vals):
    return ref_vals[val[0]] + val[0] * 36000


# In[9]:


#Create instances
for activity in Activities:
    instances = create_instances(activity)
    allInstances[activity[NAME]] = instances
    Instances.append(instances)
    Constraints[activity[NAME]] = init_constraints(activity)
    PotentialCosts[activity[NAME]] = init_potential_costs(activity)

# Create constraints
for instances in Instances:
    create_constraints_relative (instances, Constraints, Activities)
    create_constraints_preferred_intervals (instances, Constraints)
    create_constraints_excluded_intervals (instances, Constraints)
    create_constraints_minimal_distance_from (instances, Constraints, allInstances)
    create_constraints_missing_instances (instances, Constraints, RESTRICTED)
    
# Order variables
if ORDERED_VARIABLES:
    Instances.sort(reverse=True, key=order_variables)

# Run program
run_backtracking()

