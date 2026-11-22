"""Plan 165: the `ai_router` import graph stays acyclic and layered.

Function-local imports count as edges here, because they are what let the
boot cycle hide: before this plan, `runtime` eagerly imported `setup` and
`credentials`, while `setup`, `credentials` and `model_policy` imported
`runtime` back inside functions, so the module graph had one strongly
connected component. The rules below fail closed on a new cycle, on a leaf
that grows a local import, and on a leaf that re-imports the composition
root. The lazy-import ceiling stops the workaround from spreading.
"""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Measured after Plan 165's moves and again after Plan 178's picker gate was
# withdrawn in 0.6.89: 27 function-local ai_router imports, all deliberate
# (platform-only winacl, client-facing availability, CLI-only
# candidate/catalogue, the transport/errors boundary, the events leaf's one
# call-time home lookup, runtime's policy load). Bedrock raised it to 29:
# availability's cross-provider union and bedrock-region reader each read
# credentials/state lazily rather than widening the eager graph. This is a
# ceiling, not a target: shrinking it is welcome, and raising it again
# needs a comment naming the module and why.
LAZY_IMPORT_CEILING = 29

# Only the composition root's three importers may name `runtime`.
RUNTIME_IMPORTERS = {'ai_router/router.py', 'ai_router/ingress.py',
                     'ai_router/__main__.py'}

# The runtime may not reach into its installer: packaging loads ai_router
# files by path, never the reverse. These are the known exceptions, pinned so
# a new path into packaging/ fails. `*` is a segment computed at run time; a
# local loader's constant arguments fill it in.
PACKAGING_PATHS = {
    ('ai_router/candidate_evidence.py', 'packaging/VERSION'),
    ('ai_router/key_dialog.py', 'packaging/assets/router-icon.png'),
    ('ai_router/runtime.py', 'packaging/VERSION'),
    ('ai_router/work_account.py', 'packaging/client_dialog'),
    ('ai_router/work_account.py', 'packaging/download_oauth'),
    ('ai_router/work_account.py', 'packaging/native_dialog'),
}


def _modules():
    found = {}
    for path in (ROOT / 'ai_router').rglob('*.py'):
        if '__pycache__' in path.parts:
            continue
        rel = path.relative_to(ROOT).as_posix()
        found[rel[:-3].replace('/', '.')] = path
    return found


def _edges(module, path, known, lazy):
    package = module.rpartition('.')[0]
    tree = ast.parse(path.read_text())
    found, eager = set(), set()

    def add(target, in_function):
        if target in known and target != module:
            found.add(target)
            if in_function:
                lazy.append((module, target))
            else:
                eager.add(target)

    def walk(node, in_function):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                walk(child, True)
                continue
            if isinstance(child, ast.ImportFrom):
                if child.level:
                    parts = package.split('.')
                    base = parts[:len(parts) - (child.level - 1)]
                    if child.module:
                        add('.'.join(base + [child.module]), in_function)
                    else:
                        for alias in child.names:
                            add('.'.join(base + [alias.name.split('.')[0]]), in_function)
                elif child.module and child.module.split('.')[0] == 'ai_router':
                    if len(child.module.split('.')) > 1:
                        add(child.module, in_function)
                    else:
                        for alias in child.names:
                            add('ai_router.' + alias.name.split('.')[0], in_function)
            elif isinstance(child, ast.Import):
                for alias in child.names:
                    if alias.name.split('.')[0] == 'ai_router':
                        add(alias.name, in_function)
            walk(child, in_function)

    walk(tree, False)
    return found, eager


def _graph():
    known = _modules()
    graph, eager, lazy_all, lazy_by_module = {}, {}, [], {}
    for module, path in known.items():
        lazy = []
        graph[module], eager[module] = _edges(module, path, known, lazy)
        lazy_by_module[module] = lazy
        lazy_all.extend(lazy)
    return known, graph, eager, lazy_all, lazy_by_module


