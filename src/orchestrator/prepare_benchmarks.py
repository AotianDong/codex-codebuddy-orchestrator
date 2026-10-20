"""Ten reproducible small development tasks, all in non-production Git fixtures."""
from pathlib import Path
from . import scheduler as s

BASE = Path(__file__).resolve().parent
SUITE = Path.home() / '.local/state/codex-codebuddy/benchmark/suite'

CASES = [
 ('A1', 'feature', 'Add stable unique(items), preserving first occurrence order. Inputs are hashable.',
  {'module.py': 'def stable_unique(items):\n    raise NotImplementedError\n'},
  ['from module import stable_unique as f; assert f([3,1,3,2])==[3,1,2]',
   'from module import stable_unique as f; assert f([])==[]',
   'from module import stable_unique as f; assert f(["a","a","b"])==["a","b"]']),
 ('A2', 'feature', 'Implement paginate(items, page=1, page_size=2), returning list slice. Reject bool, non-int or <1 page/page_size with ValueError. Out of range returns [].',
  {'module.py': 'def paginate(items, page=1, page_size=2):\n    return list(items)\n'},
  ['from module import paginate as f; assert f([1,2,3])==[1,2]; assert f([1,2,3],2)==[3]',
   'from module import paginate as f; assert f([],3)==[]; assert f([1],8)==[]',
   'from module import paginate as f\nfor x in (0,-1,True,1.5):\n try: f([1],x)\n except ValueError: pass\n else: raise AssertionError(x)']),
 ('B1', 'bugfix', 'Fix inclusive interval overlap, endpoints touching count as overlap. Input tuples are ordered (start,end); preserve API.',
  {'module.py': 'def overlaps(a,b):\n    return a[0] < b[1] and b[0] < a[1]\n'},
  ['from module import overlaps as f; assert f((1,3),(3,5)); assert f((3,3),(3,3))',
   'from module import overlaps as f; assert not f((1,2),(3,4))',
   'from module import overlaps as f; assert f((-3,3),(-1,1)); assert f((2,4),(1,3))']),
 ('B2', 'bugfix', 'parse_bool(value): bool passes through; accept case-insensitive strings true/false with surrounding whitespace; all other inputs raise ValueError.',
  {'module.py': 'def parse_bool(value):\n    return bool(value)\n'},
  ['from module import parse_bool as f; assert f(" false ") is False; assert f("TRUE") is True',
   'from module import parse_bool as f; assert f(True) is True; assert f(False) is False',
   'from module import parse_bool as f\nfor x in (None,0,1,"yes",[],"", "0"):\n try: f(x)\n except ValueError: pass\n else: raise AssertionError(repr(x))']),
 ('C1', 'multifile', 'Add optional discount_percent=0 to pricing.line_total(price, qty). Decimal(str(price)) arithmetic; ROUND_HALF_UP to two decimals. Pass per-line discount_percent through summary.total(lines); empty returns Decimal("0.00"). Preserve old calls.',
  {'pricing.py': 'from decimal import Decimal\ndef line_total(price,qty):\n    return Decimal(str(price))*qty\n',
   'summary.py': 'from decimal import Decimal\nfrom pricing import line_total\ndef total(lines):\n    return sum((line_total(x["price"],x["qty"]) for x in lines),Decimal("0.00"))\n'},
  ['from pricing import line_total; from decimal import Decimal; assert line_total("10",2,15)==Decimal("17.00"); assert line_total("0.05",1,10)==Decimal("0.05")',
   'from summary import total; from decimal import Decimal; assert total([{"price":"10","qty":2,"discount_percent":15}])==Decimal("17.00")',
   'from summary import total; from pricing import line_total; assert str(total([]))=="0.00"; assert str(line_total("1",1))=="1.00"']),
 ('C2', 'multifile', 'normalize_name strips then lowercases strings, raising ValueError on non-strings. user_key(user) uses normalize_name(user["name"]) and normalized user["domain"], joining with @. Preserve functions, inputs not mutated.',
  {'names.py': 'def normalize_name(value):\n    return value\n',
   'users.py': 'from names import normalize_name\ndef user_key(user):\n    return user["name"]+"@"+user["domain"]\n'},
  ['from users import user_key; assert user_key({"name":" ALICE ","domain":" EXAMPLE.COM "})=="alice@example.com"',
   'from names import normalize_name\nfor x in (None,0,True):\n try: normalize_name(x)\n except ValueError: pass\n else: raise AssertionError(x)',
   'from users import user_key; u={"name":" A ","domain":" B "}; assert user_key(u)=="a@b"; assert u["name"]==" A "']),
 ('D1', 'refactor', 'Remove duplicate tax formulas. Add _tax(amount, rate); retail and wholesale both call it. Preserve current float behavior and signatures.',
  {'module.py': 'def retail(amount):\n    return amount + amount*0.2\ndef wholesale(amount):\n    return amount + amount*0.1\n'},
  ['from module import retail,wholesale; assert retail(100)==120; assert wholesale(100)==110',
   'from module import retail,wholesale; assert retail(0)==0; assert wholesale(-10)==-11',
   'import ast; from pathlib import Path; t=ast.parse(Path("module.py").read_text()); fs={x.name:x for x in t.body if isinstance(x,ast.FunctionDef)}; assert "_tax" in fs; assert all(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="_tax" for n in ast.walk(fs[k])) for k in ("retail","wholesale"))']),
 ('D2', 'refactor', 'Add _clean(value) doing strip().lower(), and use it in both clean_names and clean_tags to remove duplicated normalization. Preserve order and duplicates, and existing signatures.',
  {'module.py': 'def clean_names(values):\n    return [x.strip().lower() for x in values]\ndef clean_tags(values):\n    return [x.strip().lower() for x in values]\n'},
  ['from module import clean_names,clean_tags; assert clean_names([" A ","A"])==["a","a"]; assert clean_tags([" B "])==["b"]',
   'from module import clean_names,clean_tags; assert clean_names([])==[]; assert clean_tags(["  "])==[""]',
   'import ast; from pathlib import Path; t=ast.parse(Path("module.py").read_text()); fs={x.name:x for x in t.body if isinstance(x,ast.FunctionDef)}; assert "_clean" in fs; assert all(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="_clean" for n in ast.walk(fs[k])) for k in ("clean_names","clean_tags"))']),
 ('E1', 'integrated', 'Implement reducer.apply(state,event) without mutating input. State is dict of string key -> int. event {op:set,key,value} sets int; {op:increment,key,value} adds int, missing key starts 0; {op:delete,key} removes if present. Invalid op, missing/non-string key, bool/non-int value for set/increment raise ValueError. replay.run(events) starts {}, calls apply for each. Preserve interfaces. Plan cross-file edits internally; use independent feedback if needed.',
  {'reducer.py': 'def apply(state,event):\n    return state\n',
   'replay.py': 'from reducer import apply\ndef run(events):\n    return {}\n'},
  ['from replay import run; assert run([{"op":"set","key":"n","value":2},{"op":"increment","key":"n","value":3},{"op":"delete","key":"x"}])=={"n":5}',
   'from reducer import apply; s={"a":1}; assert apply(s,{"op":"delete","key":"a"})=={}; assert s=={"a":1}; assert apply({}, {"op":"increment","key":"z","value":2})=={"z":2}',
   'from reducer import apply\nfor e in ({"op":"oops","key":"a"},{"op":"set","key":"a","value":True},{"op":"delete"},{"op":"delete","key":1}):\n try: apply({},e)\n except ValueError: pass\n else: raise AssertionError(e)']),
 ('E2', 'integrated', 'Implement batch.ingest(rows). Each row dict has id and tags. id must be string strip non-empty else skip row. First row for normalized id wins, keep input order. normalize.tags accepts list of strings, strips/lowercases, drops empty and duplicate tags preserving order; non-string tags are ignored. Missing tags -> []. Return new dicts {id,tags}; do not mutate rows. Preserve signatures.',
  {'normalize.py': 'def tags(values):\n    return values\n',
   'batch.py': 'from normalize import tags\ndef ingest(rows):\n    return rows\n'},
  ['from batch import ingest; assert ingest([{"id":" A ","tags":[" X ","x","",None]},{"id":"A","tags":["y"]}])==[{"id":"A","tags":["x"]}]',
   'from batch import ingest; assert ingest([{"id":" "},{"id":None},{"id":"b"}])==[{"id":"b","tags":[]}]',
   'from batch import ingest; rows=[{"id":" a ","tags":[" B "]}]; x=ingest(rows); assert rows[0]["id"]==" a "; x[0]["tags"].append("c"); assert rows[0]["tags"]==[" B "]']),
]


