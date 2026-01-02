"""
Simple local DAG validator.

Usage:
    python test_airflow_locally.py

Exits:
    0 - success (imported, DAG found, validations passed)
    2 - import error when importing loa_pipelines.dag_template
    3 - no DAG found in module
    4 - validation failed (structure issues)
    1 - generic error
"""
import sys
import os
import importlib
import traceback
import inspect

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

def add_project_to_path():
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

def try_import_module(module_path):
    try:
        mod = importlib.import_module(module_path)
        return mod, None
    except Exception as e:
        return None, e

def find_dag_in_module(mod):
    # common names and factories
    candidates = []
    lookup_names = ("dag", "DAG", "create_dag", "make_dag", "build_dag", "get_dag")
    for name in lookup_names:
        if hasattr(mod, name):
            obj = getattr(mod, name)
            candidates.append((name, obj))

    # prefer direct dag objects first
    for name, obj in candidates:
        if not callable(obj):
            return obj, f"found attribute '{name}'"

    # try factories (callables) with no required args
    for name, obj in candidates:
        if callable(obj):
            try:
                sig = inspect.signature(obj)
                params = sig.parameters.values()
                # allow call if all parameters have defaults or are VAR_POSITIONAL/VAR_KEYWORD
                can_call = all(
                    p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
                    or p.default is not inspect.Parameter.empty
                    for p in params
                )
                if can_call:
                    try:
                        dag = obj()
                        return dag, f"created by factory '{name}()'"
                    except Exception:
                        # skip factory that raises on call
                        continue
            except (TypeError, ValueError):
                # builtins or callables without inspectable signature; try calling safely
                try:
                    dag = obj()
                    return dag, f"created by factory '{name}()'"
                except Exception:
                    continue

    # last resort: scan module globals for something that looks like a DAG
    for name, val in vars(mod).items():
        if name.startswith("_"):
            continue
        if hasattr(val, "dag_id") and (hasattr(val, "tasks") or hasattr(val, "task_ids")):
            return val, f"found by scanning module as '{name}'"

    return None, None

def is_dag_like(obj):
    return hasattr(obj, "dag_id") and (hasattr(obj, "tasks") or hasattr(obj, "task_ids"))

def inspect_dag(dag):
    info = {}
    info['dag_id'] = getattr(dag, "dag_id", "<missing>")
    # owner: either dag.owner if set or from default_args
    owner = getattr(dag, "owner", None)
    if not owner:
        default_args = getattr(dag, "default_args", {}) or {}
        owner = default_args.get("owner")
    info['owner'] = owner or "<unknown>"

    # tasks: try dag.tasks then dag.task_ids
    tasks = getattr(dag, "tasks", None)
    task_ids = getattr(dag, "task_ids", None)
    if tasks is None and task_ids is not None:
        # build lightweight representation
        task_ids = set(task_ids)
        info['num_tasks'] = len(task_ids)
        info['task_names'] = sorted(task_ids)
        info['tasks_map'] = {tid: None for tid in task_ids}
    else:
        tasks = tasks or []
        info['num_tasks'] = len(tasks)
        names = []
        tasks_map = {}
        for t in tasks:
            tid = getattr(t, "task_id", None) or getattr(t, "task_id", None)
            if not tid:
                # fallback: try id(t)
                tid = f"<unnamed:{id(t)}>"
            names.append(tid)
            tasks_map[tid] = t
        info['task_names'] = sorted(names)
        info['tasks_map'] = tasks_map

    # dependencies
    deps = {}
    for tid, t in info['tasks_map'].items():
        if t is None:
            # no operator objects available (only task_ids present)
            deps[tid] = {
                "upstream": set(),
                "downstream": set()
            }
            continue
        up = getattr(t, "upstream_task_ids", None)
        down = getattr(t, "downstream_task_ids", None)
        # fallback older API names
        if up is None:
            up = getattr(t, "upstream_list", None)
            if up is not None:
                up = {getattr(x, "task_id", str(x)) for x in up}
        if down is None:
            down = getattr(t, "downstream_task_ids", None) or getattr(t, "downstream_list", None)
            if isinstance(down, list):
                down = {getattr(x, "task_id", str(x)) for x in down}
        deps[tid] = {
            "upstream": set(up) if up is not None else set(),
            "downstream": set(down) if down is not None else set()
        }
    info['dependencies'] = deps
    return info