def _path_segments(node):
    """Segments of a `a / 'b' / c` chain; computed ones read `*`."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _path_segments(node.left) + _path_segments(node.right)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.split('/')
    return ['*']


def _packaging_paths():
    """(ai_router file, packaging path) for every path built into packaging/."""
    # ponytail: sees `/` path chains (including 'a/b' literals) only; add
    # joinpath, os.path.join or Path('packaging', ...) forms when one appears.
    found = set()
    for path in sorted((ROOT / 'ai_router').rglob('*.py')):
        rel = path.relative_to(ROOT).as_posix()
        tree = ast.parse(path.read_text())
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        loaders = {}
        for node in ast.walk(tree):
            chain = isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)
            if not chain or isinstance(getattr(parents.get(node), 'op', None), ast.Div):
                continue
            segments = _path_segments(node)
            if 'packaging' not in segments:
                continue
            target = '/'.join(segments[segments.index('packaging'):])
            owner = parents.get(node)
            while owner is not None and not isinstance(owner, ast.FunctionDef):
                owner = parents.get(owner)
            if '*' in target and owner is not None:
                loaders.setdefault(owner.name, set()).add(target)
            else:
                found.add((rel, target))
        calls = [node for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and getattr(node.func, 'id', None) in loaders]
        for name, targets in loaders.items():
            # A computed argument could name any file, so it pins the wildcard too.
            args = {call.args[0].value if isinstance(call.args[0], ast.Constant)
                    and isinstance(call.args[0].value, str) else '*'
                    for call in calls if call.func.id == name and call.args}
            found |= {(rel, target.replace('*', arg, 1)) for target in targets for arg in args or {'*'}}
    return found


def _cycles(graph):
    """Strongly connected components with more than one module."""
    index, low, on_stack, stack, comps, counter = {}, {}, {}, [], [], [0]

    def strong(node):
        index[node] = low[node] = counter[0]
        counter[0] += 1
        stack.append(node)
        on_stack[node] = True
        for target in sorted(graph[node]):
            if target not in index:
                strong(target)
                low[node] = min(low[node], low[target])
            elif on_stack.get(target):
                low[node] = min(low[node], index[target])
        if low[node] == index[node]:
            comp = []
            while True:
                popped = stack.pop()
                on_stack[popped] = False
                comp.append(popped)
                if popped == node:
                    break
            comps.append(comp)

    for node in sorted(graph):
        if node not in index:
            strong(node)
    return [sorted(comp) for comp in comps if len(comp) > 1]


class ImportGraphTests(unittest.TestCase):
    def test_no_import_cycles(self):
        _, graph, _, _, _ = _graph()
        self.assertEqual(_cycles(graph), [])

    def test_state_leaf_imports_nothing_local(self):
        known, graph, eager, lazy_all, lazy_by_module = _graph()
        self.assertIn('ai_router.state', known)
        self.assertEqual(eager['ai_router.state'], set())
        self.assertEqual(graph['ai_router.state'], set())
        self.assertEqual(lazy_by_module['ai_router.state'], [])

    def test_events_leaf_has_only_the_home_lookup(self):
        _, _, eager, _, lazy_by_module = _graph()
        self.assertEqual(eager['ai_router.events'], set())
        self.assertEqual(lazy_by_module['ai_router.events'],
                         [('ai_router.events', 'ai_router.state')])

    def test_only_the_composition_root_imports_runtime(self):
        known, graph, eager, lazy_all, _ = _graph()
        importers = {module for module, targets in graph.items()
                     if 'ai_router.runtime' in targets}
        files = {module.replace('.', '/') + '.py' for module in importers}
        self.assertEqual(files, RUNTIME_IMPORTERS)

    def test_lazy_imports_stay_under_the_ceiling(self):
        _, _, _, lazy_all, _ = _graph()
        self.assertLessEqual(
            len(lazy_all), LAZY_IMPORT_CEILING,
            'function-local ai_router imports grew: ' + repr(sorted(lazy_all)))

    def test_ai_router_paths_into_packaging_are_pinned(self):
        self.assertEqual(_packaging_paths(), PACKAGING_PATHS)


if __name__ == '__main__':
    unittest.main()
