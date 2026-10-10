#!/opt/venv/bin/python
import fcntl
import os
from pathlib import Path
import re
import sys


def is_modal(path, seen=None):
    seen = set() if seen is None else seen
    path = path.resolve()
    if path in seen:
        return False
    seen.add(path)
    for line in path.read_text().splitlines():
        if re.match(r'^\s*\*FREQUENCY\s*(,|$)', line, re.I):
            return True
        match = re.match(r'^\s*\*INCLUDE\s*,\s*INPUT\s*=\s*(.*?)\s*$', line, re.I)
        if match and is_modal(path.parent / match[1].strip('\"\''), seen):
            return True
    return False


def reserve(state):
    with open(state, 'r+') as counter:
        fcntl.flock(counter, fcntl.LOCK_EX)
        count = int(counter.read())
        if count >= 30:
            raise RuntimeError('Modal FEA limit reached: 30 runs per harness launch.')
        counter.seek(0)
        counter.write(str(count + 1))
        counter.truncate()


def main():
    args = sys.argv[1:]
    state = os.environ.get('PI_MODAL_FEA_STATE')
    if state and args and args[0] not in ('-v', '--version', '-h', '--help'):
        job = args[1] if args[0] == '-i' and len(args) > 1 else args[0]
        path = Path(job if job.endswith('.inp') else job + '.inp')
        try:
            if is_modal(path):
                reserve(state)
                log = os.environ.get('PI_COMPUTE_LOG')
                if log:
                    with open(log, 'a') as counter:
                        counter.write('modal_fea\n')
        except (OSError, ValueError, RuntimeError) as error:
            sys.exit(f'Cannot run CalculiX: {error}')
    os.execv('/usr/bin/ccx', ['/usr/bin/ccx', *args])


if __name__ == '__main__':
    main()
