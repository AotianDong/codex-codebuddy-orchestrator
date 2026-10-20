from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from orchestrator.dispatcher import main
raise SystemExit(main([*sys.argv[1:], 'doctor']))
