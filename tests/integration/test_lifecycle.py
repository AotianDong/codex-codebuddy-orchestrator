import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]

class LifecycleTests(unittest.TestCase):
    def test_clean_install_update_uninstall_and_protect_neighbors(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);skills=base/'skills';state=base/'state';fixture=base/'pkg'
            (fixture/'bin').mkdir(parents=True)
            cli=fixture/'bin/codebuddy';cli.write_text('fixture')
            (fixture/'package.json').write_text('{"version":"fixture"}')
            env=os.environ.copy();env.update(CBO_CLI=str(cli),CBO_NODE=sys.executable,PYTHONDONTWRITEBYTECODE='1')
            def manage(action,expected=0):
                p=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/manage.py'),action,
                                  '--skills-dir',str(skills),'--state-dir',str(state)],
                                 env=env,capture_output=True,text=True,timeout=60)
                self.assertEqual(p.returncode,expected,p.stdout+p.stderr)
            neighbor=skills/'other-skill';neighbor.mkdir(parents=True);(neighbor/'keep').write_text('keep')
            manage('install')
            installed=skills/'codex-codebuddy'
            runner=installed/'scripts/run.py'
            py=installed/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
            # Run from a clean cwd and without checkout in PYTHONPATH.
            p=subprocess.run([str(py),'-B',str(runner),'--help'],cwd=base,env=env,capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertIn('execute',p.stdout)
            cfg=(state/'config.yaml').read_bytes()
            (state/'history').mkdir();(state/'history/keep.json').write_text('{}')
            manage('install',1)
            manage('update')
            automatic=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/manage.py'),'update',
                                      '--skills-dir',str(skills)],env=env,capture_output=True,text=True,timeout=60)
            self.assertEqual(automatic.returncode,0,automatic.stdout+automatic.stderr)
            self.assertEqual(json.loads((installed/'.installation.json').read_text('utf-8'))['config'],str(state/'config.yaml'))
            self.assertEqual((state/'config.yaml').read_bytes(),cfg)
            marker=installed/'custom-user-file';marker.write_text('keep')
            manage('uninstall',1)
            self.assertTrue(marker.exists());marker.unlink()
            hidden=installed/'unknown/.installation.json';hidden.parent.mkdir();hidden.write_text('user file')
            manage('uninstall',1)
            self.assertTrue(hidden.exists());hidden.unlink();hidden.parent.rmdir()
            manage('uninstall')
            manage('uninstall')
            self.assertFalse(installed.exists());self.assertTrue((neighbor/'keep').exists())
            self.assertTrue((state/'history/keep.json').exists())

    def test_foreign_skill_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);dest=base/'skills/codex-codebuddy';dest.mkdir(parents=True)
            (dest/'SKILL.md').write_text('foreign')
            p=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/manage.py'),'uninstall',
                              '--skills-dir',str(base/'skills'),'--state-dir',str(base/'state')],capture_output=True)
            self.assertNotEqual(p.returncode,0)
            self.assertEqual((dest/'SKILL.md').read_text(),'foreign')