CASES += [
 ('F1', 'test_authoring', 'Write unittest cases in candidate_tests.py for module.add(a,b). Check positive values, negatives and zero. Production module.py must not change.',
  {'module.py': 'def add(a,b):\n    return a+b\n', 'candidate_tests.py': 'import unittest\n'},
  ['import unittest, candidate_tests; suite=unittest.defaultTestLoader.loadTestsFromModule(candidate_tests); assert suite.countTestCases()>=3; assert unittest.TextTestRunner().run(suite).wasSuccessful()',
   'import unittest, candidate_tests, module; module.add.__code__=(lambda a,b: a-b).__code__; suite=unittest.defaultTestLoader.loadTestsFromModule(candidate_tests); assert not unittest.TextTestRunner().run(suite).wasSuccessful()',
   'import unittest, candidate_tests, module; module.add.__code__=(lambda a,b: 1).__code__; suite=unittest.defaultTestLoader.loadTestsFromModule(candidate_tests); assert not unittest.TextTestRunner().run(suite).wasSuccessful()']),
 ('F2', 'test_authoring', 'Write unittest cases in candidate_tests.py for module.is_even(n). Include positive, negative and zero inputs. Production module.py must not change.',
  {'module.py': 'def is_even(n):\n    return n%2==0\n', 'candidate_tests.py': 'import unittest\n'},
  ['import unittest, candidate_tests; suite=unittest.defaultTestLoader.loadTestsFromModule(candidate_tests); assert suite.countTestCases()>=3; assert unittest.TextTestRunner().run(suite).wasSuccessful()',
   'import unittest, candidate_tests, module; module.is_even.__code__=(lambda n: True).__code__; suite=unittest.defaultTestLoader.loadTestsFromModule(candidate_tests); assert not unittest.TextTestRunner().run(suite).wasSuccessful()',
   'import unittest, candidate_tests, module; module.is_even.__code__=(lambda n: n>0 and n%2==0).__code__; suite=unittest.defaultTestLoader.loadTestsFromModule(candidate_tests); assert not unittest.TextTestRunner().run(suite).wasSuccessful()'])
]

