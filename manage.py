#!/usr/bin/python2.7

import argparse
import json
import os
import subprocess

valid_problem_types = ('batch', 'interactive', 'communication', 'output-only', 'two-phase')
valid_verdicts = ('model_solution', 'correct', 'time_limit', 'memory_limit', 'incorrect', 'runtime_error', 'failed', 'time_limit_and_runtime_error')
necessary_files = ('checker/testlib.h', 'validator/testlib.h', 'gen/testlib.h', 'gen/data', 'checker/checker.cpp', 'grader/cpp/grader.cpp', 'grader/pas/grader.pas', 'grader/java/grader.java')

string_types = (str, unicode)

HEADER = '\033[95m'
OKBLUE = '\033[94m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
FAIL = '\033[91m'
ENDC = '\033[0m'
BOLD = '\033[1m'
UNDERLINE = '\033[4m'

errors = []
warnings = []
namespace = ''


def error(description):
    errors.append(FAIL + 'ERROR: {} - {}'.format(namespace, description) + ENDC)


def warning(description):
    warnings.append(YELLOW + 'WARNING: {} - {}'.format(namespace, description) + ENDC)


def check_keys(data, required_keys, json_name=None):
    key_not_found = False
    for key in required_keys:
        if key not in data:
            if json_name:
                error('{} is required in {}'.format(key, json_name))
            else:
                error('{} is required'.format(key, json_name))
            key_not_found = True
    if key_not_found:
        raise KeyError


def error_on_duplicate_keys(ordered_pairs):
    data = {}
    for key, value in ordered_pairs:
        if key in data:
            error("duplicate key: {}".format(key))
        else:
            data[key] = value
    return data


def load_data(json_file, required_keys=()):
    try:
        with open(json_file, 'r') as f:
            try:
                data = json.load(f, object_pairs_hook=error_on_duplicate_keys)
            except ValueError:
                error('invalid json')
                return None
    except IOError:
        error('file does not exists')
        return None
    try:
        check_keys(data, required_keys)
    except KeyError:
        return None
    return data


def get_list_of_files(directory):
    return list(set(os.listdir(directory)) - {'testlib.h'})


def verify_problem():
    problem = load_data('problem.json', ['name', 'title', 'type', 'time_limit', 'memory_limit'])
    if problem is None:
        return problem

    git_origin_name = subprocess.check_output('git remote get-url origin | rev | cut -d/ -f1 | rev | cut -d. -f1', shell=True).strip()

    if not isinstance(problem['name'], string_types):
        error('name is not a string')
    elif problem['name'] != git_origin_name:
        warning('problem name and git project name are not the same')

    if not isinstance(problem['title'], string_types):
        error('title is not a string')

    if not isinstance(problem['type'], string_types) or problem['type'] not in valid_problem_types:
        error('type should be one of {}'.format('/'.join(valid_problem_types)))

    if not isinstance(problem['time_limit'], float) or problem['time_limit'] < 0.5:
        error('time_limit should be a number greater or equal to 0.5')

    memory = problem['memory_limit']
    if not isinstance(memory, int) or memory < 1 or memory & (memory - 1) != 0:
        error('memory_limit should be an integer that is a power of two')

    return problem


def verify_subtasks():
    subtasks = load_data('subtasks.json', ['samples'])
    if subtasks is None:
        return subtasks

    indexes = set()
    score_sum = 0

    validators = get_list_of_files('validator/')
    used_validators = set()

    for name, data in subtasks.iteritems():
        if not isinstance(data, dict):
            error('invalid data in {}'.format(name))
            continue

        try:
            check_keys(data, ['index', 'score', 'validators'], name)
        except KeyError:
            continue

        indexes.add(data['index'])

        if not isinstance(data['score'], int) or data['score'] < 0:
            error('score should be a non-negative integer in subtask {}'.format(name))
        elif name == 'samples':
            if data['score'] != 0:
                error('samples subtask score is non-zero')
        else:
            score_sum += data['score']

        if not isinstance(data['validators'], list):
            error('validators is not an array in subtask {}'.format(name))
        else:
            for index, validator in enumerate(data['validators']):
                if not isinstance(validator, string_types):
                    error('validator #{} is not a string in subtask {}'.format(index, name))
                elif validator not in validators:
                    error('{} does not exists'.format(validator))
                else:
                    used_validators.add(validator)

    for unused_validator in set(validators) - used_validators:
        warning('unused validator {}'.format(unused_validator))

    if score_sum != 100:
        error('sum of scores is {}'.format(score_sum))
    for i in range(len(subtasks)):
        if i not in indexes:
            error('missing index {} in subtask indexes'.format(i))

    return subtasks