def validate_structure(dag_obj, info):
    errors = []
    # dag_id
    if not info.get('dag_id') or info['dag_id'] == "<missing>":
        errors.append("DAG has no dag_id")
    # tasks existence
    if info.get('num_tasks', 0) == 0:
        errors.append("DAG has zero tasks (expected at least one).")
    # dependency references must be valid
    known = set(info['task_names'])
    for tid, dep in info['dependencies'].items():
        bad_up = [x for x in dep['upstream'] if x and x not in known]
        bad_down = [x for x in dep['downstream'] if x and x not in known]
        if bad_up:
            errors.append(f"Task '{tid}' has upstream references to unknown tasks: {bad_up}")
        if bad_down:
            errors.append(f"Task '{tid}' has downstream references to unknown tasks: {bad_down}")
    # try topological sort if available
    try:
        if hasattr(dag_obj, "topological_sort") and callable(dag_obj.topological_sort):
            _ = list(dag_obj.topological_sort())
    except Exception as e:
        errors.append(f"Topological sort failed (possible cycle): {e}")
    return errors

def print_report(mod_path, mod, found_reason, info, validation_errors):
    sep = "-" * 60
    print(sep)
    print(f"Module imported: {mod_path}")
    print(f"Import result: {'OK' if mod else 'FAILED'}")
    if mod and found_reason:
        print(f"DAG located: {found_reason}")
    print(sep)
    if info:
        print(f"DAG ID   : {info['dag_id']}")
        print(f"Owner    : {info['owner']}")
        print(f"Tasks    : {info['num_tasks']}")
        print("Task names:")
        for n in info['task_names']:
            print(f"  - {n}")
        print("Task dependencies:")
        for tid in sorted(info['task_names']):
            dep = info['dependencies'].get(tid, {})
            up = sorted(dep.get('upstream', []))
            down = sorted(dep.get('downstream', []))
            print(f"  - {tid}")
            print(f"      upstream  : {up}")
            print(f"      downstream: {down}")
    else:
        print("No DAG information available.")
    print(sep)
    if not mod:
        print("Import failed. See traceback above.")
    elif not info:
        print("No DAG found in the module.")
    elif validation_errors:
        print("VALIDATION: FAILED")
        for e in validation_errors:
            print(f"  - {e}")
    else:
        print("VALIDATION: SUCCESS - DAG structure looks good.")
    print(sep)

if __name__ == "__main__":
    add_project_to_path()
    MODULE_PATH = "loa_pipelines.dag_template"

    mod, import_err = try_import_module(MODULE_PATH)
    if import_err:
        print(f"ERROR: Failed to import '{MODULE_PATH}':")
        traceback.print_exception(type(import_err), import_err, import_err.__traceback__)
        sys.exit(2)

    dag_obj, reason = find_dag_in_module(mod)
    info = None
    validation_errors = []
    if dag_obj is None:
        print(f"ERROR: No DAG-like object found in module '{MODULE_PATH}'.")
        sys.exit(3)

    # basic type check / duck typing
    if not is_dag_like(dag_obj):
        print(f"ERROR: Found object but it does not look like a DAG (missing dag_id/tasks).")
        sys.exit(3)

    # inspect and validate
    try:
        info = inspect_dag(dag_obj)
        validation_errors = validate_structure(dag_obj, info)
    except Exception as e:
        print("ERROR: Exception while inspecting DAG:")
        traceback.print_exception(type(e), e, e.__traceback__)
        sys.exit(1)

    print_report(MODULE_PATH, mod, reason, info, validation_errors)

    if validation_errors:
        sys.exit(4)

    sys.exit(0)