QUALITY = '''import ast
from pathlib import Path
files = FILES
for name in files:
    tree = ast.parse(Path(name).read_text("utf-8-sig"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"eval","exec","compile","__import__"}, "unsafe call"
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = [x.name for x in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            assert not any(x.split(".")[0] in {"os","subprocess","socket","requests"} for x in modules), "unsafe import"
    assert len(Path(name).read_text("utf-8-sig").splitlines()) <= 100, "unexpected growth"
print("deterministic AST safety/size checks passed")
'''


def main():
    SUITE.mkdir(parents=True, exist_ok=True)
    index = []
    for task_id, category, requirement, files, checks in CASES:
        repo = SUITE / task_id
        if repo.exists():
            raise SystemExit('Suite exists; do not overwrite existing benchmark fixtures')
        repo.mkdir()
        for name, text in files.items():
            (repo / name).write_text(text, encoding='utf-8')
        verifier = 'import sys\nfrom pathlib import Path\nsys.path.insert(0,str(Path(__file__).resolve().parent))\n'
        verifier += 'CHECKS = ' + repr(checks) + '\nexec(CHECKS[int(sys.argv[1])])\nprint("assertions passed")\n'
        (repo / 'verify.py').write_text(verifier, encoding='utf-8')
        (repo / 'quality.py').write_text(QUALITY.replace('FILES', repr(list(files))), encoding='utf-8')
        s.git(repo, 'init', '-q')
        s.git(repo, 'add', '--all')
        s.git(repo, '-c', 'user.name=Benchmark', '-c', 'user.email=benchmark@localhost', 'commit', '-qm', task_id + ' baseline')
        manifest = {'version': 1, 'repository': str(repo), 'requirements': [requirement],
                    'allowed_files': ['candidate_tests.py'] if category == 'test_authoring' else list(files), 'context_files': list(files),
                    'forbidden_operations': ['Do not change tests, add dependencies, access network or source repo.',
                                             'Only propose file replacements inside allowed_files.'],
                    'acceptance': [{'id': 'functionality', 'description': requirement,
                                    'test_ids': ['check0', 'check1', 'check2', 'quality']}],
                    'tests': [{'id': 'check' + str(i), 'argv': ['$PYTHON', '-I', '-B', 'verify.py', str(i)],
                               'timeout_seconds': 15} for i in range(len(checks))]
                             + [{'id': 'quality', 'argv': ['$PYTHON', '-I', '-B', 'quality.py'], 'timeout_seconds': 15}],
                    'max_reworks': 1, 'agent_timeout_seconds': 120}
        s.write_json(SUITE / (task_id + '.json'), manifest)
        index.append({'id': task_id, 'category': category, 'manifest': task_id + '.json',
                      'core_repeats': 3 if task_id in ('C1', 'E1') else 1,
                      'source_head': s.git(repo, 'rev-parse', 'HEAD').decode().strip()})
    s.write_json(SUITE / 'index.json', {'version': 1, 'tasks': index,
        'limitations': ['Restricted proposal workflow; Agent tools disabled, not a general tool-use benchmark.',
                        'E tasks test integrated multi-file reasoning and optional feedback, not autonomous browsing.',
                        'Test source is withheld equally; requirements are supplied identically.']})
    print(len(index), 'tasks prepared')


if __name__ == '__main__':
    main()