def verify_verdict(verdict, key_name):
    if not isinstance(verdict, string_types) or verdict not in valid_verdicts:
        error('{} verdict should be one of {}'.format(key_name, '/'.join(valid_verdicts)))
        return False
    return True


def get_model_solution(solutions):
    for solution, data in enumerate(solutions):
        if isinstance(data, dict) and 'verdict' in data:
            if data['verdict'] == valid_verdicts[0]:
                return solution


def verify_solutions(subtasks):
    solutions = load_data('solutions.json')
    if solutions is None or subtasks is None:
        return solutions

    model_solution = None
    solution_files = set(get_list_of_files('solution/'))

    for solution in solutions:
        if solution not in solution_files:
            error('{} does not exists'.format(solution))
            continue
        solution_files.remove(solution)

        data = solutions[solution]

        try:
            check_keys(data, ['verdict'], solution)
        except KeyError:
            continue

        verify_verdict(data['verdict'], solution)
        check_keys(data, ['verdict'], solution)
        verified = verify_verdict(data['verdict'], solution)
        if verified and data['verdict'] == valid_verdicts[0]:  # model_solution always has index 0
            if model_solution is not None:
                error('there is more than one model solutions')
            model_solution = solution

        if 'except' in data:
            exceptions = data['except']
            if not isinstance(exceptions, dict):
                error('invalid except format in {}'.format(solution))
            else:
                for subtask_verdict in exceptions:
                    if subtask_verdict not in subtasks:
                        error('subtask "{}" is not defined and cannot be used in except'.format(subtask_verdict))
                    else:
                        verify_verdict(exceptions[subtask_verdict], '{}.except.{}'.format(solution, subtask_verdict))

    if model_solution is None:
        warning('there is no model solution')

    for solution in solution_files:
        error('{} is not represented'.format(solution))

    return solutions


def parse_data():
    subtasks = load_data('subtasks.json')
    with open('gen/data', 'r') as f:
        for line in f.readlines():
            if line[0] == '[':
                subtask = line.translate(None, '[]').strip()
            subtasks
    pass

def generate_input(solution):

    pass


def generate_output(solution):
    pass


def generate(input=True, output=True, solution=None):
    subtasks = verify_subtasks()
    solutions = verify_solutions(subtasks)
    if solution is None:
        solution = get_model_solution(solutions)
    if solution is None:
        error('there is no model solution or specified solution')
        return

    if input is True:
        generate_input(solution)
    if output is True:
        generate_output(solution)


def verify_existence(files):
    for file in files:
        if not os.path.isfile(file):
            error(file)


def verify():
    global namespace
    namespace = 'problem.json'
    verify_problem()

    namespace = 'subtasks.json'
    subtasks = verify_subtasks()

    namespace = 'solutions.json'
    solutions = verify_solutions(subtasks)

    namespace = 'not found'
    verify_existence(necessary_files)

    for error in errors:
        print error

    if not errors:
        if warnings:
            print YELLOW + 'verified ' + ENDC + 'but there are some warnings'
        else:
            print GREEN + 'verified.' + ENDC

    for warning in warnings:
        print warning


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='manage.py', formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('action', help='gen    - generating test cases\n'
                                       'verify - verifing problem utilites\n')

    args = parser.parse_args()
    if args.action == 'verify':
        verify()
    elif args.action == 'gen':
        pass
    else:
        parser.print_help()
